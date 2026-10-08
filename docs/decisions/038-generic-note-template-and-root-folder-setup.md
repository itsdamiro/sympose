---
type: decision
status: accepted
date: 2026-09-28
projects: [sympose]
concepts: [Vault upkeep]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app]
---

# 038 — A generic note template (title, created, tags) and a setup step when a root folder is created in the web app

> **Summary.** A generic note template (`title`, `created`, `tags` by default, a global `note_template_keys` setting) is used when a vault has none of its own, and the web app offers a skippable setup step when a root folder is created. A new folder is empty, so there were no notes to compute a template from. The step writes only what the user typed and confirmed.

> **Status: Accepted.** Stage 3's web-app piece of ADR 033 (issue #23). The generic keys are a global setting; the setup step is skippable and writes only what the user typed and confirmed.

## Context

ADR 033 decided a definition note per top-level folder (`People/People.md`: a purpose and a `## Template` block of property lines) and said the web app should offer it when a root folder is created, each option skippable and nothing forced. It left one thing open: a new folder is empty, so there are no notes to count a template from, and ADR 033 rejects a stub written blind.

Two facts about the code as it stands:

- A note created with no template at all already gets a stub with `title`, `created` and `tags` (`vault_write_create.create_note`). Those three keys are a literal in the code: nobody can see or change them, and the web app cannot show them.
- The order of templates is fixed by ADR 033 rule 5: a `Templates/` file made for the folder, the folder's definition, `Templates/Note template.md`, then the stub.

## Decision

1. **A generic template exists, and it is the last step of that order.** `Templates/Note template.md` when the vault has one (the user's own words win), otherwise a template built from a list of keys. The stub in `create_note` is replaced by it, so a note created with nothing else to go on reads the same list the setup step shows. Nothing else in ADR 033's order changes.
2. **The keys are a global setting**, `note_template_keys`, default `title`, `created`, `tags`. Global because a person's habits follow them, not a vault; a vault that wants its own has `Templates/Note template.md`. Only a list of names that includes `title` counts (a note must have a title); anything else (a hand-edited string, a list without `title`, a name that is not a plain property name) leaves the default, so a malformed value never reaches a note. There is no screen for it yet (the web settings screen is #79 and #29); it is edited in the settings file, like the other knobs that have none.
3. **What each key starts as.** `title` is the note's title, quoted; `created` is today's date; `tags` is an empty list; any other key is left empty. A quoted `"{{title}}"` in a template (the generic one, or the user's own) is filled with the title encoded as JSON, so a title with a colon or a quote cannot break the frontmatter (the old stub did this with its own code; it now lives in the one renderer).
4. **The setup step.** When a folder is created at the vault root in the web app, a dialog follows: a field for what the folder is for (one or two sentences, optional) and a field holding the generic template's property lines, editable. Two actions: **Skip** (nothing is written) and **Create the definition**. Closing the dialog is Skip. Nothing is drafted by a model and nothing leaves the machine: every word written is the user's, typed or accepted, so grounding needs no special case and cloud approval (ADR 031) is not involved.
5. **What is written.** `<Folder>/<Folder>.md`, in ADR 033's shape (`render`), through `create_note`, so an existing note is never replaced. The dialog's lines become the `## Template` block; the purpose becomes the paragraph. This is the exception to ADR 033's "no stub when a folder is created": that rule is about Sympose guessing, and here the user wrote it. Because a definition now exists, the folder is not offered again as due, and its template is the user's, never recounted from its notes.
6. **What the server accepts.** Only a folder that `definable` allows: a top-level folder of the user's content (`can_have_definition`: not `Templates`, not an ignored or hidden folder, one name) that exists **at the vault's root** and inside the persona's folders, and has no definition yet. A folder outside the persona's folders is answered like one that is not there (404 for both), so the answer does not say which folders exist. The text is refused (400, with the reason) when there is neither a purpose nor a property line (a definition that says nothing would only stop the folder being offered one), when there are more than 40 template lines or a line is longer than 200 characters, when a line starts a code fence or is a `---` rule (either would close the block or the frontmatter early), when the purpose is longer than 500 characters, or when a line of it starts a heading (it would be read as the note's own structure). The refusals are for the note to stay readable by `read_template` and `read_purpose`, which the rest of Sympose uses. Only that refusal (`Refused`) becomes a 400; any other error stays an error.
7. **The routes.** `GET /api/vault/note-template` answers the generic template's property lines and where they came from (`vault` or `settings`); given `folder` (and `persona`), it also answers `definable`. The web app asks right after it creates a root folder and opens the setup step only when `definable` is true, so the step never opens for a folder that could not be saved (`Templates`, an ignored folder), or for a slashless name that a persona whose first folder is not the vault's root put somewhere else. `POST /api/vault/folder/definition` writes a definition from `{path, purpose, template}` and answers like the other create routes (201; 409 when it exists; 404 when the folder is not there for this persona; 400 for a refusal; 403 and 500 as `create_note` gives them).

## Consequences

- One artifact still serves purpose and shape, and it is a plain note that travels with the vault. A folder created with the setup step and one drafted later from its notes end up the same kind of note.
- A folder with a user-written definition is never offered by the health report as due, and its template is not recounted. If the notes drift from it, that is what the health report's checks are for, not a silent rewrite.
- The old stub and `Templates/Note template.md` can no longer disagree about what "basic" means: with no file the keys decide, with a file the file does.
- A user who never opens the settings file gets exactly today's stub (`title`, `created`, `tags`), so nothing changes for a note created without a template.

## Not built

- A settings screen for `note_template_keys` (#79 and #29). A terminal `/settings` entry is not added either: it is a list, not a toggle, choice or number (ADR 036).
- The persona asking the same options (ADR 033 stage 3, the agent surface, #21).
- Setting up a nested folder, and a definition for a folder that already has notes (that is the health report's `--draft`, ADR 034).
- A title with a double quote written by hand into a template that does not quote it (`title: {{title}}`) is still unquoted; only the quoted placeholder is encoded.

## Alternatives rejected

- **Draft the definition with a model at creation.** There is nothing to draft from in an empty folder, and a model given only a name would invent a purpose (ADR 033 stage 2 measured that).
- **Copy another folder's shape at creation.** A guess about which folder to copy from; the generic keys are the one starting point that is the same for everyone and can be changed by the user in one place.
- **A per-vault setting.** A second place for the same habit; `Templates/Note template.md` already is the per-vault override.
- **Always adding `title` to a list that lacks it.** It changes what the user wrote without saying; ignoring the list is predictable and the default is one edit away.
- **A separate, larger wizard (a step for each option).** Two fields the user can leave as they are is the smallest thing that offers both options and forces neither.

## Built (2026-09-28)

`sympose/generic_template.py` (the setting, the vault's own file, the lines and the text), `create_note` reading it in place of its stub, `folder_definitions_write.write_own`, `refusal` and `definable`, `server_definition_handlers.py` (the two routes), and in the web app `FolderSetupDialog`, `vault-definition-api.ts` and the trigger in `app-shell.tsx`'s `submitCreate` (a name with no slash, created with no folder open, once the server says `definable`). `sympose/webui/` rebuilt.

**Checked.** 100 new Python tests and 18 new UI tests; 66 source mutations of the backend, 19 of the dialog and client, all caught after four survivors were given tests (a trailing-space or blank line in a template's frontmatter, a title encoded as JSON hidden by `parse_frontmatter`'s line-scan fallback, a stale-fetch guard that was dead code and was removed, a dialog that was open with nothing in it). Live in headless Chrome on a scratch vault: a root folder opens the dialog with the three default lines; Create writes `Films/Films.md` exactly as typed and the definition is not listed in the tree; Skip writes nothing; a folder inside a folder opens no dialog; a template with a code fence keeps the dialog open with the server's reason; a note then created in `Films` starts from the typed template (`title` quoted, `created` today, `tags` empty).

**Review findings (`/code-review`, high), all fixed except one that was not a defect.** The dialog opened for names that cannot have a definition, and for a slashless name that a persona scoped below the vault's root had created elsewhere, so the user found out only after filling in the form (now the `definable` answer); a definition with nothing in it was accepted by the server although the button was disabled in the page; a `---` line in the template was accepted; a key with a trailing space passed the setting's check; the folder was looked for on disk before the persona's scope was checked, so 404 against 403 said which folders exist; any `ValueError` became a 400 with its own text. Not a defect: "a failed write is reported as 201" (`translate_vault_result` already turns an `Error:` result into a 500; a test pins it).

