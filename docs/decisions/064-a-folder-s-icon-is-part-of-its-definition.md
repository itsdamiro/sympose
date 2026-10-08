---
type: decision
status: accepted
date: 2026-10-03
projects: [sympose]
concepts: [Vault upkeep]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app, topic/architecture]
---

# 064 — A folder's look is part of its definition

> **Summary.** A folder's icon and look are part of its definition note, not a list of folder names in the web app's source. The list gave `Movies` a film roll and `Quotes` a quotation mark and every other folder the generic icon, and it reflected one person's vault. A user's own folders can now have their own icons without a product change, and the built-in list can shrink later.

> **Status: Accepted (2026-10-03), designed with damiro; built the same day (#128).** Builds on ADR 033 (folder definitions), ADR 062 (a persona's look is set in her own file, from a curated icon set) and ADR 037 (what the user hides). The three questions of the first draft are settled in "Decided in the design talk" below, and existing definitions are repaired by the vault health.

## Context

A folder's icon in the web app (the main menu, the tree rows, and the "Notes in …" caption over the notes list) comes from a list of folder names written in the app's source (`VAULT_FOLDERS` in `ui/src/lib/vault-folders.ts`): a folder called `Movies` gets a film roll, `Quotes` a quotation mark, and every other folder gets the generic folder icon. The list is one person's vault written into the product, so a folder a user names `Recipes` or `Garden` is drawn like every other, and nothing the user does can change it. It also sits beside a definition note (ADR 033) that already says what a folder is for and what its notes carry, which is the natural place to say how it looks.

## Proposal

**The icon is a property of the definition note.** `Movies/Movies.md` takes an optional `icon:` property (`icon: film-roll`), the name of an icon in the curated set the app already ships for personas (ADR 062, `persona-icons.ts`). It is an ordinary frontmatter property, so Obsidian shows it and the user can edit it by hand, and no new file is introduced.

**Creating a definition includes choosing the icon and colour.** The Define folder dialog (and the draft Sympose offers) gets an icon picker from the same set, and an optional colour, so the icon is chosen when the folder is defined, not as a separate step afterwards. The default is the folder's current icon, so choosing nothing changes nothing.

**Every place a folder is drawn reads it.** The main menu, the tree rows and the notes list's caption take the icon from the definition when there is one, through the single lookup they already share (`folderIconFor`). Order of precedence: the definition's `icon`, then the built-in name list (kept as a fallback so existing vaults look the same on upgrade, and for folders with no definition), then the generic folder.

**What the backend does.** The folder tree (and the definitions it already reads) carries each folder's icon name next to its `definable` state; a value that is not a short lower-case name is ignored, as persona icons are, because the value ends up in the page. An icon name the app's set does not have falls back to the generic folder; a folder never loses its place over a bad value.

## Consequences

- A user's own folders can have their own icons without a change to the product, and the name list stops being the only way.
- The built-in list can shrink to a few neutral defaults later, which is the "personal content in the product" cleanup (#115 is the same problem for the nebula palette).
- The definition note gains a property the template and the health report must tolerate: the template's computed properties exclude `icon`, as the health report's checks must not call it a missing property.
- Only the web app draws icons; the terminal is unaffected.

## Decided in the design talk

- **The definition note is where a folder's settings live.** Its own frontmatter (not the `## Template` block, which describes the folder's notes) carries the folder's settings: `icon:` now, and `accent:` / `accent_dark:` for the folder's colour in the Knowledge Nebula (the same key names as a persona's look, ADR 062; the icon is a short lower-case name, and a colour is a six-digit hex only, not the free colour strings a persona file allows, because it comes from a note that may be from a shared vault and the nebula's renderers parse a hex; anything else is ignored). This does not contradict ADR 033's rejection of "the template in the note's own properties": that was about template lines (`role:`, `email:`) reading as the note's own; `icon` and `accent` are the folder's own settings and nothing else claims them. Other folder settings can join them later without a new file.
- **Top-level folders only**, as the definitions themselves are.
- **One icon set, shared with personas.** There is one curated set; the folder glyphs the app already uses (film roll, quotation mark, calendar, chef's hat and so on) join the persona set, so a persona and a folder pick from the same list. Which set is in use is meant to be a theme setting later (ADR 062), so a definition names an icon and never a drawing; a name the set lacks falls back to the generic folder.
- **The nebula's colour follows the same order as the icon.** The definition's `accent` (`accent_dark` in dark mode, the light one for both when it is missing), then the built-in table (`FOLDER_COLORS`, kept as a fallback), then the neutral colour. This is the fix for #115 (the palette written for one vault's folder names). Only the nebula uses the colour for now.

## Existing definitions are fixed by the vault health (damiro)

A definition that already exists cannot be given an icon by the Define folder dialog (ADR 033 never replaces a note), so the vault health is the place that finds and repairs it, the same way it already finds a folder that has no definition at all.

- **A new check: a folder whose definition has no `icon`.** It is a finding like the others (ADR 034): one line per folder, never about note content. A folder with no definition is not part of it (that is the existing "could be defined" offer).
- **The fix is offered one folder at a time and applied only on a yes**, as ADR 034 decided for any change to a note: the offer shows the change (the line `icon: film-roll` to be added to the definition's properties), and nothing is written until the user confirms. It adds the property and touches nothing else in the note (the purpose, the `## Template` block and the user's other properties are left alone), and a definition that already has an `icon` is never changed, even to a different value.
- **What it offers is not a guess.** The icon offered is the one the built-in name list gives that folder (`Movies` gets the film roll), so an existing vault looks the same after the fix as before it, and the built-in list can then shrink (#115). A folder the list does not know gets no offer from the check; the user chooses its icon in the Define folder dialog when they create a definition, or edits the note's properties.
- **The colour is not repaired.** A missing `accent` is not a finding (the nebula's fallback is a normal state); the built-in table's colour is offered together with the icon only for a folder the table knows, as the one change.
- **This is the first write the health makes**, a departure from "it changes nothing" (ADR 034, ADR 063's Close-only dialog). It is a click on an explicit button per offer, in the same dialog and from the terminal's `sympose vault --health` as a prompt, with the doctor's Fix and Decline wording; the rest of the report stays read-only.

## Alternatives rejected

- **Keep the name list in the source.** It cannot know a user's folders and carries one vault's names in the product.
- **A separate settings entry per folder.** It would live outside the vault and not travel with it, while the definition note does.
- **Infer an icon from the folder's name or contents with a model.** A guess the user cannot see or correct; a chosen icon is one click.

## Built (2026-10-03, #128)

- **Reading.** `folder_looks.py` reads `icon`, `accent` and `accent_dark` from a top-level folder's definition note (`<Folder>/<Folder>.md`, the name exactly as the folder's, nothing nested); the shape checks moved to `look.py`, shared with `persona.yaml` (a value of any other shape counts as none). `GET /api/vault/tree` puts them on the top-level folder's node and `GET /api/vault/graph` puts the colours (never the icon) on each note of that folder.
- **Drawing.** `folderIconFor(name, icon)` takes the definition's icon, then the curated name (now a name in the shared set, `VAULT_FOLDERS` holds names), then the generic folder; the main menu and the "Notes in …" caption both use it. The twelve folder glyphs joined the persona icon set. In the nebula `nodeColor` takes the definition's colour (dark: `accent_dark`, else `accent`), then the table, then the neutral colour, and the legend (`folderLegend`) now lists a folder with a colour of its own, built-in or from its definition.
- **The fix.** The check "Folder definitions with no icon" (`vault_health.check_definition_icons`) is an offer, not a fault. Its fix (`folder_looks_write.add_look`) adds the built-in icon and the colours the note does not set to the end of the note's frontmatter and goes through `overwrite_note` with the mtime it read, so a note that changed meanwhile is refused; no other line is touched by the insert (a note without frontmatter gets a block); the save is the editor's own, so a mostly-CRLF note gets CRLF on every line and the file ends with one line break; a failed write or a note that is not UTF-8 is refused with its reason and never reported as added. `BUILT_IN` in `folder_looks.py` holds the same folder, icon and colours as the web app's fallback tables, and a test fails if they drift. The terminal asks one folder at a time (`y` to write, only when both input and output are a terminal, so `--health | less` never blocks on an unseen prompt); the web dialog has an Add button on each offer (`POST /api/vault/health/icon`) and the health pill opens its dialog for an offer too, not only for a problem.
- **Not built.** The Define folder dialog's icon and colour pickers (choosing at creation); a colour tint of the folder's icon in the menu; removing the built-in lists, which waits until the fix has run on the vaults in use.

**Review (`/code-review` at its second-highest level) found and fixed:** the CRLF opening of a note was not recognised, so a second block was prepended (the test had only checked uniform line breaks); a failed `overwrite_note` was reported as added; a non-UTF-8 note raised instead of being refused; a colour in `rgb(...)`, a name or a `url(...)` could reach the nebula (now hex only); `Templates` could be offered a write that is never read back; the report did not name the note an offer is about (the check is now grouped by folder); one failure message showed under every finding of the folder; the prompt could block when output was piped; a definition named `movies.md` was read but the fix looked for `Movies.md` (now exact everywhere); a folder or icon named like an object property (`constructor`) found the table's prototype; a folder with only `accent_dark` was missing from the legend. Left as it is, knowingly: `BUILT_IN` is a third copy of the built-in table, kept equal by a test, and goes with the lists after the fix has run.

**Tests and mutation check.** Tests for reading, inserting and writing (`tests/test_folder_looks*.py`), the terminal command, the endpoints and the web (`nebula-graph`, `use-menu-items`, `checks-api`, `settings-checks`). 19 mutations of the rules; 3 survived at first, two for missing tests (a colour already set was not offered again; a nested note called like the definition) and one that showed a real flaw (the fix had normalised every CRLF in a mostly-LF note, so it no longer does). Checked in headless Chrome on a scratch vault: a definition's leaf icon is drawn in the menu, the Add click wrote exactly the three lines, and the Movies icon is the same before and after.
