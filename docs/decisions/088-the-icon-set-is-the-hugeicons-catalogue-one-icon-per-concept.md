---
type: decision
status: accepted
date: 2026-10-17
projects: [sympose]
concepts: [Vault upkeep]
amends: [062, 064, 087]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app]
---

# 088 — The icon set is the Hugeicons catalogue, one icon per concept

> **Summary.** The icon a folder or a persona can have is now chosen from about 780 icons (the 68 hand-named ones and a catalogue of 712 more) instead of 68, found by typing the icon's name. The catalogue keeps one icon per concept (a happy face but not a sad one, mail but not envelope as well) and leaves out brand logos and interface symbols. It costs about 0.8 MB of web build, which a page served from the user's own machine does not feel.

> **Status: Accepted (2026-10-17), designed with damiro.** Amends ADR 062 (the persona's set is no longer a curated few dozen), ADR 064 (same for a folder) and ADR 087 (it rejected "the whole catalogue"; this builds the part of it that folders and personas can use).

## Context

ADR 087 shipped a curated set of 68 icons and rejected offering the whole Hugeicons library because it "bundles every icon" and the server would no longer vet the name. The first user of the dialog looked for a puzzle and found none: a curated list is always one icon short, and folders are personal (a guitar, a dumbbell, a puzzle). The library has 6,067 icons, but most are not things a folder is about: 4,500 once the numbered variants of one drawing are folded together, and of those most are brand logos, file formats, arrows, weather and mood variants, and interface states (add, remove, lock, off).

The two reasons for refusing the library no longer held when measured. The app is served from the user's own machine (`127.0.0.1`), so a build 0.8 MB larger is not felt, and nothing needs lazy loading. The server can still vet a name if it holds the list.

## Decision

**The set is the hand-named icons plus a catalogue.** The 68 hand-named icons in `persona-icons.ts` keep their names, because notes already name them (`icon: film-roll`). The catalogue is a list of Hugeicons names in `scripts/icon_catalogue.txt`, one per concept, from which `scripts/gen_icon_catalogue.py` writes `ui/src/lib/icon-catalogue.ts` (name to icon, what the page draws) and `sympose/icon_catalogue.py` (the names, what the server accepts). A catalogue name is the Hugeicons name in kebab-case without its number (`Puzzle` is `puzzle`, `MailLove01` is `mail-love`). A name or an icon a hand-named entry already has is skipped, so a hand-named icon always wins its name. A test fails when the generated files are not what the list makes.

**One icon per concept.** The list was cut in two passes (the rules are in this record, the list is the result):

- By rule, from 6,067 to about 2,500: the numbered variants of a drawing folded to the first; the families that are interface (add, remove, check, lock, off, arrows and directions, alignment, text formatting, layout, panels, cursors, sorting, filters, shapes, maths symbols); AI and crypto; and the control words of a form.
- By reading, to 712: brand and app logos; file formats and programming languages; the many weather variants (rain, snow and wind stay, not rain-with-lightning-at-an-angle); one face for a mood family (happy, angry, sleeping, in love, nerd, not the other forty); one mail, one chat, one clock, one folder per use; currencies beyond the common ones; the same thing drawn twice (the hand-named film roll, not a second film; the hand-named quote, not quotes; the hand-named graduation, not graduation cap).

The judgments are the user's to overrule one icon at a time: a name missing from the list is added to `scripts/icon_catalogue.txt` and the generator run again.

**What did not change.** The icon is still found by typing, in the browser; the few keywords per hand-named icon stay (`food` finds the chef's hat), and the catalogue is found by its name. The dialog and the persona card draw the icon from the same map. The server refuses a name outside the set, so what the page draws is still always a name Sympose knows.

**Personas share the set.** A persona proposing a new persona is still offered the 68 hand-named icons in its tool description (listing 780 names in every call would cost tokens on each one), but any name in the whole set is accepted.

## Consequences

- A folder or a persona can have an icon for a puzzle, a guitar, a camper or a kettlebell, without a pull request first.
- The web build is about 0.8 MB larger (about a quarter of it after compression).
- The picker's list is longer (about 780 names when nothing is typed). It scrolls; typing narrows it.
- A concept the list lacks is found by asking for it, and costs one line in a text file and one command.
- A newer Hugeicons release adds nothing on its own: the list is fixed, so the set changes only by a deliberate edit.

## Alternatives rejected

- **All 6,067 icons.** Six thousand names with no order (`arrow-down-03`, `bitcoin-ellipse`, `file-off`), most of them no folder's subject, and a picker nobody can look through. The cut is the point.
- **Lazy-loading the catalogue when the picker opens.** It would keep the first page small, but the page is served from the user's own machine, and a folder drawn with a catalogue icon would have to wait for the chunk. Right if the web app is ever served over a network.
- **Searching a hosted icon API.** A network call per keystroke for a local-first app, and the icon would stop being a vetted name in a shared vault.
- **A model that picks the icon.** Same reason as ADR 064: a guess the user cannot see or correct.

## As built (2026-10-17)

- `scripts/icon_catalogue.txt` (the list), `scripts/gen_icon_catalogue.py` (writes both files; `--check` reports whether they are current), `ui/src/lib/icon-catalogue.ts` and `sympose/icon_catalogue.py` (generated).
- `persona-icons.ts`: the hand-named block is `CURATED`; `ICON_SET` is the catalogue with it on top.
- `look.py`: `SUGGESTED_ICON_NAMES` (the hand-named, offered to a persona) and `ICON_NAMES` (everything accepted). A test pins the hand-named lists to each other, the catalogue files to each other and to the generator, and every name to the shape the server accepts.
