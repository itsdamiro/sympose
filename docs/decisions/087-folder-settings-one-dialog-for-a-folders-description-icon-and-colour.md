---
type: decision
status: accepted
date: 2026-10-17
projects: [sympose]
concepts: [Vault upkeep]
amends: [033, 038, 064]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app]
---

# 087 — Folder settings: one dialog for a folder's description, icon and colour

> **Summary.** Right-click a top-level folder, choose Folder settings, and one dialog holds what the folder is for, the properties its notes start with, its icon and its colour. The icon is found by typing. Saving creates the folder's definition note or edits the one that exists, changing only the lines the dialog owns. This is the icon and colour picker ADR 064 left unbuilt, and it ends "a definition that exists can never be changed from the app".

> **Status: Accepted (2026-10-17), designed with damiro.** Amends ADR 033 (a definition that exists is no longer out of reach of the app), ADR 038 (the setup step after a new root folder is the same dialog) and ADR 064 (the pickers).

## Context

Folder definitions are built (ADRs 033, 034, 038, 064) but three things were missing. The "Define folder" dialog only creates a definition note and refuses when one exists, so a folder described once could be changed only by hand in the editor. Nothing in the app lets the user choose a folder's icon or colour; ADR 064 put both in the definition note's properties and built only the reading side and the health report's offer to add the built-in look. And the icon set the app ships is 50 names shared with personas, thin for a user's own folders (nothing for travel, work, money or health).

## Decision

**One dialog, "Folder settings".** The right-click menu of a top-level folder offers Folder settings where it offered Define folder, for any folder that can have a definition (ADR 033's rule: the user's own content, not `Templates` or an ignored folder), whether or not a definition exists. The dialog opens filled from the note when there is one. The skippable setup step after a new root folder (ADR 038) is the same dialog, with Skip in place of Cancel.

**Four fields.**

- **Icon**, found by typing. The field shows the folder's current icon; typing filters the set by name and by a few keywords each icon carries (`food` finds the chef's hat, `film` the film roll); arrow keys and Enter choose; clearing goes back to the built-in icon for the name, then the generic folder (ADR 064's order). The filtering is in the browser: the set is under 100 names, so there is no search endpoint.
- **Colour**, for the Knowledge Nebula: a row of preset pairs (the palette the built-in folders already use, light and dark together), a cross for none, and a colour input for each theme, labelled Light and Dark and drawn alike. Picking either sets that theme's colour and the other is worked out from it (the same hue, brighter and softer for dark, deeper and stronger for light, in the ranges the presets use), so one pick is enough, from whichever side (damiro, 2026-10-17). Stored as `accent` and `accent_dark`, six-digit hex only (ADR 064); a note edited by hand can still hold two unrelated colours, and the dialog shows them as they are until the input is used.
- **What is this folder for?** and **Properties new notes start with**: as in ADR 038, the user's own words.

**The icon set grows by 18** folder-minded glyphs (travel, work, money, health, tasks, places, photos, mail, video, school, pets and so on) in the one set personas share. The set stays curated: a name outside it is refused by the server, so what the page draws is always a name Sympose knows.

**Saving.** One call, `PUT /api/vault/folder/settings`, replaces `POST /api/vault/folder/definition`; `GET /api/vault/folder/settings` replaces `GET /api/vault/note-template` and returns what the dialog starts from (the note's own values when it exists, the generic template when it does not).

- No definition yet: the note is created, as in ADR 038, with the look in its frontmatter when one was chosen. A dialog with nothing in it is refused.
- A definition exists: the note is edited in place, and only what changed. The dialog sends all its fields; the server compares each with the note and rewrites only a field that differs: the `icon`, `accent` and `accent_dark` lines of the frontmatter (a cleared field removes its line), the purpose paragraph (everything before the `## Template` heading except `# ` title lines, the span `read_purpose` already reads), and the template's code block (the span `read_template` already reads; a note without a Template section gets one at its end). Every other line stays: the user's other properties, whatever follows the template block, the line endings. An unchanged field is never rewritten, so a purpose longer than the dialog's 500-character limit does not stop an icon change.
- The write is the editor's own (`overwrite_note` with the mtime read), so a note that changed meanwhile is refused with a 409 and nothing is overwritten. The user's click in the dialog is the Accept, as it is for creating a definition today; no persona writes anything.

**A reading bug fixed with it.** `read_purpose` read the whole file, so a definition with properties (every one the health report's icon offer had touched) gave the persona its frontmatter as the folder's purpose in the vault map (`---\nicon: film-roll\n...`). It now skips the frontmatter.

**Not in this slice.** The persona offering a definition while talking (#23's agent surface) is built since, as a draft the user accepts (ADR 033, update of 2026-10-20), and does not reuse this write. The health report's draft keeps its own shape. The built-in name lists stay as the fallback until the health fix has run on the vaults in use (ADR 064).

## Consequences

- A folder's icon, colour, description and template are changed in one place, in the app, without hand-editing a note. The note stays the single source, so it still travels with the vault.
- Editing a definition by hand in Obsidian and in the dialog remain equal: the dialog never rewrites what it was not asked to change.
- The persona icon proposals (ADR 078) draw from the same, larger set.
- `POST /api/vault/folder/definition` and `GET /api/vault/note-template` are gone; the web app was their only caller.
- A purpose that holds several paragraphs or headings (everything before the Template heading counts as the purpose) is shown whole in the dialog and rewritten whole if the user edits it; leaving it alone leaves it exactly as it is.

> **Amendment (2026-10-17): the icon set is larger (ADR 088).** The curated 68 became 780 (the hand-named ones and a catalogue of one icon per concept), still found by typing and still checked by the server against a list; the rejection below of the whole library stands for the whole 6,000, not for a considered cut of it.

> **Amendment (2026-10-20): a folder below a top-level one has a colour of its own (ADR 090).** Folder settings stays for top-level folders. A folder below one has a smaller dialog (Folder colour, on its row's menu) whose colour is kept in the top-level folder's note as a `subfolders` property, with no definition note of its own.

## Alternatives rejected

- **A model that picks the icon from the folder's name or notes.** A guess the user cannot see or correct (ADR 064 rejected it); typing is one step. Right if a user ever has hundreds of folders to dress at once.
- **Searching the whole Hugeicons catalogue (thousands of names).** Bundles every icon or needs a server round-trip per keystroke, and the name would stop being a vetted value written into a note from a shared vault. The curated set can grow by a pull request when a folder needs a glyph it lacks.
- **Two colour inputs, light and dark.** Every folder would need two decisions and the second is nearly always the first made brighter. One pick with the other worked out is enough; a note can still carry two colours by hand. Right if users want pairs the derivation cannot produce.
- **Keeping Define folder (create only) beside a new edit dialog.** Two dialogs for one note; the user would have to know which applies.
- **Rewriting the whole note from the dialog.** Loses a user's other properties and any text after the template block.

## As built (2026-10-17)

- **Backend.** `folder_settings_write.py` (`read`, `save`, `Settings`), `folder_settings_text.py` (`with_look`, `with_purpose`, `with_template`: pure text edits), `folder_looks_write.rewrite_note` (the one read, change, write of a definition note, shared with the health fix, with `Missing`, `Changed` and `Failed` beside `Refused`), `folder_definitions.split_frontmatter` and `template_span`. Routes `GET` and `PUT /api/vault/folder/settings` replace `GET /api/vault/note-template` and `POST /api/vault/folder/definition`. 18 icons joined the set (`look.ICON_NAMES` and `persona-icons.ts`, a test pins that they are the same).
- **Web.** `FolderSettingsDialog` (it was `FolderSetupDialog`), `IconPicker` (a combobox over the set, `searchIcons` in `icon-search.ts`: name first, then a few words each icon answers to), `FolderColorField` (two alike colour inputs, words not icons) and `counterpart` in `folder-colors.ts`. The list opens on a click or a keystroke, not on focus, because a dialog focuses its first field when it opens. The right-click item reads Folder settings.
- **A look value the set lacks is not refused when it is left alone.** Only a field that differs from the note is checked, so a note naming an icon from a future set can still have its purpose changed.
- **The reading bug.** A definition with properties gave the persona its own frontmatter as the folder's purpose in the vault map; fixed in `read_purpose` (test in `test_vault_map.py`).
- **Checked.** Tests for the text edits, the save and its refusals, the routes, the picker, the colour field and the dialog; 38 of 38 backend and 25 of 25 frontend mutants caught (11 survived at first and each got a test); real headless Chrome on a scratch vault: Folder settings from the right-click menu, typing "travel" lists airplane and globe, Escape closes the list and not the dialog, Save changed the note's icon, colour and purpose lines and no other line (a user's `type:` property and the text after the template block stayed), the menu icon and the nebula's colours followed, a new root folder opened the same dialog with Skip, a code fence in the template was refused with its reason, and the dialog reopened on the saved values with Save off. Retrieval eval unchanged in all four modes (auto 62 of 68) after one new reference entry; a first wording of the entry took `writes-notes` and one case away, so it avoids "write" and "note" (as ADR 086 found).
