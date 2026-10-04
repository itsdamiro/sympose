# 070 — Pending changes and annotations are stored per note in the persona's own folder

> **Status: Proposed (2026-10-04).** Not built. The storage and API half of the design in ADR 042 (amended 2026-10-04) and ADR 069: what is kept, where, how a proposal knows it has gone outdated, and what the editor and the Drafts section read. Turn-based, web app only.

## Context

ADR 042 settled that a persona's create or edit is only a proposal until the user accepts it, drawn as a tracked change in the open note; ADR 069 settled that highlights and comments are kept out of the vault and travel with the next message. Both are state Sympose creates for itself, so both belong in the persona's data folder (`profiles/<handle>/`, beside `sessions/` and `recaps/`) and never in the vault the user browses.

They are one idea seen twice: something attached to a note, saved quietly, that either side can resolve. This record gives them one store, one key and one set of rules.

## Decision

**One file per note, in a `notes/` folder of the persona's data folder.** A note's entry is a small JSON file named after the note's vault-relative path (made safe as a single file name, with the path kept inside the file). It holds that persona's proposals and annotations for that note. A per-note file is easy to read, easy to delete when the note goes, and two notes never contend for one lock; it takes the same lock discipline `vault_write.get_file_lock` already gives a vault file. The trash index's single sidecar is shaped for a bin and is not the model.

**What an entry holds.**

- **A proposal** (`kind`: `edit` or `create`): an id, the time, her one-sentence explanation, and for an edit a patch: the passage she quoted (`find`), what replaces it (`replace`), and a little text before and after the passage as it stood when she wrote it (`context`). A `create` holds the whole proposed text and its working name (ADR 042 amendment) instead. State: `pending`, `outdated`, or `resolved` (accepted or declined).
- **An annotation** (ADR 069): an id, author (`user` or `persona`), the quoted passage with its context, the comment text, the time, and state `open` or `resolved`; a persona reply is an annotation with a `reply_to`.

**How a proposal knows it has gone outdated.** No version numbers or modification times: the stored `find` plus its `context` is the anchor. When the note is opened, and again after each edit, the editor looks for `find` in the note with its context. Found once, the proposal is pending and follows the text as the user edits. Not found, because the user rewrote those words, it is `outdated` and drawn greyed with a short note that the note changed there since it was written; the user declines it or asks her to redo it. Found more than once with the context unable to tell which, it is also `outdated` rather than applied to a guess. Annotations use the same finder and show as detached when their passage is gone.

**Accepting.** The editor applies an accepted change to its own text, as an ordinary edit the user can undo (the passage replaced once, as the finder located it), and the note is saved by the ordinary save: `overwrite_note` with its `expected_mtime`, so a save conflict is reported the way it is today (`NOTE_CONFLICT`). A new note is created by the ordinary create (`create_note`, which refuses an existing path, `NOTE_EXISTS`). The server then forgets the proposal. Declining only forgets it. Accepting the note from the toolbar applies every pending proposal in it, saves once and forgets them; the outdated ones are left for the user. No route in this record writes a vault file.

**A new note she proposes** is held only in this store until it is accepted. The editor opens it as if it were a note, from the Drafts section, under its working name; the file is created only on accept. A proposal for a new note is listed in Drafts by its working name and is not searchable, not in the vault tree, the nebula or the map (nothing reads this store but the Drafts listing and the editor).

**One key for a note.** The vault accepts `A/Note` and `A/Note.md`, stray quotes and spaces, `./A/Note` and `A/../A/Note` for the same note, so the store normalizes every path to one key (the path from the vault root, with `.md`, no `./` or `..`) at its single entrance; routes, the rename and purge hooks and the persona's tool all go through it, and the routes report that key back. A path that leaves the vault or names no note is refused (a bad request on the routes). Letter case is not folded: the tree and the search both supply a note's real name, and the vault itself resolves a path exactly.

**Rename, move and delete follow the note.** The vault's rename and move already carry pinned notes and the trash index with them; they carry this entry too, by renaming its file and the path kept inside it. When a note changes outside Sympose, so its entry no longer matches any note, the entry is shown as detached, never silently dropped. Deleting a note to the bin keeps its entry (restoring the note restores its drafts); emptying the bin from the Bin removes the entry with the note.

**Per persona.** The store lives in each persona's folder, so two personas' drafts and comments for the same note are separate, and the Drafts section shows the active persona's. Each persona proposes in her own voice.

**The API** (web app only, resolved against the active persona like the other `/api` routes; a note's path is a query parameter, as in `/api/vault/note`):

- `GET /api/vault/drafts` — the notes with at least one proposal, each with its path, whether it is a new note, its working name, a count and the time of the latest; what the Drafts section lists.
- `GET /api/vault/changes?path=` — one note's proposals and annotations, each with its status worked out against the note on disk now (`pending` or `outdated`; `attached` or `detached`), whether the note exists yet, and its modification time.
- `POST /api/vault/changes/resolve` — forget named proposals, or all of the note's, once they are accepted or declined; the comments are kept.
- `POST /api/vault/annotations`, `PATCH /api/vault/annotations` (the text and/or the state, in one save) and `DELETE /api/vault/annotations?path=&id=` — the user's highlights and comments; a highlight on words that occur more than once says where it starts.
- The chat request carries the open note's path; the engine reads that note's open annotations (ADR 069) and, for the persona's own proposals, writes them through one tool (ADR 042, to be recorded in its own record with the prompt).

None of these routes writes a vault file, and none reaches `purge` or `empty_trash`.

**Folders.** The app has no folder rename or move, so no hook for one exists, and a feature that adds one must carry the entries under that folder's path. What exists today is checked: deleting a folder keeps the entries of the notes in it, restoring the folder brings them back, and emptying the bin forgets them.

## Consequences

- A new module for the store (shaped like `vault_trash_index.py` for the file handling, with its own lock) and a small number of handlers; the vault's rename, move and permanent delete each gain one call to carry or remove an entry.
- The finder (find a passage by quote plus context, report none, one or many) is one function shared by proposals and annotations, tested on its own, and also used by the editor.
- Nothing in the vault changes until an accept, so the vault tree, search, the nebula and the map are untouched by drafts by construction.
- A note's entry is plain JSON, so it is readable by hand and survives a Sympose update that does not change its shape; a schema field lets a later version migrate it.

## Open questions

- How much context is kept before and after a passage (a fixed number of characters or the surrounding sentence), to be set from a measurement on edited notes.
- Whether declined and accepted proposals are kept as history for a time or removed at once; the first version removes them.
- Whether the note-level Accept saves once when some proposals are outdated (it applies the pending ones and leaves the outdated ones for the user), which is the default here.
- **Two proposals on one passage (found 2026-10-04, not fixed).** Two proposals quoting the same passage (the same change proposed twice, or two different replacements for it) are each found exactly once in the note, so both read as pending, and the note-level Accept applies both: the text came out doubled ("Plenty of textPlenty of text"). Settle in slice 5, with her tool: `propose_edit` refuses, or replaces, a proposal whose passage overlaps one already waiting, and the editor's Accept all skips a change whose range was already changed by another in the same pass. Needs a test for each side.

## Alternatives rejected

- **One index file for all notes.** Rejected: every change locks everything, and one corrupt file loses every draft; a file per note scopes both.
- **Version numbers or modification times to detect staleness.** Rejected: a time says the note changed, not whether it changed where the proposal is; the quoted passage with its context says exactly that.
- **Storing proposals in the vault as draft notes.** Rejected in ADR 042 and again here: a file in the vault is a write and would show to every tool that reads the vault.
- **Per-vault instead of per-persona storage.** Rejected: proposals are a persona's own voice, and two personas disagreeing about one note should not overwrite each other.
