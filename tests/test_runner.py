"""Runner: output framing (\\r progress, partial lines), stop handling, resumable streaming."""

import sys
import time

from netdeck.catalog import Step, Tool
from netdeck.hostenv import Privilege
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
