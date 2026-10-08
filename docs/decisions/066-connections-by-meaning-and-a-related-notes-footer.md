---
type: decision
status: accepted
date: 2026-10-04
projects: [sympose]
concepts: [Grounding]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 066 — Connections by meaning: the persona's "possibly related" line and a Related notes section in the notes panel

> **Summary.** Connections by meaning: each note is the average of its passages' vectors with the vault's average subtracted, and its neighbours above a bar feed the persona's "possibly related" line and a Related notes section in the notes panel. Notes about the same thing with no link, tag or folder were invisible to each other. It needs no model call and stores nothing new, but a vault whose notes were never embedded shows nothing.

> **Status: Accepted, built (2026-10-04), designed with damiro.** Closes the last piece of #78 (whole-vault awareness). Builds on ADR 035 (mechanical connections, which kept the meaning-based half for a separate pass), ADR 027 (search by meaning and its cache of vectors), ADR 031 (what a cloud model may receive) and the notes panel's `CollapsibleFooterSection`.

## Context

A note's connections today are facts read off the vault: it links to or from another note, shares a tag or an alias, or sits in the same top-level folder (ADR 035). Two notes about the same thing with no link, tag or folder between them are invisible to each other, to the persona and to the user. Search already holds what is needed to see them: every passage of every note has a vector in the embedding cache (ADR 027), so how close two notes are in meaning is a sum over numbers already stored, with no model call.

ADR 035 kept this apart on purpose: a real link is an exact, explainable fact and "close in meaning" is a fuzzy one, so mixing them before either was measured alone would make a wrong answer hard to trace. That split stays.

The notes panel has a pinned footer made of `CollapsibleFooterSection`s (stackable, foldable, any content, flexing height) that so far holds only the recent notes. A list of the notes related to the open note, each with a link and a relevance meter, is the first thing that belongs there for a reason other than recency, and it shows the user the same connections the persona is given.

## Decision

**One computation, two readers.** For a note, its closest notes by meaning: each note is represented by the average of its passages' vectors; the vault's own average note is subtracted from every one and each is scaled to unit length again (so a hub note, or the common ground every note in a vault shares, is not close to everything); the note's neighbours are the notes whose representation is closest to its own by cosine, and a neighbour is kept only above a bar. Measured below: without the subtraction the median pair of unrelated notes already scores 0.74. The same function serves the persona and the panel, so what the user sees is what she was given.

**Never presented as a link.** In the prompt it is a separate line on the note's passage, worded as close in meaning ("possibly related"), after the mechanical connections and never merged into them; a note already named there, or already grounded in the turn, is not repeated. In the panel it is a list under its own heading.

**Only above a bar; some notes get none.** A weak neighbour is worse than none, so a neighbour is kept only at a similarity of **0.40 or more** (after the subtraction above), at most **3** for the persona and **5** in the panel. The search threshold (0.72) is a bar for a message against a passage and does not carry over: it would keep nearly every pair here. The bar is a property of the embedding model and of how short a vault's notes are, so the number is not shown to the user; the user chooses a **level**, the setting `connections_relevance` (damiro, 2026-10-04: "the temperature of relevancy"):

| Level | Bar | Measured |
|---|---|---|
| `close` | 0.50 | few neighbours, nearly all clearly related (about 40% of notes get any) |
| `balanced` (default) | 0.40 | roughly 85 to 89% right on both vaults (about 70 to 85% of notes get some) |
| `wide` | 0.30 | many neighbours, about half of the extra ones loose (it opens ideas) |

0.30 is the lowest level offered; below it a reading of the sample found mostly noise. The levels are a property of `nomic-embed-text`; a different embedding model needs its own bars, measured the same way (#4). One setting for both readers, so the persona's line and the footer always agree.

**The meter is a calibrated relevance, not the raw cosine.** The percentage is the similarity placed between the chosen level's bar (0%) and **0.70** (100%), the point where about one note in ten has its best neighbour on both vaults measured; it shows an order and a rough strength, never a probability.

**The knobs: `connections_by_meaning`, `auto` or `off`, default `auto`** (a setting in the shared registry, so the terminal and the web list it; the Context group). `auto` computes them when the embedding model is a local one that answers, and quietly does nothing when it is not (the same behaviour as search by meaning in `auto`); `off` computes nothing, adds nothing to the prompt and hides the footer section. A cloud embedding model is never used for this: the notes would be sent to it (ADR 031, `sharing.embeds_notes`).

**Privacy.** What reaches a cloud chat model is a list of note titles close in meaning, which is the same kind of thing the `connections` category already covers (a note's neighbours, by title), so it is under that category and needs no new one: a user who has not approved `connections` sends none of it, and the reply's header and `/share` already name the category. The footer section is the user's own screen and sends nothing.

**Where it is drawn.** A `RelatedNotesFooter` section in the notes panel's footer, shown when a note is open in the editor: a caption "Related notes", then one row per neighbour (the note's name, opening it in the editor like every other note link, and a slim meter with the percentage). It uses `CollapsibleFooterSection` and its tokens and the closest existing list's row, not new values. It says nothing while the index is still being built, and shows no section at all for a note with no neighbour above the bar.

**Parity.** The persona's line is the same in both channels. The panel is the web app's alone, as the notes panel is; the terminal's way to see the same list is not part of this record (to decide once the list has proved useful).

## Measured (2026-10-04, `nomic-embed-text`, cached vectors only, no model call)

Two vaults: the public Obsidian help docs (176 notes) and a personal vault (617 notes, short notes and quotes among longer ones; its contents stay out of this repository).

- **Why the subtraction.** Plain averaged cosine: median pair 0.74, the best neighbour of half the notes 0.89, and at 0.82 only 2% of notes have none, so no bar separates related from unrelated, and the hub note (Home) tops many lists. After subtracting the vault's average: median pair about 0, 99th percentile 0.50 (docs) and 0.33 (personal), and the hub no longer leads.
- **The bar, by reading neighbours that are the new information** (not linked, in another top-level folder), judged by one reader from titles. Personal vault, 20 pairs from a random sample at a floor of 0.35: about 55% right, the weak ones at 0.35 to 0.41; at 0.40 and above, 8 of 9 right. Docs, 26 pairs at 0.40: about 85% right. Weak examples at the bar: a shortcut note beside a cursor note, a recovery note beside a plans-and-storage note.
- **Coverage at 0.40, any neighbour:** 85% of the docs' notes and 68% of the personal vault's have at least one; the others get none. At 0.50 it is 59% and 41%, which is why the bar is not higher.
- **Against the links people wrote** (a weak yardstick, since people link for navigation too): the linked note is in a note's top 5 by meaning 22% (docs) and 25% (personal) of the time against 3% and 1% by chance, and the median rank of a linked note is 21 and 30 of 176 and 617, so meaning and links mostly find different things, which is the point of showing both.
- **Cost.** 1 ms to compare all 617 notes with each other and 0.35 ms for one note against 5,000, with numpy (the optional `fast` extra); the plain-loop path is slower and is checked when built. No new store.

**Limits of this reading.** One reader, titles and not full notes, about 45 pairs, two vaults, one embedding model. It supports the bar and the 0.70 end of the meter as a first setting, not as a finished figure.

**The persona's answers, with a real chat model (`gemma2:9b`, the Obsidian help docs, scratch profiles; the driver is not kept).** Six plain factual questions, twice each, with the line off and on: 11 of 12 matched with it off, 12 of 12 with it on, so answers did not get worse. Six link traps (is note A linked to note B, where B is close in meaning to A and not linked), twice each: with the line in her prompt in 10 of 12 replies, none stated the close-in-meaning note as a link, read by hand (a keyword counter flagged 5 of 12 against 3 of 12 off, but the flagged ones were true statements about other links of the notes). She also did not use the line in a reply to a question about links, which is not the question it is for. **One problem found that is not from this feature:** with the feature off and on, in 2 of 2 replies each, she said "Workspaces links to Workspace" for two notes that are not linked, inferring it from their similar titles; recorded for a later grounding pass, not changed here.

**Not measured.** The plain-loop cost without numpy; a question that asks what is related to a note (where she should use the line, said as a guess); a third vault (#2).

## Consequences

- A note's neighbours are found without a model call, from vectors already cached; nothing new is stored.
- A user can browse their vault by meaning, not only by link, and see why the persona says two notes belong together.
- A vault whose notes were never embedded (the model is missing, the first index still running) simply shows no related notes; nothing fails.
- The relevance percentage is a convention of this feature; the record says how it is made so that it is not read as a probability.

## Alternatives rejected

- **Merging these into the mechanical connections.** The persona could state a guess as a fact; ADR 035's reason, unchanged.
- **The raw cosine as the percentage.** Reads as a weak match when it is a strong one on this model.
- **A new approval category.** The thing sent is the same kind of thing `connections` already covers, titles of neighbouring notes; a second category would ask the user the same question twice.
- **A background job that precomputes every note's neighbours.** Nothing here is slow enough to justify a store and its invalidation until measured; the mtime-keyed cache `connections.py` already uses is tried first.
- **A free number for the bar, or a knob for the count or the meter.** The number means nothing to a user and is wrong for another embedding model; three named levels carry the choice the user really has (how loose a relation may be). The count and the meter's top are measured conventions, not preferences. A footer slider is possible later, over the same setting.

## Built (2026-10-04)

- `engine/related.py`: `neighbours` (the vault's average note taken away, cosine, the level's bar, cached per set of passage vectors), `for_hits` (the persona's `related` field, at most 3, never a note already grounded or already a connection), the two settings and `percent`. `semantic.passage_vectors` (gated like search: keywords mode, a cloud embedding model, a model not answering) and `VectorSet.row`.
- The prompt: `RELATED_TO` says "Possibly related (close in meaning, a guess from the text, not a link; never say they are linked)", after the mechanical connections; `sharing` strips it, counts it once with the connections and lists the `connections` category when it is sent. Wired in `turn_evidence` and in the lookup tools, so a turn's own search and her own lookups give the same passages.
- Settings `connections_by_meaning` (`auto`, `off`) and `connections_relevance` (`close`, `balanced`, `wide`) in the shared registry, group Context, so the terminal's `/settings` and the web Settings list them with no more code.
- `GET /api/vault/related?path=&persona=` (`enabled` false only when off; a note the user hid is marked), `useRelatedNotes`, `RelatedNotesFooter` and `RelevanceMeter`, and a `trailing` slot on the shared `VaultTreeRow`. The section sits above Recent in the notes panel's footer, shown for the open vault note and never while a persona's own file is open.
- Tests: 41 test functions in Python (the engine, each run with numpy and without, with a fake model that reads a vector written in each note; the gate; the prompt; the endpoint) and 17 for the web; 18 of 19 mutations of `related.py` caught (the survivor is `>=` against `>` at an exact tie of two floats, an equivalent mutant), 14 of 14 of the web code. Real headless Chrome on a scratch copy of the docs: the section's icon, text, caption and row height line up with the Recent rows (x = 288 and 308, 28 px); `close`, `balanced`, `wide` and `off` change the list as designed against the real embedding model.

**Review (`/code-review` at its second-highest level) found, and what was done.** Fixed: the cache of notes had no lock where its siblings do (two threads could both evict and raise `KeyError`; a deterministic test with a slow `pop` now pins it); the text a user reads before approving `connections` did not say that notes close in meaning are in it (now it does, with a test); an empty answer given while the first index was still being built stayed until the user changed note (the endpoint says `indexing`, the web asks again every five seconds while it does); averaging the vectors in plain Python took 0.57 s for 6,555 passages once per vault change (with numpy it is one grouped sum, `VectorSet.note_set`, and every test runs on both paths); the module reached into a private helper of `grounding` (uses `scope_index`). Checked and not a defect: the two title derivations are the same code path (`title`, else `name`, else the file stem), so a note is not named twice as a connection and as related; the new wrapper in the footer keeps it inside the panel at 900, 520 and 420 px with many recent notes (measured in Chrome), both sections scrolling inside themselves. **Left as limits, knowingly:** a vault of a few notes gets no neighbours (the vault's average note is only an average of a vault; with one note the centred vector is zero, with two they are opposite), which is silent; a lookup the persona makes herself skips only the notes in that result, not those grounded earlier in the turn (the automatic path skips all of them); two notes with the same title in different folders count as one when a connection is named.

## Not built yet

- A terminal way to see the same list; a footer slider over the level; bars for another embedding model (#4); a line in the reference library about the two settings (needs the retrieval eval before and after, `tests/live_retrieval_cases.py -v`).
