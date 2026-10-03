# 064 — A folder's icon is part of its definition

> **Status: Proposed (2026-10-03). Not built.** Builds on ADR 033 (folder definitions), ADR 062 (a persona's look is set in her own file, from a curated icon set) and ADR 037 (what the user hides). Nothing here is decided until it is agreed in a design talk.

## Context

A folder's icon in the web app (the main menu, the tree rows, and the "Notes in …" caption over the notes list) comes from a list of folder names written in the app's source (`VAULT_FOLDERS` in `ui/src/lib/vault-folders.ts`): a folder called `Movies` gets a film roll, `Quotes` a quotation mark, and every other folder gets the generic folder icon. The list is one person's vault written into the product, so a folder a user names `Recipes` or `Garden` is drawn like every other, and nothing the user does can change it. It also sits beside a definition note (ADR 033) that already says what a folder is for and what its notes carry, which is the natural place to say how it looks.

## Proposal

**The icon is a property of the definition note.** `Movies/Movies.md` takes an optional `icon:` property (`icon: film-roll`), the name of an icon in the curated set the app already ships for personas (ADR 062, `persona-icons.ts`). It is an ordinary frontmatter property, so Obsidian shows it and the user can edit it by hand, and no new file is introduced.

**Creating a definition includes choosing the icon.** The Define folder dialog (and the draft Sympose offers) gets an icon picker from the same set, so the icon is chosen when the folder is defined, not as a separate step afterwards. The default is the folder's current icon, so choosing nothing changes nothing.

**Every place a folder is drawn reads it.** The main menu, the tree rows and the notes list's caption take the icon from the definition when there is one, through the single lookup they already share (`folderIconFor`). Order of precedence: the definition's `icon`, then the built-in name list (kept as a fallback so existing vaults look the same on upgrade, and for folders with no definition), then the generic folder.

**What the backend does.** The folder tree (and the definitions it already reads) carries each folder's icon name next to its `definable` state; a value that is not a short lower-case name is ignored, as persona icons are, because the value ends up in the page. An icon name the app's set does not have falls back to the generic folder; a folder never loses its place over a bad value.

## Consequences

- A user's own folders can have their own icons without a change to the product, and the name list stops being the only way.
- The built-in list can shrink to a few neutral defaults later, which is the "personal content in the product" cleanup (#115 is the same problem for the nebula palette).
- The definition note gains a property the template and the health report must tolerate: the template's computed properties exclude `icon`, as the health report's checks must not call it a missing property.
- Only the web app draws icons; the terminal is unaffected.

## Open questions for the design talk

- Whether the icon belongs in the definition's frontmatter or in a line of the `## Template` block; the frontmatter is proposed because the template block describes the folder's notes, not the folder.
- Whether sub-folders get an icon of their own or only top-level folders (the definitions are per top-level folder, ADR 033).
- Whether the icon set grows beyond the persona set (a folder wants a film roll, a persona does not), and whether the set is one list or two.

## Alternatives rejected

- **Keep the name list in the source.** It cannot know a user's folders and carries one vault's names in the product.
- **A separate settings entry per folder.** It would live outside the vault and not travel with it, while the definition note does.
- **Infer an icon from the folder's name or contents with a model.** A guess the user cannot see or correct; a chosen icon is one click.
