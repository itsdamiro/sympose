"""The committed `sympose/webui/` build matches `ui/src` (docs/decisions/028): built fresh, into a
scratch directory, with the same `vite build` that produces the committed one, and diffed byte for
byte against what is committed. `ui/`'s build is deterministic for unchanged source — checked by
hand, two builds with nothing changed are byte-identical, filenames included (Vite's content
hashes are stable, not a source of noise) — so any difference found here is real drift: someone
edited `ui/src` and forgot `npm run build` before committing. Skipped where `npx` is not on PATH:
this one test needs Node, the rest of the suite does not."""

import filecmp
import os
import shutil
import subprocess

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UI_DIR = os.path.join(_ROOT, "ui")
_WEBUI_DIR = os.path.join(_ROOT, "sympose", "webui")
_NPX = shutil.which("npx")


def _relative_files(root: str) -> set[str]:
    return {
        os.path.relpath(os.path.join(dirpath, name), root)
        for dirpath, _, names in os.walk(root)
        for name in names
    }


@pytest.mark.skipif(_NPX is None, reason="npx is not on PATH")
def test_the_committed_webui_build_matches_ui_src(tmp_path):
    subprocess.run(
        [_NPX, "vite", "build", "--outDir", str(tmp_path)],
        cwd=_UI_DIR, check=True, capture_output=True, text=True,
    )
    committed, fresh = _relative_files(_WEBUI_DIR), _relative_files(str(tmp_path))
    assert committed == fresh, (
        f"`sympose/webui/` does not match a fresh `npm run build` of `ui/src` — run it and commit the result.\n"
        f"committed only: {sorted(committed - fresh)}\nfresh only: {sorted(fresh - committed)}"
    )
    _, mismatched, errors = filecmp.cmpfiles(_WEBUI_DIR, str(tmp_path), committed, shallow=False)
    assert not mismatched and not errors, (
        f"`sympose/webui/` does not match a fresh `npm run build` of `ui/src` — run it and commit the result.\n"
        f"content differs: {mismatched}, unreadable: {errors}"
    )
