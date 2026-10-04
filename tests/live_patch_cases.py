"""A real-model check of how faithfully a model edits a note when asked for a patch (docs/decisions/042, Spike B).

ADR 042 gates a persona that writes on a write-specific accuracy bar, not on the retrieval number: not "does the
model find the right note" but "does it change what was asked and nothing else, without inventing". This script
gives a model an invented note and an instruction and asks for the change in one of three shapes, then scores the
result by applying it to the note:

  json     {"patches": [{"find": ..., "replace": ...}], "say": ...}
  blocks   SEARCH / REPLACE blocks (plain text between markers, no escaping)
  rewrite  the whole new note (the baseline: nothing for the user to review but a diff of everything)

Each run is scored on three steps: `parsed` (the reply had the shape), `matched` (every `find` is in the note
exactly once, character for character) and `correct` (the resulting note is what the instruction asked, nothing
else changed, and a request that needs facts the note lacks invents none). Nothing of anyone's vault is read or
sent: the notes below are invented, so a cloud model may be named. Opt-in and not deterministic; every figure is
a fact about that model only, so read the failing replies (-v).

    python tests/live_patch_cases.py [-v] [runs] [model ...]      (default model: ollama_chat/gemma2:9b)"""

import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GARDEN = """---
title: Garden plan
---
# Garden plan

I run **three times** a week and I also plan the garden. The beds are *raised* and the soil is rich.

## Beds

- Tomatoes by the fence
- Basil near the [[Herbs]] note
- Carrots in the long bed

## Schedule

Water the beds every morning. We recieve the seedlings in March and plant them in April.
"""
TRIP = """# Trip checklist

## Documents

- Passport
- Pack charger
- Tickets

## Electronics

- Phone
- Pack charger
- Headphones
"""
SCHEDULE = "Water the beds every morning. We recieve the seedlings in March and plant them in April."


def sub(note: str, old: str, new: str) -> str:
    return note.replace(old, new, 1)


# id, note, instruction, expected result (exact, after tidying blank lines) or None, checks for the cases with none.
CASES = [
    ("swap", GARDEN, "Change 'three times' to 'four times'.", sub(GARDEN, "three times", "four times"), {}),
    ("add-bullet", GARDEN, "Add a bullet 'Peppers in the greenhouse' after the Carrots bullet.", sub(GARDEN, "- Carrots in the long bed\n", "- Carrots in the long bed\n- Peppers in the greenhouse\n"), {}),
    ("typo", GARDEN, "Fix the spelling mistake in the Schedule section.", sub(GARDEN, "recieve", "receive"), {}),
    ("duplicate", TRIP, "Change the first 'Pack charger' line to 'Pack charger and cable'.", sub(TRIP, "- Pack charger\n", "- Pack charger and cable\n"), {}),
    ("keep-link", GARDEN, "Change the Basil bullet to say 'Basil near the [[Herbs]] note and the pond'.", sub(GARDEN, "note\n", "note and the pond\n"), {}),
    ("delete", GARDEN, "Remove the Tomatoes bullet.", sub(GARDEN, "- Tomatoes by the fence\n", ""), {}),
    ("formal", GARDEN, "Rewrite the Schedule paragraph in a more formal tone.", None, {"removed": [SCHEDULE], "changed": True, "must": [r"March", r"April"], "forbid": [r"\d"]}),
    ("new-section", GARDEN, "Add a section 'Notes' at the end saying the soil needs compost in autumn.", None, {"removed": [], "must": [r"## Notes", r"compost"], "forbid": [r"\d"]}),
    ("no-facts", GARDEN, "Add the exact price of the tomato seeds to the Tomatoes bullet.", None, {"removed": [], "forbid": [r"\d", r"[$£€]"]}),
]
COMMON = (
    "You are editing the user's note, shown between the markers. Make only the change asked and change nothing else. "
    "If the request needs information that is neither in the note nor in the request, make no change and say what you need.\n\n"
)
SHAPES = {
    "json": 'Reply with only a JSON object: {"patches": [{"find": "...", "replace": "..."}], "say": "one sentence"}. "find" is copied from the note exactly, character for character, and appears in the note exactly once (include a neighbouring word or line if it does not on its own). Write line breaks inside strings as \\n. No change: "patches": [].',
    "blocks": "Reply with one sentence saying what you changed, then one block per change, exactly in this form:\n<<<<<<< SEARCH\n(text copied from the note exactly, appearing in it exactly once)\n=======\n(the new text)\n>>>>>>> REPLACE\nNo change: reply with the sentence only.",
    "rewrite": "Reply with the complete new note and nothing else.",
}


def tidy(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in text.strip().splitlines()))


def parse(shape: str, reply: str, note: str) -> tuple[bool, bool, str]:
    """`(parsed, matched, new note)` for a reply in `shape`."""
    if shape == "rewrite":
        body = re.sub(r"^```\w*\n|\n```$", "", reply.strip())
        return True, True, "\n".join(line for line in body.splitlines() if line.strip() not in ("--- NOTE ---", "--- END NOTE ---"))
    try:
        if shape == "json":
            body = re.search(r"\{.*\}", reply, re.S)
            patches = [(p["find"], p["replace"]) for p in json.loads(body.group(0)).get("patches", [])]
        else:
            patches = re.findall(r"<<<<<<< SEARCH\n(.*?)\n?=======\n(.*?)\n?>>>>>>> REPLACE", reply, re.S)
    except Exception:
        return False, False, note
    text = note
    for find, replace in patches:
        if not find or text.count(find) != 1:
            return True, False, note
        text = text.replace(find, replace, 1)
    return True, True, text


def correct(case: tuple, new: str) -> bool:
    _, note, _, expected, checks = case
    if expected is not None:
        return tidy(new) == tidy(expected)
    if checks.get("changed") and tidy(new) == tidy(note):
        return False
    old_lines, new_lines = note.splitlines(), new.splitlines()
    diff = [line for line in difflib.ndiff(old_lines, new_lines) if line[:2] in ("- ", "+ ")]
    removed = [line[2:] for line in diff if line[0] == "-"]
    added = "\n".join(line[2:] for line in diff if line[0] == "+")
    return (
        all(line in checks["removed"] for line in removed)
        and all(re.search(rx, new) for rx in checks.get("must", []))
        and not any(re.search(rx, added) for rx in checks.get("forbid", []))
    )


def run(model: str, runs: int, verbose: bool) -> None:
    import litellm

    for shape, rule in SHAPES.items():
        totals = [0, 0, 0]
        for case in CASES:
            cid, note, instruction = case[0], case[1], case[2]
            scores = []
            for _ in range(runs):
                prompt = f"{COMMON}{rule}\n\n--- NOTE ---\n{note}--- END NOTE ---\n\nRequest: {instruction}"
                try:
                    reply = litellm.completion(model=model, messages=[{"role": "user", "content": prompt}], timeout=120).choices[0].message.content or ""
                except Exception as error:
                    reply = f"(call failed: {str(error)[:120]})"
                parsed, matched, new = parse(shape, reply, note)
                scores.append((parsed, matched, parsed and matched and correct(case, new)))
                if verbose and not scores[-1][2]:
                    print(f"      [{shape}/{cid}] {reply[:260]!r}", flush=True)
            for i in range(3):
                totals[i] += sum(s[i] for s in scores)
            print(f"  {shape:8} {cid:12} parsed {sum(s[0] for s in scores)}/{runs}  matched {sum(s[1] for s in scores)}/{runs}  correct {sum(s[2] for s in scores)}/{runs}", flush=True)
        n = runs * len(CASES)
        print(f"{model} {shape}: parsed {totals[0]}/{n}  matched {totals[1]}/{n}  correct {totals[2]}/{n}\n", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(HERE, ".."))
    from sympose.envfile import load_env

    load_env()
    args = [a for a in sys.argv[1:] if a != "-v"]
    runs = int(args[0]) if args and args[0].isdigit() else 4
    for name in [a for a in args if not a.isdigit()] or ["ollama_chat/gemma2:9b"]:
        run(name, runs, "-v" in sys.argv)
