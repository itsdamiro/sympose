# 072 — How a persona acts on the vault: four modes the user chooses, all ending in the user's Accept, and her edit tool in two shapes

> **Status: Proposed (2026-10-04).** Not built. Slice 5 of #21: the persona's side of ADR 042 (amended), ADR 069 (comments) and ADR 070 (the store). Web app only; the terminal is not expected to edit notes.

## Context

Everything the user sees is built: proposals are stored (ADR 070), drawn as tracked changes in the open note, accepted or declined one by one or for the whole note, listed under Drafts (ADR 071), and comments are written and kept (ADR 069). What does not exist is the persona making a proposal, and her reading the comments. Until then proposals exist only when made in code or by tests.

The user wants how much she does on her own to be their choice, set the way Claude Code's permission modes are, and decided on 2026-10-04 that **in every mode the user has the last say, by clicking Accept.** No mode writes to the vault on its own. The reason is who the notes belong to: the user is a writer, and a wrong edit to their own words costs more than an extra click. Claude Code's accept-edits and auto modes write to disk at once and rely on the mode being chosen up front plus a rewind; Sympose takes the stricter line on purpose. This replaces ADR 042's reserved second tier (direct writing, a per-persona per-folder opt-in gated on a faithfulness bar): it is not pursued, and nothing in this record reserves it.

## Decision

**Four modes, one setting per persona** (`edit_mode`, kept with her other settings, not a literal in code). They differ in how much she does before the user's Accept, never in whether the Accept is needed:

| Mode | What she does before the user's Accept |
|---|---|
| `plan` | She talks about a change and may describe it in chat, but proposes nothing: her edit tool is not given to her, and the prompt tells her so. |
| `manual` (default) | When asked, she proposes tracked changes in the open note, and the user accepts or declines each one (ADR 042). A new note she proposes is a draft (ADR 071). |
| `accept` | Her edits to the open note are applied to the editor's text as soon as she makes them, drawn as changes the user can undo; the user's Accept (or the ordinary save) is what puts them in the file. If autosave is on, her applied edits are not autosaved until the user has touched the note, so an edit never reaches the file without the user being there. A new note is still a draft. |
| `auto` | She acts on her own initiative: she may propose a change or a new note without being asked, to the open note and to others she has been given, and several at once. Everything she does waits as a pending change or a draft until the user accepts it. |

Nothing in any mode writes the vault: the file changes only through the user's Accept (the editor's save for an edit, the ordinary create for a draft, both with their existing `expected_mtime` and name-in-use refusals). Delete is not part of any mode: she has no tool that removes a note, and it stays soft through the bin (ADR 042).

**Auto and small models: a warning, as information.** Choosing `auto` shows a note specific to the model the persona uses, from a table of what was measured (like `lookup.MEASURED`). The user's Accept does not make a wrong change harmless: a change that looks right and is wrong can be accepted by mistake, and `auto` puts more of them in front of the user. So:

- For `gemma2:9b`: a patch right 29 times of 36, an edit applied but wrong 2 times of 36, and a price invented once in 4 when the request needed a fact the note did not hold (ADR 042, Measured). Read each change before accepting it.
- For a model smaller than `gemma2:9b`, or any model not measured: nothing is known about how faithfully it edits, and smaller models are expected to be worse, not better.
- For a model measured as faithful (Gemini Flash, 36 of 36 on the same set): the shorter form, measured on a small set of invented notes only.

It is information, not a block: the user can choose `auto` with any model. The same note, shorter, is shown beside `accept`.

**What she can edit in the first version: the note open in the editor, and new notes.** A passage can only be quoted from text she has seen word for word. In `auto`, "others she has been given" means notes opened in full inside the turn through the `vault_lookup` tool loop (ADR 040), which is a later step; in the first version `auto` differs from `manual` by acting unasked on the open note and by proposing new notes. Asked to change a note that is not open, she says so and asks the user to open it. The edit is checked against the text the editor holds, which can be ahead of the file, so the chat request carries the open note's path and the editor's current text.

**Her edit tool, in two shapes, one parser** (the pattern of ADR 041's memory): a model that can call tools is given `propose_edit(find, replace, say)` and `propose_note(text, title, say)`; a model that cannot writes a marked block in its reply, which Sympose reads, files as a proposal and removes from what is shown. Both end in `note_changes.propose_edit` or `propose_create` (ADR 070), which refuse a passage not found exactly once. The prompt must not contain look-alike markers: Spike B found a small model anchoring on the prompt's own end marker.

**She sees the open note and its comments with the user's message,** under a size cap: the note's text (new category `open_note` in `/share`, ADR 031, withheld from a cloud model until approved) and its unresolved comments, labelled new since the last message or earlier, under a cap (ADR 069, category `annotations`). Nothing extra is sent when no note is open in the editor, and not in `plan`. Whether the whole note is sent every turn or only under a cost rule is a setting, not a trigger written into code: what to do with it is her judgment, not a phrase list (ADR 042's rule on structural detection and judgment).

**Two proposals on one passage** (a known bug, ADR 070): `propose_edit` refuses, or replaces, a proposal whose passage overlaps one already waiting, and Accept all skips a change whose range another change in the same pass already changed. Needs a test for each side. `auto` makes this likelier, since she may propose unasked.

**The list refreshes at the end of a chat turn,** since that is when she proposes (ADR 071).

## Consequences

- A persona can act on the vault for the first time, and in every mode the vault changes only when the user clicks Accept. The risk that remains is a wrong change accepted by mistake, which is why the figures are shown rather than hidden.
- A new setting, a model-specific note table, a small tool pair and a marker parser, a `/share` category, and the prompt text for four modes. Each prompt change needs a retrieval eval before and after.
- The terminal sees `plan` only: it can say a change is waiting and point to the web app.
- No undo store and no direct-write path are needed: the editor's own undo covers `accept`.

## Open questions

- **Per persona or per folder.** The first version is per persona; narrowing by folder is not designed.
- **How `auto` limits itself:** how many unasked proposals in one turn, and whether she may propose on a note she was not shown. Set from measurement and use, not guessed.
- **The cap on the note's text and on the comments**, and whether a note longer than the cap is sent in part.
- **How faithful the marker shape is against the tool shape**, on `gemma2:9b` and Gemini Flash, with the real prompt (not Spike B's), which is the measurement slice 5 starts with; and whether the figures above hold on a longer note.
- **Where the note table lives and how a model gets an entry** (a measurement script and a row, like `lookup.MEASURED`).
- **`accept` mode and an applied edit the user then edits over:** the same outdated rule as a pending change, or just a text change; settled when built.

## Alternatives rejected

- **A mode that writes the vault without the user's Accept (ADR 042's reserved second tier).** Rejected by the user: the last say is theirs in every mode. It also removes the need for a write-faithfulness bar as a gate, an `expected_mtime` of its own and an undo store.
- **No `auto` mode, only plan, manual and accept.** Rejected: `auto` is the user's choice of how much initiative she takes; with every change pending it carries no more than the risk of a wrong change accepted, which the warning addresses.
- **One note for every model.** Rejected: it would be ignored; the figures differ by model and the user should see the ones for the model in use.
- **Applying edits to the file in `accept` mode.** Rejected: the save, or the Accept, stays the user's act.
- **Whole-note rewrites instead of patches.** Rejected in ADR 042 and by Spike B: a rewrite is applied wrong far more often (9 of 36 against 2 for a patch) and shows nothing exact to review.
- **Sending the open note only when the message looks like an edit request.** Rejected: a phrase list, and a missed phrase means a silent refusal.
