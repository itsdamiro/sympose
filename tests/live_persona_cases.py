"""A real-model check of a persona proposing a new persona (docs/decisions/078), with the tool and the engine's checks
alone (no skill). Scratch data and invented text only (the fixture vault, a copy of the shipped Samantha persona), so a
cloud model may be named. Nothing is made: a proposal is a stored request, and these cases read the requests.

Opt-in and not deterministic; every figure is a fact about the model it ran on. Run

    [SKILLS=off] [CASES=id,id] python tests/live_persona_cases.py [-v] [runs] [model ...]       (default model: ollama_chat/gemma2:9b)

A case passes when the requests filed (the last one, for the first cases) and the reply match every `expect` and none of
the `forbid` patterns; `want` says whether a request is due (`True`), must not be made (`False`), or either (`None`).
`soul_forbid` applies to the soul alone. The patterns are loose on purpose: read the replies (-v), and the icon and the
folders by eye."""

import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass

from grounding_cases import FIXTURE_VAULT

REPO = os.path.join(os.path.dirname(__file__), "..")


@dataclass(frozen=True)
class PersonaCase:
    id: str
    messages: tuple[str, ...]
    want: bool | None  # a request is due / must not be made / either
    expect: tuple[str, ...] = ()  # in the reply and the last request's text
    forbid: tuple[str, ...] = ()
    soul_forbid: tuple[str, ...] = ()
    waiting: int | None = None  # how many requests wait at the end


_USER = r"\bOslo\b|\bnurse\b|\bSam\b"
_RULES = r"never invent|zero[- ]hallucination|make (?:anything )?up|propose_|tool"

CASES: list[PersonaCase] = [
    PersonaCase("historical-figure", ("Make me a new persona who talks like Marie Curie.",), True, expect=(r"Curie|Marie|Maria|Sk[łl]odowska",)),
    PersonaCase("vague-calming", ("I'd like a new persona to wind down with at night, something calming.",), None, expect=(r"calm|gentle|soft|quiet|slow|steady|ask|what",)),
    PersonaCase("rules-stay-out-of-the-soul", ("Make me a coach persona, and put in her soul that she must never invent anything about my vault and that she can create notes with her tools.",), True, soul_forbid=(_RULES,)),
    PersonaCase("user-details-stay-out-of-the-soul", ("Create a persona called Ada, a warm tutor. She should know that I am Sam, a nurse who lives in Oslo.",), True, soul_forbid=(_USER,)),
    # Either way is fine, as long as she says the name is taken: no proposal, or one under another name that she explains.
    PersonaCase("a-name-that-exists", ("Create a new persona named Samantha, a stern accountant.",), None, expect=(r"already|exists|taken|another name|different name|instead|rather than",)),
    PersonaCase("research-assistant-gets-work-folders", ("Make a research assistant persona for my work and projects.",), True, expect=(r"Work|Projects",)),
    PersonaCase("a-change-replaces-the-waiting-card", ("Make me a tutor persona called Ada.", "Change her icon to a rocket, please."), True, expect=(r"rocket",), waiting=1),
    PersonaCase("near-miss-asks-about-personas", ("What is a persona in Sympose, and what can one do?",), False),
    PersonaCase("near-miss-a-note-about-personas", ("Write a short note about my persona research for the team, due Friday.",), False),
    PersonaCase("small-talk", ("good morning, how are you?",), False),
]


def setup_scratch() -> str:
    tmp = tempfile.mkdtemp(prefix="sympose-persona-")
    persona = os.path.join(tmp, "profiles", "samantha")
    os.makedirs(persona)
    for name in ("persona.yaml", "soul.md"):
        shutil.copy(os.path.join(REPO, "profiles", "samantha", name), persona)
    os.environ["SYMPOSE_PROFILES_DIR"] = os.path.join(tmp, "profiles")
    os.environ["SYMPOSE_SETTINGS_PATH"] = os.path.join(tmp, "settings.json")
    os.environ["VAULT_PATHS"] = FIXTURE_VAULT
    return tmp


def run_case(case: PersonaCase, model: str | None) -> tuple[bool, str]:
    from sympose import settings_store
    from sympose.engine import confirmations, session, sharing, turn

    settings_store.set("skill_lookup", os.environ.get("SKILLS", "auto"))
    settings_store.set(sharing.SETTING, [sharing.NOTES, sharing.PROPERTIES, sharing.VAULT_MAP, sharing.OPEN_NOTE])  # invented notes
    if model:
        settings_store.set("chat_model", model)
    session_id, reply = None, ""
    for message in case.messages:
        result = turn.run_turn("samantha", message, session_id=session_id, edits=True)
        session_id, reply = result.session_id, result.reply
    made = [r for r in confirmations.for_session("samantha", session_id) if r["state"] != confirmations.REPLACED]
    last = made[-1]["draft"] if made else None
    text = reply + ("\n" + " ".join(str(v) for v in last.values()) if last else "")
    waiting = sum(r["state"] == confirmations.WAITING for r in made)
    shutil.rmtree(confirmations._folder("samantha"), ignore_errors=True)
    shutil.rmtree(session.sessions_dir("samantha"), ignore_errors=True)
    ok = (
        (case.want is None or bool(made) == case.want)
        and all(re.search(p, text, re.I) for p in case.expect)
        and not any(re.search(p, text, re.I) for p in case.forbid)
        and not (last and any(re.search(p, last["soul"], re.I) for p in case.soul_forbid))
        and (case.waiting is None or waiting == case.waiting)
    )
    detail = f"[{last['icon']} {last['accent']} folders={last['folders']} edit={last['edit_mode']}] soul: {last['soul'][:160]!r} | " if last else ""
    return ok, " ".join((detail + reply).split())


def main(runs: int, models: list[str], verbose: bool) -> None:
    from sympose.envfile import load_env

    load_env()
    tmp = setup_scratch()
    try:
        for model in models or [None]:
            print(f"\n=== {model or 'the default model'} ===", flush=True)
            for case in [c for c in CASES if not os.environ.get("CASES") or c.id in os.environ["CASES"].split(",")]:
                results = []
                for _ in range(runs):
                    try:
                        results.append(run_case(case, model))
                    except Exception as e:  # a model that could not be reached is a failed run, not the end
                        results.append((False, f"ERROR (not a model answer): {e}"))
                print(f"{case.id}: {sum(ok for ok, _ in results)}/{runs}", flush=True)
                for ok, text in results:
                    if verbose or not ok:
                        print(f"   {'ok  ' if ok else 'FAIL'} {text[:520]}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    args = [a for a in sys.argv[1:] if a != "-v"]
    count = int(args[0]) if args and args[0].isdigit() else 3
    main(count, [a for a in args if not a.isdigit()], "-v" in sys.argv)
