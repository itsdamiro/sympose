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

# 051. Pins, recents and open folders survive odd names, renames and size

> **Summary.** Pinned notes, recents and open folders are stored as a JSON array, not a comma-joined cookie, and a rename or move rewrites the paths of pins and recents. Obsidian allows commas in note names, and a renamed note kept a stale pin. The old comma form is still read so no one loses pins; a name with a comma that the old form already split cannot be recovered.

Status: Accepted (damiro, 2026-10-01). Closes #105.

## Context

The pinned notes, the recent notes and the expanded folders of the vault tree are cookies holding a comma-joined list of paths. Four things were wrong, each confirmed in the code:

- Obsidian allows commas in note names, so `Notes, 2026.md` was read back as two entries.
- A rename or a move of a note updated only the open note, so its pin and its place in the recents stayed under the old path, where nothing resolves it, and the note silently left both lists.
- Pins and expanded folders had no limit, and a browser refuses a cookie past about 4 KB, so a long enough list stopped saving without a word.
- The expanded-folders cookie was shared by every vault.

## Decision

- **JSON, not commas.** The three lists are stored as a JSON array of strings. A value that does not start with `[` is read as the old comma form, so nobody loses their pins on upgrade. A name with a comma that the old form already split cannot be recovered.
- **A rename or move rewrites the path.** Pins and recents map the old path to the new one (`remapPath`). Only notes can be renamed or moved in the app, so folders need nothing.
- **A delete keeps the entry.** A deleted note keeps its path in the bin, and restoring it puts it back at that path, so its pin should come back with it.
- **No pruning of dead paths.** The tree is fetched per persona, and a persona scoped to some folders sees a subset of the vault: pruning against it would delete pins that are valid for another persona. A dead path costs a few bytes and is not shown.
- **A size cap that forgets the oldest, openly.** A list is trimmed at about 3.5 KB (encoded) before it is saved, dropping the oldest entries first (the front of pins and expanded folders, the end of recents, which are newest-first). A save therefore never fails silently. Someone with a very large pin set loses their oldest pins.
- **The expanded folders are per vault**, through the same vault-scoped key as pins and recents; the old shared cookie is not carried over (open folders are cheap to reopen).

## Consequences

- One small module (`cookie-list.ts`) owns reading, writing and remapping, replacing three hand-rolled copies.
- A cookie written by the old build is still read; the next save rewrites it as JSON.
- The cap is a number in one place.

## Alternatives rejected

- **Prune paths missing from the tree.** Rejected above: persona scope and the bin's restore make "missing" not mean "dead".
- **Store pins in the backend settings file.** No size limit and shared across browsers, but it breaks the rule that UI preferences live in cookies and costs a round trip per pin. Revisit if the cap proves too tight.
- **Escape commas inside the comma form.** A format that every reader must unescape correctly, for no gain over JSON.
- **Split a long list over several cookies.** More machinery than a cap that only ever touches a very large list.
