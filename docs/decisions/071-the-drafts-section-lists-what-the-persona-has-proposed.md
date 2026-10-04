# 071 — The Drafts section lists what the persona has proposed, and a new-note draft opens in the editor before any file exists

> **Status: Proposed (2026-10-04).** Not built. The notes-panel half of #21, after ADR 070 (what is stored, and the routes) and ADR 042's amendment (the review in the editor). Web app only; turn-based.

## Context

A persona's proposals are kept per note in her own folder (ADR 070) and drawn as tracked changes when the note is open (ADR 042, amended). Nothing yet tells the user that she has proposed something in a note they have not opened, and a new note she proposes exists nowhere the user can reach it: ADR 070 keeps it only in the store until it is accepted. The routes are built: `GET /api/vault/drafts` lists the notes with a proposal waiting (path, whether it is new, its working name, a count, the time of the latest), and `GET /api/vault/changes?path=` returns one note's proposals.

## Decision

**A Drafts section at the top of the notes panel,** above the notes list and the Pinned list, shown only while there is at least one draft. It is built from the same shared section caption and row components as Pinned and Recent, so corners, spacing and hover match them (measured against Pinned in a real browser before it is called done). It is not a footer section: ADR 042's amendment puts it at the top, because it is a to-do the user should see before the notes.

**Rows.** A draft of a new note is listed under its working name (3 to 5 words, ADR 042) with a "new" mark; a draft of an existing note is listed under the note's title with the count of changes waiting. Newest first, as the route returns them. The row opens the draft; it has no pin, rename or delete of its own (a draft is not a note: declining is how it goes away, in the editor).

**Opening a draft of an existing note** is opening the note: the editor already draws its proposals (slice 3). Nothing else is needed.

**Opening a draft of a new note** shows the proposal's `text` in the editor under its working name, from `GET /api/vault/changes`, with no file behind it. The editor treats the text as the note's text so the user can edit it before deciding. Accept creates the file with the ordinary create (`POST /api/vault/note`, which refuses an existing name rather than overwriting it) and then forgets the proposal (`POST /api/vault/changes/resolve`); Decline only forgets it. If the working name is taken by a note that now exists, Accept stops and says so, and the draft stays. The created note is named by its working name; asking whether to rename it is the persona's, in chat, and comes with her tool (slice 5), not here.

**When the list is read.** When the panel mounts, when the active persona changes, after any Accept or Decline, after a note is saved, and when the window regains focus. There is no polling: the persona proposes during a chat turn, and the chat reports the end of a turn, so the list is read again then too (the terminal is not involved: it does not edit notes).

**Per persona.** The list is the active persona's; switching persona shows hers (ADR 070).

## Consequences

- A proposal is seen without opening the note it is about, and a new note she proposes can be read, edited and accepted without any file existing before the user says so.
- The vault stays untouched until an Accept; the tree, search, the nebula and the map do not know drafts exist.
- Until slice 5 (her tool) proposals exist only when made in code or by tests, so the section is checked with seeded entries.

## Open questions

- How the editor holds a note that has no file: whether the panel's load and save path takes a "draft" source like the persona's own files do (`file` in `MarkdownPanel`), or the create happens as the first save. The first looks smaller; it is settled when the code is read, and this record is amended with the answer.
- Whether a draft that only has outdated changes (every passage rewritten) still belongs in the list. This record lists it, since the user may want to decline it.

## Alternatives rejected

- **A footer section like Recent.** Rejected: the footer is for reference lists the user reaches for; a draft is a to-do and belongs where the eye starts.
- **Creating the file at once as a hidden or marked note, so the editor needs no special case.** Rejected in ADR 042 and ADR 070: a file in the vault is a write, and the vault would show it to every tool.
- **A badge on the note's own row instead of a section.** Rejected: it works for an existing note and cannot show a new one, which has no row.
- **Polling the drafts route.** Rejected: nothing proposes except during a chat turn, which already tells the panel when it ends.
