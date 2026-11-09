"""Job execution: spawn tools without a shell, stream their output, stop them cleanly."""

from __future__ import annotations

import contextlib
import getpass
import logging
import os
import select
import shlex
import signal
import subprocess
import threading
import time
import uuid
from typing import Dict, List, Optional

from netdeck.catalog import GUI, STREAM, TERMINAL, Internal, Step, Tool
from netdeck.hostenv import Privilege, which
from netdeck.terminal import launch_in_terminal

log = logging.getLogger(__name__)

MAX_LINES = 50_000
TRIM_CHUNK = 5_000
MAX_JOBS_KEPT = 100
MAX_CONCURRENT = 12
FLUSH_PARTIAL_AFTER = 0.3  # seconds before an unterminated line is shown
STOP_GRACE = 2.0  # seconds between INT, TERM and KILL when stopping a job
SUPERVISOR_LADDER = 4.0  # ELEVATED_SUPERVISOR's own INT -> TERM -> KILL spacing (2 s + 2 s)


class JobError(Exception):
    pass


class Job:
    """One tool run. Output lines are addressed by absolute index so clients can resume."""

    def __init__(self, tool: Tool, params: Dict, display: List[str], elevated: bool) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.tool = tool
        self.params = params
        self.display = display
        self.elevated = elevated
        self.status = "running"
        self.exit_code: Optional[int] = None
        self.started = time.time()
        self.ended: Optional[float] = None
        self.artifact: Optional[str] = None
        self.offset = 0  # absolute index of self.lines[0]
        self.lines: List[str] = []
        self.revs: List[int] = []
        self.rev = 0
        self.open_line = False  # last line is still being written (no newline yet)
        self.cond = threading.Condition()
        self.stop_event = threading.Event()
        self.proc: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None

    # -- output ---------------------------------------------------------------
    def _bump(self) -> int:
        self.rev += 1
        return self.rev

    def emit(self, text: str, *, final: bool = True) -> None:
        """Append a line, or replace the currently open line."""
        with self.cond:
            rev = self._bump()
            if self.open_line and self.lines:
                self.lines[-1] = text
                self.revs[-1] = rev
            else:
                self.lines.append(text)
                self.revs.append(rev)
            self.open_line = not final
            if len(self.lines) > MAX_LINES:
                del self.lines[:TRIM_CHUNK]
                del self.revs[:TRIM_CHUNK]
                self.offset += TRIM_CHUNK
            self.cond.notify_all()

    def close_line(self) -> None:
        with self.cond:
            if self.open_line:
                self.open_line = False
                if self.revs:
                    self.revs[-1] = self._bump()
                self.cond.notify_all()

    def changes_since(self, cursor: int, rev: int):
        """Return (lines [(index, text)], new_cursor, new_rev). Caller holds no lock."""
        with self.cond:
            start = max(cursor - 1, self.offset)
            out = []
            for i in range(start - self.offset, len(self.lines)):
                if self.revs[i] > rev:
                    out.append((i + self.offset, self.lines[i]))
            return out, self.offset + len(self.lines), self.rev

    def finish(self, status: str, code: Optional[int]) -> None:
        self.close_line()
        with self.cond:
            self.status = status
            self.exit_code = code
            self.ended = time.time()
            self._bump()
            self.cond.notify_all()

    def wake(self) -> None:
        """Wake every stream waiting on this job (used when the server shuts down)."""
        with self.cond:
            self.cond.notify_all()

    @property
    def running(self) -> bool:
        return self.status == "running"

    def summary(self) -> Dict:
        return {
            "id": self.id, "tool": self.tool.id, "name": self.tool.name, "category": self.tool.category,
            "status": self.status, "exit_code": self.exit_code, "started": self.started, "ended": self.ended,
            "command": self.display, "elevated": self.elevated, "artifact": self.artifact,
            "lines": self.offset + len(self.lines), "params": self.params,
        }

    def text(self) -> str:
        with self.cond:
            return "\n".join(self.lines) + "\n"


def _clean_env() -> Dict[str, str]:
    env = dict(os.environ)
    env.update({"TERM": "dumb", "NO_COLOR": "1", "COLUMNS": "160", "LINES": "50"})
    env.pop("CLICOLOR_FORCE", None)
    return env


def _close_quietly(stream) -> None:
    if stream is None:
        return
    with contextlib.suppress(OSError, ValueError):  # already closed by the other of stop/exec
        stream.close()


def resolve_argv(argv: List[str]) -> List[str]:
    binary = which(argv[0])
    if not binary:
        raise JobError(f"'{argv[0]}' is not installed")
    return [binary] + list(argv[1:])


def display_argv(argv: List[str], elevated: bool, privilege: Privilege) -> str:
    prefix = {"sudo": "sudo ", "pkexec": "pkexec "}.get(privilege.mode, "") if elevated else ""
    return prefix + shlex.join(argv)


class JobManager:
    def __init__(self, privilege: Privilege, terminal_pref: str = "auto") -> None:
        self.privilege = privilege
        self.terminal_pref = terminal_pref
        self.jobs: Dict[str, Job] = {}
        self.lock = threading.Lock()

    # -- public API -------------------------------------------------------------
    def preview(self, tool: Tool, params: Dict) -> Dict:
        elevated = tool.needs_root(params)
        plan = tool.plan(self._build_params(params, elevated))
        commands = []
        for step in plan.steps:
            if isinstance(step, Internal):
                commands.append(f"(built-in) {step.label}")
            else:
                commands.append(display_argv(step.argv, elevated, self.privilege))
        return {"commands": commands, "elevated": elevated}

    def start(self, tool: Tool, params: Dict) -> Dict:
        if tool.binary and not which(tool.binary):
            raise JobError(f"{tool.name} needs '{tool.binary}', which is not installed")
        elevated = tool.needs_root(params)
        if elevated and tool.mode == STREAM and not self.privilege.available:
            raise JobError(self.privilege.describe() + " This tool needs administrator rights.")
        plan = tool.plan(self._build_params(params, elevated))

        if tool.mode == TERMINAL:
            argv = resolve_argv(plan.steps[0].argv)
            launch_in_terminal(argv, title=f"NetDeck · {tool.name}", sudo=elevated, preference=self.terminal_pref)
            return {"launched": True, "command": display_argv(plan.steps[0].argv, elevated, self.privilege)}
        if tool.mode == GUI:
            argv = resolve_argv(plan.steps[0].argv)
            subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            return {"launched": True, "command": shlex.join(plan.steps[0].argv)}

        with self.lock:
            if sum(1 for j in self.jobs.values() if j.running) >= MAX_CONCURRENT:
                raise JobError(f"Too many running jobs (max {MAX_CONCURRENT}). Stop one first.")
            display = [display_argv(s.argv, elevated, self.privilege) if isinstance(s, Step)
                       else f"(built-in) {s.label}" for s in plan.steps]
            job = Job(tool, params, display, elevated)
            job.artifact = plan.artifact
            self.jobs[job.id] = job
            self._prune()
        job.thread = threading.Thread(target=self._run, args=(job, plan.steps), name=f"job-{job.id}", daemon=True)
        job.thread.start()
        return {"job": job.summary()}

    def get(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job

    def running_jobs(self) -> List[Job]:
        """Snapshot of the jobs still running, safe while other threads start jobs."""
        with self.lock:
            return [job for job in self.jobs.values() if job.running]

    def list(self) -> List[Dict]:
        return [j.summary() for j in sorted(self.jobs.values(), key=lambda j: j.started, reverse=True)]

    def stop(self, job_id: str) -> None:
        job = self.get(job_id)
        if job.running:
            job.stop_event.set()
            threading.Thread(target=self._terminate, args=(job,), daemon=True).start()

    def remove(self, job_id: str) -> None:
        job = self.get(job_id)
        if job.running:
            raise JobError("Stop the job before removing it")
        with self.lock:
            self.jobs.pop(job_id, None)

    def shutdown(self, grace: float = STOP_GRACE) -> None:
        """Stop every running job at once and wait for them, bounded by the signal ladder.

        Each job gets INT, then TERM, then KILL, ``grace`` seconds apart, all jobs in parallel, so
        shutdown takes at most about ``3 * grace`` however many jobs are running.
        """
        running = self.running_jobs()
        for job in running:
            job.stop_event.set()
            job.wake()
        stoppers = [threading.Thread(target=self._terminate, args=(job, grace), daemon=True) for job in running]
        for thread in stoppers:
            thread.start()
        deadline = time.monotonic() + 3 * grace + 1.0
        for thread in stoppers + [job.thread for job in running if job.thread]:
            thread.join(max(0.0, deadline - time.monotonic()))
        survivors = [job.id for job in running if job.proc and job.proc.poll() is None]
        if survivors:
            log.error("jobs still running after shutdown deadline: %s", ", ".join(survivors))

    # -- internals ----------------------------------------------------------------
    def _build_params(self, params: Dict, elevated: bool) -> Dict:
        return dict(params, _elevated=elevated, _user=getpass.getuser())

    def _prune(self) -> None:
        finished = sorted((j for j in self.jobs.values() if not j.running), key=lambda j: j.started)
        for job in finished[: max(0, len(self.jobs) - MAX_JOBS_KEPT)]:
            self.jobs.pop(job.id, None)

    def _run(self, job: Job, steps) -> None:
        code: Optional[int] = 0
        try:
            for index, step in enumerate(steps):
                if job.stop_event.is_set():
                    break
                if len(steps) > 1:
                    if index:
                        job.emit("")
                    label = step.label if step.label else job.display[index]
                    job.emit(f"━━ {label} ━━")
                if isinstance(step, Internal):
                    code = step.fn(job.params, job.emit, job.stop_event)
                else:
                    code = self._exec(job, step.argv)
            if job.stop_event.is_set():
                job.finish("stopped", code)
            else:
                job.finish("done" if code == 0 else "failed", code)
        except JobError as exc:
            job.emit(f"✗ {exc}")
            job.finish("error", None)
        except Exception as exc:
            log.exception("job %s crashed", job.id)
            job.emit(f"✗ Internal error: {exc}")
            job.finish("error", None)

    def _exec(self, job: Job, argv: List[str]) -> Optional[int]:
        argv = resolve_argv(argv)
        if job.elevated:
            argv = self.privilege.wrap(argv)
        log.info("job %s exec: %s", job.id, shlex.join(argv))
        # A supervised (pkexec) child is stopped by closing its stdin, so keep the write end.
        supervised = job.elevated and self.privilege.stops_via_stdin
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE if supervised else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=_clean_env(),
                                start_new_session=True)
        job.proc = proc
        try:
            self._pump(job, proc)
            code = proc.wait()
        finally:
            _close_quietly(proc.stdin)
        if job.elevated and self.privilege.mode == "pkexec" and code in (126, 127) and not job.stop_event.is_set():
            job.emit("✗ Authorization was cancelled or denied.")
        return code

    def _pump(self, job: Job, proc: subprocess.Popen) -> None:
        """Read output, honouring \\r progress updates and flushing partial lines."""
        fd = proc.stdout.fileno()
        buf = b""
        flushed = b""
        last_data = time.monotonic()
        try:
            while True:
                ready, _, _ = select.select([fd], [], [], 0.2)
                if ready:
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        break
                    buf += chunk
                    last_data = time.monotonic()
                    buf = self._split(job, buf)
                elif buf and buf != flushed and time.monotonic() - last_data > FLUSH_PARTIAL_AFTER:
                    job.emit(buf.decode("utf-8", "replace"), final=False)
                    flushed = buf
        finally:
            if buf:
                job.emit(buf.decode("utf-8", "replace"))
            job.close_line()
            proc.stdout.close()

    @staticmethod
    def _split(job: Job, buf: bytes) -> bytes:
        while True:
            nl, cr = buf.find(b"\n"), buf.find(b"\r")
            if nl < 0 and cr < 0:
                return buf
            if cr >= 0 and (nl < 0 or cr < nl):
                if buf[cr + 1:cr + 2] == b"\n":  # CRLF
                    job.emit(buf[:cr].decode("utf-8", "replace"))
                    buf = buf[cr + 2:]
                else:
                    segment = buf[:cr]
                    if segment:
                        job.emit(segment.decode("utf-8", "replace"), final=False)
                    buf = buf[cr + 1:]
            else:
                segment = buf[:nl]
                if segment or not job.open_line:
                    job.emit(segment.decode("utf-8", "replace"))
                else:
                    job.close_line()
                buf = buf[nl + 1:]

    def _terminate(self, job: Job, grace: float = STOP_GRACE) -> None:
        proc = job.proc
        if not proc or proc.poll() is not None:
            return
        if proc.stdin:
            # Supervised elevated child: the root-side supervisor runs the INT/TERM/KILL ladder.
            _close_quietly(proc.stdin)
            try:
                proc.wait(timeout=SUPERVISOR_LADDER + grace)
            except subprocess.TimeoutExpired:
                log.error("job %s: elevated process did not stop", job.id)
                job.emit("✗ The elevated process did not stop. Check it with your system monitor.")
            return
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                return
            except PermissionError:
                log.error("job %s: not permitted to signal process group %s", job.id, proc.pid)
                job.emit("✗ NetDeck is not permitted to stop this process.")
                return
            try:
                proc.wait(timeout=grace)
                return
            except subprocess.TimeoutExpired:
                continue
