---
type: decision
status: accepted
date: 2026-10-05
projects: [sympose]
concepts: [Vault upkeep]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/data-safety, topic/web-app]
---

# 074 — Moving a folder onto another

> **Summary.** A folder can be moved by dragging it onto another folder or the vault root, which first asks the server for a read-only plan and moves only when nothing is left to ask. A move is a rename where the parent changes, so the same references must follow. A merge can rename notes the user did not expect, which is why it is a single prompt; dropping a folder onto itself or its own subfolder is not offered.

> **Status: Accepted (damiro, 2026-10-05); built 2026-10-06.** Second half of the folder work (ADR 073 was the rename). Dragging a folder onto another folder, or onto the vault root, the drop a note already has.

## Context

ADR 073 renames a folder and carries everything that names it: the wikilinks and embeds with its name in their path, its definition note, the personas' own folder scopes, the hidden list, every persona's pending changes and comments, and in the browser the pins, recents, open note and section. A move is a rename where the parent changes too, so the same things must follow. Three things are new: the destination may already hold a folder with that name, a folder can be dropped into itself, and a move changes what is inside a folder, so it can change what a persona is allowed to read.

Things that exist already and are reused: `vault_write_rename_folder`, `vault_write_relink_folder`, `persona_scope.rename_folder`, `vault_hidden.rename_folder`, `note_changes_store.move_prefix`, `cookie-list.remapPrefix`, the note rename's relinking (`vault_write_relink`).

## Decision

**What the user can do.** Drag a folder row onto another folder row, or onto the vault root, in the notes tree. The app first asks the server for a **plan** (read only), shows what needs the user's word, and moves only when there is nothing left to ask or the user has answered.

**A drop that is not allowed** is not offered: a folder onto itself or onto one of its own subfolders (no highlight, nothing happens), and onto the folder it is already in.

**1. A folder with that name is already there: the user is asked, never refused and never decided silently.** The prompt offers **rename** (a new name for the folder being moved) or **merge** (a button); closing it cancels. Merging puts the folder's contents into the one that is there; subfolders with the same name merge into each other, one level after another, without more prompts.

**2. A merge never overwrites a note.** If the same file name is in both (at any depth), the plan lists them in **one** prompt: rename the incoming ones (`Anna.md` becomes `Anna (2).md`, the first free number; other files, such as an image, the same way) or cancel the whole merge. Links that named an incoming note by its path follow it to its new name, through the note rename's own relinking. The merged-away folder is removed once it is empty.

**3. A move that changes what a persona can read asks first.** A scope that names the moved folder follows it (as in ADR 073), so her reach does not change. But a folder moved into a folder she is scoped to makes its notes readable by her (and, with a cloud model, sendable under the sharing settings), and a folder moved out of one takes them away. When any persona's reach would change, the plan says so and the app asks before moving, naming each persona and how many notes she gains or loses ("This gives Grace access to 12 notes. Move anyway?"); a move that changes nobody's reach has no extra step, and Samantha (scope `*`) never triggers it.

**4. Links that name the folder are always rewritten to its full new path** (`[[People/Anna]]` becomes `[[Archive/People/Anna]]`), whether or not Obsidian would still find the old form. The rule of ADR 073 decides *which* links: a wikilink or embed whose qualifier names the folder and, read against the folder's files as they were, points into it; a name-only link is never touched; `#heading` and `|alias` are kept; plain Markdown links are not rewritten (#42, #101). After a merge, links to the merged-away folder point at the destination.

**5. Definition notes get no special handling.** A top-level folder moved below the top keeps its `X/X.md` as an ordinary note (the app reads definitions only on top-level folders, ADR 033) and counts again if the folder goes back to the top; in a merge of two that both have one, the destination's stays and the incoming one is renamed like any clashing note. The confirmation says what happened ("X is no longer a top-level folder, so its description stopped applying"). Notes created in a moved folder take the template of their new top-level folder (ADR 033's matching is by top-level name).

**6. Everything else follows, as in ADR 073:** the personas' own folder scopes that name the folder or one inside it (comments kept; the user told which), the hidden list, every persona's pending changes and comments (`move_prefix`, and per note for a renamed clash), and in the browser the pins, recents, the open note and section and the **expanded-folders cookie** (which ADR 073 left out and a move must not: the moved folder does not come back collapsed; renaming gets the same fix).

**7. Vault health shows what a move or merge leaves behind** (ADR 034): observations, not faults, read only. **(a)** a note named after its folder inside a folder that is not top-level (`Projects/Garden/Garden.md`: it looks like a definition that stopped applying; moving the folder back to the top would make it one); **(b)** a numbered twin (`Anna (2).md` beside `Anna.md` in one folder, which is what a merge's rename makes, so it may be a duplicate to combine). A fix for them belongs to the future `vault --fix` (#101), which health leads into, as the definition-icon check already does for its own fix. **Deferred:** a check for plain Markdown links to no file, which a rename or move does not rewrite (#42); it needs its own design for reading and later fixing those links.

**The operation**, one request after the answers (`vault_write_move_folder`), in this order, the first steps being the only ones that can stop the rest:

1. **Validate** (as ADR 073, plus: the destination is a folder inside the sandbox or the root, not the folder or inside it, and not its present parent; the folder's name is unchanged unless the user chose to rename it for a clash). Anything at the destination with that name that is not a folder is refused.
2. **Move the directory** (`os.rename` under the file locks) when there is no clash; for a merge, move the contents one file at a time, renaming the clashing ones as chosen, and remove the emptied folders. If the first step fails nothing else is done.
3. **Rewrite the links** (item 4), the renamed clashing notes through the note rename's relinking.
4. **Scopes, hidden list, pending changes** (item 6).
5. **The answer** `{path, detail, relinked, failed, personas, personas_unchanged}` as for a rename; steps after the directory has moved are best effort and reported, never raised after the fact.

**The routes.** `POST /api/vault/folder/move-plan` (read only: `{clash, note_clashes, reach: [{persona, gains, loses}], definition}`) and `PATCH /api/vault/folder/move` with `path`, `destination`, `persona`, `if_exists` (`merge` or `rename` with `new_name`), `rename_clashing_notes` and `confirm_reach`. Errors as for a rename.

## Consequences

- A folder can be moved or merged in the app without breaking the links that name it, any persona's access except where the user has said yes, the pending changes and comments, or the pins and open folders.
- A merge can rename notes the user did not expect to see renamed; that is why it is one prompt that lists them, and why health points at the twins afterwards.
- Always rewriting touches notes whose links were still working. That was the user's choice for explicit links over fewer changes.
- A move of a big folder is a pass over the vault, like a rename's.

## Alternatives rejected

- **Refuse a clash.** Rejected by the user: they want to be able to merge.
- **Merge silently, or rename automatically (`Folder 2`).** Rejected by the user: a clash is the user's call, asked each time.
- **Ask once per clashing note (keep mine, keep theirs, rename).** Rejected for one prompt that lists them all: a big merge would otherwise mean many prompts, and "keep theirs" is a way to lose a note.
- **Refuse a merge when any note clashes.** Rejected: merge would only work for folders with nothing in common.
- **Warn first and ask before moving a folder that has a definition note.** Rejected by the user: the move is reversible, and an extra prompt for it is more than the case is worth; health shows it afterwards.
- **Move and tell the user afterwards what a persona gained or lost.** Rejected by the user for asking first: a persona's reach can include a cloud model, so the user should decide before the notes become readable, not learn after.
- **Refuse any move that changes a persona's reach.** Rejected: it would block a legitimate move for a one-line question.
- **Rewrite a link only when Obsidian would no longer find it by its old form.** Rejected by the user for always rewriting to the full path: explicit links over fewer changes to the notes.

## Built (2026-10-06)

**Backend.** `vault_move_folder_plan` (the read-only plan, slice 1; also for a folder going in under a new name, so the reach asked about is the real one), `vault_write_move_folder` (the move, a rename on a clash, a merge), `vault_write_merge_folder` (numbering what is in both, moving files across one at a time), `vault_write_relink_folder` (a move rewrites the folder's whole path in a link, a rename its own segment), `server_folder_handlers` (`PATCH /api/vault/folder/move`, which answers `{path, detail, relinked, failed, definition, personas, personas_unchanged, merged, renamed, left_behind}`, and `POST /api/vault/folder/move-plan`), and `vault_health_moves` (the two observations of item 7, never a problem; a numbered twin means a number of 2 or more).

**Merge.** What is in both is renamed first, inside the incoming folder (a note through the note rename, so the links that named it follow it and its pending changes follow through a callback as each rename happens), and then everything is moved across with nothing overwritten, so the folder links are rewritten against the files as they are after the renames. A file where the other folder has a folder of that name (or the reverse) is numbered like any other. Hidden files and folders are never moved: they stay, and so does the source folder, and the answer says how many files are left (`left_behind`). Scopes, the hidden list and pending changes follow the folder to its new path whether or not something was left behind; what is left is hidden files, which are not notes, or a file that appeared meanwhile.

**Web app.** A folder row is dragged onto a folder row, the heading of the folder in view, a root folder in the main menu, the vault name at the top of the menu or the empty space below the root folders (the last two are the vault root; damiro chose both). A drop on itself, its own subfolder or its present parent is not offered: no highlight, no cursor. `use-folder-move` saves a note with unsaved edits, asks for the plan, asks what the plan says needs asking (`FolderMoveDialog`: rename or merge; the files in both in one prompt; "This gives Grace access to 12 notes. Move anyway?"), moves, and follows: pins, recents, the open note, the section (a root folder moved inside another leaves the section as that other root), and **the tree's expanded folders** (`folder-moved`), for a rename too. When a merge renamed the note that is open, the editor closes instead of landing on the note that was there.

**Checked in real headless Chrome** (invented vault, three personas, a hidden note, a pending change and a comment, a pin, an open note): a plain move with the folder's open state kept, its links, a persona's scope, her pending change; a clash answered by a new name (the folder there untouched, links inside and outside, the hidden list, the comment, the pin); a merge with a note in both, with the editor open on the incoming one; a move that changes two personas' reach, cancelled and then agreed; a drop on itself, its parent and the heading, which send nothing; a move to the vault root by the vault name and by the empty space. **Found there and fixed:** a drag lost its highlight when it moved onto a row's own icon or label (the browser reports the child's `dragenter` before the parent's `dragleave`); it now stays lit until the drag leaves the row (this also fixes it for notes). The review found and I fixed: a bad new name was reported as "into itself", the reach asked about was the merge's when the user had chosen a new name, a failing rename in the middle of a merge lost the pending changes of the ones before it, a failing merge step raised instead of reporting what was left, the vault-root highlight could stay on over a row, and the section after moving a root folder inside another.

## Not covered

- A deleted note or folder in the bin keeps the path it came from (ADR 045, 050).
- Pins, recents and open folders are in the browser that moved the folder; another browser keeps the old paths until they are unpinned (as for a rename, ADR 051).
- Plain Markdown links are not rewritten (#42, #101); health does not yet look for them.
- Moving a folder that holds a persona's own files (`profiles/` is not in the vault).
- A move across two vaults.
- The links to a file that a merge renamed and that is not a note (an image in both folders) are not followed; they keep the old path, which is the other folder's file now. Only notes have the note rename's relinking.
- A hidden file, or a hidden note in a folder, that a merge left in the source folder keeps the scope, the hidden state and the pending changes of the folder it was in, which have moved.
- The drop handlers of the tree, the heading and the main menu are three copies of one idea with small differences; a shared hook would hold them together (tech debt, no behaviour in it).
