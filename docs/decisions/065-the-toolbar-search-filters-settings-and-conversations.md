# 065 — The toolbar search filters Settings and the conversations

> **Status: Accepted (2026-10-03), designed with damiro.** Builds on ADR 044 (the engine settings in the web app), ADR 057 (the list of conversations) and the content panel's toolbar (ADR 012).

## Context

The search field in the content panel's toolbar is the same on every page, but only the vault's folder view reads it. On Settings (about forty rows in a dozen sections) and on the Persona page (a persona's conversations) it opens, accepts text and does nothing, which reads as broken.

## Decision

**The field searches what the page holds.** On a vault folder it is unchanged ("Search vault"). On Settings it is "Search settings" and on the Persona page "Search conversations". The query is cleared when the kind of page changes, so a vault query never filters Settings; moving between folders keeps it, as before.

**Settings: a row shows when every word of the query is in its label, its own description (engine settings carry one) or its section's title.** Searching a section's title ("notifications") shows the whole section; searching a row ("autosave") shows that row in its section; a section with no match is hidden; while a query is typed every section with a match is open (what the user folded is not changed or forgotten, and comes back with the query cleared). With no match anywhere the page says so. The match is a plain, case-insensitive "every word is contained", the same on every row because it lives in the two shared pieces every Settings row is built from (`ControlSection`, `ControlRow`); a section drawn without `ControlRow`s (the hidden list, the cloud sharing switches, the toolbar buttons) is found by its title only.

**Conversations: a row shows when every word of the query is in its title.** The pinned group and "All conversations" keep their order and captions, a caption with no row left disappears, and with nothing left the list says so. Searching what was said inside the conversations is not part of this: it needs the backend (ADR 056 already reads past conversations for the persona) and a round trip per keystroke, and is left for if real use asks for it.

## Conversation search: what is built and what is not

**Built (this record).** On the Persona page the field filters the conversation list by title, in the browser, from the list the page already has. The title is the name the user gave the conversation, else the first words of its opening message, else "New conversation" for one with no message yet (which that placeholder matches too). The match is the shared one (every word, case ignored, anywhere in the title), so a conversation is found by a word from its title and not by one said later in it. Pinned conversations stay in their group; a group with no row left loses its caption. Nothing is requested from the backend and nothing about a conversation reaches a model.

**Not built: searching what was said inside the conversations.** It is the natural next step and has a known shape, written down here so it is not redesigned from scratch:
- **Where.** A backend search over the persona's session files (the same `.jsonl` the transcripts live in, ADR 057), exposed like the vault search (a debounced `GET` that returns hits), so the browser still holds no search logic of its own. It is the sibling of the model's own `search_chats` tool (ADR 056), whose reader and keyword matching it can reuse rather than repeat.
- **How it shows.** Hits stay inside the same list: a conversation whose title does not match but whose text does is listed under its title with the matching line beneath it (the way the vault search's content matches show a snippet), and a click opens the conversation.
- **Cost.** Local keyword matching reads files and costs no model call and no cloud data; it is a round trip per pause in typing, not per keystroke. Matching by meaning (embeddings for chats) stays in ADR 056's "Not built".
- **Why not now.** The title filter answers "where was that chat about my taxes"; the inside search answers a different question and should be built when real use asks for it (issue #18 holds that question for the engine's own search across past sessions, and this would share its answer).

## Consequences

- A page's search does nothing only where there is nothing to search (the Bin, which has its own two lists).
- The match is local and instant: no request, no change to what the model or the cloud receives.
- A new Settings row built from `ControlRow` is searchable with no further work; one built another way is found by its section's title until it is.

## Alternatives rejected

- **A separate search field inside Settings and the Persona page.** The toolbar already has the field, and a second one would say that one of them does nothing.
- **Fuzzy or ranked matching.** About forty rows do not need it, and a result list in a different order than the page would lose the page's grouping.
- **Searching conversation bodies now.** See above.
