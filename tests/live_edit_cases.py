"""A real-model check of a persona proposing an edit to the open note with the real prompt (docs/decisions/072).

Spike B (`live_patch_cases.py`) measured a bare prompt. This sends what a turn would: Samantha's real system prompt,
the open note and the edit instructions in the user turn (a small model follows what sits last and nearest the
question, ADR 020), then the request. A change is proposed in the reply as a marker, the shape a model that cannot call
tools must use (ADR 041's pattern):

    <!-- propose_edit: {"find": "...", "replace": "...", "say": "one sentence"} -->

Each reply is scored on the same three steps as Spike B (`parsed`, `matched`, `correct`) with the same nine edit
requests, plus the cases that matter for `manual` mode: a question about the note, thanks, and a "would it be
better" discussion must produce no marker at all (she does not propose unasked). Scratch data and invented notes only,
so a cloud model may be named. Opt-in, not deterministic: read the failing replies (-v).

    python tests/live_edit_cases.py [-v] [runs] [model ...]      (default model: ollama_chat/gemma2:9b)"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from live_patch_cases import CASES, GARDEN, correct  # noqa: E402

EDIT_RULES = (
    "The note open in the editor is below. When the user asks you to change it, do not rewrite it: say in a sentence "
    "what you will change, then add one line for each change, exactly in this form: "
    '<!-- propose_edit: {"find": "...", "replace": "...", "say": "..."} --> '
    '"find" is copied from the note exactly, character for character, and appears in the note exactly once '
    "(include a neighbouring word if it does not on its own); write line breaks in strings as \\n. The user reviews "
    "each change before anything is saved. If the request needs information that is neither in the note nor in the "
    "request, propose nothing and say what you need. If the user is only asking or talking, propose nothing."
)
NO_PROPOSAL = [
    ("question", GARDEN, "Which vegetables are in the beds?"),
    ("thanks", GARDEN, "Thanks, that looks good."),
    ("discuss", GARDEN, "Would it be better to put the carrots somewhere else, do you think?"),
]
_MARKER = re.compile(r"<!--\s*propose_edit:\s*(\{.*?\})\s*-->", re.S)


# Where the instructions sit, and how firmly they are put (the soul's chattiness outweighed them in `A`):
#   A rules, note, request      B note, request, rules (nearest the question)      C B, and the request framed as a task
#   D C, and a line in the system prompt saying a requested change is made by proposing it
VARIANT = os.environ.get("EDIT_VARIANT", "A")
TASK = "This is a task on the note, not a chat: answer it by doing it as described below, with no questions and no remarks about the garden."
SYSTEM_LINE = "When the user asks you to change the note open in the editor, you make the change by proposing it, as the message describes; you do not only talk about it."


def user_turn(note: str, request: str) -> str:
    if VARIANT == "A":
        return f"{EDIT_RULES}\n\nThe open note, Garden plan.md:\n\n````\n{note}````\n\n{request}"
    head = f"The open note, Garden plan.md:\n\n````\n{note}````\n\nThe user's request: {request}\n\n"
    return head + (f"{TASK}\n\n" if VARIANT in "CD" else "") + EDIT_RULES


def patches(reply: str) -> tuple[bool, list[tuple[str, str]]]:
    """`(every marker was valid JSON, the (find, replace) pairs)`."""
    found, ok = [], True
    for raw in _MARKER.findall(reply):
        try:
            data = json.loads(raw)
            found.append((data["find"], data["replace"]))
        except Exception:
            ok = False
    return ok, found


def apply(reply: str, note: str) -> tuple[bool, bool, str]:
    """`(parsed, matched, new note)`; a reply with no marker is a valid reply that changes nothing."""
    ok, found = patches(reply)
    if not ok:
        return False, False, note
    text = note
    for find, replace in found:
        if not find or text.count(find) != 1:
            return True, False, note
        text = text.replace(find, replace, 1)
    return True, True, text


def system_prompt() -> str:
    from sympose import profile
    from sympose.engine import prompt

    text = prompt.build_system_prompt(profile.get_profile("samantha"))
    return f"{text}\n\n{SYSTEM_LINE}" if VARIANT == "D" else text


def run(model: str, runs: int, verbose: bool) -> None:
    import litellm

    system = system_prompt()

    def ask(note: str, request: str) -> str:
        try:
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user_turn(note, request)}]
            return litellm.completion(model=model, messages=messages, timeout=180).choices[0].message.content or ""
        except Exception as error:
            return f"(call failed: {str(error)[:120]})"

    totals = [0, 0, 0]
    for case in CASES:
        cid, note, instruction = case[0], case[1], case[2]
        scores = []
        for _ in range(runs):
            reply = ask(note, instruction)
            parsed, matched, new = apply(reply, note)
            scores.append((parsed, matched, parsed and matched and correct(case, new)))
            if verbose and not scores[-1][2]:
                print(f"      [{cid}] {reply[:300]!r}", flush=True)
        for i in range(3):
            totals[i] += sum(s[i] for s in scores)
        print(f"  edit     {cid:12} parsed {sum(s[0] for s in scores)}/{runs}  matched {sum(s[1] for s in scores)}/{runs}  correct {sum(s[2] for s in scores)}/{runs}", flush=True)
    n = runs * len(CASES)
    print(f"{model} [{VARIANT}] edits: parsed {totals[0]}/{n}  matched {totals[1]}/{n}  correct {totals[2]}/{n}", flush=True)

    quiet = 0
    for cid, note, request in NO_PROPOSAL:
        none = 0
        for _ in range(runs):
            reply = ask(note, request)
            if "propose_edit" not in reply:
                none += 1
            elif verbose:
                print(f"      [{cid}] proposed unasked: {reply[:300]!r}", flush=True)
        quiet += none
        print(f"  quiet    {cid:12} no proposal {none}/{runs}", flush=True)
    print(f"{model} [{VARIANT}] no unasked proposal: {quiet}/{runs * len(NO_PROPOSAL)}\n", flush=True)


if __name__ == "__main__":
    from live_prompt_cases import setup_scratch
    from sympose.envfile import load_env

    load_env()
    setup_scratch()
    args = [a for a in sys.argv[1:] if a != "-v"]
    runs = int(args[0]) if args and args[0].isdigit() else 4
    for name in [a for a in args if not a.isdigit()] or ["ollama_chat/gemma2:9b"]:
        run(name, runs, "-v" in sys.argv)
