"""A real-model comparison of the two ways a persona reaches the vault (docs/decisions/040): `auto`, where
Sympose searches before the reply, and `ask`, where the persona decides with `search_notes` and `open_note`.
It replays the cases of `live_prompt_cases` (plus three that need the tools) on scratch data only: the
fixture vault, a copy of the shipped persona, a temporary settings file. Nothing of anyone's own vault,
profiles or sessions is touched, and everything the fixture vault holds is synthetic, so the categories a
cloud model may receive are all approved in the scratch settings file only.

Opt-in and not deterministic; it calls a real model and every figure is a fact about that model only:

    python tests/live_lookup_cases.py <auto|ask> [model [runs [case-id ...]]]

Per case it prints how many runs passed, the model calls and lookups per turn, and each reply. At the end,
the two numbers the ADR's bar is about: how often a case that needs a note looked one up (`ask`), and how
often one that needs none did not; and every run that passed no check without looking anything up."""

import os
import shutil
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from live_prompt_cases import LIVE_CASES, REPO, LiveCase, run_case, setup_scratch  # noqa: E402

_CASES = {
    "open-named-note": (("can you open my Atlas note and tell me what it says about the timeline?",), (r"October|November",)),
    "follow-up-needs-a-second-lookup": (
        ("what did we decide about the database for Atlas?", "and when is the launch target?"), (r"November",),
    ),
    "names-the-folders-from-the-map": (("which folders does my vault have?",), (r"Journal", r"Recipes")),
}
EXTRA = [LiveCase(name, messages, expect=expect) for name, (messages, expect) in _CASES.items()]
NEEDS_A_NOTE = {
    "uses-the-note", "prefers-the-note-to-its-own-ideas", "asked-to-search", "honest-when-nothing-matches",
    "open-named-note", "follow-up-needs-a-second-lookup",
}
NEEDS_NONE = {
    "small-talk-stays-small-talk", "general-knowledge-with-no-notes", "recap-stays-out-of-small-talk",
    "general-knowledge-with-an-unrelated-note-attached", "unknowable-fact-is-not-invented", "no-false-learning",
    "names-the-folders-from-the-map",
}
DEFAULT_CASES = sorted(NEEDS_A_NOTE | NEEDS_NONE | {"sympose-who-made-it", "says-where-it-came-from", "recap-does-not-hide-the-vault"})


def _watch(turns: list[dict]):
    """Record, for every turn `run_case` runs, its lookups and how many model calls (and seconds) it took."""
    from sympose.engine import model as model_mod, turn

    real_call, real_run = model_mod.call_model, turn.run_turn
    calls = {"n": 0}

    def call(*args, **kwargs):
        calls["n"] += 1
        return real_call(*args, **kwargs)

    def run(*args, **kwargs):
        calls["n"], started = 0, time.perf_counter()
        result = real_run(*args, **kwargs)
        turns.append({"lookups": result.lookups, "calls": calls["n"], "seconds": time.perf_counter() - started,
                      "mode": (result.sent or {}).get("mode", "auto")})
        return result

    model_mod.call_model, turn.run_turn = call, run
    return lambda: (setattr(model_mod, "call_model", real_call), setattr(turn, "run_turn", real_run))


def main(mode: str, model: str, runs: int, only: list[str]) -> None:
    tmp = setup_scratch()
    from dotenv import dotenv_values

    for key, value in dotenv_values(os.path.join(REPO, ".env")).items():
        if key.endswith("_KEY") and value:
            os.environ[key] = value  # the model's key, into this process only
    from sympose import settings_store
    from sympose.engine import sharing

    settings_store.set("chat_model", model)
    settings_store.set("vault_lookup", mode)
    settings_store.set("cloud_share", list(sharing.CATEGORIES))  # scratch settings: the fixture vault is synthetic
    settings_store.set("grounding_search", "keywords")  # no embedding server needed
    pool = {case.id: case for case in [*LIVE_CASES, *EXTRA]}
    names = only or DEFAULT_CASES
    rows: list[tuple[str, int, list[dict], list[str]]] = []
    try:
        for name in names:
            turns: list[dict] = []
            restore = _watch(turns)
            try:
                results = [run_case(pool[name]) for _ in range(runs)]
            finally:
                restore()
            passed = sum(ok for ok, _ in results)
            per_run = len(pool[name].messages)
            print(f"\n{name}: {passed}/{runs}  calls/turn {statistics.mean(t['calls'] for t in turns):.1f}  "
                  f"lookups/turn {statistics.mean(len(t['lookups']) for t in turns):.1f}  "
                  f"seconds/turn {statistics.mean(t['seconds'] for t in turns):.1f}  ran {sorted({t['mode'] for t in turns})}", flush=True)
            for i, (ok, reply) in enumerate(results):
                queries = [e.get("query") or e.get("path") for t in turns[i * per_run:(i + 1) * per_run] for e in t["lookups"]]
                print(f"   {'ok  ' if ok else 'FAIL'} {queries} {reply[:190]}", flush=True)
            rows.append((name, passed, turns, [r for _, r in results]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # the directory this run made, nothing else
    looked = lambda t: bool(t["lookups"])  # noqa: E731
    need = [t for n, _, ts, _ in rows if n in NEEDS_A_NOTE for t in ts]
    none = [t for n, _, ts, _ in rows if n in NEEDS_NONE for t in ts]
    print(f"\n== {mode} on {model}: pass {sum(p for _, p, _, _ in rows)}/{sum(runs for _ in rows)}")
    print(f"   turns of cases that need a note: {sum(map(looked, need))}/{len(need)} looked something up")
    print(f"   turns of cases that need none:   {sum(not looked(t) for t in none)}/{len(none)} looked nothing up")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[0] if args else "ask", args[1] if len(args) > 1 else "gemini/gemini-flash-latest",
         int(args[2]) if len(args) > 2 else 3, args[3:])
