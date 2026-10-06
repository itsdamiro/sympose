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

    [EDIT_MODE=manual|auto] [EDIT_TOOL=1] python tests/live_edit_cases.py [-v] [runs] [model ...]      (default model: ollama_chat/gemma2:9b)

`EDIT_FOCUS=1` instead compares two things a turn could send for an edit request (docs/decisions/076): the whole open note, as
now, against only the passage the user pointed at, with its section and the note's outline. The focus arm is scored two
ways: `strict` (the `find` must be in the whole note exactly once, the rule the app applies today) and `scoped` (once in the
section sent, which the app would know the user attached, and applied there). A request with no passage to point at (a new
section) sends the whole note in both arms."""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from live_patch_cases import CASES, GARDEN, correct  # noqa: E402

NO_PROPOSAL = [
    ("question", GARDEN, "Which vegetables are in the beds?"),
    ("thanks", GARDEN, "Thanks, that looks good."),
    ("discuss", GARDEN, "Would it be better to put the carrots somewhere else, do you think?"),
]
_MARKER = re.compile(r"<!--\s*propose_edit:\s*(\{.*?\})\s*-->", re.S)


# The text is the product's own (`edit_turn.message`), so what is measured is what ships. EDIT_MODE picks the wording
# (manual, accept: the plain one; auto: the one that also invites a change she notices). EDIT_TOOL=1 gives the model the
# product's tool definitions (`edit_tools.TOOLS`) and the wording a model with tools gets, and reads its tool calls; each
# call is turned into the same marker as the default shape (a model without tools), so scoring is identical.
MODE = os.environ.get("EDIT_MODE", "manual")
TOOL = os.environ.get("EDIT_TOOL") == "1"
# EDIT_LEAN=1 drops the rules for a new note and for a comment, to see whether the longer block costs a small model
# its edits (the lines are there for the cases that need them, and cost the others).
LEAN = os.environ.get("EDIT_LEAN") == "1"


def user_turn(note: str, request: str) -> str:
    from sympose.engine import edit_turn

    if LEAN:
        edit_turn._NOTE_MARKER = edit_turn._COMMENT_MARKER = ""
    edit = edit_turn.Edit(MODE, TOOL, edit_turn.OpenNote("Garden plan.md", note))
    return edit_turn.message(edit, request)


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

    return prompt.build_system_prompt(profile.get_profile("samantha"))


def ask_model(model: str, system: str, note: str, request: str) -> str:
    import litellm

    try:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_turn(note, request)}]
        if not TOOL:
            return litellm.completion(model=model, messages=messages, timeout=180).choices[0].message.content or ""
        from sympose.engine import edit_tools

        reply = litellm.completion(model=model, messages=messages, tools=edit_tools.TOOLS, timeout=180).choices[0].message
        calls = "".join(f"\n<!-- {c.function.name}: {c.function.arguments} -->" for c in reply.tool_calls or [])
        return (reply.content or "") + calls
    except Exception as error:
        return f"(call failed: {str(error)[:120]})"


# The words the user would point at for each request (none for a request about the note as a whole).
POINTED_AT = {
    "swap": "three times", "add-bullet": "Carrots in the long bed", "typo": "recieve", "duplicate": "- Pack charger",
    "keep-link": "Basil near the [[Herbs]] note", "delete": "Tomatoes by the fence", "formal": "Water the beds every morning",
    "no-facts": "Tomatoes by the fence",
}
_HEADING = re.compile(r"^#{1,6} ", re.M)


def section_span(note: str, at: int) -> tuple[int, int]:
    """The part of `note` from the heading before `at` to the next heading."""
    starts = [m.start() for m in _HEADING.finditer(note)]
    begin = max([x for x in starts if x <= at], default=0)
    end = min([x for x in starts if x > at], default=len(note))
    return begin, end


def focus_text(note: str, pointed: str) -> tuple[str, tuple[int, int]]:
    """What a turn would send instead of the note, and where in the note the section sent is."""
    begin, end = section_span(note, note.index(pointed))
    outline = "\n".join(line for line in note.splitlines() if _HEADING.match(line))
    text = (f"[The note's headings:\n{outline}\n\nThe user pointed at: \"{pointed}\". Only the section it is in is shown below; "
            f"the rest of the note is not.]\n\n{note[begin:end]}")
    return text, (begin, end)


def apply_scoped(reply: str, note: str, span: tuple[int, int]) -> tuple[bool, bool, str]:
    """Like `apply`, but a `find` need only be in the section sent exactly once, and is replaced there."""
    ok, found = patches(reply)
    if not ok:
        return False, False, note
    begin, end = span
    part = note[begin:end]
    for find, replace in found:
        if not find or part.count(find) != 1:
            return True, False, note
        part = part.replace(find, replace, 1)
    return True, True, note[:begin] + part + note[end:]


def run_compare(model: str, runs: int, verbose: bool) -> None:
    system = system_prompt()
    arms = ["whole", "focus-strict", "focus-scoped"]
    totals = {a: [0, 0] for a in arms}  # matched, correct
    n = 0
    for case in CASES:
        cid, note, instruction = case[0], case[1], case[2]
        row = {a: [0, 0] for a in arms}
        for _ in range(runs):
            n += 1
            whole = ask_model(model, system, note, instruction)
            parsed, matched, new = apply(whole, note)
            row["whole"][0] += matched
            row["whole"][1] += bool(parsed and matched and correct(case, new))
            if cid in POINTED_AT:
                text, span = focus_text(note, POINTED_AT[cid])
                reply = ask_model(model, system, text, instruction)
                strict = apply(reply, note)
                scoped = apply_scoped(reply, note, span)
            else:  # nothing to point at: the whole note, in every arm
                reply, strict, scoped = whole, (parsed, matched, new), (parsed, matched, new)
            for arm, got in (("focus-strict", strict), ("focus-scoped", scoped)):
                row[arm][0] += got[1]
                row[arm][1] += bool(got[0] and got[1] and correct(case, got[2]))
                if verbose and not (got[0] and got[1] and correct(case, got[2])):
                    print(f"      [{arm}/{cid}] {reply[:300]!r}", flush=True)
        for a in arms:
            totals[a][0] += row[a][0]
            totals[a][1] += row[a][1]
        print(f"  {cid:12} " + "  ".join(f"{a} {row[a][1]}/{runs}" for a in arms), flush=True)
    total = runs * len(CASES)
    print(f"{model} [{MODE}{'+tools' if TOOL else ''}] correct of {total}: " + "  ".join(f"{a} {totals[a][1]} (matched {totals[a][0]})" for a in arms) + "\n", flush=True)


def run(model: str, runs: int, verbose: bool) -> None:
    system = system_prompt()

    def ask(note: str, request: str) -> str:
        return ask_model(model, system, note, request)

    totals, wrong = [0, 0, 0], 0
    for case in CASES:
        cid, note, instruction = case[0], case[1], case[2]
        scores = []
        for _ in range(runs):
            reply = ask(note, instruction)
            parsed, matched, new = apply(reply, note)
            if MODE == "auto" and cid != "typo":
                new = new.replace("receive", "recieve")  # `auto` may also fix the invented note's seeded typo, which it should notice: not an error in the requested edit
            scores.append((parsed, matched, parsed and matched and correct(case, new)))
            wrong += bool(patches(reply)[1]) and bool(scores[-1][1]) and not scores[-1][2]  # a change that was placed and is wrong
            if verbose and not scores[-1][2]:
                print(f"      [{cid}] {reply[:300]!r}", flush=True)
        for i in range(3):
            totals[i] += sum(s[i] for s in scores)
        print(f"  edit     {cid:12} parsed {sum(s[0] for s in scores)}/{runs}  matched {sum(s[1] for s in scores)}/{runs}  correct {sum(s[2] for s in scores)}/{runs}", flush=True)
    n = runs * len(CASES)
    print(f"{model} [{MODE}{'+tools' if TOOL else ''}] edits: parsed {totals[0]}/{n}  matched {totals[1]}/{n}  correct {totals[2]}/{n}  placed but wrong {wrong}/{n}", flush=True)

    quiet, noticed = 0, 0
    for cid, note, request in NO_PROPOSAL:
        none = 0
        for _ in range(runs):
            reply = ask(note, request)
            others = [f for f, _ in patches(reply)[1] if "recieve" not in f] if MODE == "auto" else None  # in `auto` only the seeded typo may be proposed unasked
            noticed += MODE == "auto" and "recieve" in reply and "propose_edit" in reply
            if (others is None and "propose_edit" not in reply) or (others is not None and not others and patches(reply)[0]):
                none += 1
            elif verbose:
                print(f"      [{cid}] proposed unasked: {reply[:300]!r}", flush=True)
        quiet += none
        print(f"  quiet    {cid:12} no proposal {none}/{runs}", flush=True)
    print(f"{model} [{MODE}{'+tools' if TOOL else ''}] no unasked proposal{' except the seeded typo' if MODE == 'auto' else ''}: {quiet}/{runs * len(NO_PROPOSAL)}"
          + (f"  (noticed the typo in {noticed})" if MODE == "auto" else "") + "\n", flush=True)


if __name__ == "__main__":
    from live_prompt_cases import setup_scratch
    from sympose.envfile import load_env

    load_env()
    setup_scratch()
    args = [a for a in sys.argv[1:] if a != "-v"]
    runs = int(args[0]) if args and args[0].isdigit() else 4
    for name in [a for a in args if not a.isdigit()] or ["ollama_chat/gemma2:9b"]:
        (run_compare if os.environ.get("EDIT_FOCUS") == "1" else run)(name, runs, "-v" in sys.argv)
