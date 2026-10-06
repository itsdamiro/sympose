# 071 — The Drafts section lists what the persona has proposed, and a new-note draft opens in the editor before any file exists

> **Status: Accepted, built (2026-10-04).** The notes-panel half of #21, after ADR 070 (what is stored, and the routes) and ADR 042's amendment (the review in the editor). Web app only; turn-based.

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

## What was built, and how the open questions were settled

- **The editor holds a note with no file through the editor's `file` seam,** the one a persona's own file uses (`useDraftEditor`, `DraftBanner`): the text comes from the proposal, and the editor's key for it is `draft:<handle>/<path>`, never a vault path. The first alternative, making the first save create the file, was rejected: autosave and the flush on leaving a note both save without being asked, so an edit would have made the note without the user accepting it.
- **Saving a draft only keeps the edit, for the session (replaced 2026-10-05, see the amendment).** The button, `⌘/Ctrl-S`, autosave and leaving the draft store the text in the hook; reopening the draft shows it; Decline and Accept forget it. Known limit: the editor's "Saved" notice appears on `⌘/Ctrl-S` in a draft though nothing is written to the vault, and the edit is lost on a reload of the page.
- **Accept** flushes the editor, then creates the note (the ordinary create, which refuses a name in use and leaves the draft), writes the text over the stub the create makes, forgets the proposal and opens the note. If the write fails after the create, the empty note stays and the draft is kept, with the reason shown. **Decline** flushes (so an unsaved edit is not sent to a path that is not a note), forgets the proposal and creates nothing.
- **A draft with only outdated changes is listed,** so it can be declined.
- **The list is read** on mount, on a persona change, when the vault is refreshed, when the window is focused and when a change is resolved or a draft accepted or declined (`announceDraftsChanged`). The end of a chat turn is not wired yet: until the persona's tool exists (slice 5) nothing proposes during a turn; slice 5 adds it.
- **A draft row has no menu and no reserved room for one:** the shared note row now keeps the room on the right for a `⋯` button only when it has one, so the end label (the count or "new") does not move when the row is focused.

## Amendment (2026-10-05): the section also lists notes with an open comment

**Decided with the user.** The Drafts section is also where a note shows that it has an open comment, so everything that needs a look is in one place, above the notes and Pinned. This replaces the earlier rule that "a note that only has comments is not a draft". Merged into the one group (not a second group) at the user's choice; the alternative of a separate group was weighed and set aside.

- **Which notes.** Any note that holds a proposal waiting or an open comment (a comment of the user's or of hers, until it is resolved; the answers under a comment belong to it and are not counted). A resolved comment does not list a note. Per persona, like the proposals.
- **Rows.** The row keeps the shared note row. It ends with what is waiting: for a new note "new" (as before); otherwise the number of changes waiting when there are any, and the number of open comments with a small comment icon when there are any (a note with changes only shows what it showed before). A note with comments and no changes opens like any note; its comments are in the editor (ADR 069).
- **Caption.** "Drafts" while only proposals are listed, "Comments" while only comments are, "Drafts & comments" when both kinds are. It is shown only while at least one row is listed.
- **Route.** `GET /api/vault/drafts` returns `comments` (the open count) beside `count` (the changes waiting) for each entry; a note with only comments has `count: 0`. `time` is the latest of the note's proposals and open comments, so the list stays newest first. The list is read at the same moments as before, and also after a comment is added, changed, resolved or deleted (the editor announces it, as it does for a resolved change).

## Amendment (2026-10-05): saving a draft keeps the edit in her folder

The first build kept a draft's edits only in the page for the session, and said "Saved" on `⌘/Ctrl-S` though nothing was kept anywhere durable: a reload lost them. Now **saving a draft (the button, `⌘/Ctrl-S`, autosave, leaving the draft) writes the edited text into the draft's proposal in her folder** (ADR 070's store, never the vault), so "Saved" is true and the edit survives a reload and a restart. A new route, `PATCH /api/vault/changes/draft` (`path`, `persona`, `text`), replaces the text of the note's new-note proposal and answers 404 when the note has none; the working name is left as it is (the user renames the note when it is accepted). The editor's save reports a failed write as an error instead of "Saved". Accept and Decline are unchanged: the first still creates the file, the second forgets the proposal. The vault is still touched only by Accept.

## Alternatives rejected

- **A footer section like Recent.** Rejected: the footer is for reference lists the user reaches for; a draft is a to-do and belongs where the eye starts.
- **Creating the file at once as a hidden or marked note, so the editor needs no special case.** Rejected in ADR 042 and ADR 070: a file in the vault is a write, and the vault would show it to every tool.
- **A badge on the note's own row instead of a section.** Rejected: it works for an existing note and cannot show a new one, which has no row.
- **Polling the drafts route.** Rejected: nothing proposes except during a chat turn, which already tells the panel when it ends.
- **A second group for commented notes (2026-10-05).** Weighed with the user and set aside: they preferred one place for everything that needs a look; the row and caption say which kind each is.
- **Listing only the comments waiting on the user, or only the user's waiting on her.** Rejected by the user for the simpler rule: any open comment.
- **Only changing the notice to say the draft is not in the vault (2026-10-05).** Rejected: the edit would still be lost on a reload.

## Amendment (2026-10-06): the section lists the drafts of the folder in view

The Drafts section listed every draft of the persona in every folder, so a comment on a note in `Projects/` showed above the notes of `Archive/`. It now lists only the drafts whose note is inside the folder in view, at any depth (the same scope as Pinned); `Notes and Pets/` is not in `Notes/`. With no folder in view (a note at the vault's root) it lists the drafts of root notes. A draft of another folder is still reachable from that folder, and a new-note draft appears under the folder its working path is in.

When the Drafts section is shown the notes list under it is captioned ("Notes in {folder}") even with nothing pinned, so the two are told apart: before, only Pinned above the list gave it a caption and the notes ran on from the Drafts rows. The gap from the last draft to that caption is the same as from Drafts to Pinned (measured in headless Chrome: 45 px).
