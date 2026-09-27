"""`sympose vault` (docs/decisions/034): `--health` reports on the notes and changes nothing, `--draft <folder>`
drafts a folder's definition (ADR 033), shows it and writes it only when the person answers yes."""

import sys
from typing import Any, Callable, TextIO

from sympose import folder_definitions_write as write_defs
from sympose import profile as profiles
from sympose import vault_health, vault_health_report
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS


def _profile(persona: str | None, out: TextIO) -> dict[str, Any] | None:
    found = profiles.resolve_profile(persona)
    if found is None:
        print(f"sympose vault: there is no persona named {persona!r}" if persona else "sympose vault: the default persona cannot be found (run `sympose doctor`)", file=out)
    return found


def health(persona: str | None = None, out: TextIO | None = None) -> int:
    """Prints the report; 0 when no problem was found, else 1 (a folder offered a definition is not a problem)."""
    out = out or sys.stdout
    found = _profile(persona, out)
    if found is None:
        return 1
    scanned = vault_health.scan(found)
    if scanned is None:
        print("sympose vault: no vault is set up (see VAULT_PATHS in .env.example)", file=out)
        return 1
    scope, results = scanned
    print("\n".join(vault_health_report.render(scope, results)), file=out)
    return 1 if vault_health_report.problem_count(results) else 0


def _why(proposal: Any) -> str:
    from sympose.engine import folder_purpose as purpose

    return {
        purpose.WRITTEN: "The purpose was written by the model from the titles of the folder's notes and the names of its sub-folders.",
        purpose.UNCLEAR: "The titles do not show what the folder is for, so its purpose is left empty for you to write.",
        purpose.WITHHELD: "The model is a cloud model and `notes` is not approved for it (`/share`), so nothing was sent and the purpose is left empty.",
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
