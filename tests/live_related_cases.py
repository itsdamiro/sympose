"""A real-model check that she uses the "possibly related" line (docs/decisions/066), through the real `run_turn`
on scratch data: the small vault `tests/fixtures/related_vault` (two pairs of notes close in meaning, no link
between either, and fourteen others on other things), a copy of the shipped Samantha persona in a temporary
profiles directory and a temporary settings file. Nothing of anyone's own vault, profiles or sessions is touched.

Opt-in and not deterministic: it needs Ollama with the chat and embedding models, and every figure is a fact
about that model only. Run it with

    python tests/live_related_cases.py [runs-per-case [case-id ...]]

A case passes when the reply names the note close in meaning where it should (`expect`) and never says it is
linked (`forbid`); the patterns are loose, so read the replies too."""

import os
import shutil
import sys

import live_prompt_cases as live
from live_prompt_cases import LiveCase

PERSONA = {"name": "Samantha", "handle": "samantha", "vault_folders": ["*"]}
HERE = os.path.dirname(os.path.abspath(__file__))
# `off` is the same question with the line left out: the baseline she must not do better than by luck.
CASES: list[tuple[str, LiveCase]] = [
    ("auto", LiveCase("related-to-starter", ("what else in my notes is related to my sourdough starter?",), expect=(r"Weekend Bread Baking",), forbid=(r"(?<!not )(?<!n't )\blinks? to\b", r"is linked (?:to|with)"))),
    ("auto", LiveCase("related-to-marathon", ("which notes are connected to my marathon training log?",), expect=(r"Trail Running Routes",), forbid=(r"is linked (?:to|with)",))),
    ("auto", LiveCase("similar-trap", ("does my marathon training log link to the trail running routes note?",), forbid=(r"(?<!not )(?<!n't )(?<!no )\blinks? to\b.*trail running", r"yes[,.]? (?:it )?(?:is )?link",))),
    ("off", LiveCase("related-to-starter-off", ("what else in my notes is related to my sourdough starter?",), expect=(r"Weekend Bread Baking",))),
]


def main(runs: int, only: list[str]) -> None:
    tmp = live.setup_scratch()
    os.environ["VAULT_PATHS"] = os.path.join(HERE, "fixtures", "related_vault")
    from sympose import settings_store
    from sympose.engine import grounding, semantic_refresh

    try:
        semantic_refresh.build(grounding.scope_index(PERSONA))
        for mode, case in [c for c in CASES if not only or c[1].id in only]:
            settings_store.set("connections_by_meaning", mode)
            results = [live._run_or_error(case) for _ in range(runs)]
            print(f"\n{case.id} [{mode}]: {sum(ok for ok, _ in results)}/{runs}   ({case.messages[-1]!r})", flush=True)
            for ok, reply in results:
                print(f"   {'ok  ' if ok else 'FAIL'} {reply[:300]}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # the directory this run made, nothing else


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(HERE, ".."))
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3, sys.argv[2:])
