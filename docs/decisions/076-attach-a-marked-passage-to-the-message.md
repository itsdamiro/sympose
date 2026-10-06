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

## As built (2026-10-06)

- **Where the paperclip is:** in the small tab above a waiting change (with Accept and Decline), in the box that opens on a comment, and, so that attaching a commented passage is one click, as a small icon above the end of the commented words, shown when the words are pointed at (or the icon is reached by keyboard). It is not drawn all the time because, on tight lines, it sits over the line above. Words a waiting change covers have no second one (the tab has it).
- **The sent message shows it:** beside the time on the user's message, a paperclip, with the count when more than one passage went. The turn record keeps the count as `sent.attached` (never the words, like the rest of that record), so it shows after a reload too.
- **Text fields share one focus style:** the composer's (a plain border that turns the brand colour), also in the comment box, the workspace rename field and the frontmatter fields, in place of the heavy ring.
- Checked in real Chrome (a scratch vault, a local model, the reply faked): the tab, one highlight on words with both a comment and a change, attaching from the tab, the card and the words, the chip, the request body, the mark on the sent message, and that accepting a change takes away the comment it answered (the editor now reads the comments again after an accept).
