---
type: decision
status: accepted
date: 2026-10-20
projects: [sympose]
concepts: [Apps, Vault upkeep]
amends: [064, 087]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app]
---

# 090 — A folder below a top-level folder takes a colour, kept in its top-level folder's note

> **Summary.** Right-click any folder below a top-level one (`Projects/sympose`, `Projects/stylo`) and choose Folder colour: its notes are drawn in that colour in the Knowledge Nebula, so one project can be told from another. The colour is a `subfolders` property in the top-level folder's own definition note (`Projects/Projects.md`), so no note is made just to hold a colour. A note takes the colour of its nearest coloured folder, at any depth. Built 2026-10-20.

> **Status: Accepted (2026-10-20), designed with damiro.** Amends ADR 064 (a look is read only from a top-level folder's note; subfolders now have a colour, not an icon) and ADR 087 (the dialog is for top-level folders; this is a smaller one for the folders below them).

## Context

- Folder colours exist only for top-level folders (ADR 064, 087). The Knowledge Nebula colours a note by its top-level folder (`NebulaNode.folder`), so everything under `Projects/` is one colour. A vault that keeps one folder per project under `Projects/` cannot tell its projects apart, and that is what the colour was asked for (2026-10-20: "define a sub folder color, at least 2 levels from the root, to differentiate a project").
- A definition note is for top-level folders only (ADR 033); a note named after a deeper folder is flagged by the vault health as a description that stopped applying (`vault_health_moves`).
- The vault owner's word: no extra Markdown file just to define a colour; keep it in the parent folder's note. Folders are named by the user and several may be coloured.
- ADR 073 and 074 set the rule that renaming or moving a folder carries every record that names it by path.

## Decision

**Where it lives.** The definition note of the top-level folder holds a `subfolders` property: a map from a path below that folder to the colour pair the top-level folder already uses (`accent` light, `accent_dark` dark, six-digit hex, ADR 064).

```yaml
subfolders:
  sympose:
    accent: '#7c3aed'
    accent_dark: '#b98cff'
  sympose/decisions:
    accent: '#be123c'
    accent_dark: '#f2889b'
```

It is the top-level folder's note for a folder at any depth, not the direct parent's: there is one place to look, and a folder in the middle needs no note. The note stays the single source and travels with the vault. Obsidian's Properties panel shows a nested value as an unsupported type and leaves it as it is.

**Reading.** An entry is used when its key is a plain folder path (no empty, hidden or `..` part, any backslash read as a slash) and it sets at least one colour of the safe shape; anything else reads as no entry. Only a top-level folder that can have a definition (`can_have_definition`) counts, and only from `<Top>/<Top>.md`.

**Which colour a note has.** The nearest coloured folder above it wins, up to but not including the top-level folder: `Projects/sympose/decisions/85.md` takes `sympose/decisions`, else `sympose`, else the top-level folder's own colour (ADR 064), else the built-in one. The server resolves it and puts `accent` and `accent_dark` on each graph node, plus `colored_by` (the folder's path) when the colour is a subfolder's, so the page needs no copy of the rule. A tree folder carries only its own entry (for the dialog), never an inherited one.

**Where it shows.** The Knowledge Nebula (the dots, and the legend, which lists a coloured subfolder by its path beside its top-level folder). The tree, the folder views and what the persona reads do not change.

**Setting it.** A folder below a top-level folder has Folder colour in its right-click and `⋯` menu in the tree. It opens a small dialog with the same swatches, cross and Light and Dark pickers as Folder settings (one pick works out the other theme). Cancel writes nothing. The dialog is the Accept: no persona writes it.

- `GET /api/vault/folder/color?path=` gives `{editable, accent, accent_dark}`, `editable: false` for a path that is not below one of the user's own top-level folders or not in the persona's scope.
- `PUT /api/vault/folder/color` with `path`, `accent`, `accent_dark` sets the entry, or clears it when both are left out.
- The write is the editor's own (`rewrite_note`, with the mtime read), so a note that changed meanwhile is refused with 409. Only the `subfolders` property is rewritten, in YAML block style: an entry of another path stays as it is (even one this code cannot read), a comment written inside that property is not kept, and every other line of the note stays as it was. A `subfolders` value that is not a map is refused and nothing is changed.
- A top-level folder with no definition note gets one made with only this property and a title line (the same note the Folder settings dialog would make, nothing in it but the colour). Clearing a colour never creates a note.

**A renamed or moved folder carries its entries.** After the rename or move has moved the directory (ADR 073, 074), the entries for that folder and the ones below it are taken out of the old top-level note and written under the new path, in the same note for a rename and a move inside one top-level folder, and in the new top-level folder's note (made if it has none) for a move to another. The toast says how many were carried. A folder that now has an entry already keeps it. A folder that becomes top-level has no entry of its own any more, and one that is no longer top-level leaves its own `subfolders` behind in its note (the move toast already says its description stopped applying). Failing to write is said in the toast; the move stands.

**Deleting.** A deleted folder's entry stays (a folder restored from the bin as a unit, ADR 050, comes back coloured); an entry with no folder is never drawn and is harmless.

## Consequences

- A project folder can have its own colour in the Nebula without a note of its own; the colour and the folder's description, icon and purpose all sit in one note.
- A top-level folder's note now carries a nested property the user may also write by hand (Obsidian's source mode). An entry written wrongly is ignored, not an error.
- A note made only to hold a colour makes the folder "defined": the nudge to describe a folder (ADR 033's `due_folders`) stops for it, though it has no purpose or template. The Folder settings dialog opens on such a note as an empty description and can fill it in.
- Rewriting the `subfolders` block drops a comment inside it.
- The legend grows by one line per coloured subfolder.

## Not part of this

A colour in the tree or folder views (declined again on 2026-10-20), the persona proposing or setting a colour, colouring a top-level folder from this dialog (it has Folder settings), per-note colours, and a `--fix` for an entry whose folder is gone.

## Update (2026-10-20): an icon, and a health observation for an entry whose folder is gone

Decided with damiro when the leftovers were closed: the tree colour stays out (the nebula and its legend only), the icon goes in, and the check is an observation.

**An icon.** An entry in `subfolders` may also hold `icon`, the name of an icon in the app's set (`look.ICON_NAME` on reading, `look.ICON_NAMES` on a save, as for a top-level folder, ADR 064 and 087). An entry may hold an icon alone, colours alone or both; a bad value reads as none and an entry with nothing usable is left out. The icon belongs to its own folder only: a deeper folder does not inherit it, and an entry with an icon but no colour colours nothing, so `nearest` goes on past it to the folder above. The tree folder carries its own `icon` beside its colour; the note's node never carries an icon.

**Where it shows.** The tree draws the icon in place of the folder glyph (open or closed) on a row below a top-level folder, and nowhere else. A top-level folder's icon is still not drawn in the tree (it shows in the main menu and the folder view's caption, ADR 064), so the two rows of the tree are not changed by this. A name the icon set lacks is drawn as the usual glyph.

**Setting it.** The dialog is now Folder look (menu item, title and toasts say so): the same icon picker as Folder settings above the same colour field. Save is on when the icon or either colour changed; clearing the icon, both colours or both writes the entry without the key, and an entry left with nothing is removed. `GET`/`PUT /api/vault/folder/color` keep their path and gain `icon` (the route, the module `subfolder_colors`, `folder-color-dialog.tsx` and `folder-color-api.ts` keep their names: renaming them would have touched every reference to this ADR for no change in behaviour). A rename or move carries the icon with the entry.

**A health observation.** `sympose vault --health` lists, under "Subfolder colours and icons for a folder that is gone", each `subfolders` entry of a top-level folder's note whose folder is not in the vault (`vault_health.check_subfolder_looks`). It is an observation, never a fault (it does not change the exit code), and nothing is written: an entry with no folder is never drawn and does no harm, and a folder restored from the bin comes back with its look (see Deleting). There is no `--fix` for it; the line names the note, and the entry is removed by hand. A folder that exists but is empty counts as there. Not checked: an entry in a note the persona cannot read.

**Checked.** `tests/test_subfolder_colors.py` (the icon read, its bad shapes, `nearest` past an icon-only entry, the text edit, the save with and without colours, clearing, a refused icon, a rename carrying it), `tests/test_server_subfolder_colors.py` (the routes, the tree's `icon`, no icon on a node), `tests/test_vault_health_subfolders.py`, and in the web app the dialog, the API client, the menu and the tree (a subfolder draws its icon, an unknown name and a top-level folder do not change). 10 of 10 mutants caught (six Python, four web app).

## Alternatives rejected

- **A definition note per subfolder** (`Projects/sympose/sympose.md`). Rejected by the vault owner: a file only to hold a colour. It would also need ADR 033's top-level-only rule lifted and the health check taught to leave such notes alone.
- **The direct parent's note** (`Projects/sympose/Plan.md`'s colour in `Projects/sympose/sympose.md`). Same files, many places to look; a deeper folder would need a note in every folder above it.
- **Sympose's own settings file.** Not in the vault, so the colour would not travel with it or show in Obsidian, against ADR 064's choice that the note is the source.
- **A flat property per folder** (`color_sympose: ...`). Obsidian's Properties panel would list them but folder names with spaces or slashes make bad keys, and there would be no single block for the app to own.
- **A list of strings** (`- "sympose #7c3aed #b98cff"`). Visible in Obsidian's panel, but a format of our own to parse and to explain; a map is plain YAML.
- **Resolving the nearest colour in the page.** The server already knows each note's path and the entries; a second copy of the rule in the page would have to match it.
- **Colouring the tree rows as well.** The colour was asked for to tell projects apart in the nebula; ADR 087 colours only the nebula for a top-level folder, and a coloured tree is one more surface for the vault owner to read, which he has declined for other features.

## Test plan and what was checked

- `tests/test_subfolder_colors.py` (the property read and its bad values, the nearest folder, the text edit keeping every other line and CRLF, the save: in place, creating the note, clearing, refusals, a changed note, and the carry for a rename, a move inside one note, a move to another note and a merge) and `tests/test_server_subfolder_colors.py` (the routes, the node and tree fields, the legend's `colored_by`, a rename and two kinds of move through the real handlers).
- In the web app: `folder-color-api`, `folder-color-dialog`, the row menu (offered below a top-level folder only, and only when wired) and the legend.
- The real app on a scratch vault (headless): right-click `Projects/sympose`, Folder colour, Violet, Save wrote the entry into `Projects/Projects.md` and nothing else; the nebula drew the `Plan` note violet and listed `Projects/sympose` in the legend; a deeper folder took its own colour; renaming the folder carried both entries and said so; clearing both left the note as it started.
- The reference library says how to do it (`The web app.md`, a new entry), with two retrieval messages: `auto` was 69 of 75 before and is 71 of 77 after, both new messages passing and the same six failures as before (`gemma2:9b` search and `nomic-embed-text`, the synthetic vault).
