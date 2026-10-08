---
concepts: [Safe file handling]
---

# 050. A deleted folder can be restored as a unit

Status: Accepted (damiro, 2026-10-01). Closes #118. Builds on ADR 045.

## Context

ADR 045 made the bin list every file a deleted folder held, each restorable on its own. Putting a whole folder back meant restoring each file by hand, and a folder of hundreds of images was hundreds of rows.

The bin's layout cannot say which files were deleted together. A folder deleted as a unit is moved whole to `.trash/<folder>`, but a note deleted alone goes to `.trash/<its folder>/<note>.md`, the same place. A later note deleted from a new folder of the same name lands in the old folder's bin directory, and looks like one of its files.

## Decision

- **The delete records the group.** When a non-empty folder is moved to the bin, `delete_folder` writes an entry to `.trash-folders.json`, a hidden sidecar in the bin beside the clash index: the folder's bin directory, its original path, the time it was deleted, and the paths of the files it held. Members are the recorded files still in the bin; a note deleted alone into the same directory later is not one of them and stays a loose row. The deletion time is the delete's own, since files moved in a folder keep their last-edit times.
- **The listing groups.** `GET /api/vault/trash` also returns `folders` (`trash_dir`, `original_path`, `deleted_at`, `count`), and a row that belongs to one carries `folder`. The bin shows a folder as one row, its name and "12 files, deleted 2d ago", with a "Restore folder" button; it expands to the files, each still restorable or deletable on its own, as before. Loose files are listed as before.
- **Restoring a folder restores what is free, and says what it skipped.** `POST /api/vault/trash/restore-folder` puts back every recorded file still in the bin, through the same per-file restore (sandbox checks, locks), and never overwrites. A file whose spot is taken, or that is outside the persona's folders, or that failed, is skipped and named in the answer with the reason. The message says "Restored 10 of 12 files. Skipped 2 that already exist: a.md, b.md." Nothing is refused wholesale and nothing is overwritten.
- **Old bins.** A folder deleted before this change has no record, so its files stay loose rows, as today. No migration.
- **Housekeeping.** A record is dropped once its bin directory is gone; emptying the bin removes the sidecar. The sidecar is bookkeeping, not a deleted file: never listed, never counted.

## Not done

- **Empty sub-folders** of a deleted folder are not put back (only files are restored; a folder appears when a file is restored into it).
- **"Delete a folder forever"** as one action. Files can be deleted one by one or by emptying the bin.
- **Grouping a folder deleted by hand**, file by file: there is no folder to put back.

## Alternatives rejected

- **Infer groups from the bin's directories.** Wrong for the reuse case above, and cannot tell a folder from a path that happens to share a prefix.
- **Refuse the whole restore when anything is in the way.** Leaves a large folder unrestorable because of one file; restoring what is free and listing the rest loses nothing.
- **Overwrite or rename on conflict.** Changes or duplicates the owner's notes; skipping and saying so is the conservative choice.
