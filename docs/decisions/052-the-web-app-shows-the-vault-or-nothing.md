---
type: decision
status: accepted
date: 2026-10-01
projects: [sympose]
concepts: [Apps]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 052. The web app shows the vault or nothing, and drops what nothing used

Status: Accepted (damiro, 2026-10-01). Closes #116; the rest of its findings are #119 and #120.

## Context

A code review of the web app found dead weight and one grounding problem:

- `lib/mock-nebula.json` (232 KB) was imported statically into the main bundle and was the first-paint and offline graph. Its notes and tags are not in anyone's vault, yet the same graph feeds the editor's `#tag` autocomplete, so it could offer a tag that does not exist.
- `noteDelayMs` was a stored nebula preference that no settings control sets, and its only user, the `animateBirth` handle, has no caller.
- `react-router-dom` served two routes, `/` and `/shell`, that render the same shell.
- Only `status-line.ts` honoured `prefers-reduced-motion`.
- The slide-swap completion handlers committed on any bubbled `animationend`, so an animation in a descendant could commit a swap early.

## Decision

- **No stand-in graph.** The graph starts empty and is the vault's once `GET /api/vault/graph` answers. The badge says `connecting`, `live vault` or `vault unreachable`. This follows the rule that every claim about the vault is backed by the vault.
- **`noteDelayMs` and `animateBirth` are removed.** `animateBirth` scattered every node and revealed them one by one; nothing ever called it. With it go the `__birthed` flag, the reveal timer and the reheat throttle in both renderers.
- **`react-router-dom` is removed.** `App` renders the shell. The server already answers every path with `index.html`, so `/shell` still works.
- **One global reduced-motion rule** shortens animation and transition durations to almost nothing instead of removing them, so `animationend` still fires and the slide-swap logic that waits for it keeps committing.
- **The completion handlers only count their own element:** the content slot's own slide-out, and in the editor the slot itself or the three scoped content elements.

## Consequences

- The main bundle loses the 232 KB sample and a routing library.
- Offline, the nebula is empty with a visible reason, instead of a plausible but false graph.
- The two nebula renderers lose about 160 lines. A cookie `sympose:nebula.note_delay_ms` left by an old build is ignored.

## Alternatives rejected

- **A lazy offline demo graph, loaded only when the fetch fails.** It keeps the false-tags problem for anyone who is offline, and the app is local-first: if the backend is down there is no vault to show.
- **Turn animations off under reduced motion.** Would leave the slide-swap waiting forever for an `animationend` that never comes.
