---
type: decision
status: accepted
date: 2026-10-01
projects: [sympose]
concepts: [Safe file handling]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 048. Saving a note keeps its line endings and refuses a file it cannot read as text

> **Summary.** Saving a note keeps its line endings (CRLF or LF, whichever most lines used) and refuses to save over a file that is not valid UTF-8. Both caused silent changes on a first save: a Windows note flipped its line endings and a stray byte became "�". A mixed file is made uniform on save.

Status: Accepted (damiro, 2026-10-01). Closes #98.

## Context

The editor opens a note through `read_note`, which reads it as text: Windows line endings (CRLF) become plain ones (LF), and any byte that is not valid UTF-8 becomes "�". A save writes back what the editor holds. So a note from a Windows editor changed its line endings on its first save, and a file with a stray byte lost that byte, with nothing typed. The changes show up as sync conflicts and as noise in git, in the owner's own notes.

## Decision

- **Line endings are kept.** A save looks at the file on disk under the same lock that guards the write: if most of its line breaks are CRLF, the saved text is written with CRLF, otherwise with LF. The editor still sees and sends LF. A file that mixes both is written in the style most of its lines had, so a mixed file is made uniform; this is the one remaining change, and only for a file that was inconsistent already.
- **A file that is not valid UTF-8 is not saved over.** The editor may still open it (the unreadable bytes show as "�"), but a save answers 422 "This note has bytes that are not valid text, so saving it here would change them. Edit it in another editor." and writes nothing. Carrying the raw bytes through the editor is not possible (JSON and the editor hold text), so refusing is the only way to leave the file exactly as it is.
- The trailing newline is unchanged: a note is saved with exactly one (ADR 006's rule, stated in `read_note`).
- The link rewrite on a rename already preserved both (`vault_write_relink`), and is unchanged.

## Alternatives rejected

- **Send the file's raw line endings to the editor.** The browser's editor normalizes them itself, so the server would have to guess anyway; restoring the style on save is the same work with no change to what the editor holds.
- **Save with replacement characters and warn.** Damages the file to tell the owner about it.
- **Open a file with unreadable bytes read-only.** Needs a new state in the editor for a rare file; the refusal on save does the protecting.
