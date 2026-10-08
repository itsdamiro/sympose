---
concepts: [Conversation history]
---

# 057 — Past conversations: a list to open, rename, pin and delete, and switching conversations while a reply is being written

> **Status: Accepted, built** (engine, API, terminal and web app). Amends ADR 044 ("New conversation is still unavailable while a reply is in flight"), builds on ADR 006 and 049 (the session file, append-only), ADR 008 (messages sent mid-reply wait) and ADR 042 (soft delete only).

## Context

A conversation is its own file (`profiles/<handle>/sessions/<id>.jsonl`) with an id and a title (its first message), and any of them can already be loaded by id (`GET /api/chat/session?session_id=`). A reply is saved into the id the message was sent with. What is missing is every way for the user to use that:

- The web chat holds one conversation per persona and shows only the latest. There is no list, no way to go back to an older conversation, and "New conversation" is hidden while a reply is being written, because that one conversation's state (turns, session id, waiting messages, "sending") would be replaced under a reply that is still coming.
- The terminal's `/history` was a mock and was removed; nothing replaces it.
- A conversation cannot be renamed or deleted from the app.

The model is a chat tool with threads: the user moves between conversations and may leave one while its reply is still being written.

## Decision

**A list of the persona's conversations**, pinned ones first and then newest first, each with its title, how many turns it has and when it was last used; a conversation that is replying says so. A started but empty conversation is listed only if it is the newest (it is the "new conversation" the user opened on purpose, ADR 044).

- **Web:** on the persona's profile, beside the persona card. Choosing one opens it in the chat, where the user continues it. A new conversation can be started from the chat at any time.
- **Terminal:** `/sessions`, with `/history` as the same command. It lists the conversations by number; `/sessions open <n>`, `/sessions rename <n> <title>`, `/sessions pin <n>` (`unpin` undoes it) and `/sessions delete <n>` act on them. Opening one starts a new conversation generation that continues the chosen session, the same way a persona switch does (`app.session_by_generation`), so a reply still being written lands in the conversation it was sent from.

**Rename** appends a new meta line with the title (ADR 049: a later meta line wins on load). Nothing is rewritten. A renamed title is kept; only a conversation with no title is named by its first message.

**Pin** keeps a conversation at the top of the list, as pinned notes stay at the top of the tree. Unlike a note's pin (a browser cookie, ADR 051), a conversation's pin is written to the conversation itself: a later meta line in the session file carries `pinned` (a time, or none to unpin), the same append-only way a rename is kept (ADR 049). That is a deliberate difference. A conversation is the persona's own data, listed by the terminal and the web app alike, so its pin has to be seen by both; it follows the file when the conversation is deleted and brought back; it needs no remapping when the title changes (the id does not); and it has no cookie size limit. Pinned conversations are listed in the order they were pinned.

**Delete is soft** (ADR 042's rule, and the bin's in ADR 045: nothing the user wrote is destroyed by a click). The session file and its recap move to `profiles/<handle>/sessions/.trash/`, so the persona stops knowing the conversation (a recap of it no longer reaches her prompt) and the user can get it back from the Bin (below). A conversation with a reply being written cannot be deleted (409); it can be stopped first.

**Deleted conversations are in the Bin, apart from the notes** (amended 2026-10-02). A user looks for a deleted thing in one place, so the Bin holds conversations too. They are not mixed into the list of notes and files: the Bin has two sections, Notes and Conversations, and the Conversations one lists the active persona's deleted conversations, newest deletion first, each with its title, how many turns it had and when it was deleted. Each can be restored (the file and its recap go back, and it is in the persona's list again, pinned as it was) or deleted for good, and the section has Empty. Deleting for good is the one irreversible step, so it always asks. A conversation is restored under its own id; when one by that id already exists the restore is refused (409) rather than replacing it. The terminal has the same: `/sessions bin` lists them, `/sessions restore <n>` and `/sessions purge <n>` act on one by its number in that list. The trash folder holds what a delete moved; the deletion time is the file's modification time, set when it is deleted (nothing else reads the modification time of a session file).

**Switching while she is replying.** The reply always finishes into the conversation it was sent from, and is saved there. What changes is the browser's state:

- The conversation state moves from one per persona to one per conversation: its turns, draft, waiting messages and "replying" flag. Leaving a conversation does not stop or lose its reply.
- **Whether replies in different conversations run at the same time is a setting, `parallel_replies`** (`auto`, `on`, `off`; default `auto`). It is not a limit of the app but of the machine, and the user is told so where the setting is. A cloud model's replies run on the provider's servers, so two conversations cost nothing in speed: `auto` runs them side by side. A local model's replies share one machine's graphics chip and memory (ADR 015's window is per request, so each running reply also holds its own): two at once are each slower, and Ollama must be set to serve requests side by side (`OLLAMA_NUM_PARALLEL`), so `auto` runs them one after the other. `on` runs them side by side whatever the model (the user's machine, the user's call) and `off` always one at a time. The setting's summary says this in the settings screens.
- Two messages in the same conversation always run in order (that lock stays, now per conversation), and waiting messages of one conversation still join into one turn (ADR 008). When replies cannot run side by side, a message sent in another conversation while a reply is being written waits, is shown in its own conversation as waiting, and goes when the persona is free, in the order the messages were sent.
- The status line and the Stop button belong to a conversation, not a persona: each shows on the conversation that owns the reply in flight, and Stop stops that one. The context meter reads the conversation on screen.
- A conversation whose reply finished while the user was elsewhere is marked as having a new reply until it is opened.

**Effects on the rest.** Continuing an old conversation grows its turn count, so its recap is rewritten the next time recaps run (ADR 023's header does exactly this). Its compaction notes (ADR 055) carry on from where they were. The conversation on screen is not recapped into the prompt (it is already there). Nothing here sends anything new to a cloud model.

**What this changes in the engine, and how much of it is already done.** Three per-persona records have to become per-conversation: the live phase (`turn_status`), the stop request (`turn_cancel`) and the lock that orders messages (`server_chat_handlers._LOCKS`).

- *Built as groundwork, behaviour unchanged.* `turn_status` and `turn_cancel` are keyed by persona and conversation. A turn binds its conversation (`run_turn` does it, and every phase it sets, including from the lookup loop, is its conversation's own). A caller that names only the persona sees what it saw before: the persona's oldest reply in flight for the phase, and a stop for the persona stops every reply it is writing; with a conversation id it is that conversation's. The web routes and the terminal still call them by persona, so nothing a user sees changes. Tests show two conversations of one persona keep their own phase, a stop for one leaves the other running, and a reply past its commit refuses a stop while the other accepts one.
- *Checked, nothing to do.* A turn always has a conversation id from its start (`run_turn` names it before the first model call, not at the first save), so the terminal's first reply needs no temporary key. The persona's memory files are written under one lock shared by every persona (`memory.py`, `memory_write.py`), so two replies at once cannot write them at the same time.
- *Not built.* The message lock is still one per persona, and the routes (`/api/chat/cancel`, `/api/chat/status`) do not yet take a conversation id. Those two, the `parallel_replies` setting and the per-conversation browser state are what remain.

**New API, all local, no model call:** `GET /api/chat/sessions?persona=`, `PATCH /api/chat/session/<id>` (the title, and whether it is pinned), `DELETE /api/chat/session/<id>`, and for the Bin `GET /api/chat/sessions/bin?persona=`, `POST /api/chat/sessions/bin/restore`, `DELETE /api/chat/sessions/bin?persona=&id=` and `POST /api/chat/sessions/bin/empty`.

## As built (2026-10-02, first slice: engine, API and terminal)

- `engine/session_manage.py`: `list_sessions` (pinned first in the order pinned, then the one last used first; a blank conversation only when it is the newest; each row says whether a reply is being written into it), `rename` (a later meta line, title of 1 to 80 characters on one line), `pin` (a later meta line with `pinned_at`; pinning one already pinned, or unpinning one that is not, writes nothing), `delete` (the file and its recap to `sessions/.trash/`, an earlier file of the same name there is never replaced, `busy` while a reply is being written). `session_ids` already ignores the trash folder (it lists `*.jsonl` of the directory only). `turn_cancel.running` is the public question "is a reply in flight".
- Web API: `GET /api/chat/sessions?persona=`, `PATCH /api/chat/session/<id>` (title and/or pinned, the row comes back), `DELETE /api/chat/session/<id>?persona=` (404, 422 for a bad title, 409 while a reply is being written). The routes live in `server_session_handlers.py`.
- Terminal: `/sessions` and `/history` (`cli/sessions_command.py`): the numbered list, `open <n>` (a new generation that continues the chosen conversation, the last four turns shown again, the meter re-estimated), `rename <n> <title>`, `pin <n>`, `unpin <n>`, `delete <n>` (deleting the conversation on screen starts a new generation). A reply still being written in the conversation left lands in its own, as after a persona switch.
- Not yet: the web app's list on the persona's profile and the browser's state per conversation (so "New conversation" works while a reply is being written), the routes taking a conversation id for the status and Stop, and the `parallel_replies` setting. The restore of a deleted conversation is by hand, as designed.

## As built (2026-10-02, second slice: the web app, the Bin and `parallel_replies`)

- **Per-conversation state in the browser** (`ui/src/lib/use-chat.ts`). The state is one record per conversation, keyed in the browser by a number of its own, not by the session id, which a new conversation has only once the backend has been told. A reply that lands goes to the record it was sent from, whichever conversation is on screen, and marks it unread when the user is elsewhere. Opening a conversation the browser already holds shows that record (its draft, its waiting messages, its reply in flight); one it does not hold is read from its saved turns. "New conversation" is offered while a reply is being written; on a conversation that is blank already it does nothing, and when the backend answers with the blank conversation the browser already holds, that one is shown rather than a second record for one id. Deleting the conversation on screen puts a fresh one in its place.
- **The list on the persona's profile** (`conversation-list.tsx`, `use-session-list.ts`), under the model row. Pinned first, then the last used. Each row shows its turns and age, `replying…` while a reply is written into it (the browser's own knowledge and the backend's `replying`), a dot for a reply nobody has read, a pin mark. Pin, Rename (a field in the row, Enter saves, Escape leaves) and Delete are on the row's `⋯` and on a right-click, one list for both. Delete asks as any delete does and moves the conversation to the Bin; one with a reply being written cannot be deleted.
- **The Bin keeps the two apart** (`bin-view.tsx`, `conversation-bin.tsx`): a switch, Notes and Conversations. Conversations lists the active persona's deleted ones, newest deletion first, with Restore, Delete forever (always asks) and Empty (always asks). The engine side is `engine/session_bin.py`: a deletion sets the file's time to the moment of deletion; a name in the Bin is the file name without its extension (`<id>`, or `<id>.2` when the id was deleted twice), and nothing that is not a plain file name is accepted. Restoring puts the file and its recap back under the conversation's own id and refuses (409) when one by that id exists. Routes: `GET /api/chat/sessions/bin`, `POST .../restore`, `DELETE ...?id=`, `POST .../empty`. The terminal has `/sessions bin`, `restore <n>`, `purge <n>`.
- **Status and Stop by conversation.** `GET /api/chat/status` and `POST /api/chat/cancel` take an optional `session_id`; without it they act on the persona as before. The status line says `queued` while a message waits for another conversation's reply.
- **The locks** (`server_chat_locks.py`). One lock per conversation when replies may run side by side, otherwise one per persona; two messages in one conversation always run in order. A message waiting for its lock is registered, so Stop (and a persona-wide stop) cancels it and it is never run.
- **`parallel_replies`** (`engine/parallel.py`, group "Conversations" in both settings screens): `auto` (side by side on a cloud model, one after the other on a local one), `on`, `off`; an unusable value is `auto`. The reference notes say why, in plain words.
- **Measured.** In a real browser against a scratch install with `gemma2:9b`: a reply was in flight, the user opened a new conversation (blank at once, no Stop button, the first row showing `replying…`), the reply landed in the first conversation with a dot, opening it cleared the dot; a message sent in a second conversation while the first replied showed `queued`, and Stop returned its text to the message box while the first reply carried on and landed; a conversation was deleted from the list, found under Conversations in the Bin, and restored into the list.
- **Not done.** `parallel_replies` is read only by the web app: the terminal runs a reply per conversation generation as before. A conversation the browser holds is not read again from the backend when another window continues it.

## Amendment (2026-10-03, found in the pre-#21 review): stopping a first message

A first message in the web chat has no conversation id until its reply lands (the engine makes one up), so its Stop sent no `session_id`, and a stop with none ends every reply the persona is writing, including the other conversations' when `parallel_replies` is on. The stop request now carries `unnamed` when the web has no id: it ends only the replies (and waiting messages) that began without one, which the registry marks (`turn_cancel.begin(..., named=False)`). Persona-wide stop for a caller that wants it is unchanged. Rejected: opening the conversation before the first message, as "New conversation" does (the route reuses the latest blank conversation, which another open conversation in the browser may already hold, and it would put a second path into the logic that reconciles the blank conversation the backend answers with); a client-made id (it would copy the engine's id format).

Two more from the same review. The Bin of a persona no longer shows the rows of the persona before it while its own load or fail to load (its Restore and "Empty" would have acted on the new persona with the old rows and count). And the list of conversations keeps only the answer to the newest read, so a slower answer for the persona before cannot arrive last and leave the new persona's list stuck on "loading".

## Not built

- A model-written title (the first message stays the default title).
- Searching across conversations (ADR 056) and archiving one to a note (#20); both would fit on this list.
- The list in the terminal showing which conversation has a reply in flight beyond a marker.

## Alternatives rejected

- **Hard delete.** A click that destroys a conversation, its recap and its notes is the kind of thing the project has always avoided (ADR 042, 045).
- **Rewriting the title line in place.** The file is append-only (ADR 049); a later meta line is the existing way to change a field.
- **One reply at a time always.** Simple, but it makes a cloud model wait for nothing: the limit is the machine's for a local model, not the provider's.
- **Parallel always.** On a local model two replies at once are each slower and Ollama may not serve them side by side; the user should not find that out by waiting.
- **Only the terminal first.** The question came from the web chat, where "New conversation" is blocked; the terminal list is small and comes with it.
