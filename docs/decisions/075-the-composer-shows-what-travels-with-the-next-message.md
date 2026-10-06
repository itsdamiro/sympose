# 075 — The composer shows what travels with the next message

> **Status: Accepted (damiro, 2026-10-06); not built.** Follows ADR 069 (comments) and ADR 072 (the persona sees the open note). Web app only.

## Context

With a note open in the editor, the next chat message carries more than the words typed: the note's text (ADR 072, category `open_note`) and the open comments on it (ADR 069, category `annotations`). A local model gets both. A cloud model gets each only if the user approved that category (ADR 031), and otherwise the turn holds it back and the reply header says so afterwards. Today the user cannot see, before sending, what the persona will see.

The principle, as damiro put it: **the user must be able to see what the persona sees. Everything on an open note is seen unless the app says otherwise.**

## Decision

**A row above the text box, inside the composer, shows what travels.** One chip per thing: the open note ("Rose") and its open comments ("2 comments"). The row exists only when something would travel; with no note open it takes no space. It is not beside the conversation controls (new conversation, pin, Condense): those act on the whole conversation, while a chip describes the next message only and needs room for a name.

**1. A chip shows the name and the count, not the text.** Clicking it opens the exact text that will be sent (the note's text; each comment with the passage it is about). The chip is a summary, the click is the proof.

**2. The ✕ on a chip leaves that thing out of the next message only.** After that message is sent the chip is back. It is not a setting and is never saved; changing the open note also resets it. (A lasting opt-out would let the persona quietly stop seeing a note the user still has open, against the principle above.)

**3. When a cloud model would withhold a chip's category, the chip says so.** It is dimmed and reads "not sent to this model", with an **Allow** link beside it. Allow approves that one category for cloud models (`open_note` for the note chip, `annotations` for the comments chip; the same approval as `/share` and the Settings sharing section, ADR 031), so the next message carries it. The user is never asked to leave the composer to find out why the persona did not see the note. For a local model nothing is ever withheld, so no chip is dimmed.

**4. The chip and the turn must agree.** The row is computed from the same rules the turn uses (the model's locality, the approved categories, the leave-out of item 2), not a second copy of them: a chip that says "sent" while the turn withholds is a grounding bug, not a cosmetic one. The leave-out travels to the server with the message, and the server's own `withheld` answer is still what the reply header reports.

**Not in this decision.** Notes found by search (ADR 040) are not chips: they are chosen by the persona's lookup after the message, so they cannot be known before sending; the reply header continues to name them. Terminal: unchanged (editing and the open note are web only; `/share` already shows the categories).

## Consequences

- One new component above the composer and a small hook that derives the chips; the share approval it triggers already exists (`sharing.set_approved`, behind the settings route).
- The server accepts a per-message leave-out of the two categories; nothing is persisted.
- The reference library's chat and privacy pages gain a paragraph on the row (`sympose/reference/`), with the retrieval eval run before and after.
- Tests: a chip per state (sent, left out, withheld), the leave-out ending after one message, Allow turning the category on, and a test that the chip's verdict equals the turn's for each model kind.
