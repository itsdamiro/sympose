#!/usr/bin/env python3
"""Mutation check for new tests: change one thing in the code, run the tests, expect a failure.

Usage: python3 scripts/mutate.py mutants.json
  {"cwd": ".", "test": "pytest -q tests/test_a.py",
   "mutants": [{"file": "src/a.py", "old": "if x > 0:", "new": "if x >= 0:"}, ...]}

For each mutant the file is changed, the tests run, and the file is put back from a copy saved in a temp folder
(never `git checkout`: it discards uncommitted work). Reports CAUGHT (tests failed), SURVIVED (tests passed: add a test,
or decide it is an equivalent change and say so), NOMATCH (the old text is not in the file: the mutant tested nothing).
A mutant gets a modification time of its own: Python trusts a cached bytecode file whose recorded time and size match
the source, so a same-length change made in the same second would otherwise run the old code and look like a survivor.
Run one at a time per file. Exits 1 on any SURVIVED or NOMATCH, or if the tests do not pass unmutated.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


def passes(cmd: str, cwd: str) -> bool:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, env=env, check=False).returncode == 0


def digest(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(spec_path: str) -> int:
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    cwd, test = spec.get("cwd", "."), spec["test"]
    if not passes(test, cwd):  # otherwise every mutant would look caught
        print("BASELINE FAILS: the tests do not pass unmutated; fix that first.")
        return 1
    backup_dir, results, before, tick = tempfile.mkdtemp(prefix="mutate-"), [], {}, int(time.time()) + 10
    try:
        for m in spec["mutants"]:
            path = os.path.join(cwd, m["file"])
            before.setdefault(path, digest(path))
            saved = os.path.join(backup_dir, "saved")
            shutil.copy2(path, saved)
            with open(path, encoding="utf-8", newline="") as f:
                text = f.read()
            label = f'{m["file"]}: {m["old"][:60]!r}'.replace("\n", " ")
            if m["old"] not in text:
                results.append(("NOMATCH", label))
                continue
            try:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(text.replace(m["old"], m["new"], 1))
                tick += 1
                os.utime(path, (tick, tick))
                results.append(("SURVIVED" if passes(test, cwd) else "CAUGHT", label))
            finally:
                shutil.copy2(saved, path)
            print(*results[-1], flush=True)
        for path, digest_before in before.items():
            if digest(path) != digest_before:
                print(f"RESTORE FAILED: {path} differs from its original", file=sys.stderr)
                return 1
    finally:
        shutil.rmtree(backup_dir, ignore_errors=True)
    for status, label in results:
        if status == "NOMATCH":
            print(status, label)
    bad = [r for r in results if r[0] != "CAUGHT"]
    print(f"{len(results) - len(bad)} of {len(results)} caught" + (f"; {len(bad)} to look at" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) if len(sys.argv) == 2 else print(__doc__) or 2)
