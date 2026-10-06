# 076 — Attach a marked passage to the message

> **Status: Accepted (damiro, 2026-10-06); building.** Replaces ADR 075 (the composer's automatic chips for the open note and its comments), which the user rejected: a row that appears on its own is one more thing to read, and "everything on the note goes" gave no way to say which part is meant.

## Context

A persona that edits the user's note is sent the open note and its open comments with every message (ADR 069, 072). That stays, silently: the user is not made aware of it, since it is how she can do anything with the note at all. What the user lacked was a way to say *this part*: "make this bold" pointed at nothing but a comment's position.

## Decision

**1. An icon on a marked item attaches it to the next message.** The marked items are the tracked change, the applied edit and the comment, each already drawn on the note: a paperclip in the tab above a change, and in the card that opens on a comment. Clicking it puts a **chip** in the composer, under the text, with a snippet of the words; the chip has its own remove button, and attaching the same passage twice adds it once. The chips are the user's own act, never drawn on their own, and are cleared when the message is sent.

**2. What goes with a message that has an attachment.** For a model that can call tools, not the whole note but the note's headings, a line naming the words the user pointed at, and the section (up to the next heading) each of them is in; the rest of the note is not sent, and the model can open it itself with the read tool it has for other notes. A model that cannot call tools gets the whole note as before, since it cannot ask for more. A message with no attachment is as before: the whole open note. Open comments travel as before, in every case.

**3. Measured before built (2026-10-06).** `tests/live_edit_cases.py` with `EDIT_FOCUS=1`, Gemini Flash with the product's tools, the nine edit requests of ADR 072, four runs each on invented notes: whole note 36 of 36, section with the rule of today (the find must be in the whole note once) 36 of 36, section with the find needing to be in the section once 36 of 36. `gemma2:9b` (which never gets this shape) did fail the duplicate line under the strict rule and passed under the scoped one, so the app may later resolve a find inside the attached section. The notes were about 340 characters, so the saving a long note would give was not measured, only that nothing was lost.

**4. The chip says what it is.** A snippet of the attached words, a paperclip, and a remove button titled "Remove". No count, no "sent with your message" row.

## Consequences

- The `leave_out` request field and the per-turn comments switch of ADR 075 go; `attached` (path, quote, context) replaces them on `POST /api/chat/turn`.
- The user no longer sees, on the composer, that the note goes with a message. This is deliberate (see Context); the reply header still names what was sent.
- The reference library says how to attach (and drops the chips of 075).
