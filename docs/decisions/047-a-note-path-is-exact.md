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

# 047. A note's path is exact: reading, saving, renaming and deleting never search by name

> **Summary.** A note's path is exact: reading, saving, renaming and deleting never fall back to searching by name. Two notes can share a name in different folders, and the write layer already treated a path as exact. A stale root-level path now fails with "not found", and a caller that passed only a name must give the path.

Status: Accepted (damiro, 2026-10-01). Closes #99.

## Context

Two notes may share a name when they sit in different folders (`Journal/Meeting.md`, `Archive/Meeting.md`); in one folder they cannot. The path is what tells them apart. The write layer already treated a path with a folder in it as exact: a request for `A/Note.md` resolves to that file or to nothing, never to another note of the same name.

A note at the top of the vault has no folder in its path, so `Meeting.md` looked like a bare name, and a bare name was looked up: first at the top of an allowed folder, then by a recursive, case-insensitive match on the file name anywhere under it (the alphabetically first wins). So if `Meeting.md` at the top had been deleted or moved, and the screen was out of date (a stale tree, a double click), a save, rename or delete of `Meeting.md` acted on `Archive/Meeting.md`. The web app is the only caller, and it always sends the path it shows, so the name lookup served nothing.

## Decision

- Every name given to `resolve_existing_note` is a path from the vault's root, with or without the `.md`. `Meeting` means `Meeting.md` at the top of the vault and nothing else.
- The two lookups by name (at an allowed folder's top, and the recursive match) are removed. A path that does not exist is "not found", whatever else in the vault shares its name.
- The persona's own lookups of notes by name (wikilinks, the search and open tools) are a different code path and are not changed.

## Consequences

A stale root-level path now fails with "not found", like a stale path with a folder in it. A caller that relied on giving only a name (none in this repository) must give the path.

## Alternatives rejected

- **Refuse only when a same-named note exists elsewhere.** Keeps a lookup that can guess, and gives one answer or another depending on what else is in the vault.
- **Mark the web app's requests as exact and keep the lookup for others.** Two rules for one function, and no other caller exists.
