# 044 — The web chat: its shape, and the order it is built in

> **Status: Accepted (2026-09-30). Slice 1 built and pushed (see the amendment at the end); slices 2 and 3 are not.** It settles how #29 (chat in the web app) is put together and in which slices, before any code, after the full code review of 2026-09-30 found that the web app's shell is the one place in the project where modularity has slipped (#95).

## Context

The chat panel in the web app is presentational only: a panel, a composer and a mock transcript (its canned persona replies were removed in the review, #94, so it now starts empty). The backend has no chat route; only the terminal calls the engine (`run_turn`). ADR 006 and `docs/VISION.md` already settle the important part: every channel is a thin adapter over one engine, so the web chat calls the same `run_turn` the terminal does and adds no second copy of engine logic. The engine already saves sessions, so the browser does not need to own them. It does not queue: ADR 008 puts queueing at each channel's call site, so the web route keeps its own lock per persona (built with the chat route; it cannot order a terminal chat and a web chat against each other, which are separate processes).

What is not settled is the shape of the adapter and the order to build it in. Two facts from the code shape the answer:

- `ui/src/routes/app-shell.tsx` is 1,737 lines and owns vault fetching, search, note CRUD, history, panel policy and the chat state. Most of the project is modular (short backend modules; a Settings screen made of separate sections). The shell is the exception, and putting chat state into it would make it worse.
- The backend has no settings route at all. The list of settings lives in `cli/settings_registry.py`, reachable only from the terminal, and the web app's Settings only holds web-only preferences (editor, notifications, hidden from view, nebula appearance).

## Decision

**Modular by default.** Every piece that can stand alone is its own file, tested on its own, and the shell only wires them together. It is not refactored beyond that: chat is taken out of the picture, the rest of the shell is left as it is.

- the chat API client (talks to the backend)
- the chat state (the conversation, the live status, the draft, whether a reply is in flight), as its own hook
- session resume
- the panel
- a transcript item for system lines (below)
- the grounded-notes view
- the context meter
- one Settings section per group of settings

The panel is loaded lazily, as the nebula already is. That helps only how fast the page first opens; it is a bonus, not the reason for the split.

**Live status while a reply is being made.** The terminal shows what is actually happening while it waits (searching, reading, asking; ADR 043), because a silent wait feels broken. The web chat shows the same. The engine already records the phase (`turn_status`), so a small status route reports it and the browser asks for it about every half second while a reply is in flight. This is chosen over a persistent live connection because it looks the same to the user and is much simpler and sturdier for a single-user local server; it can be replaced later without changing what the user sees. The reply itself arrives whole; any typed-out effect is drawn in the browser from the finished reply (the terminal already does the same with `reply_reveal`, ADR 032), so the engine is unchanged.

**A conversation resumes after a refresh, in sections.** A route returns the latest session for a persona, one section at a time: the last turns first, and older ones on request ("the turns before this one"), with what reached each reply (ADR 025). The panel loads the latest section on open and fetches older turns as the user scrolls up, keeping their place so the view does not jump. Paging is part of the route from the start, since retrofitting it later would change the route and every caller. It only affects what is drawn: what the model sees is still bounded by the engine's own history window (`history_as_messages`). A "new conversation" control starts a fresh session. The latest session is whichever channel wrote it, so a conversation begun in the terminal can be continued in the browser and the reverse; sessions are already one flat file per persona regardless of channel.

**System lines in the transcript, as in the terminal.** The terminal shows four kinds of system line between the turns: confirmations ("Now talking to @x", "Switched model to ..."), errors ("@x couldn't reply: ...", "the reply was not saved"), notices (the trim notice, the cloud announcement, a staged memory change) and command output (`/grounded`, `/context`, help). The web chat has no equivalent: its transcript knows only user and persona turns, and toasts are transient. A new transcript item, `ChatSystemLine`, carries those four kinds, in its own file, and reply errors are shown through it from the first slice. Toasts stay for transient feedback outside the chat.

**Settings live in the existing Settings screen.** The engine settings become new sections in the content panel's Settings, in the same style as the nebula, editor and notification sections, grouped as the terminal's `/settings` groups them (what is shown, context and reply limits, search, note lookup, memory, cloud sharing). To make one list serve both channels, the registry moves out of `cli/` into a shared module and gets a small backend route; the terminal and the web read the same list and each module still decides what is valid (ADR 036's rule, unchanged). This also covers the web half of #79.

**The first slice chats with local models only.** The web chat does not send to a cloud model until the web app can show what would leave the machine and let the user control it (ADR 031). Until then, if the model in use is a cloud one, the chat says so in a system line and does not send. Nothing is silently sent: the engine already withholds every category not in `cloud_share`, so the gap is being told, not being protected, and the notice and controls arrive with the settings sections (slice 2). Local models are the default, so the first slice is usable as it stands.

## The slices, by difficulty and dependency

**Slice 1: foundation, local models (no dependency on the settings work).**

| Piece | Difficulty | Depends on |
|---|---|---|
| Chat state in its own file; the panel loaded lazily | Easy to medium | nothing |
| The chat route (a thin door to `run_turn`, with a lock per persona and the local-only guard) | Medium | nothing |
| The status route and its polling | Medium to hard: the server has nothing like it yet | the chat route |
| `ChatSystemLine`, reply errors shown through it | Easy | nothing |
| Wiring the panel: send, reply, live status, no double send while a reply is in flight, auto-scroll, Markdown and wikilinks in replies | Medium | the two routes, the state, the system line |
| Session resume and "new conversation" | Medium | the chat route |
| Loading older turns as the user scrolls up, keeping their place | Medium: keeping the scroll position steady is the fiddly part | resume |
| Grounded-notes view | Easy to medium | resume (the data comes from the recorded turn) |
| The local-only guard | Easy | the state |

**Slice 2: settings, then cloud models.**

| Piece | Difficulty | Depends on |
|---|---|---|
| The settings registry moved to a shared module, plus its route | Medium | nothing |
| Settings sections in the content panel, one per group | Medium to hard | the registry route |
| The cloud notice and share control in the chat (a banner while a cloud model is in use; after each reply, what went and what was withheld, both already reported by the engine) | Medium | the settings sections |
| The context meter | Medium | the chat route |
| Lifting the local-only guard | Easy | the cloud notice |

**Slice 3: the rest of #29.** The indexing notice, queued-message display (needs an API that reports the queue), the model picker.

The parts that need the most attention are the live status (new kind of route for this server) and the settings and share group (a small project of its own, because the registry moves).

## Not decided here

- Whether the first slice should also block sending while a reply is in flight, or accept a second message and let the engine's per-persona queue hold it. The first slice blocks, since the queue cannot be shown yet (slice 3).
- Whether polling is later replaced by a persistent connection. It is an implementation change with no visible difference, so it waits for evidence it is needed.

## Alternatives rejected

- **Put the chat state in the shell and split the shell afterwards.** Cheaper today, but the shell is already the largest file in the app and every later piece (meter, share control, queue) would land in it too.
- **A broad clean-up of the whole shell first.** Not needed to build chat, and a large risky job of its own; the goal is that chat is not added to the tangle, not that the tangle is undone.
- **A persistent live connection for the status.** More machinery for the same result on a local, single-user server.
- **Cloud models in the first slice with only a notice.** Possible, since the engine already reports what was sent and withheld, but the controls are part of the same settings work and the first slice is useful without them.

## Amendment (2026-09-30): slice 1 as built, and three decisions made while building it

**Built (slice 1, local models only).** `POST /api/chat/turn` (a lock per persona, a non-local model refused with 409 and a plain message), `GET /api/chat/status` (the live phase), `GET /api/chat/session` (the latest conversation in sections, `before`/`limit`, pinned to a `session_id` so older pages stay in the conversation the first page came from) and `POST /api/chat/session` (a fresh, empty conversation); in the browser `useChat` (one conversation per persona, resume, older turns on scroll, New conversation), `chat-api`, `ChatSystemLine`, the panel loaded lazily as its own chunk, `GroundedNotes`, `ChatMarkdown`. Checked in a real headless Chrome on a scratch vault and against `gemma2:9b`.

**A note is only ever a link in the chat.** The chat never shows a note's content. A note appears as a link: a `[[wikilink]]` in a reply, or a path under the reply's "Based on ..." line. Clicking it opens the note in the markdown editor in preview (read) mode, through a `previewRequest` the shell bumps; it is set at once rather than through the animated read/edit swap, which only completes when the toolbar row it animates is on screen. The mode is the existing read/edit preference, so it stays until the user switches back. A note hidden from view (ADR 037) or since deleted is not opened. Links from the built-in reference library are never offered.

**Replies are formatted.** A persona's reply is drawn as Markdown through stylo's read-only preview, styled as text in the conversation (no card, list markers restored, headings at reply scale): bold, lists, code and tables come out; raw HTML from a model shows as harmless text and a `javascript:` link is dead. Web links open only for http, https and mailto (`openMarkdownLink`, shared with the editor, which also no longer opens a relative link as a broken tab of this app).

**New conversation is saved, not only cleared.** It opens an empty session (a file with only its meta line, named by its first message) that counts as the latest, so a refresh shows it blank; pressing the button twice reuses the blank one. Recaps ignore blank sessions when picking the last conversation. The plain alternative (blank in the browser only) brought the old conversation back after a refresh, which was wrong.

**Known and deliberate.** The web ignores the terminal's `show_grounding` setting (always on) until slice 2 gives it a way to read settings. A message sent while a reply is in flight is not accepted (no queue display yet, slice 3). The terminal and the web chat write the same session files but cannot lock against each other (separate processes).


## Amendment (2026-09-30): slice 2's settings, decided before building

**Two kinds of setting, and each has one owner.** A setting that changes what the engine sends or does (context and reply limits, the follow-up search, recaps, how notes are found and how close they must be, who looks in the notes, memory) is an *engine setting*: one list, one module that decides what is valid, read by both channels. A setting that only changes how one channel draws things is a *display knob* and belongs to that channel. The terminal's five (`show_grounding`, `show_trim_notice`, `show_meter`, `show_background_status`, `reveal_speed`) stay in `cli/`, where the display modules they name already live. The registry could not simply move out of `cli/` because it imported those five modules; splitting the list is what lets it move without the engine importing terminal code.

**What moves.** `Setting`, the engine rows, `find`, and the rules for applying a value (flip a toggle or a choice, parse and save a number, refuse what the owning module does not accept) move to `sympose/engine/settings_registry.py` and `settings_apply.py`. The terminal's `/settings` lists its display rows followed by the shared ones, in the same order as before, and calls the shared apply functions; its behaviour and messages do not change. A new `GET /api/settings` returns the engine rows grouped (key, kind, summary, current value, default, choices, hint) and `PUT /api/settings/{key}` sets one (a `null` value restores the default), answered with the value now in force and an error text when the owning module refused it. The browser never holds a rule of its own: it draws what the route describes.

**Sections.** The Settings panel gets one section per group: Context, Search, Note lookup, Memory (the same grouping the terminal uses). Each row is a switch, a stepper or a number field according to `kind`. `chat_model` and `cloud_share` are engine settings too but have their own controls: `cloud_share` comes with the chat's notice (next), the model picker is slice 3.

**Web display knobs.** The web chat's own knobs are cookie-backed UI preferences (like the editor and nebula ones), not backend settings, since they change nothing the engine does. The first is the grounded-notes line, which now respects a switch (default on) in place of the always-on behaviour slice 1 noted. The rest (reveal speed, trim notice, meter, busy indicator) are added with the pieces they control.

**Order.** Registry move and route, then the sections, then the cloud notice and share control (which lifts the local-only guard), then the meter. Each is its own commit.

**Alternatives rejected.** Keeping one registry with the display rows and letting the web ignore what it cannot use: the engine would keep importing terminal code and a web screen would carry rows that do nothing. Storing the web display knobs in `settings.json` through the route: it would put a browser's drawing preference in the file the terminal also reads.

**Built (slice 2, settings; the cloud notice and the meter are next).** `engine/settings_registry.py` (`Setting`, the twelve engine rows with a `group`, `find`) and `engine/settings_apply.py` (`value_text`, `set_value`, `flip`, `set_number`) hold the rules for both channels; `cli/display_settings.py` keeps the terminal's five display rows and `cli/settings_registry.py` joins them to the shared ones, so `/settings` lists what it did before. `GET /api/settings` and `PUT /api/settings/{key}` (`server_settings_handlers.py`; a refusal is a 422 with the module's own reason, and the value is left as it was). In the browser: `settings-api`, `use-engine-settings`, `EngineSettingsSections` (Context, Search, Note lookup, Memory: a switch, segments, a menu for a choice of more than three values, or a number field saved on Enter or leaving the field, with Reset), and `ChatDisplaySection` with `use-chat-display-preferences`, whose first knob, the "Based on ..." line, is on by default and is a cookie, not a backend setting. This replaces slice 1's "always on". A decision made while building: the route does not check a number's type, because the shared parser already refuses anything that is not a number (a mutation check showed the route's own check was redundant).
