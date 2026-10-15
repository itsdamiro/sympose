"""`sympose vault` (docs/decisions/034): `--health` reports on the notes and changes nothing, `--fix` offers each repair one at
a time and makes it only on a yes (ADR 084), `--draft <folder>` drafts a folder's definition (ADR 033), shows it and writes it only
when the person answers yes."""

import sys
from typing import Any, Callable, TextIO

from sympose import folder_definitions_write as write_defs
from sympose import profile as profiles
from sympose import vault_fixes, vault_health, vault_health_report
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS


NO_VAULT = "sympose vault: no vault is set up yet. Set VAULT_PATHS in your .env file to the folder of your Obsidian vault (see .env.example)."


def _profile(persona: str | None, out: TextIO) -> dict[str, Any] | None:
    found = profiles.resolve_profile(persona)
    if found is None:
        print(f"sympose vault: there is no persona named {persona!r}" if persona else "sympose vault: no default persona was found. Run `sympose doctor` to see why.", file=out)
    return found


def health(persona: str | None = None, out: TextIO | None = None) -> int:
    """Prints the report; 0 when no problem was found, else 1 (a folder offered a definition or an icon is not a
    problem). It only reads: `fix` is what changes a note (ADR 084)."""
    out = out or sys.stdout
    found = _profile(persona, out)
    if found is None:
        return 1
    scanned = vault_health.scan(found)
    if scanned is None:
        print(NO_VAULT, file=out)
        return 1
    scope, results = scanned
    print("\n".join(vault_health_report.render(scope, results)), file=out)
    return 1 if vault_health_report.problem_count(results) else 0


def fix(persona: str | None = None, out: TextIO | None = None, ask: Callable[[str], str] | None = None) -> int:
    """Offers each repair the report has, one at a time (ADR 084), and makes it only on a yes; `q` stops, and so
    do Ctrl-C and the end of the input. The vault is scanned again after every answer, so nothing is done from stale
    information, and an answered repair is not offered twice. 0, or 1 when a repair failed or there is no terminal to
    ask in."""
    out = out or sys.stdout
    if ask is None:
        if not (sys.stdin.isatty() and out.isatty()):  # a prompt into a pipe or a file would hang unseen
            print("sympose vault --fix asks about each change, so it needs a terminal.", file=out)
            return 1
        ask = input
    found = _profile(persona, out)
    if found is None:
        return 1
    answered: set[tuple[str, str, str, str]] = set()
    changed = failed = declined = 0
    results: list[Any] = []
    try:  # Ctrl-C stops the walk wherever it falls, a prompt or the scan between two, and the summary is still given
        while True:
            scanned = vault_health.scan(found)
            if scanned is None:
                print(NO_VAULT, file=out)
                return 1
            results = scanned[1]
            offers = [f for _, here in results for f in here if f.repair and f.repair.key not in answered]
            if not offers:
                break
            if not answered:
                print(f"{len(offers)} repair{'s' if len(offers) != 1 else ''} can be offered, one at a time. y makes it, n or Enter leaves it, q stops.", file=out)
            offer = offers[0]
            print(f"\n{offer.note}: {offer.message}", *(f"  {line}" for line in offer.repair.show), sep="\n", file=out)
            try:
                answer = ask("Make this change? [y/N/q] ").strip().lower()
            except EOFError:
                break
            if answer in ("q", "quit"):
                break
            answered.add(offer.repair.key)
            if answer not in ("y", "yes"):
                print("Left as it is.", file=out)
                declined += 1
                continue
            done, message = vault_fixes.apply(found, offer.repair)
            print(message, file=out)
            changed += done
            failed += not done
    except KeyboardInterrupt:
        print("\nStopped.", file=out)
    left = sum(1 for check, here in results for f in here if check.fixable and f.repair is None)
    summary = f"{changed} changed, {declined} left as they are" + (f", {failed} could not be made." if failed else ".")
    print(f"\n{summary}" + (f" {left} more findings have no repair here." if left else ""), file=out)
    return 1 if failed else 0


def _why(proposal: Any) -> str:
    from sympose.engine import folder_purpose as purpose

    return {
        purpose.WRITTEN: "The model wrote this description from your note titles.",
        purpose.UNCLEAR: "The titles do not show what the folder is for, so its purpose is left empty for you to write.",
        purpose.WITHHELD: "This is a cloud model and your notes aren't shared with cloud models (/share), so nothing was sent and the description is blank.",
        purpose.FAILED: f"The model could not write a purpose ({proposal.reason}), so it is left empty.",
    }[proposal.state]


def _shown(proposal: Any) -> list[str]:
    made = proposal.draft
    if not made.template:
        source = "No property is carried by enough of the folder's notes, so the template is empty."
    elif made.from_templates_file:
        source = "The template is the properties of your Templates file for this folder."
    else:
        source = f"The template is counted from {made.notes} notes of the folder."
    return [f"Draft of {made.rel_path}:", "", *made.text.rstrip().splitlines(), "", source, _why(proposal)]


def draft(folder: str, persona: str | None = None, out: TextIO | None = None, ask: Callable[[str], str] = input) -> int:
    """Shows the definition `folder` would get and writes it only on a yes; 0 when it was written or declined."""
    from sympose.engine import folder_purpose as purpose  # imported here: it brings in litellm, a few seconds

    out = out or sys.stdout
    found = _profile(persona, out)
    if found is None:
        return 1
    print(f"Drafting a definition for {folder!r} from the titles of its notes...", file=out)
    proposal = purpose.propose(found, folder)
    if proposal is None:
        print(f"sympose vault: {folder!r} cannot be given a definition: it is not a folder of notes you can read, or it has one already", file=out)
        return 1
    print("\n".join(_shown(proposal)), file=out)
    try:
        answer = ask("\nWrite it? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        print("Not written.", file=out)
        return 0
    message = write_defs.write(found, proposal.draft)
    refused = {NOTE_EXISTS: "That note exists already, so nothing was changed.", NOTE_DENIED: "This persona may not write there, so nothing was written."}
    print(refused.get(message, message), file=out)
    return 1 if message in refused else 0
