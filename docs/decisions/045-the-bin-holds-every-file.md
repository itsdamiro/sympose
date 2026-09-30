# 045 — The bin lists, restores and purges every file, not only notes

> **Status: Accepted (2026-09-30).** Built the same day. Closes #100, found by the full code review of 2026-09-30 (reviewer-reported; reproduced on a scratch vault before fixing).

## Context

`delete_folder` moves a whole folder to `<vault>/.trash/<folder>`, so everything in it goes: notes, but also attachments, PDFs, canvases and hidden files. The recovery half (`vault_trash`) handled only `.md`: `list_trashed` skipped every other file, `purge_all` emptied only what was listed, and `_prune_empty_dirs` only ran for a purged note. Reproduced: delete a folder holding a note, an image, a PDF, a `.canvas` file and a hidden config folder, then empty the bin. The bin listed one item and "emptied" one; the image, PDF, canvas and hidden file stayed on disk, invisible in the app and impossible to restore or purge from it. Restoring the note left its attachments behind, so an image link in it would break. `restore` and `purge` by path were already generic (a rename and an unlink); the gap was the listing and the emptying.

## Decision

**The bin lists every file** a deleted note or folder left there, each with its original path, restorable and purgeable on its own by the same routes. Hidden files and folders (`.DS_Store`, `.obsidian`, the clash index sidecar) are not listed, as the tree does not list them.

**Emptying the bin removes every file** in the persona's scope, independent of the list: the hidden files it does not show go too, and the folders that leaves empty are pruned. What is outside the persona's `vault_folders` stays, as before. Nothing is followed out of the bin (`purge` already refuses a path whose real location escapes it; a link is left alone). The clash index is bookkeeping, not a deleted file: it is never purged as one, and the entries a purged file needed are forgotten as before. The count reported is the listed files removed, and the wording says "items", not "notes".

**Old bins show what they stranded.** Files stranded by deletes made before this change are simply listed the next time the bin is opened, so they become recoverable; no migration.

**Whole-folder restore is not part of this.** Restoring a folder as a unit ("put Trip and everything in it back") is a feature, not a bug fix: it needs grouping in the bin's UI and a rule for a destination that is partly occupied. It is filed separately.

## Consequences

- A deleted folder's attachments can be recovered, one file at a time, and no longer pile up invisibly on disk.
- A bin with many files lists them all: a deleted folder of hundreds of images shows hundreds of rows until whole-folder restore exists.
- Hidden files removed by emptying cannot be restored first, since they are never listed; they are application state (`.DS_Store`, editor config), not user content.

## Alternatives rejected

- **List a deleted folder as one row.** Needs to know a folder was deleted as a unit, which the bin's layout does not record (a folder's files and separately deleted notes look the same), plus new UI and restore rules: the separate feature above.
- **Only fix emptying and leave attachments unlisted.** The disk would be clean, but the files could still not be recovered, which is what the bin is for.
- **List hidden files too.** They would clutter the list with files the user never sees in the vault.
- **Empty only what is listed.** That is the bug: it leaves files no one can reach.
