---
type: decision
status: accepted
date: 2026-10-01
projects: [sympose]
concepts: [Persona, Settings]
amends: [44]
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 046. A model pick is a local override, not an edit of the shipped persona file

> **Summary.** A model picked in the terminal or web picker is saved to a local `persona.local.yaml` holding only `model:`, not into the tracked `persona.yaml`. Every pick had dirtied a committed file for Samantha, and one careless `git add -A` would have shipped it. Resetting to the defaults is deleting one file.

Status: Accepted (damiro, 2026-10-01). Supersedes the "Known limitation, accepted" paragraph at the end of ADR 044.

## Context

ADR 044 saves a model picked in the terminal's `/model` or the web picker into the persona's own `persona.yaml`. For Samantha that file is tracked in git, because it is the shipped default persona, so every pick dirtied a committed file. The workaround (leave it out of commits, `git diff profiles/` first) depended on remembering, and one careless `git add -A` would have shipped a personal model choice as the product default. Sympose is meant to be shared, so what is committed under `profiles/samantha/` must be exactly the defaults, and nothing a user does in the app may change it.

## Decision

- The tracked `persona.yaml` and `soul.md` are the defaults and are never written by the app.
- A model pick is saved to `profiles/<handle>/persona.local.yaml`, a file holding only `model:`. `profiles/samantha/*` is already ignored except the two shipped files, so the override is never tracked; no `.gitignore` change is needed.
- `get_profile` reads `persona.yaml`, then lets a valid `model` in `persona.local.yaml` win over the `model` in it. Precedence stays: override, then the persona file's own `model`, then the `chat_model` setting, then the local default.
- Choosing "no model of its own" (`set_model(handle, None)`) deletes the override, which returns the persona to its shipped default.
- The override file is the app's, not hand-edited: only `model` is read from it, and it is written whole and atomically, so the line-editing and comment-preserving machinery for `persona.yaml` is no longer needed.
- A local file that is unreadable or not valid YAML is ignored with a logged warning. It never drops the persona from the roster: the persona still loads with its shipped model.
- Path safety is unchanged: the persona folder must resolve inside the profiles root, and saving still requires the persona to exist.

## Consequences

- `git status` stays clean after any pick; the always-modified `persona.yaml` is gone.
- A user's own hand-written `model:` in `persona.yaml` (for a persona they authored) still works as the baseline; the app's picks sit on top of it.
- Resetting to the defaults is deleting one file.
- Existing installs that saved a pick into `persona.yaml` keep working (that value is the baseline); a later pick then overrides it in the new file.

## Alternatives rejected

- **Moving `profiles/` out of git with a template default copied at first run.** A larger change to how a fresh install gets its persona, and it makes the shipped default invisible in the repo. Not needed to fix this problem.
- **`git update-index --assume-unchanged` / `skip-worktree`.** Hides the change on one machine only, breaks on pull conflicts, and fixes nothing for other users.
- **Storing the pick in `settings.json` keyed by handle.** Works, but splits a persona's identity across two places and does not fit the persona-folder model of ADR 011.
- **Keeping the write into `persona.yaml` and relying on discipline.** The status quo; one `git add -A` from a leak.
