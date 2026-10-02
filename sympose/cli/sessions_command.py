"""`/sessions` (and `/history`, the same command; docs/decisions/057): the persona's past conversations, numbered, and
what can be done to one: `open <n>`, `rename <n> <title>`, `pin <n>`, `unpin <n>`, `delete <n>`. A number is the
conversation's place in the list as it is when the command runs, so a command acts on what `/sessions` shows now.

Opening a conversation starts a new generation that continues it, as a persona switch starts one with no session:
a reply still being written in the conversation left lands in its own, and the messages typed from now on go to
the one opened. Deleting is soft (the files move to `sessions/.trash/`)."""

from datetime import datetime

from rich.style import Style

from sympose.cli import meter, meter_estimate, transcript as transcript_mod
from sympose.cli.options import active_model
from sympose.engine import session, session_compaction, session_manage

NAMES = ("/sessions", "/history")
_SHOWN_TURNS = 4  # the last turns of an opened conversation that are shown again, so the user sees where it stopped

_USAGE = (
    "Usage: /sessions lists the conversations. /sessions open <n>, rename <n> <title>, pin <n>, unpin <n> or "
    "delete <n> act on one by its number."
)
_FAILED = {
    session_manage.NOT_FOUND: "That conversation is no longer there.",
    session_manage.BAD_TITLE: f"A title is one line of 1 to {session_manage.MAX_TITLE} characters.",
    session_manage.BUSY: "A reply is being written in that conversation: stop it first, or wait.",
    session_manage.FAILED: "Could not save the change.",
}


def _when(stamp: str | None) -> str:
    try:
        return datetime.fromisoformat(stamp or "").astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return "?"


def _line(number: int, row: dict, current: str | None) -> str:
    marks = [mark for mark, on in (("pinned", row["pinned_at"]), ("replying", row["replying"]), ("this one", row["id"] == current)) if on]
    title = row["title"] or "(new conversation)"
    turns = f"{row['turns']} turn{'s' if row['turns'] != 1 else ''}"
    return f"{number:>3}. {title} · {turns} · {_when(row['updated_at'])}" + (f" · {', '.join(marks)}" if marks else "")


def _show_list(app, rows: list[dict]) -> None:
    if not rows:
        transcript_mod.mount_line(app, "No earlier conversations yet.", "system")
        return
    transcript_mod.mount_line(app, f"@{app.persona.handle}'s conversations (open one with /sessions open <n>):", "system")
    for number, row in enumerate(rows, 1):
        transcript_mod.mount_line(app, _line(number, row, app.session_id), "system")


def _row(app, rows: list[dict], text: str) -> dict | None:
    if not text.isdigit() or not 1 <= int(text) <= len(rows):
        transcript_mod.mount_line(app, f"There is no conversation number {text or '?'}: /sessions lists them.", "system")
        return None
    return rows[int(text) - 1]


async def _open(app, row: dict) -> None:
    loaded = session.load_session(app.persona.handle, row["id"])
    if loaded is None:
        transcript_mod.mount_line(app, _FAILED[session_manage.NOT_FOUND], "system")
        return
    for timer in app.active_reply_timers:  # a reply being revealed belongs to the conversation left
        timer.stop()
    app.active_reply_timers.clear()
    app.reply_skips.clear()
    app.session_generation += 1
    app.session_by_generation[app.session_generation] = row["id"]
    app.condensed_by_generation[app.session_generation] = session_compaction.covered(loaded)
    app.last_sent = None
    await app.transcript.remove_children()
    app.last_speaker = None
    turns = loaded["turns"]
    if len(turns) > _SHOWN_TURNS:
        transcript_mod.mount_line(app, f"({len(turns) - _SHOWN_TURNS} earlier turns not shown)", "system")
    for turn in turns[-_SHOWN_TURNS:]:
        transcript_mod.mount_line(app, transcript_mod.styled_line("You  ", Style(bold=True, dim=True), turn["user"]), "user")
        transcript_mod.mount_line(app, turn["assistant"], "persona")
    transcript_mod.mount_line(app, f"Continuing \"{row['title'] or 'a new conversation'}\" ({len(turns)} turns).", "system")
    meter.clear(app)
    meter_estimate.start(app, active_model(app.persona, app.model_override).id)
    app.transcript.scroll_end(animate=False)


async def run(app, args: str) -> None:
    handle = app.persona.handle
    rows = session_manage.list_sessions(handle)
    word, _, rest = args.strip().partition(" ")
    word, rest = word.lower(), rest.strip()
    if not word:
        _show_list(app, rows)
    elif word in ("open", "rename", "pin", "unpin", "delete"):
        number, _, title = rest.partition(" ")
        row = _row(app, rows, number)
        if row is None:
            return
        if word == "open":
            await _open(app, row)
            return
        if word == "rename":
            outcome = session_manage.rename(handle, row["id"], title)
        elif word == "delete":
            outcome = session_manage.delete(handle, row["id"])
        else:
            outcome = session_manage.pin(handle, row["id"], word == "pin")
        done = {"rename": "Renamed.", "pin": "Pinned.", "unpin": "Unpinned.", "delete": "Moved to the trash folder (sessions/.trash)."}[word]
        transcript_mod.mount_line(app, done if outcome == session_manage.OK else _FAILED[outcome], "system")
        if word == "delete" and outcome == session_manage.OK and row["id"] == app.session_id:
            app.session_generation += 1  # the conversation on screen is gone: the next message starts a new one
            meter.clear(app)
    else:
        transcript_mod.mount_line(app, _USAGE, "system")
    app.transcript.scroll_end(animate=False)
