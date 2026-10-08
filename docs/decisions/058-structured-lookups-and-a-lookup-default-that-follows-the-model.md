---
type: decision
status: accepted
date: 2026-10-02
projects: [sympose]
concepts: [Vault tools]
amends: [40]
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 058 — Structured lookups (`find_notes`, ADR 035's layer 4) and a `vault_lookup` default that follows the model

> **Summary.** A new read-only tool, `find_notes`, answers structural questions (links, tags, properties, folders) with optional combined filters, and the `vault_lookup` default now follows the model. The existing tools took only text, so "which notes link to Atlas?" had nothing to work from. One tool with filters was chosen over one per question because every tool description is sent on every turn.

> **Status: Accepted (design, 2026-10-02: damiro found both the tool and the default sound).** Built the same day: `find_notes` and `by_model`; see "As built" and "Measured". Completes ADR 035's layer 4 ("numbers the map does not hold") and amends ADR 040 (the default of `vault_lookup`). Tracked on #78 (layer 4) and #85 (the fit decision).

## Context

A persona that can call tools (ADR 040) has `search_notes`, `open_note` and `list_notes`. All three take text: a query, a name, a folder. A request that is about the *structure* of the vault has nothing to work from: "which notes link to Atlas?", "everything tagged `idea` in Projects", "the films I have not watched yet" (a property), "how many notes mention backups?". The data to answer them is already computed: the snapshot holds every note's properties and body, the manifest its tags and links, `connections` its backlinks. Only the question has no door.

The reason to answer them with a tool and not with more in the prompt is cost. The whole vault's names and links are about 11,000 tokens on a 669-note vault, which does not fit a local model's window and would be paid for on every message by a cloud one. A tool returns only the notes that match, so only they use tokens, and only when she asks.

Separately, `vault_lookup` defaults to `auto` for every model, so a user on a model that can call tools gets none of this until they find the setting. That is the wrong default for those models, and the user must still be the one who decides.

## Decision

**One new tool, `find_notes`, read-only and inside the persona's scope like the other three.** One tool with optional filters, not one tool per kind of question: each tool's description is sent on every turn, and a model chooses among fewer tools more reliably. Every filter is optional, they are combined (all must match), and none is guessed:

- `folder`: notes under that folder (and its subfolders).
- `tag`: notes with that tag in their properties (the tags the manifest already reads).
- `property` and `value`: notes with that property; with `value`, whose value equals it (case ignored, a list property matches any of its entries, a `[[link]]` value by the note's name, the same reading ADR 030's property passages use).
- `links_to` and `linked_from`: notes that link to, or are linked from, the named note (by the connections' own link graph, bracketed links in the body and in properties).
- `text`: notes whose body contains that text, case ignored. This is the "how many notes mention X" case; it is an exact substring, not a search by meaning.

**What comes back.** The count of matching notes first, then the notes alphabetically by file name, numbered, with the value of the property when one was asked for ("Dune (Films/Dune.md), watched: no"), at most 100 and then "and N more", as `list_notes` does. A filter that matches nothing says so. A note named in `links_to` that does not exist is "not found". At least one filter is required: no filter would be the whole vault, which `list_notes` and the map already cover in the shapes that fit.

**Gated like what it returns** (ADR 031): names are `notes`; a call that filters on or shows a property or a tag needs `properties` as well, because it reveals them. A cloud model that may not receive them gets the withheld line and a count, never the names. The turn record keeps `{tool: "find_notes", filters, found}`, never names.

**Cost is the persona's to weigh and the user's to bound.** It is part of `ask`, so it shares `vault_lookup_rounds` and costs a model call per lookup, as the others do. It is not in `auto`, where the persona has no tools.

**The default of `vault_lookup` follows the model, and the user decides.** `vault_lookup` gains a third value, `by_model`, which becomes the default (what an unset setting means):

- `ask` when the model in use can call tools **and** has been measured fit (ADR 040's bar: no vault fact stated without a lookup that turn, no more failures than `auto` on the same cases). The list starts with `gemini/gemini-flash-latest`, the one model measured, and grows only by measurement, a line in code and in the ADR for each.
- `auto` otherwise: a model that cannot call tools, one that can but is not measured, and every model when `vault_lookup` is `auto`.
- A user's explicit `auto` or `ask` always wins. `ask` on a model that can call tools but is not on the list is allowed, as today; the setting's description says which models are on the list and what the default does for the model in use now.

The existing safety stays: a model that fails with the tools twice is not given them again (ADR 040), the turn then runs `auto`, and the record says which mode ran.

## Why the list and not "any model that can call tools"

ADR 040 measured a small cloud model that could call tools and answered "I see no mention of the subject" without having looked, the failure the project treats as a bug. A tool-capable model is not the same as a model that uses the tools when it should. The list keeps the default honest, and the user can still choose `ask` anywhere.

## As built

- `engine/lookup_find.py` (`find_notes`: the seven filters, the count, the 100-name cap, the gate), `engine/lookup_scope.py` (the persona's notes and how a tool names one, moved out of `lookup_tools` so the four tools share it) and `engine/lookup_result.py` (the tools' result type). `connections.link_graph` is the one new public door onto the link graph. A tag matches its nested tags (`idea` finds `idea/new`), a yes or no value is compared as the boolean YAML read it as, and a note named in `links_to` or `linked_from` that is not there is "not found".
- **A listing teaches the filter.** A first run found that asked "which of my films have I not watched?", the persona listed the folder and then opened every note to see their properties, because nothing told her a `watched` property existed. `list_notes` and `find_notes` now end with the property names the listed notes have ("Properties these notes have: watched (4), year (3). Filter on one with property and value."), only when the cloud model may receive `properties`; names of properties are as much the user's data as their values. The tool's own description also says to use it instead of opening notes one by one.
- `vault_lookup` is `by_model` unless the user chose `auto` or `ask` (`lookup.mode`, `lookup.chooses_ask`); the models it asks on are `lookup.MEASURED`, one line each. The settings row (terminal and web) lists the three values with `by_model` as the default. The tests start with `MEASURED` empty (`tests/conftest.py`), like the other shipped defaults, so no test runs a tool loop by accident.
- The prompt for `ask` (`HOW_YOU_WORK_ASK`) names the four tools and tells her to give `find_notes`'s count and never a guess; the reference notes (Settings, How Samantha uses your notes, Choosing a model, Not built yet) say what the default is and which models it covers.

## Measured (2026-10-02, `gemini/gemini-flash-latest`, real calls on scratch data only)

- **ADR 040's cases with four tools present** (`tests/live_lookup_cases.py ask`, 16 cases, 3 runs each): pass 47 of 48 (ADR 040 with three tools: 46 of 48 in `ask`, 44 of 48 in `auto`). Every one of the 21 turns that need a note looked something up, and 15 of the 21 turns that need none looked nothing up (the same 15 as before: the six that did search were a trip and an unknown name, as then). The one failure is a case's wording pattern: the reply said the physicist was not known and not in the notes, which is the right answer. No reply stated a vault fact without a lookup. The bar of ADR 040 is met with the fourth tool, for this model.
- **`find_notes`** on seven invented films and notes, 3 runs each: a property ("films I have not watched": Dune and Heat) 3 of 3 correct; a tag 3 of 3 in one call; "which notes link to Arrival" 3 of 3 in one call; "how many notes mention backups" 3 of 3, the count read from the tool (2); "any notes tagged western" 3 of 3 answered no from a count of 0, in one run with a second lookup of the word itself; small talk 3 of 3 with no tool. Before the listing named the properties, 2 of 3 runs on the property question opened the four notes one at a time; after, 4 of 5 went straight to the filter (the fifth still opened them, with the right answer).
- **Not measured:** a folder of more than 100 matches, a cloud model that may receive `notes` but not `properties` through a real turn (covered by tests only), another model than Gemini Flash (so the list holds one model), and a vault of the user's own.

## Not built

- All of the above.
- Meaning-based connections ("notes like this one"), which stay with the embeddings (ADR 027) and #78 layer 3.
- Sorting by a property or a date, and combining filters with "or": a user's question is answered by listing the matches, or by two calls.
- A per-persona `vault_lookup` (ADR 040 left it open).

## Alternatives rejected

- **Put the vault's names and links in the prompt.** Measured at about 11,000 tokens on 669 notes: past a local model's window, paid on every cloud message, and small models follow long lists poorly (ADR 039).
- **One tool per question** (`backlinks`, `notes_with_tag`, `count_mentions`). More descriptions on every turn and more to choose among, for the same code underneath.
- **The engine reads the message and applies the filters** (before the model sees it). That decides what counts as a structural question from its wording, a phrase list the project has rejected; the model chooses, the engine only runs it.
- **`ask` by default for every tool-capable model.** Rejected for the measured reason above.
- **A new setting for the default.** `vault_lookup` already is the setting; a third value keeps one place.
