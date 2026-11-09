"""Red-drill harness for NetDeck delivery plans: green -> red (disposable copy) -> restored green.

usage: python drill.py <drill.json>

drill.json: {"id", "path", "old", "new", "test": [pytest node ids], "expect": regex}
The mutation is applied exactly once to a throwaway copy of the repository; the original tree is
never modified, so restoration is the deletion of the copy plus a byte-for-byte check of the original.
Writes reports/drills/<id>.log and prints a JSON summary with fingerprints. Exit 0 only when baseline
and restored runs pass and the mutated run fails with the expected diagnostic.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REPORTS = None  # set from the drill spec: <plan dir>/reports/drills, next to the spec's drills/ directory
IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "reports")


def digest(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_tests(root: str, tests: list) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=os.path.join(root, "src"), PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests]
    return subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=600)


def main() -> int:
    global REPORTS
    with open(sys.argv[1], encoding="utf-8") as fh:
        spec = json.load(fh)
    REPORTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[1]))), "reports", "drills")
    target = os.path.join(ROOT, spec["path"])
    before = digest(target)
    log = [f"# drill {spec['id']}: {spec['path']}", f"mutation: {spec['old']!r} -> {spec['new']!r}", ""]

    baseline = run_tests(ROOT, spec["test"])
    log += ["## baseline (original tree)", f"exit {baseline.returncode}", baseline.stdout[-4000:], ""]

    work = tempfile.mkdtemp(prefix=f"drill-{spec['id']}-")
    try:
        copy = os.path.join(work, "repo")
        shutil.copytree(ROOT, copy, ignore=IGNORE)
        mutated_path = os.path.join(copy, spec["path"])
        with open(mutated_path, encoding="utf-8") as fh:
            text = fh.read()
        count = text.count(spec["old"])
        if count != 1:
            raise SystemExit(f"mutation must apply exactly once, found {count}")
        with open(mutated_path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(spec["old"], spec["new"]))
        mutated = digest(mutated_path)
        red = run_tests(copy, spec["test"])
        log += ["## mutated (disposable copy)", f"exit {red.returncode}", red.stdout[-6000:], red.stderr[-2000:], ""]
    finally:
        shutil.rmtree(work, ignore_errors=True)

    after = digest(target)
    restored = run_tests(ROOT, spec["test"])
    log += ["## restored (original tree)", f"exit {restored.returncode}", restored.stdout[-4000:]]

    match = re.search(spec["expect"], red.stdout)
    ok = (baseline.returncode == 0 and red.returncode > 0 and match is not None
          and before == after and restored.returncode == 0 and mutated != before)
    os.makedirs(REPORTS, exist_ok=True)
    log_path = os.path.join(REPORTS, f"{spec['id']}.log")
    log.insert(2, f"result: {'PASS' if ok else 'FAIL'}  observed: {match.group(0) if match else None!r}")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(log) + "\n")
    summary = {
        "id": spec["id"], "ok": ok, "log": os.path.relpath(log_path, ROOT),
        "baseline_exit": baseline.returncode, "mutated_exit": red.returncode, "restored_exit": restored.returncode,
        "observed": match.group(0) if match else None,
        "before": {"path": spec["path"], "sha256": before},
        "mutated": {"path": spec["path"], "sha256": mutated},
        "after": {"path": spec["path"], "sha256": after},
        "mutation": f"{spec['path']}: {spec['old']!r} -> {spec['new']!r}",
        "command": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *spec["test"]],
    }
    with open(os.path.join(REPORTS, f"{spec['id']}.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps(summary, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
