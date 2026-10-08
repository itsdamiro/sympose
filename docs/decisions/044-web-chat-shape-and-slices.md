---
type: decision
status: accepted
date: 2026-09-30
projects: [sympose]
concepts: [Apps]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 044 — The web chat: its shape, and the order it is built in

> **Status: Accepted (2026-09-30). All three slices are built and pushed (see the amendments: slice 1, the settings, the cloud notice and share control, the model picker, the context meter, the indexing notice, and messages sent mid-reply joined as in the terminal).** It settles how #29 (chat in the web app) is put together and in which slices, before any code, after the full code review of 2026-09-30 found that the web app's shell is the one place in the project where modularity has slipped (#95).

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

## Amendment (2026-09-30): the cloud notice and share control, decided before building

**What ADR 031 asks of the web chat.** A cloud model is announced and the user is asked what may leave, before anything is sent; each cloud turn shows what was sent and what was held back; the categories can be changed later. The engine already does the holding back (`sharing.gate`) and already records `cloud` and `withheld` in each cloud turn's `sent` record, so the web adds only the showing and the asking.

**A route, so the browser holds no rule.** `GET /api/sharing?persona=` answers with the model the persona uses, whether it is cloud (the engine's own `is_local` decides, not a copy in the browser), and every category with its description and whether it is approved. `PUT /api/sharing/{category}` with `{"shared": true|false}` approves or stops approving one through `sharing.set_approved` and answers with the same shape. It changes the one `cloud_share` list the terminal's `/share` uses, so the two channels cannot disagree.

**The notice is a standing banner, not a one-time dialog.** The web has no model picker until slice 3, so a model becomes a cloud one by the persona's file or the `chat_model` setting, and there is no moment of choosing to hang a dialog on. A banner above the conversation, shown whenever the persona's model is a cloud one, says what the ADR's notice says ("it receives your messages and this conversation; from your vault it may receive ...") and carries a switch per category. It is on screen before the first message is written, which is what lets the local-only guard go: nothing is sent to a cloud model that the user has not been shown the terms of. Everything is off until switched on, as in the terminal. A local model shows no banner.

**Each cloud reply says what happened.** A quiet line under the reply, beside "Based on ...": "Sent: notes, recaps · Held back: properties". It reads the `cloud` and `withheld` lists already in the reply's `sent` record, so a resumed conversation shows it too. A local reply, and a cloud reply that involved nothing of the vault, show nothing.

**Not done here.** The history rule (ADR 031, "A consequence to know": a local model's replies that quoted notes travel as history if the model later changes to a cloud one) still needs the user's call and is unchanged. A switch between local and cloud made in the web app arrives with the model picker (slice 3), which will show the notice change then.

**Alternatives rejected.** A modal the first time a cloud model is used: it would need a stored "seen" flag and would hide the state afterwards, when the user is most likely to wonder what is being sent. Putting the switches only in Settings: the ADR requires the user to be told at the point of use.

**Built (slice 2, the cloud notice and share control).** `GET /api/sharing` and `PUT /api/sharing/{category}` (`server_sharing_handlers.py`, over `sharing.approved`/`set_approved`, so the terminal's `/share` and the web read and write one list); `CLOUD_NOT_AVAILABLE` and the local-only guard in `send_turn` are gone. In the browser: `sharing-api`, `useSharing` (read per persona; a state read for another persona is never shown for this one), `CloudNotice` (a standing banner above the message box while the model is a cloud one: what always goes, and a switch per category, all off by default) and `CloudSent` ("Sent: ... · Held back: ..." under a reply, read from the reply's own `sent` record so a resumed conversation shows it too, and shown even when the grounded-notes line is off). Checked in headless Chrome on a scratch cloud persona with no key: the notice shows only for that persona, a switch saves to `cloud_share`, and a message is sent (it fails on the missing credentials, shown as an error line) instead of being refused. Not checked: a real cloud reply, which would send to an outside service. The meter is next.

## Amendment (2026-09-30): the model picker, decided before building

**The choice is saved on the persona, from both channels (damiro, 2026-09-30).** Picking a model in the terminal's `/model` or in the web app's picker writes it as `model:` in that persona's `persona.yaml`, so it is kept across restarts and both channels see it; ADR 010's order is unchanged (an explicit per-call model beats the persona's `model`, which beats the `chat_model` setting, which beats the local default). The web sends no model with a turn: the turn already uses the persona's own model. This replaces the terminal's session-only pick that stuck across persona switches: each persona now has its own model, so a persona switch clears the terminal's in-session pick and the persona's saved model applies. A pick whose save failed still applies for the session and says so.

**Writing the file without disturbing it.** `persona.yaml` is hand-written and carries comments, so it is not re-dumped. `persona_model.set_model` edits only the top-level `model:` line (replacing it, appending it, or removing it for "back to default"), keeps line endings, writes the file whole-or-not-at-all (`atomic_write`), and refuses to write unless the edited text parses to exactly the old data with only `model` changed. A file it cannot read, parse or verify is left untouched and the pick is reported as not saved.

**One list of models.** `ModelOption`, `MODEL_OPTIONS` and `model_option_for` move from `cli/options.py` to `engine/model_options.py`, so both channels read the same list (the same move as the settings registry). `GET /api/models?persona=` answers with the list (each entry marked cloud or local by the engine's own rule), the model the persona uses now, and the model it would fall back to with none of its own. `PUT /api/personas/{handle}/model` sets or, with `null`, clears the persona's own model; the server accepts only an id from that list (else 422), so the browser cannot make the server call a model the product does not offer. A model named by hand in `chat_model` or a persona file still works, as the default, not through the picker.

**The cloud notice follows the model in use.** After a switch the chat re-reads what the persona's model may receive, so the banner and switches describe what will run. Switching to a cloud model shows the banner at once with everything off; every switch adds a system line ("Switched model to ..."), and switching to a local one says nothing from the vault leaves the computer.

**ADR 031's history rule, decided (damiro, 2026-09-30): leave it as it is, but the user is told and accepts.** A conversation is not cut on a switch. Switching from a local model to a cloud one in a web conversation that already has replies asks first, through the confirmation the app already has (`confirm`, so it follows the user's "Delete confirmation" preference, dialog by default): earlier replies in this conversation, which may quote notes, are sent to the cloud model as history whatever is switched on. Switch continues; Cancel keeps the current model. An empty conversation, a switch between two cloud models and a switch to a local model ask nothing. ~~The terminal only says the same in its switch notice; it does not ask.~~ Superseded by the amendment at the end of this ADR: the terminal asks too. The data still travels once the user has accepted, by their own decision.

**Not done.** Whether a model's API key is present is not checked: a missing key is the engine's own error line, as in the terminal. The terminal's background refreshes keep using the in-session pick.

**Alternatives rejected.** A browser cookie sent with each turn: the choice would not survive a change of browser and the terminal could not share it. `chat_model`: it is global and beaten by a persona's own model. Re-dumping the whole YAML: it would drop the user's comments. Cutting or restarting the conversation on a switch: offered and declined; the user prefers to keep the thread and decide knowingly.

**Built (slice 3, the model picker).** `persona_model.set_model` (a targeted edit of the `model:` line; the edited text must parse to the old data plus only that change, else nothing is written; 18 tests, each mutation-checked), `engine/model_options.py` (the list, moved from `cli/options.py`), the terminal's `/model` saving the pick and saying so ("Saved for @handle." or that it applies for this session only), a persona switch clearing the session's pick, and the history sentence in the switch notice (`share.history_notice`). `GET /api/models` and `PUT /api/personas/{handle}/model` (`server_model_handlers.py`; a listed id or `null`, else 422; a file that cannot be saved safely is a 500 and left alone). In the browser: `models-api`, `useModels`, `ModelPicker` (the composer's chip, now a menu), `useModelSwitch` (the confirmation when a conversation with replies goes from local to cloud, the "Switched model to ..." line), `useChat.notice`, and `useSharing` reading again when the model changes; the persona card's model follows the pick. The confirmation is the app's own `confirm`, so a user whose "Delete confirmation" preference is "None" is not asked (their preference, as decided). Checked in headless Chrome on a scratch profile: the chip changes, the banner appears and goes, `persona.yaml` keeps its comment and gains or loses only the `model:` line, a real `gemma2:9b` reply, then a switch to cloud asks, Cancel changes nothing, Switch saves. Two things found on the way: `conftest` now gives every test a profiles folder of its own, since a test that picked a model could otherwise have written the real `profiles/samantha/persona.yaml`; and a reference-note edit ("The pick is kept for that persona.") was compared against the retrieval baseline (identical), after a longer wording cost one embeddings case. Known and left: the terminal tells the user about the history but does not ask; the terminal's model pick still is not offered for a model outside the list.

**Amendment (2026-09-30): the cloud notice can be closed (damiro).** The switches in the notice are liked; the box itself must be closable. Closing is remembered in a cookie (`sympose:chat.cloudNoticeClosed`, like the other interface preferences: it changes only what this page draws). Two rules keep ADR 031's "not silent" intact: the closed state is cleared whenever the model in use is a local one, so the next local-to-cloud switch shows the notice again (the moment ADR 031 says to announce), and a closed notice is never the only way to reach the switches: while the model is a cloud one and the notice is closed, the model picker's menu has "What this model may receive..." which opens it again. Closing does not change what is shared: the categories stay as they were set, and everything is still off until switched on. A switch between two cloud models keeps it closed, as ADR 031 says nothing is announced then.

**The same switches are in Settings (damiro).** A "Cloud models" section in the Settings panel (`CloudSharingSection`) lists every category with what it is and an On/Off switch, plus a Shown/Hidden switch for the notice, whichever model is in use and whether or not the notice is closed. It takes the chat's own sharing state as props, not a second copy, so a switch there and the notice beside it always agree. `cloud_share` stays the one list the terminal's `/share` also uses. Checked live in headless Chrome: close, reopen from the model menu and from Settings, a switch in Settings updating the notice's pressed state and the saved `cloud_share`, a local model resetting the closed state, and a cloud-to-cloud switch leaving it closed. The shell wiring that joins these has no unit test (the shell has none); the live check is what covers it.

**Resolved by [ADR 046](046-a-model-pick-is-a-local-override-not-an-edit-of-the-default.md) (2026-10-01).** A model pick used to be written into the tracked `profiles/samantha/persona.yaml`, which then showed as modified and had to be left out of commits by hand. A pick now goes into an untracked `persona.local.yaml` beside it that overlays the shipped file, and the app never writes the shipped file.

**Amendment (2026-09-30): the message box grows (damiro).** The web chat's message box was a one-row text area that never grew, so a long message scrolled inside a single line. It now grows with what is typed up to about eight lines (192 px) and scrolls inside from there, and returns to one line once the message is sent. It is measured on the box itself (`scrollHeight`), so wrapped text counts and not only line breaks, and it is measured again when the panel opens and when the box's width changes: found in a real browser, the first version measured while the panel was still closed (no width, so even the placeholder wrapped) and showed a 192 px empty box on first load, which jsdom cannot show. The terminal's composer is a single-line `Input` and is not changed: making it grow means replacing it with a multi-line box, which touches the Tab command cycle, `/settings` number entry and the pickers, and Enter-to-send would need another key for a new line. That is a separate design question, not decided here.

**Amendment (2026-09-30): the web chat's busy line matches the terminal's (damiro).** ADR 043's rotation and letter-by-letter typing were built only in the terminal; the web chat's line stayed a fixed "Thinking about your message…" that never changed however long the wait (found when damiro, using the web chat, did not see either). The web chat now shows the same line, built as its own pieces:

- **The persona's own phrases** come from `GET /api/chat/status-phrases?persona=` (`{phrases, own}`): the persona's `status_phrases.md`, or the generic four while it has none. The first read for a persona with none of its own also starts the one-time background generation from its soul (`status_phrases.generate_in_background`, deduplicated per persona), the same lazy trigger the terminal uses at launch; it happens when the chat opens and not when a message is sent, so the model call does not compete with the first reply (the stacking ADR 043 found). As there, it is not gated by cloud sharing (the soul goes with every turn regardless). The browser reads again after a reply while the persona has none of its own, so the phrases appear once they exist.
- **One state machine, the same rules** (`lib/status-line.ts`, a pure function of the phase, the time and the phrases, so it is tested with a scripted clock): the phase's literal text, witty from 3 seconds, the literal text again every other 3-second slot, a witty pick never the one just shown; each phrase typed out one letter at a time at 40 characters a second, whole after that, redrawn only when the text changed. The constants are the terminal's, declared again in TypeScript because the two are separate programs.
- **A web display knob** (`typeStatus`, a cookie, on by default; Settings > Chat) turns the typing off, and a browser that asks for reduced motion (`prefers-reduced-motion`) gets whole phrases whatever the knob says. Rotation stays either way.
- A spinner in front of the text, as in the terminal, replaces the pulse (a pulsing line and typed letters fight each other).

The web chat has no background jobs to show (recap, memory, indexing): those are the terminal's, so only a turn's own phases (searching, reading, thinking) rotate here.

## Amendment (2026-09-30): the context meter, decided before building (damiro)

**A ring, not a bar.** The composer footer has no room for the terminal's ten-cell bar beside the model picker and the New conversation button. The meter is a small ring that fills as the conversation uses its prompt budget, with the percentage beside it (`62%`). It means exactly what ADR 018 says: the share of the prompt budget in use, 100% being where the next message starts leaving older turns out; it leans high (the 15 percent margin). Colour follows ADR 018 (normal below 70%, warning from 70%, error from 90%), and the number is always shown so colour is never the only signal; the ring is a `meter` for screen readers.

**The details are on demand.** A ring drops the raw counts and the explanation the terminal's `/context` prints. Hovering or focusing the meter shows them in a tooltip: `3,812 of 6,144 tokens`, what 100% means, that it leans high, and, for an estimate, that it is one.

**Where the figure comes from.** After each reply, from the turn result, which already carries `context_used` and `context_limit`, together with the model that produced it. A figure belongs to the model that measured it (ADR 018), so it is dropped when the persona's model changes. When there is no figure but the conversation has replies, the browser asks a new route, `GET /api/chat/context?persona=&session_id=`, for an **estimate** for the persona's current model: the engine's own `estimate_context` (no model call; the persona's system prompt plus the kept history, counted with that model's tokenizer, leaning low where a real figure leans high). That covers what the terminal cannot: a refresh that resumes a conversation, and a model switch, show a figure at once instead of an empty meter until the next reply. An estimate is drawn as `~62%` with a dashed ring and says so in the tooltip; the next real reply replaces it. A stale answer (another persona, session or model chosen meanwhile) is dropped. This closes the two leftovers of #27: the web half, and restoring the meter on resume.

**When it is shown.** Only once there is a figure (an empty conversation, or a model whose window is unknown, shows nothing and takes no room). It is not shown while the persona has no session yet.

**A web display knob** (`showMeter`, a cookie, on by default; Settings > Chat) mirrors the terminal's `show_context_meter`.

**Not done.** Counting the message being typed (ADR 018 rejects it).

**Alternatives rejected.** A bar in the footer: no room. The ring alone with no number: the number is what people read, and colour alone fails colour-blind users. Keeping the terminal's rule (empty until the next reply): the web resumes conversations, so it would show nothing exactly when a long conversation is most likely to be near its limit.

**Built (slice 2, the context meter).** `GET /api/chat/context` (`server_chat_handlers.get_context`, over the engine's own `estimate_context`); in the browser `lib/context-meter.ts` (percent, level and the words, the terminal's rules), `fetchContextEstimate`, `useChat`'s `context` (the last reply's count and the model that made it) and `sessionId`, `useContextMeter` (the real figure while it belongs to the model in use, else an estimate, never a stale answer), `ContextMeter` (the ring, a `meter` for screen readers, a tooltip with the full figures) in the composer footer, and a `showMeter` switch in Settings > Chat. Checked in a real browser against the local model: no meter for an empty conversation; a real reply gave 13% (772 of 6,144 tokens) with the tooltip; a refresh showed the resumed conversation as `~12%` with a dashed ring (an estimate, a little below the real figure, as ADR 018 says it leans); switching the model re-estimated for that model's window (`~0%` under a cloud model with a window of about a million tokens, `~12%` back on the local one); the Settings switch hid and showed it. This closes #27's web half and its restore-on-resume item; counting the message being typed stays rejected (ADR 018). Known: percentages round half up in the browser and half to even in the terminal (62.5 reads 63 and 62), which changes nothing that matters.

## Amendment (2026-10-01): the terminal asks before a local-to-cloud switch in a conversation (damiro)

The web chat asks before a model switch sends an ongoing conversation's earlier replies to a cloud model as history (above); the terminal only told the user afterwards. Both now ask, so the same switch is the same decision on either surface.

- **When it asks:** exactly the web's rule: the model in use is local, a conversation with replies is going (the session has started), and the model picked is a cloud one. An empty conversation, a cloud-to-cloud switch and a switch to a local model ask nothing and apply at once.
- **How it asks:** the picker the terminal already uses for a yes/no (the memory review's "Save / Discard" is the precedent). After choosing the model, a line says what would happen (earlier replies, which may quote notes, are sent to the cloud model as history whatever `/share` allows), then a two-row picker: "Switch to <model>" and "Keep the current model". Esc is the same as keeping: nothing changes. The choice is carried by the row itself, so no pending state is stored.
- **What a yes does:** the same as a pick that needed no question: saved for the persona (ADR 046), the meter re-estimated, the cloud notice said, and the `/share` list opened if some categories are not yet approved (ADR 031).
- **The old after-the-fact notice is removed** (`share.history_notice`): it would now repeat what the user has just been asked and accepted. The rule itself is unchanged: a conversation is not cut on a switch, and "Start a new conversation" is how to leave the history out; the question says so.
- **Not affected:** `/persona` switching (it starts a fresh session), and the direct `apply_picker_choice` path used by tests and by any future caller that has already asked.

## Amendment (2026-10-01): a model named by hand is a row in the picker (damiro)

`chat_model` or a persona's `persona.yaml` can name any model litellm resolves, but the picker only listed the fixed set, so such a model ran with no row to show it or to switch back to. `model_options.offered(*in_use)` now returns the fixed list plus one row for each id in use that it does not hold (labelled with its own id, `short` the last path part); the terminal's `/model` and the web's `GET /api/models` use it, for the model in use. The web app needed no change: its button already showed an unlisted current model and its icon already followed `current_cloud`.

- **Cloud or local stays the engine's rule** (`sharing.is_local`), not something the list says, so a hand-named cloud model gets the cloud notice, the `/share` rules and the question before a local-to-cloud switch in a conversation exactly as a listed one.
- **What the route accepts** widened by the same rule and no further: a listed id, the model already in use, or the default (`chat_model`), so a hand-named model can be chosen again and "Use the default" works. Any other unlisted id is still refused with 422, so the browser cannot make the server call a model nobody configured.
- **Not done:** typing a new model name into the picker (it would be a way to reach any model from the browser); a missing API key is still the engine's own error line.


## Amendment (2026-10-01): the indexing notice, while a reply is in flight (damiro)

While the search index is still being built, the engine answers by keyword instead of by meaning (`semantic._vectors_for` returns nothing until the build is done). The terminal shows `indexing NN%` above the composer, but the web chat said nothing, so a first reply could be weaker with no explanation.

- **Only while a reply is in flight** (chosen over also showing it while idle, which would need a slow background poll for a line nobody is waiting on). A second, quieter line sits under the busy line: "Still indexing your notes (40%). Until it is done, searches use keywords." (worded so it holds for a reply that does not search at all) It is gone as soon as the build finishes or the reply arrives.
- **No new route.** `GET /api/chat/status`, which the chat already polls while it waits, also returns `indexing`: the whole percent of the build (`semantic_refresh.progress()`), or `null` when none is running. The figure is the engine's and global, not per persona, as in the terminal.
- It is a plain statement of the engine's behaviour, not a setting: the terminal's line has no knob for it either.

## Amendment (2026-10-01): messages sent mid-reply are joined, as in the terminal (damiro)

The first slice blocked sending while a reply was in flight, waiting for a way to show a queue. ADR 008's amendment of the same day drops the queue for the terminal: a message sent mid-reply shows at once and waits, and what waited goes out as one turn when the reply lands. The web chat does the same, so "Slice 3: queued-message display" is settled by not needing one.

- **The message box never blocks.** A message sent while the persona's reply is in flight appears in the conversation at once, unmarked, and waits in the browser (`use-chat`), per persona.
- **When the reply lands**, what waited is sent as one turn, the messages joined by blank lines, continuing the session the reply returned; one waiting message goes alone. The persona answers them together and the conversation file holds them as one user turn, as in the terminal. A reply that failed shows its error line and the waiting messages are still sent.
- **Nothing in the engine or the API changes**; no route reports a queue. Waiting messages live only in the open tab: closing it before the reply lands drops them, as an unsent draft would (they were never sent).
- "New conversation" is still unavailable while a reply is in flight. (Amended 2026-10-02 by ADR 057: the state is now one per conversation, so it is available, and a reply lands in the conversation it was sent from.)

## Amendment (2026-10-03): a persona whose phrases cannot be made is left alone for ten minutes

The web chat reads a persona's busy-line phrases again after every reply while it has only the generic ones, and each read starts a background generation. A model that errors, or answers with nothing usable (a reasoning model that spends its whole reply limit thinking), therefore cost one wasted model call per reply, billed on a cloud model and competing with the next reply on a local one. A failed generation now records the time and `generate_in_background` declines for `RETRY_AFTER_SECONDS` (600) afterwards; the record is kept in the running process only, so a restart tries again. Found in the pre-#21 review; covered by `tests/test_engine_status_phrases.py`. Rejected: a settings-store knob for the wait (nothing a user would tune: the phrases are cosmetic); writing the generic phrases to the persona's file on failure (it would make them the persona's own for good, and `own` is what stops the retries).

## Amendment (2026-10-03): the controls under the message box, and the stage's top-right toolbar

damiro asked to take the plus (an attachment placeholder that was always disabled) out of the row under the message box, put a new-conversation icon there instead, with the pin toggle beside it once a conversation has started, and the Condense button too, shown only when condensing is really advisable instead of all the time; and to drop the stage's top-right toolbar down to the nebula toggle, keeping the toolbar's style for other uses, with a chat toggle that has an appropriate icon.

**The row.** At the left, one group ("Conversation controls"): a new-conversation icon (disabled until there is a conversation to leave; enabled while a reply is in flight, as before), a pin toggle (`aria-pressed`, "Pin conversation" / "Unpin conversation", shown once the conversation has a turn and has been saved, since pinning is a mark on a saved conversation, ADR 057), and Condense. At the right, the context meter and the model chip. The buttons take the toolbar button look in one shared class (`toolbarButtonClass`, 28 px, muted, tinted on hover and when pressed), the same one the panels' collapse buttons use.

**When Condense is advisable** (`condenseAdvised`, `lib/context-meter.ts`): the context meter has reached its warning level (70%, its amber) **and** there is something to fold: more answered turns than the newest `KEEP_TURNS` (3, the engine's own, `engine/compaction.py`) plus those the notes already stand for; older turns not loaded yet count as plenty. Otherwise the button is not drawn at all; while notes are being written it stays and says "Condensing…" even if the meter drops. The meter's own amber is the signal, so there is no second number to keep in step; the automatic condensing starts later (`compact_at`, 80% by default), so this is the earlier moment, for a user who turned that off or would rather choose. Rejected: a setting for the threshold (the meter's levels are already the app's); showing it disabled when not advisable (damiro asked for it not to be displayed all the time).

**The toolbar.** `ChatActionGroup` keeps its look (a `bg-secondary` pill of `size-7` icon buttons) and its place beside `NebulaModeToggle`, now holding the chat toggle only: its disabled "Bookmark" placeholder is gone (the pin is in the row), and its icon is a plain chat bubble, because the bubble with a plus is the new-conversation icon. The phone header's identical Chat button takes the same icon. Without this toggle the desktop chat panel could not be shown or hidden at all.

