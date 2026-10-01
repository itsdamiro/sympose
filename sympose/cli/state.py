"""The CLI app's run-time state (docs/decisions/008): which model and panel are active, the
session, one lock per persona, and the counters that decide whether a turn is in flight.
Set up once from `SymposeCLI.on_mount`; split out of `app.py` to hold the 200-line cap."""

import asyncio

from sympose.cli.selection import SelectionPanel


def init(app) -> None:
    # `None` until `/model` picks one, so a persona's own model (or the
    # `chat_model` setting) applies — see `options.active_model`.
    app.model_override = None
    app.panel: SelectionPanel | None = None
    app.panel_kind: str | None = None
    # The number `/settings` is asking for in the chat box, while it is (docs/decisions/036).
    app.pending_setting: str | None = None
    # `/clear` wipes the visible transcript only; it does not start a new session (no `/new`-style
    # command exists yet). A persona switch does: it bumps `session_generation`, so a call still in
    # flight from before must not be read as the live conversation once it resolves. The persona
    # handle alone isn't enough: switching away and back to the *same* persona would restore a
    # matching handle with a stale session id anyway.
    app.session_generation = 0
    # The session id each generation actually resolved to (docs/decisions/008), so a queued message
    # for the same persona/generation can continue it even after an unrelated persona switch.
    # `SymposeCLI.session_id` is this dict read at the current generation, never a second copy.
    app.session_by_generation: dict[int, str | None] = {}
    # Exactly what the last completed reply's `TurnResult.sent` held (docs/decisions/025) — `None`
    # before any reply, and after `/clear`, which wipes the transcript but not this: the record it
    # describes is still true of the persona's last real reply, `/clear` or not. `/grounded` reads
    # this back rather than the transcript, so it survives a clear (#26).
    app.last_sent: dict | None = None
    # One lock per persona handle (docs/decisions/008), not a single
    # global one: sessions are stored per-handle
    # (sympose/engine/session.py), so two different personas' turns
    # never touch the same file and never actually race each other —
    # only two turns for the *same* persona need to queue behind one
    # another. The composer itself is never blocked either way.
    app.turn_locks: dict[str, asyncio.Lock] = {}
    # The messages sent while a reply for (persona handle, session generation) is running or waiting
    # its turn; they go out together as one turn when it lands (docs/decisions/008, amendment of
    # 2026-10-01). A key is present exactly while that conversation has a run going.
    app.turn_runs: dict[tuple[str, int], list[str]] = {}
    # Every currently-streaming reply's own timer — not a single slot,
    # since turns for different personas (or two queued same-persona
    # turns) can now genuinely stream concurrently post-lock.
    app.active_reply_timers: set = set()
    # What the Stop line acts on (docs/decisions/054): the persona handles whose engine call is running
    # right now, the functions that show a reply that is being revealed whole, and whether a stop was
    # accepted and is waiting for the engine to end its call.
    app.generating: set[str] = set()
    app.reply_skips: set = set()
    app.stopping = False
    # A plain counter, not `turn_locks[...].locked()`, for "is any turn
    # genuinely in flight right now" (docs/decisions/008): incremented
    # the instant `send_message` starts and decremented only once it's
    # fully done, covering the *whole* call including any time spent
    # queued. `Lock.locked()` is a point-in-time snapshot that briefly
    # reads `False` in the gap between one queued call releasing the
    # lock and the next one resuming to re-acquire it — a real, if
    # narrow, window where `/quit` could wrongly take the graceful
    # path and reproduce the exact hang this mechanism exists to
    # prevent (an already-running blocking call can't be cancelled).
    app.pending_turns = 0
    # Tab/Shift+Tab cycle-and-fill state for the `/`-autocomplete
    # overlay (see `composer.py`/`picker.py`); `None` means no
    # cycle session is active (last edit was real typing, not Tab).
    app.tab_matches = None
    app.tab_index = -1
    app.filling_tab_count = 0
    # Which "chatter" (user / persona / system) mounted the last line:
    # `transcript.py`'s `mount_line` only adds a gap above a line when
    # this changes, so consecutive lines from one speaker stay grouped.
    app.last_speaker: str | None = None
