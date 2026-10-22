---
type: decision
status: accepted
date: 2026-10-22
projects: [sympose]
concepts: [Persona, Drafts]
amends: [071]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/engine]
---

# 094 — A new note with no folder named is made in the persona's Inbox folder

> **Summary.** A new-note draft whose folder nobody named is filed in `Inbox` in the first folder of the persona's scope, set when the draft is proposed, instead of in whichever folder the web app has open when the user clicks Accept. It ships as the default with no setting. A folder the persona was asked for still wins, and Archive's `Sessions` and the jobs' `Jobs` keep theirs.

## Context

ADR 071 (amendment of 2026-10-06) decided that an accepted new note is made in the folder the persona was asked for, else the folder the user is in, else her main folder. The last two are decided by the web client at Accept (`use-draft-editor.ts`: `proposed?.folder || folder?.()`), so the place is not known when the draft is made, and anything that shows the draft before Accept cannot say where it will go.

The review of Slack slice 2 (2026-10-22) hit it: a draft proposed from Slack has no folder in view, so its block names no destination and Accept puts the note wherever the web app is open. The same gap showed in earlier features, each of which solved it alone: Archive files in `<first folder>/Sessions` (ADR 086), the vault health report in `<first folder>/Jobs` (ADR 091), a folder's definition in the folder itself (ADR 033). damiro asked for one dedicated folder for drafts, the same for every feature (2026-10-22).

## Decision

- **The folder is `Inbox`, in the first folder of the persona's scope** (`Inbox` at the top of the vault when her scope is the whole vault), the same rule as `Sessions` and `Jobs`, so two personas with different scopes never share one. A persona with no vault has no folder and nothing changes for her.
- **It is set when the draft is proposed**, not at Accept: `propose_create` is given the folder when the caller named none, so the draft, the Drafts row, the Slack block and the web app all say the same place. The web client's `folder?.()` fallback is removed; a draft that was already waiting with no folder is made in the persona's main folder (a name with no folder in it is, to the vault routes, a name in her main folder).
- **Shipped as the default, with no setting and no file made at install.** The folder is made by the first Accept that needs it, with its parents, as for any folder a persona is asked for (ADR 071). The vault changes only on Accept (CLAUDE.md).
- **A folder she was asked for wins.** "Make it in Projects/Sympose" is kept. Archive (`Sessions`), the job reports (`Jobs`) and a folder's definition keep the folders they set.
- **The name is `Inbox`, not `Drafts`.** The app already has a Drafts group for what is waiting; a vault folder of the same name would be taken for it.
- **One helper** for "a subfolder of the first folder of her scope" replaces the two copies in `session_archive._folder` and `job_mechanical._folder`, and the new default.
- **Said to the model and to the reader:** the `propose_note` tool text ("leave it out to make it in the folder the user is in") now says Inbox; the reference page `Creating notes.md` and the Slack block name the folder.

## Consequences

- The place of a draft is known and shown before Accept, in every surface, and Slack needs no special case.
- A note the persona makes without being told a place no longer lands among whatever the user had open; the cost is one more folder in the vault, which the user moves notes out of. The folder is plain and can be renamed or deleted like any other.
- Reference library and a retrieval eval (before and after) change with the page, since the persona quotes it.
- A persona whose folders are all hidden or excluded cannot read what she filed in `Inbox`; it is in her first folder, so it is in her scope.

## Alternatives rejected

- **One `Inbox` at the vault root for every persona.** Simpler to find, but a persona whose scope leaves out the root cannot read her own filed notes, and personas would share one pile. Right if scopes stop being per persona.
- **A folder setting.** More configuration for something with a sensible default; the same reason ADR 086 gave for `Sessions`. Right when a user has a vault where `Inbox` means something else.
- **Ignoring a folder she was asked for.** Predictable but overrides what the user asked.

## As built (2026-10-22)

- `vault_paths.folder_in_scope(profile, name)` is the one helper; `session_archive._folder` and `job_mechanical._folder` call it. `note_changes.INBOX = "Inbox"`; `edit_tools._propose` fills the folder for a new note with `clean_folder(asked) or folder_in_scope(profile, INBOX)` (so a folder that leaves the vault is not kept and the Inbox is used), for the tool call and the marker. `propose_create` itself is unchanged: it files what it is given, and a caller with no persona (none today besides a test) leaves no folder.
- The web app's Accept no longer asks which folder the user is in (`useDraftEditor` lost its `folder` option, `app-shell.tsx` its ref); it makes the note in the folder the proposal carries. A draft already waiting with no folder is made in her main folder, not in the folder in view as before. The Drafts list is unchanged: a new note is still listed in every folder.
- The `propose_note` tool text says "Leave it out to make it in the Inbox folder." The reference pages say it: `Creating notes.md` has its own short entry, "Where does a new note go if I do not choose a folder?" (put in the folder entry, with "new" in its heading, a general request about a "new project" attached it, since that entry already holds `Projects/Sympose`; without "new" the plain question was not found), and `The web app.md` one clause; one reference case and one retrieval message. Retrieval `auto` 82/88 (81/87 before), the same six failures.
- Checked: 12 new Python tests and 1 web test changed, 22 Python mutants (21 caught, 1 shown equivalent and then removed by tightening the Slack room estimate, whose 3 new mutants are caught) and 2 web mutants caught. The review's seven findings are in ADR 093's last amendment.

## Amendment (2026-10-23): the Drafts list follows the folder

The line above that says the Drafts list is unchanged ("a new note is still listed in every folder") is superseded: a new note is listed only in its destination folder (ADR 071 amendment of the same date), so a note proposed for the `Inbox` is found in the `Inbox`.
