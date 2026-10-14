"""A real-model check of the table rule a model with tools is given beside an open note that holds a table (docs/decisions/072,
amendment of 2026-10-06): a change inside a table is one cell's own words, and a row or column is added or removed by quoting
the whole table. Scratch data and an invented note only, so a cloud model may be named. Each reply's tool calls are scored by
applying them with the app's own check (`table_spans.problem`): a change it would refuse is a failure, and a request the rule
says cannot be made must propose nothing and say so. Opt-in, not deterministic: read the failing replies.

    TABLE_ARM=rule|none python tests/live_table_cases.py [runs] [model]      (default model: gemini/gemini-flash-latest)

`rule` is the shipped text, `none` blanks the table rule. The shipped text ends with the sentence for a cell whose words are found
elsewhere in the note (a count such as `2` also sits inside `12`, so a single cell cannot be quoted alone)."""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

NOTE = """# Garden plan

## Beds

| Plant | Count | Place |
|---|---|---|
| Basil | 2 | window |
| Carrots | 12 | long bed |
| Tomatoes | 6 | fence |

## Schedule

Water the beds every morning. We recieve the seedlings in March.
"""
SAYS_CANT = re.compile(r"can(?:no|')t|cannot|unable|not able|isn't possible|not possible|won't be able|can only", re.I)
# (id, request, "ok" when a change the app accepts is wanted or "decline" when she must say she cannot, check on the new note)
CASES = [
    ("cell", "Change the Basil count from 2 to 4 in the table.", "ok", lambda n: "| Basil | 4 | window |" in n),
    ("add-row", "Add a row to the table for Mint, 1, on the windowsill.", "ok", lambda n: bool(re.search(r"\|\s*Mint\s*\|\s*1\s*\|", n)) and "Carrots" in n),
    ("remove-row", "Remove the Carrots row from the table.", "ok", lambda n: "Carrots" not in n and "Basil" in n and "Tomatoes" in n),
    ("add-column", "Add a Notes column to the table.", "ok", lambda n: "Notes" in n and all(row.count("|") == 5 for row in n.splitlines() if row.startswith("|"))),
    ("delete-table", "Delete the whole table from the note.", "decline", None),
    ("typo", "Fix the typo in the schedule.", "ok", lambda n: "receive" in n and "recieve" not in n and "| Basil | 2 | window |" in n),
]


def run(model: str, runs: int, verbose: bool) -> None:
    import litellm

    from sympose import profile, table_spans
    from sympose.engine import edit_tools, edit_turn, prompt

    arm = os.environ.get("TABLE_ARM", "rule")
    if arm == "none":
        edit_turn._TABLES = ""
    system = prompt.build_system_prompt(profile.get_profile("samantha"))
    wanted, declined, refused = [0, 0], [0, 0], 0
    for cid, request, kind, check in CASES:
        good = 0
        for _ in range(runs):
            edit = edit_turn.Edit("manual", True, edit_turn.OpenNote("Garden plan.md", NOTE))
            messages = [{"role": "system", "content": system}, {"role": "user", "content": edit_turn.message(edit, request)}]
            try:
                said = litellm.completion(model=model, messages=messages, tools=edit_tools.TOOLS, timeout=180).choices[0].message
            except Exception as error:
                print(f"   [{cid}] call failed: {str(error)[:100]}", flush=True)
                continue
            reply, text, bad, commented = said.content or "", NOTE, 0, False
            for call in said.tool_calls or []:
                try:
                    args = json.loads(call.function.arguments)
                except Exception:
                    bad += 1
                    continue
                if call.function.name == "comment_on":
                    commented = True
                elif call.function.name == "propose_edit":
                    find, replace = args.get("find", ""), args.get("replace", "")
                    at = text.find(find) if find and text.count(find) == 1 else -1
                    if at < 0 or table_spans.problem(text, at, at + len(find), replace):
                        bad += 1  # not placed once, or a change the app refuses to draw
                        refused += at >= 0
                        continue
                    text = text.replace(find, replace, 1)
            passed = bad == 0 and (bool(check(text)) if kind == "ok" else text == NOTE and (bool(SAYS_CANT.search(reply)) or commented))
            good += passed
            counts = wanted if kind == "ok" else declined
            counts[0] += 1
            counts[1] += passed
            if verbose and not passed:
                print(f"      [{cid}] bad={bad} commented={commented} calls={[c.function.name for c in said.tool_calls or []]} reply={reply[:200]!r}", flush=True)
        print(f"  {cid:13} {kind:8} {good}/{runs}", flush=True)
    print(f"{model} [table {arm}] wanted change {wanted[1]}/{wanted[0]}  declined when it must {declined[1]}/{declined[0]}  proposals the app refuses {refused}\n", flush=True)


if __name__ == "__main__":
    from live_prompt_cases import setup_scratch
    from sympose.envfile import load_env

    load_env()
    setup_scratch()
    args = [a for a in sys.argv[1:] if a != "-v"]
    run(args[1] if len(args) > 1 else "gemini/gemini-flash-latest", int(args[0]) if args else 4, "-v" in sys.argv)
