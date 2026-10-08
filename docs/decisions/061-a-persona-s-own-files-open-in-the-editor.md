---
type: decision
status: accepted
date: 2026-10-03
projects: [sympose]
concepts: [Persona]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app]
---

# 061 — A persona's own files open in the markdown editor

> **Summary.** A persona's four files (soul, profile, context, decisions) open in the web app's own markdown editor from one "FILES" menu replacing the disabled Soul and Memory chips. Nothing served these files to the web. Edits take effect on her next reply, and the shipped files stay untouched because overrides go elsewhere.

> **Status: Accepted and built (2026-10-03), designed with damiro.** Builds on ADR 011 (a persona's directory), ADR 012 (the soul is voice only), ADR 041 (persona memory, three files and a rewrite gate), ADR 046 (the tracked persona files are defaults the app never writes) and ADR 060 (the web chat's chrome).

## Context

The Persona page has two placeholder buttons, Soul and Memory, disabled with "coming soon". The intent is that a user can see, and edit, what a persona is made of: the voice she speaks in and what she knows about them, in the same markdown editor they use for their notes. Nothing serves these files to the web: the editor opens vault notes only (`GET`/`PUT /api/vault/note`, scoped to the vault), and a persona's files live in `profiles/<handle>/`, outside it.

Three facts shape the design:

- Memory is not one file. It is `profile.md`, `context.md` and `decisions.md` (ADR 041), so there is no single "memory" document to open.
- Samantha's `soul.md` is tracked in git, the shipped default (ADR 012). ADR 046 settled that such a file is never written by the app: a model pick goes to an untracked `persona.local.yaml`. Saving a soul edit into `soul.md` would dirty a committed file, or be lost on an upgrade.
- The engine can stage a rewrite of `profile.md` or `context.md` as a `.pending` file for the user's approval (ADR 041); the terminal reviews it with `/memory review`. The web has no equivalent, so a web user could not act on it. Terminal and web are meant to offer the same.

## Decision

**One control, one dropdown.** The Soul and Memory chips become one chip, "FILES", the model chip's size and style, in capitals, beside the model chip. It opens a menu (the app's shared menu surface) of the persona's four files: Soul (`soul.md`), Profile (`profile.md`), Context (`context.md`) and Decisions (`decisions.md`), each with a one-line description, and a mark on Profile or Context when a proposed rewrite is waiting. Choosing one opens it in the editor panel, in the same editor, with the same preferences, autosave and save.

**The files are served by an allow-list, never a path.** `GET /api/personas/{handle}/files` lists the four with whether each exists, whether Soul has a local override and whether a rewrite is pending; `GET` and `PUT /api/personas/{handle}/files/{name}` read and write one, and `name` is checked against the four names, so no other file of the persona (its `persona.yaml`, its sessions) can be reached. A write is atomic, rolls the previous content into `<file>.bak` as the memory writes already do, and presents the file's mtime as notes do, so a change made elsewhere (the engine appending a decision, the terminal) is refused with the same "changed on disk, discard my edits and reload" choice.

**Soul is a local override.** The tracked `soul.md` is never written. Saving the soul writes `profiles/<handle>/soul.local.md`, an untracked file (the existing ignore rules already cover it), and `load_soul` reads it first, then `soul.md`. The editor opens whichever is in effect; while editing the shipped soul it says that saving makes the user's own copy, and while a local copy is in use it offers "Reset to default", which asks first and moves the copy aside to `soul.local.md.bak`, so what the user wrote is not thrown away. The memory files are already untracked and are edited in place.

**The editor learns a second kind of file.** `MarkdownPanel` takes the file's load and save as a pair of functions (the vault's by default) and a flag for a plain file: no note actions menu (rename, delete), no frontmatter card, no links footer, and a title ("Samantha · soul.md") in place of the vault path. The shell holds which file the editor shows, a vault note or a persona file, and opening either replaces the other. A strip at the top of the document (the editor's toolbar does not say which file is open) names the file and carries what is particular to it: the soul's local-copy line, a pending rewrite, or what the file is.

**Proposed rewrites are reviewed in the web.** When a rewrite of `profile.md` or `context.md` is waiting, the file's banner says so with a Review button. It opens a dialog showing the proposal as a diff against the current file, with Accept (applies it, rolling the old content into `.bak`, the engine's own `apply`) and Discard (removes the proposal). The terminal's `/memory review` is unchanged.

## Consequences

- Edits take effect on her next reply: every one of these files is read on each turn. Nothing is sent anywhere by editing; what a cloud model may receive stays `/share`'s.
- A user can now change the soul and the memory in the web app, so the ADR 046 rule holds without a second mechanism: the shipped file is the starting point, and the user's version is a local file beside it.
- The editor's file I/O becomes a seam. It is the first time the editor opens something that is not a vault note; the vault-only parts are switched off by one flag instead of being deleted.
- Not built: editing the terminal's side (it has `/memory review` and no editor), `persona.yaml` (the model has its own picker, ADR 046), the persona's sessions and recaps (they are history, not memory).

## Alternatives rejected

- **Two buttons, Soul and Memory, with a menu only on Memory.** The soul and the three memory files are the same kind of thing to the user: a file about the persona. One list is simpler and leaves room for more files.
- **Editing `soul.md` in place.** It dirties a tracked file and loses the edit on an upgrade (ADR 046).
- **One combined "memory" document.** The three files have different rules (`decisions.md` is append-only for the engine, the other two are rewritten under a gate), so a combined text cannot be saved back to them cleanly.
- **Serving the files through the vault routes.** Those are scoped to the user's vault and its folder rules; widening them would put a persona's files inside the boundary that protects the user's notes.
- **A separate editor component for persona files.** It would copy the panel's chrome (the card, the resize, the reveal, the collapse) and drift; injecting the I/O keeps one editor.
- **Applying a rewrite from the banner without showing it.** The rewrite gate exists because a weak model can garble a whole file; the user should see what changes before it does.
