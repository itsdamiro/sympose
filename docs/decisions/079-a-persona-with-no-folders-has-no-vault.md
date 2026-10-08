---
type: decision
status: accepted
date: 2026-10-08
projects: [sympose]
concepts: [Persona]
amends: [29]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/privacy]
---

# 079 — A persona with no folders has no vault

> **Summary.** A persona whose `vault_folders` is empty, or whose entries are all unsafe, can read and write nothing, instead of being widened to the whole vault. A persona file with no `vault_folders` key at all keeps the day-one default of the whole vault. Fail closed, as ADR 009 and 029 did for the other two ways a scope used to widen.

> **Status: Accepted (damiro, 2026-10-08).** Amends ADR 029 (a folder that is not there is not widened to the whole vault); closes the last open fail-open path of `vault_paths.get_allowed_dirs`.

## Context

`get_allowed_dirs` widened a persona's scope to the whole vault in three cases the person probably did not intend: `vault_folders: []` (the empty list is falsy and fell through to the legacy single-folder key, whose default `""` means the whole vault), `vault_folders:` with nothing after it, and a list whose every entry failed the safe-path check (`return allowed or [mv]`, written so that "a misconfigured persona never ends up with zero writable directories"). `vault_folders` is the hard boundary VISION names; each of these turned a narrowing into the widest grant.

## Decision

**Decided by the user: it means no vault.**

1. If the persona has a `vault_folders` key, it is honoured as written. An empty list, an empty value, or a list whose entries are all unsafe gives `[]`: no readable or writable folder. A list with some unsafe entries keeps the safe ones.
2. If the persona has no `vault_folders` key (and no legacy `vault_folder`), nothing changes: the whole vault. This is the day-one default and the fallback profile; it is an absence, not a statement.
3. An explicit `*`, `all` or `""` entry still means the whole vault.
4. Everything downstream already treats `[]` as "no vault" (`resolve_sandbox` returns `None`; the routes return an empty result or 403; the engine does not offer `ask` without a vault), so no caller changed. The persona still chats; she just has no notes.

## Consequences

- A persona file written with an empty list now behaves as written. Anyone relying on `[]` to mean everything must write `'*'`.
- A persona with no vault is possible, which is what an empty list now says.
- `sympose doctor` still names an unsafe entry (it is not a folder in any vault). It does not report an empty list: that is a choice, not a mistake.

## Alternatives rejected

- **Reject `[]` as an error and fail to load the persona.** Stricter, but it makes a pure-chat persona impossible. Right if a persona without a vault ever proves to be a mistake more often than a wish.
- **Require the key.** Would break the day-one default and every persona file written before the key existed.
