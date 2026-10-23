"""Accepting or declining a persona's new-note draft (docs/decisions/093, "Accept and Decline in Slack"; the web app's Accept goes
through here too, `POST /api/vault/changes/accept`): the one place a draft becomes a note. The note is made with
`vault_write_create.create_note` (the sandbox, the lock and the refusal to overwrite the routes have), named by its title in the
draft's folder, and only then is the proposal forgotten. Nothing here runs unless the user pressed Accept."""

import contextlib
import os
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass

from sympose import draft_decisions, note_changes, persona_files, profile as profile_mod, vault_write_create
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS

NAME_LIMIT = 80
TRIES = 20  # the name, then the name with (2) to (20)
_UNFIT = re.compile(r'[\\/:*?"<>|#^\[\]]')  # what a file name or a link cannot hold
_MADE = re.compile(r"`(.+)`")  # the path in "Created note: `Folder/Name.md`"
LOCK = "accept.lock"
_lock = threading.Lock()


@contextlib.contextmanager
def _one_at_a_time(handle: str) -> Iterator[None]:
    """A note is made and its proposal forgotten as one step, so a double press makes one note: in this program by a lock, and
    between programs (the web app and `sympose slack` are two, and a press can reach both) by a lock on a file in the persona's
    own folder. Where the system has no file locks the first alone stands."""
    with _lock, contextlib.ExitStack() as stack:
        try:
            import fcntl

            path = persona_files.slack_path(handle, LOCK)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fcntl.flock(stack.enter_context(open(path, "a")), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield


class Gone(Exception):
    """The draft is not waiting any more: decided already, in the web app or by an earlier press."""


class Refused(Exception):
    """The note could not be made. The message is plain words for the user and holds nothing from the vault but the draft's name."""


@dataclass(frozen=True)
class Decided:
    name: str  # the draft's working name
    path: str | None  # the note made (a vault path with its `.md`); `None` for a decline


def file_name(title: str | None) -> str:
    """A title as a file name: no characters a file name or a link cannot hold, no
    runs of spaces, at most 80 characters, `Untitled` when nothing is left."""
    return " ".join(_UNFIT.sub(" ", title or "").split())[:NAME_LIMIT] or "Untitled"


def _waiting(handle: str, path: str, proposal_id: str) -> dict:
    proposal = note_changes.pending_new_note(handle, path, proposal_id)
    if proposal is None:
        raise Gone(proposal_id)
    return proposal


def accept(handle: str, path: str, proposal_id: str) -> Decided:
    """Make the note the draft `proposal_id` under `path` proposes, with the text it holds now, and forget the draft."""
    with _one_at_a_time(handle):
        proposal = _waiting(handle, path, proposal_id)
        name = str(proposal.get("name") or "Untitled")
        profile = profile_mod.resolve_profile(handle)
        if profile is None:
            raise Refused(f"{name} could not be saved: this persona was not found.")
        # A draft under a working path (`new/<id>.md`) is named by its title in its folder, and numbered when that name is taken. One
        # that already has a real path (older than the working paths) is made there, and only there.
        if path.startswith("new/"):
            base = "/".join(part for part in (proposal.get("folder"), file_name(name)) if part)
            names = [base if n == 1 else f"{base} ({n})" for n in range(1, TRIES + 1)]
        else:
            names = [path]  # `create_note` takes the path with its `.md`
        for target in names:
            result = vault_write_create.create_note(profile, target, str(proposal.get("text") or ""))
            if result == NOTE_EXISTS:
                continue
            if result == NOTE_DENIED:
                raise Refused(f"{name} could not be saved: its folder is outside what this persona may write to.")
            if not (made := _MADE.search(result)):
                raise Refused(f"{name} could not be saved: the vault could not be written.")
            # Told before the draft is forgotten, so an editor that looks in between never finds a gone draft with no answer. The
            # note is made: a record that cannot be written costs the editor its jump to the note, never the Accept.
            with contextlib.suppress(OSError):
                draft_decisions.record(handle, path, "accepted", made.group(1))
            try:
                note_changes.discard_proposal(handle, path, proposal_id)
            except KeyError:
                pass  # forgotten at the same moment elsewhere: the note is made all the same
            return Decided(name, made.group(1))
        taken = "a note with that name exists, and so do the numbered ones" if len(names) > 1 else f"a note already exists at {names[0]}"
        raise Refused(f"{name} could not be saved: {taken}. Rename one and try again.")


def decline(handle: str, path: str, proposal_id: str) -> Decided:
    """Forget the draft; nothing is written."""
    with _one_at_a_time(handle):
        name = str(_waiting(handle, path, proposal_id).get("name") or "Untitled")
        try:
            note_changes.discard_proposal(handle, path, proposal_id)
        except KeyError:
            raise Gone(proposal_id) from None
        with contextlib.suppress(OSError):
            draft_decisions.record(handle, path, "declined", None)
        return Decided(name, None)
