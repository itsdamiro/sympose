# 072 — How a persona acts on the vault: four modes the user chooses, all ending in the user's Accept, and her edit tool in two shapes

> **Status: Proposed (2026-10-04).** Not built. Slice 5 of #21: the persona's side of ADR 042 (amended), ADR 069 (comments) and ADR 070 (the store). Web app only; the terminal is not expected to edit notes.

## Context

Everything the user sees is built: proposals are stored (ADR 070), drawn as tracked changes in the open note, accepted or declined one by one or for the whole note, listed under Drafts (ADR 071), and comments are written and kept (ADR 069). What does not exist is the persona making a proposal, and her reading the comments. Until then proposals exist only when made in code or by tests.

The user wants how much she does on her own to be their choice, set the way Claude Code's permission modes are, and decided on 2026-10-04 that **in every mode the user has the last say, by clicking Accept.** No mode writes to the vault on its own. The reason is who the notes belong to: the user is a writer, and a wrong edit to their own words costs more than an extra click. Claude Code's accept-edits and auto modes write to disk at once and rely on the mode being chosen up front plus a rewind; Sympose takes the stricter line on purpose. This replaces ADR 042's reserved second tier (direct writing, a per-persona per-folder opt-in gated on a faithfulness bar): it is not pursued, and nothing in this record reserves it.

## Decision

**Four modes, set per persona with a global fallback** (`edit_mode`). A persona's own `edit_mode` is the setting that counts, read from the user's untracked `persona.local.yaml` first (the same override file the chosen model lives in, ADR 046, so a user's choice never edits a shipped file) and then from the shipped `persona.yaml`; the global `edit_mode` in the settings registry (listed in both channels like every other setting) applies only to a persona with neither. Both ship as `manual`: shipped Samantha has `edit_mode: manual` written in her file, a persona created in the app gets it written at creation, and the global setting is the fallback for hand-made files, so no persona can inherit a more autonomous mode she was not given on purpose. Neither value is a literal in code beyond the one default (ADR rule on settings). The warning below is shown when a user chooses `accept` or `auto` for a persona or globally, and names the model the persona uses. The earlier idea, inheriting a global mode only when the persona's model was measured as faithful, was dropped as a rule the engine would guess at; the explicit value in the file replaces it.

**The four modes** (they differ in how much she does before the user's Accept, never in whether it is needed):

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

## Measured (2026-10-04): the marker with the real prompt, on `gemma2:9b`

`tests/live_edit_cases.py`: Samantha's real system prompt, the open note and the instructions in the user turn, the marker shape (`<!-- propose_edit: {...} -->`), Spike B's nine edit requests, plus three messages where nothing should be proposed (a question about the note, thanks, "would it be better to..."). Invented notes only. Two runs per case (18 replies per variant), so these are directions, not rates. Spike B's bare prompt had 29 of 36 right for the same model.

| Where the instructions sit | Edits right | No proposal when none asked |
|---|---|---|
| A: before the note and the request (one run) | 3 of 9 | 3 of 3 |
| B: after the request, last in the message | 11 of 18 | 6 of 6 |
| C: B plus "this is a task, not a chat" | 4 of 18 | 6 of 6 |
| D: C plus a system-prompt line "you make the change by proposing it" | 12 of 18 | 2 of 6 |

What the replies show:

- **The persona costs about 20 points.** With Samantha's soul the model often chats about the note ("do you want me to try a rewrite?") instead of proposing; instructions placed last (B) help, as ADR 020 predicts for small models, and a firmer "task, not a chat" (C) made it worse.
- **A push to act causes unasked proposals.** D proposed a typo fix after "thanks" and a change after a "would it be better" question (4 of 6 messages). That is the behaviour `manual` must not have and `auto` is for: the wording of D belongs to `auto` only, B's to `manual`.
- **A passage that is not unique is refused, in the open:** "change the first Pack charger line" quoted a passage found twice, 0 of 2 matched, and the user would be told a change could not be placed, not shown a wrong one.
- **Some wrong patches are applied:** asked to add a bullet it wrote the new line without the list marker, and asked to add a section at the end it put an empty heading after "Schedule". Both are patches that find their passage and are wrong, the case a person must catch at Accept.
- **Her one-sentence explanation can misdescribe the patch:** for the section it said "added a Notes section at the end" over a patch that did not. The explanation shown beside a change is her claim, not a description of the diff; the diff is what the user reviews.
- **Not measured yet:** the tool-call shape; a longer note; more runs on `gemma2:9b`.

**Gemini Flash (`gemini/gemini-flash-latest`), same script, variants B and D, four runs per case (36 edit replies and 12 quiet replies each; the user approved a scratch cloud run, invented notes and Samantha's shipped prompt only):** 36 of 36 edits right and 12 of 12 quiet in both. The persona did not cost it anything, the pushier wording of D did not make it propose unasked, and it did not hit any of the failures above (it quoted a unique passage for the "first Pack charger" line, wrote the bullet marker, put the new section at the end). So the difference between the two models is large and the wording matters only for the small one; the table of what to show beside `auto` and `accept` (above) holds as written, with Flash's own figure now measured through the real prompt as well as Spike B's bare one.

## Built so far (2026-10-05): the setting, the persona's control and the warning (steps 1 and 2)

- **Engine.** `engine/edit_mode.py` (the four modes with a line each, the global `edit_mode` setting defaulting to `manual`, `for_persona`, and `note(mode, model)`, the measured figures by model); `profile` reads `edit_mode` as well as `model` from the untracked `persona.local.yaml`, over the shipped `persona.yaml`; the row is in the settings registry under a new group "Editing", so both channels list it; shipped Samantha has `edit_mode: 'manual'`.
- **Saving.** `persona_model` now merges: a pick keeps the other key in `persona.local.yaml` (it used to write `model:` alone, which would have erased the mode), clearing the last key deletes the file, and a mode that is not one of the four is refused.
- **Routes.** `GET` and `PUT /api/personas/{handle}/edit-mode` (`server_edit_mode_handlers.py`): the mode that counts, whether it is hers or the global one's, the four modes with a line each, and the note for `accept` and `auto` computed for the model she uses, so the screen holds no figure of its own.
- **Persona page.** An "EDITS" chip beside FILES (`PersonaEditMenu`, `useEditMode`): it reads the mode ("(default)" when she follows the Settings page), opens the four modes, and "Use the default" clears her own. Choosing `accept` or `auto` asks first with the note for her model, through `confirm()` so it follows the user's Notifications setting (dialog or the one-line form); with confirmations set to none the choice is applied at once and the same note is shown as a notice, so the figures are never skipped.
- **Checked** in headless Chrome on a scratch copy: the chip and menu, the dialog with the `gemma2:9b` figures, no file before confirming, `edit_mode: auto` written only to the local file, "Use the default" deleting it.
- **Not built yet:** the marker parser and tool pair, the prompt wording per mode, the `open_note` and `annotations` share categories, `accept`'s behaviour in the editor, the duplicate-proposal fix, and the note beside the global setting on the Settings page (its row shows the mode only).

## Built so far (2026-10-05): the edit tool and its turn (step 3, backend)

- **The tool pair, one parser.** `engine/edit_tools.py`: `propose_edit` and `propose_note` as tool calls, the same arguments as a marked block in the reply for a model that cannot call tools; a marker is filed and removed from what is shown, and one that cannot be placed (bad JSON, a missing field, a passage found twice, no open note) is told to the user in the reply and recorded as not saved.
- **The turn.** `engine/edit_turn.py` resolves what she is given from her mode (`plan`: no tool and no note, and a line saying she cannot change notes; the others: the tool or the marker, and the open note when there is one). The note, the request and the rules reach the model last in the user's turn (the note in a fence longer than any run of backticks inside it); the conversation stores only what the user said. The note is cut to a cap, the `open_note_cap` setting (12000 characters; a cut note says so, and she is told to propose only within what she sees); a change is still placed in the whole note. `run_turn` takes `open_note` and `edits`: only the web app sets them, so the terminal never gives her the tool. `POST /api/chat/turn` accepts `edits` and `open_note {path, text}`. A turn whose tools are refused is retried with the marker. `auto` differs from `manual` by wording only for now ("even if the user did not ask").
- **The duplicate-proposal bug is closed** on both sides (ADR 070).
- **The note is a share category (`open_note`, ADR 031).** A cloud model is not sent the note's text until the user approves the category; the persona is told a note is open but withheld (she cannot see or change it, and says so), the turn records it as withheld, and a sent note is recorded in the turn's cloud categories (the web's reply footer names it "the open note"). Local models always receive it. Only the open note is a category so far: one that sent nothing would only confuse the list.
- **Her comments (2026-10-05).** A third tool, `comment_on(find, text)` (or `<!-- comment_on: {...} -->`), files a comment of hers on a passage through the same parser and the same unique-passage rule; it is given only with a note open and never in `plan`. The editor draws her comments in the brand blue and the user's in amber (a light tint with an underline, measured at 4.4:1 light and 6.1:1 dark for the note's text on it), and a line holding both shows two dots; the dot is drawn in the line's own left space, so a comment never changes the editor's width.
- **Not built:** the comments travelling to her (`annotations`, with the category when they travel); the screen sending `open_note`; `accept`'s behaviour in the editor; the refresh of the Drafts list at the end of a turn; the per-mode wording measured again with this exact text (the figures above are for the script's wording).

## Alternatives rejected

- **A mode that writes the vault without the user's Accept (ADR 042's reserved second tier).** Rejected by the user: the last say is theirs in every mode. It also removes the need for a write-faithfulness bar as a gate, an `expected_mtime` of its own and an undo store.
- **No `auto` mode, only plan, manual and accept.** Rejected: `auto` is the user's choice of how much initiative she takes; with every change pending it carries no more than the risk of a wrong change accepted, which the warning addresses.
- **One note for every model.** Rejected: it would be ignored; the figures differ by model and the user should see the ones for the model in use.
- **Applying edits to the file in `accept` mode.** Rejected: the save, or the Accept, stays the user's act.
- **Whole-note rewrites instead of patches.** Rejected in ADR 042 and by Spike B: a rewrite is applied wrong far more often (9 of 36 against 2 for a patch) and shows nothing exact to review.
- **Sending the open note only when the message looks like an edit request.** Rejected: a phrase list, and a missed phrase means a silent refusal.
