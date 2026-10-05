# 073 — Renaming a folder carries its links, the personas' scopes and the persona's changes with it

> **Status: Accepted (damiro, 2026-10-05).** First half of the folder work on #21's list: **rename**. Moving a folder (dragging it onto another) is the next step and gets its own record. The user chose: links that name the folder are rewritten, a persona's folder scope that names it is updated and the user is told which, and rename comes before move.

## Context

The app can rename and move a note, but not a folder. The vault is the user's own Obsidian vault, so a folder's name is in more places than its path:

- **Links.** A link by name alone (`[[Anna]]`) does not care where the note lives. A link that names the folder (`[[People/Anna]]`, `![[People/Photos/anna.png]]`) breaks when it is renamed. A note's rename already rewrites links (`vault_write_relink`); a folder's would break the same kind of link for every note in it (the documented limit of #101 for notes).
- **A persona's scope.** A persona can be limited to folders (`vault_folders`, ADR 046-era profiles). Rename the folder and a persona that names it silently stops seeing it, or starts failing its sandbox.
- **The definition note.** `<Folder>/<Folder>.md` (ADR 033) is named after the folder, by Obsidian's folder-note convention.
- **What Sympose keeps by path:** the hidden list (ADR 037, exact paths in the settings file), the persona's pending changes and comments for each note (ADR 070, `note_changes_store`, keyed by note path), and in the browser the pins, recents, open folders (ADR 051), the open note and the folder in view.
- **The search index and the map** are built from the files, so they follow on the next read; a rename is not different from a note's in that.

ADR 070 already says a future folder move "must carry entries under the folder's path"; ADR 051 says "only notes can be renamed or moved in the app, so folders need nothing", which this record ends.

## Decision

**The operation** (`vault_write_rename_folder.rename_folder`), one request, in this order, the first step being the only one that can stop the rest:

1. **Validate.** The folder exists, is inside the persona's sandbox, and is not the vault root. The new name is one path segment (a rename keeps the parent; moving is the next record): not empty, not `.` or `..`, no `/` or `\`, not starting with `.` (that would hide it from the vault), and none of `[ ] | #`, which break the wikilinks that will name it. A name already taken by something else is refused (`exists`); a change of case only (`people` to `People`) is allowed where the file system treats them as one.
2. **Rename the directory** (`os.rename`, under the same file locks as a note's rename). If this fails nothing else is done.
3. **Rewrite the links that name the folder**, in every note of the vault inside the sandbox, notes inside the renamed folder included. A wikilink or embed (`[[…]]`, `![[…]]`, with its `#heading` and `|alias` kept) is rewritten when its path qualifier contains the old folder's name and, read against the folder's files as they were, resolves to one of them: the qualifier before the folder's name must be a tail of the folder's parent path, and what follows it must be a path inside the folder. So `[[People/Anna]]` becomes `[[Team/Anna]]`, `[[Sub/Anna]]` (the shortest unique path form) is left alone when `Sub` is a different folder, and a name-only link is never touched. Plain Markdown links (`[x](People/Anna.md)`) are not rewritten, as for a note (#42). A note that cannot be rewritten (permissions) is counted and reported, not hidden.
4. **The definition note.** For a top-level folder with `<Old>/<Old>.md`, that note is renamed to `<New>/<New>.md` through the note rename (which rewrites `[[Old]]` links), unless the new name is taken.
5. **Personas whose scope names the folder.** Every persona whose `vault_folders` holds the folder, or a folder inside it, has that entry rewritten in her own `persona.yaml` (text edit of the entry, comments and layout kept; the file is parsed again afterwards and, if it does not read as expected, it is put back and the persona is reported as needing a manual edit). The user is told which personas changed, by name.
6. **Hidden entries** for the folder or anything under it follow (settings file, this vault).
7. **The persona's changes follow** (`note_changes_store.move_prefix`): every note's entry under the old path moves to the new path, for every persona, as a note's rename already does for one note.

**The answer** is `{path, detail, relinked, failed, personas}`: the new path, a sentence for the user, how many notes were relinked and how many could not be, and the names of the personas whose scope changed. Steps 3 to 7 are best effort once the directory has moved: a failure is reported in `failed` or `personas_unchanged`, never raised after the fact.

**The route.** `PATCH /api/vault/folder` with `path`, `new_name`, `persona`. Errors as for a note: not found, exists, denied, invalid name.

**The app.** The folder row's `⋯` menu gets **Rename**, the same inline field a note has (Enter commits, Esc or blur cancels). On success the app: points the open note at its new path if it is inside the folder (saving its unsaved edits there first, as a note's rename does); remaps the pins, recents and open folders by prefix (`remapPrefix` beside `remapPath`); repoints the folder in view; and reads again the vault, the Drafts list and the hidden list. The toast says what was relinked and which personas changed.

## Consequences

- A folder can be renamed in the app without breaking links that name it, a persona's access to it, the pending changes and comments, or the user's pins.
- A rename of a big folder rewrites every note that links into it (a pass over the vault, like the health report); the notes' modified times change only for the notes whose links changed.
- The persona's `persona.yaml` is edited by the app for the first time. It is a user's own file for any persona except Samantha, and Samantha's scope is `*`, which names no folder.

## Alternatives rejected

- **Leave the links and warn (the note rename's documented limit).** Rejected by the user: a folder rename would break many links at once.
- **Stop and ask before touching a persona's scope, or leave it and warn.** Rejected by the user for update-and-say-which: the scope follows the folder and the user sees it did.
- **Rename and move together.** Rejected by the user: move needs its own thought (a destination, a name clash, a folder dropped into itself).
- **Rewrite plain Markdown links too.** Not done, for the reason a note's rename does not (#42); the two should be done together later.
- **Keep the old name as an alias on disk.** Obsidian has no such thing, and a second folder would appear in the vault.

## Built (2026-10-05)

`vault_write_rename_folder` (the directory, the links through `vault_write_relink_folder`, the definition note), `persona_scope` (the personas' own scopes), `vault_hidden.rename_folder`, `note_changes_store.move_prefix` and `PATCH /api/vault/folder` (`server_folder_handlers`), which answers `{path, detail, relinked, failed, definition, personas, personas_unchanged}`. In the app, Rename is in the `⋯` / right-click menu of a folder row in the tree, and in the right-click menu of a root folder in the main menu (not on the collapsed rail, which has no room for the field).

**Found in the real browser, and fixed:** the rename rewrites links on disk, in a note inside the folder as much as in any other, so a note open in the editor with unsaved edits would conflict with its own file (or overwrite the new links) when saved afterwards, and its edit was lost. So **the app saves a note with unsaved edits before it sends the request** (whichever note it is, since any note may link into the folder) and cancels the rename if that save fails; afterwards the editor reloads the note from disk at its new path. Checked: an edit typed into a note inside the renamed folder is in the file at the new path, with its own `[[Folder/Note]]` link rewritten.

**Checked in the real browser end to end** (invented vault, a scoped persona, a hidden entry, a pending change, a pin, a definition note): the directory, the links in a note outside and in one inside the folder (including `[[Folder]]` to the definition note and `[[Folder/Sub/Note]]`), the persona's `persona.yaml` (comments kept), the hidden list, both personas' pending changes and comments, the pin, the main menu entry and the open note all followed.

## Not covered

- A deleted note or folder in the bin keeps the path it came from; restoring it after its folder was renamed puts it back under the old name (ADR 045, 050).
- The tree's expanded folders (a cookie of paths) are not remapped: the renamed folder and the ones inside it come back collapsed.
- Pins, recents and open folders are in the browser that renamed the folder; another browser keeps the old paths until they are unpinned (as for a note's rename, ADR 051).
- Moving a folder; renaming a folder that holds a persona's own files (`profiles/` is not in the vault).
