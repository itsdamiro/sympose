---
type: decision
status: accepted
date: 2026-10-06
projects: [sympose]
concepts: [Persona edits]
amends: []
supersedes: [75]
tags: [type/decision, status/accepted, project/sympose, topic/web-app]
---

# 076 — Attach a marked passage to the message

> **Summary.** Instead of automatic chips, the user attaches a marked passage to the next message with a paperclip on a tracked change, an applied edit or a comment, and it shows as a chip above the composer; with an attachment, a tool-capable model gets only the headings and the attached section. The open note and its comments still travel silently, so the composer no longer shows that the note goes. This replaces ADR 075; `attached` (path, quote, context) replaces `leave_out` on `POST /api/chat/turn`.

> **Status: Accepted (damiro, 2026-10-06); building.** Replaces ADR 075 (the composer's automatic chips for the open note and its comments), which the user rejected: a row that appears on its own is one more thing to read, and "everything on the note goes" gave no way to say which part is meant.

## Context

A persona that edits the user's note is sent the open note and its open comments with every message (ADR 069, 072). That stays, silently: the user is not made aware of it, since it is how she can do anything with the note at all. What the user lacked was a way to say *this part*: "make this bold" pointed at nothing but a comment's position.

## Decision

**1. An icon on a marked item attaches it to the next message.** The marked items are the tracked change, the applied edit and the comment, each already drawn on the note: a paperclip in the tab above a change, and in the card that opens on a comment. Clicking it puts a **chip** in the composer, floating above the message box, joined to it by a short line (not inside the box's text), with a snippet of the words; the chip has its own remove button, and attaching the same passage twice adds it once. The chips are the user's own act, never drawn on their own, and are cleared when the message is sent.

**2. What goes with a message that has an attachment.** For a model that can call tools, not the whole note but the note's headings, a line naming the words the user pointed at, and the section (up to the next heading) each of them is in; the rest of the note is not sent, and the model can open it itself with the read tool it has for other notes. A model that cannot call tools gets the whole note as before, since it cannot ask for more. A message with no attachment is as before: the whole open note. Open comments travel as before, in every case.

**3. Measured before built (2026-10-06).** `tests/live_edit_cases.py` with `EDIT_FOCUS=1`, Gemini Flash with the product's tools, the nine edit requests of ADR 072, four runs each on invented notes: whole note 36 of 36, section with the rule of today (the find must be in the whole note once) 36 of 36, section with the find needing to be in the section once 36 of 36. `gemma2:9b` (which never gets this shape) did fail the duplicate line under the strict rule and passed under the scoped one, so the app may later resolve a find inside the attached section. The notes were about 340 characters, so the saving a long note would give was not measured, only that nothing was lost.

**4. The chip says what it is.** A snippet of the attached words, a paperclip, and a remove button titled "Remove". No count, no "sent with your message" row.

## Consequences

- The `leave_out` request field and the per-turn comments switch of ADR 075 go; `attached` (path, quote, context) replaces them on `POST /api/chat/turn`.
- The user no longer sees, on the composer, that the note goes with a message. This is deliberate (see Context); the reply header still names what was sent.
- The reference library says how to attach (and drops the chips of 075).

## As built (2026-10-06)

- **Where the paperclip is:** in the small tab above a waiting change (with Accept and Decline), in the box that opens on a comment, and, so that attaching a commented passage is one click, as a small icon above the end of the commented words, shown when the words are pointed at (or the icon is reached by keyboard). It is not drawn all the time because, on tight lines, it sits over the line above. Words a waiting change covers have no second one (the tab has it).
- **The chip floats above the box**, in the manner of the tab above a change, because the user did not want it inline with the text of the message.
- **The sent message shows it:** beside the time on the user's message, a paperclip, with the count when more than one passage went. The turn record keeps the count as `sent.attached` (never the words, like the rest of that record), so it shows after a reload too.
- **Text fields share one focus style:** the composer's (a plain border that turns the brand colour), also in the comment box, the workspace rename field and the frontmatter fields, in place of the heavy ring.
- Checked in real Chrome (a scratch vault, a local model, the reply faked): the tab, one highlight on words with both a comment and a change, attaching from the tab, the card and the words, the chip, the request body, the mark on the sent message, and that accepting a change takes away the comment it answered (the editor now reads the comments again after an accept).

## Amendment (2026-10-07): her words are placed in the section she was shown

**The rule today, replaced.** A change she proposes (`propose_edit`) or a comment she leaves (`comment_on`) quotes a passage that had to be in the whole note exactly once, though with an attachment she is shown only one section: a line that is unique in the section could be refused because the note holds it elsewhere too, and she had no way to know.

**Now:** with an attachment, the sections she was shown (`edit_turn.focus` returns their `(start, end)` in the note, `Edit.scope`) are passed to the tool. If her passage is in the note more than once, it is placed where it is found **exactly once inside those sections**. The text around it (forty characters each side) is kept with it as for any proposal, and if that text does not tell the place from the others, so the passage could not be found again later, the change is refused ("more than once; quote more of it") rather than guessed. A passage found twice inside the sections, or not inside them, is refused as before; without an attachment nothing changes. The same applies to a comment (`note_changes._resolve`). `passage_finder.starts_within` finds the occurrences inside the sections.

**Her prompt is not changed** (measured 2026-10-07, below): it still says the passage appears in the note exactly once; with an attachment, "in the section shown" is what now decides.

**The saving on a long note, measured as characters sent (2026-10-07, 27 real notes of the repository from 3 to 31 thousand characters, a passage from the middle of each of their sections, one at a time):** the section sent is a median of 15% of the note (9 to 11% for the notes over 20,000 characters; worst case 24 to 67%). Whole-note sending is cut at `open_note_cap` (12,000 characters), so on a long note an attachment also lets her work on a passage beyond that cut, which she could not be shown before. How well a model edits in a long section was not measured (the earlier figures are for 340-character notes).


**Measured on a long note (2026-10-07; invented 9,068-character garden note with five sections and lines repeated across them; seven requests x four runs; tool calls through the product's own prompt, tools and placement; a change counts only if the resulting text is exactly the expected one; Gemini Flash and `gemma4:e4b` on Ollama with a 16k window, the one tool-calling local model quick enough to run):**

| Correct, of 28 | whole note, request says "this line" (nothing pointed at) | whole note, request names the section and the line | section attached, today's prompt | section attached, prompt reworded to "once in the part shown" |
|---|---|---|---|---|
| Gemini Flash | 21 | 26 | **27** | 26 |
| `gemma4:e4b` | 5 | 4 | **20** | 22 |
| Prompt sent, characters | about 10,250 | about 10,700 | about 3,230 | about 3,260 |

- **The section is a third of the prompt and no less accurate.** On Flash it matched a request that spells out where the line is (27 of 28 against 26), and beat the unpointed one on every duplicated line (without a pointer a request for "this line" cannot be done). The local model could not work in the whole note at all (placed but refused 14 and 17 times of 28, because the lines it quoted were not unique) and did in the section (refused 0 of 28 in both section arms, on both models).
- **The new placement rule is what makes the duplicated lines work:** every one of the 16 duplicated-line requests per model was placed in the section arms, with no refusal.
- **The reworded prompt makes no difference** (Flash 26 against 27, `gemma4:e4b` 22 against 20, both inside the noise of four runs per case), so the wording stays as it is.
- **Limits of this measurement.** One invented note; four runs per case, so single cases are noisy (`unique-sentence` moved between 2 and 4 of 4 on Flash with the same prompt); a request to delete a line scores 0 of 4 for `gemma4:e4b` in every arm, which is how it quotes (it leaves a blank line, and the check wants the line and its break gone), not the placement. A note over the 12,000-character cap was not tried. A first run of the local model with the default window (4,096) sent a truncated prompt and was discarded; the product sets the window for a local model, the test script did not.
