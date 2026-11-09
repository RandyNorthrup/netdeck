"""Runner: output framing (\\r progress, partial lines), stop handling, resumable streaming."""

import os
import sys
import time

import pytest

from netdeck import runner
from netdeck.catalog import Step, Tool
from netdeck.hostenv import Privilege, supervised
from netdeck.runner import Job, JobManager


def make_tool(argv_fn):
    return Tool("t", "Test", "connectivity", "Test tool.", None, argv_fn)


def wait(job, timeout=10):
    end = time.time() + timeout
    while job.running and time.time() < end:
        time.sleep(0.05)
    return job


def run_python(manager, code):
    tool = make_tool(lambda p: [Step([sys.executable, "-c", code])])
    result = manager.start(tool, {})
    return wait(manager.get(result["job"]["id"]))


def manager():
    priv = Privilege("none")
    return JobManager(priv)


def test_lines_and_exit_code():
    job = run_python(manager(), "print('a'); print('b'); raise SystemExit(3)")
    assert job.lines == ["a", "b"]
    assert job.status == "failed" and job.exit_code == 3


def test_carriage_return_overwrites_line():
    code = ("import sys,time\n"
            "for i in range(3):\n"
            "    sys.stdout.write(f'\\rprogress {i}'); sys.stdout.flush(); time.sleep(0.05)\n"
            "print('\\ndone')")
    job = run_python(manager(), code)
    assert job.lines == ["progress 2", "done"]


def test_crlf_and_partial_flush():
    code = ("import sys,time\n"
            "sys.stdout.write('Testing...'); sys.stdout.flush(); time.sleep(0.6)\n"
            "sys.stdout.write(' ok\\r\\nnext\\n')")
    job = run_python(manager(), code)
    assert job.lines == ["Testing... ok", "next"]


def test_stop_sends_sigint():
    m = manager()
    code = ("import signal,sys,time\n"
            "signal.signal(signal.SIGINT, lambda *a: (print('summary'), sys.exit(0)))\n"
            "print('started', flush=True)\n"
            "time.sleep(30)")
    tool = make_tool(lambda p: [Step([sys.executable, "-c", code])])
    job = m.get(m.start(tool, {})["job"]["id"])
    time.sleep(0.5)
    m.stop(job.id)
    wait(job)
    assert job.status == "stopped"
    assert "summary" in job.lines


def test_changes_since_resume():
    job = Job(make_tool(lambda p: []), {}, [], False)
    job.emit("one")
    job.emit("two", final=False)
    lines, cursor, rev = job.changes_since(0, 0)
    assert lines == [(0, "one"), (1, "two")] and cursor == 2
    job.emit("two!")  # replaces the open line
    lines, cursor, rev2 = job.changes_since(cursor, rev)
    assert lines == [(1, "two!")] and rev2 > rev
    assert job.changes_since(cursor, rev2)[0] == []


def test_privileged_without_elevation_is_refused():
    m = manager()
    tool = Tool("p", "Priv", "firewall", "Needs root.", "true", lambda p: ["true"], privileged=True)
    try:
        m.start(tool, {})
    except Exception as exc:  # noqa: BLE001
        assert "administrator" in str(exc)
    else:
        import os
        assert os.geteuid() == 0


# -- stopping elevated (polkit) jobs and shutdown -------------------------------------------------

INTERRUPTIBLE = ("import signal,sys,time\n"
                 "signal.signal(signal.SIGINT, lambda *a: (print('interrupted', flush=True), sys.exit(130)))\n"
                 "print('up', flush=True)\n"
                 "time.sleep(60)")
IGNORES_SIGINT = ("import signal,time\n"
                  "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
                  "print('up', flush=True)\n"
                  "time.sleep(60)")


class PolkitLikePrivilege(Privilege):
    """pkexec mode without pkexec: the same supervisor wrapper, run as the current user."""

    def _detect(self) -> str:
        return "pkexec"

    def wrap(self, argv):
        return supervised(argv)


def wait_for_line(job, text, timeout=10):
    end = time.time() + timeout
    while text not in job.lines and time.time() < end:
        time.sleep(0.05)
    assert text in job.lines, f"never saw {text!r}: {job.lines}"


def start_python(manager, code, privileged=False):
    tool = Tool("t", "Test", "connectivity", "Test tool.", None,
                lambda p: [Step([sys.executable, "-c", code])], privileged=privileged)
    return manager.get(manager.start(tool, {})["job"]["id"])


@pytest.mark.parametrize("how", ["stop", "shutdown"])
def test_unsignalable_elevated_job_is_stopped_through_supervisor(monkeypatch, how):
    """A root-owned child cannot be signalled; closing the supervisor's stdin must still stop it."""
    def refuse(pgid, sig):
        raise PermissionError(1, "Operation not permitted")  # what os.killpg does for a root-owned child

    monkeypatch.setattr(runner.os, "killpg", refuse)
    m = JobManager(PolkitLikePrivilege("pkexec"))
    job = start_python(m, INTERRUPTIBLE, privileged=True)
    assert job.elevated
    wait_for_line(job, "up")
    start = time.monotonic()
    if how == "stop":
        m.stop(job.id)
    else:
        m.shutdown()
    wait(job, timeout=8)
    assert job.status == "stopped", job.lines
    assert "interrupted" in job.lines, job.lines
    assert time.monotonic() - start < 6
    assert job.proc.poll() is not None


def test_shutdown_stops_jobs_concurrently():
    """Three jobs that only exit on SIGTERM: one grace period in parallel, not three in sequence."""
    m = manager()
    jobs = [start_python(m, IGNORES_SIGINT) for _ in range(3)]
    for job in jobs:
        wait_for_line(job, "up")
    pids = [job.proc.pid for job in jobs]
    start = time.monotonic()
    m.shutdown(grace=2.0)
    elapsed = time.monotonic() - start
    assert elapsed < 4.0, f"shutdown took {elapsed:.1f}s"
    for job, pid in zip(jobs, pids, strict=True):
        assert job.proc.poll() is not None
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
        assert job.status == "stopped"
