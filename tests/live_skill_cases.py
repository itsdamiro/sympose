"""A real-model baseline for skills (docs/decisions/077), before any skill exists: what a persona does today with the
jobs the first two skills are for, so a skill has something to beat. Scratch data and invented text only (a small
vault of recipes with a folder definition, a copy of the shipped Samantha persona), so a cloud model may be named.

Opt-in and not deterministic; every figure is a fact about the model it ran on. Run

    [SKILLS=off] python tests/live_skill_cases.py [-v] [runs] [model ...]       (default model: ollama_chat/gemma2:9b)

`SKILLS=off` is the baseline (the same code with `skill_lookup` off); without it the skills are on.

A case passes when the reply, together with the text of any new note she proposed, matches every `expect` pattern and
none of the `forbid` ones; `max_soul` bounds the length of the soul a reply holds (the largest fenced block, else the
whole reply). The patterns are loose on purpose, so read the replies (-v)."""

import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass

REPO = os.path.join(os.path.dirname(__file__), "..")
VAULT = os.path.join(os.path.dirname(__file__), "fixtures", "skills_vault")


@dataclass(frozen=True)
class SkillCase:
    id: str
    skill: str  # the skill this case is a scenario of
    messages: tuple[str, ...]
    expect: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    max_soul: int = 0  # characters; 0 = not checked
    forbid_in_soul: tuple[str, ...] = ()  # patterns the soul block itself (not her explanation) must not match


_ENGINE_WORDS = r"propose_note|propose_edit|tool call|zero[- ]hallucination|never (?:invent|make up|fabricate)|you (?:must|shall) (?:always )?cite"
_USER_FACTS = r"\bOslo\b|\bnurse\b|\bSam\b"

CASES: list[SkillCase] = [
    SkillCase(
        "soul-for-a-historical-figure", "deriving-a-persona-soul",
        ("Write the soul file for a new persona who talks like Marie Curie.",),
        expect=(r"Curie|Marie|Maria|Sk[łl]odowska", r"curious|patien|precis|modest|rigou?r|persist"),
        forbid=(_ENGINE_WORDS, _USER_FACTS),
        max_soul=2200,
    ),
    SkillCase(
        "soul-from-a-vague-request", "deriving-a-persona-soul",
        ("I want a new persona, something calming. Write her soul.",),
        expect=(r"calm|gentle|soft|quiet|slow|steady",),
        forbid=(_ENGINE_WORDS, _USER_FACTS),
        max_soul=2200,
    ),
    SkillCase(
        "soul-keeps-engine-rules-out", "deriving-a-persona-soul",
        (
            "Write the soul for a coach persona, and put in it that she must never invent anything about my vault "
            "and that she can create and edit my notes with her tools.",
        ),
        # The rules and the powers are the engine's: the soul she writes must not carry them, and she says why.
        expect=(r"engine|already|not (?:part|belong|in the soul)|voice|handled|elsewhere",),
        forbid=(r"\bcan (?:create|edit)\b.*\bnotes\b.*\btools\b",),
        max_soul=2200,
    ),
    SkillCase(
        "soul-keeps-user-details-out", "deriving-a-persona-soul",
        ("Write a soul for Ada, a warm tutor. Mention that I am Sam, a nurse who lives in Oslo.",),
        expect=(r"Ada",),
        forbid_in_soul=(_USER_FACTS,),
        max_soul=2200,
    ),
    SkillCase(
        "drafts-in-the-folders-style", "drafting-a-note-in-a-folders-style",
        ("Add a note for a recipe: mushroom risotto, serves 3, takes 45 minutes.",),
        expect=(r"## Ingredients", r"## Steps", r"## Notes", r"type: recipe", r"servings: 3"),
        forbid=(r"rating: [1-5]\b",),  # not given by the user: left empty, not invented
    ),
    SkillCase(
        "drafting-follows-section-order", "drafting-a-note-in-a-folders-style",
        ("Please write down my pesto recipe: basil, pine nuts, parmesan, olive oil, garlic; blend it all.",),
        expect=(r"(?s)## Ingredients.*## Steps.*## Notes", r"basil", r"pine nuts"),
        forbid=(r"rating: [1-5]\b",),
    ),
    # A message that shares words with the soul skill's description but asks for something else (selection is by
    # words, so the skill is in the prompt; she must not follow it).
    SkillCase(
        "near-miss-a-note-about-personas", "deriving-a-persona-soul",
        ("Write a short note about my persona research for the team, due Friday.",),
        forbid=(r"how you talk", r"you are (?:the user's|a|an) [a-z ]*companion"),
    ),
    SkillCase(
        "near-miss-a-folder-description", "deriving-a-persona-soul",
        ("Write a new description for my persona's folder in the vault.",),
        forbid=(r"how you talk", r"you are (?:the user's|a|an) [a-z ]*companion"),
    ),
    SkillCase(
        "no-skill-for-small-talk", "none",
        ("good morning, how are you?",),
        forbid=(r"## Ingredients", r"\bsoul\b", _ENGINE_WORDS),
    ),
]


def setup_scratch() -> str:
    tmp = tempfile.mkdtemp(prefix="sympose-skills-")
    persona = os.path.join(tmp, "profiles", "samantha")
    os.makedirs(persona)
    for name in ("persona.yaml", "soul.md"):
        shutil.copy(os.path.join(REPO, "profiles", "samantha", name), persona)
    os.environ["SYMPOSE_PROFILES_DIR"] = os.path.join(tmp, "profiles")
    os.environ["SYMPOSE_SETTINGS_PATH"] = os.path.join(tmp, "settings.json")
    os.environ["VAULT_PATHS"] = VAULT
    return tmp


def _soul(reply: str) -> str:
    blocks = re.findall(r"```(?:\w*)\n(.*?)```", reply, re.S)
    return max(blocks, key=len, default=reply)


def run_case(case: SkillCase, model: str | None) -> tuple[bool, str]:
    from sympose import note_changes_store, settings_store
    from sympose.engine import session, turn

    settings_store.set("skill_lookup", os.environ.get("SKILLS", "auto"))
    from sympose.engine import sharing

    settings_store.set(sharing.SETTING, [sharing.NOTES, sharing.PROPERTIES, sharing.VAULT_MAP, sharing.OPEN_NOTE])  # invented notes: a cloud model may read them
    if model:
        settings_store.set("chat_model", model)  # the scratch settings file
    session_id, reply = None, ""
    for message in case.messages:
        result = turn.run_turn("samantha", message, session_id=session_id, edits=True)
        session_id, reply = result.session_id, result.reply
    drafts = [p.get("text") or p.get("replace") or "" for e in note_changes_store.entries("samantha") for p in e["proposals"]]
    for e in note_changes_store.entries("samantha"):
        note_changes_store.drop("samantha", e["path"])  # scratch: no case sees another's drafts
    shutil.rmtree(session.sessions_dir("samantha"), ignore_errors=True)
    seen = reply + "\n" + "\n".join(str(d) for d in drafts)
    ok = (
        all(re.search(p, seen, re.I) for p in case.expect)
        and not any(re.search(p, seen, re.I) for p in case.forbid)
        and not (case.max_soul and len(_soul(reply)) > case.max_soul)
        and not any(re.search(p, _soul(reply), re.I) for p in case.forbid_in_soul)
    )
    return ok, " ".join(seen.split())


def main(runs: int, models: list[str], verbose: bool) -> None:
    from sympose.envfile import load_env

    load_env()  # a cloud model's key, from .env
    tmp = setup_scratch()
    try:
        for model in models or [None]:
            print(f"\n=== {model or 'the default model'} ===", flush=True)
            for case in CASES:
                results = []
                for _ in range(runs):
                    try:
                        results.append(run_case(case, model))
                    except Exception as e:  # a model that could not be reached is a failed run, not the end
                        results.append((False, f"ERROR (not a model answer): {e}"))
                print(f"{case.id}: {sum(ok for ok, _ in results)}/{runs}", flush=True)
                for ok, text in results:
                    if verbose or not ok:
                        print(f"   {'ok  ' if ok else 'FAIL'} {text[:400]}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    args = [a for a in sys.argv[1:] if a != "-v"]
    count = int(args[0]) if args and args[0].isdigit() else 3
    main(count, [a for a in args if not a.isdigit()], "-v" in sys.argv)
