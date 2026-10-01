# 056 — What the persona may reach from earlier conversations, and how: recap knobs and a `past_chats` setting

> **Status: Accepted (design), not built.** Nothing here is built. Builds on ADR 023 (recaps), ADR 031 (what a cloud model may receive), ADR 040 (the persona looks up notes itself) and ADR 025 (what is recorded). It is the design for #18's "search across past sessions"; the durable-facts half of #18 is ADR 041.

## Context

A persona knows an earlier conversation only through its recap: a few sentences, written from the user's messages only (ADR 023), and only the two newest are read, up to 800 characters each. A user who had two long conversations about films on the web chat asked "what did we talk about last time?" and the persona said, truthfully, that films did not come up. Two things were behind it:

- The web chat never wrote recaps at all (#126, fixed). The terminal started them at launch and the web had no launch.
- Even with a recap, the persona cannot give what it thought last time. A recap holds none of its replies, on purpose: replies include what it got wrong or made up, and a recap that records them turns them into "something the user said" (measured again in ADR 055: 5 of 5 runs). So "what was your take on it?" has no source at all, and the full conversation is the only place that answer lives.

What is already a choice the user makes, and what is not:

- **Notes** have both ways. `vault_lookup` (ADR 040) is `auto` (Sympose searches the vault before each reply and attaches what it finds) or `ask` (the persona gets `search_notes` and `open_note` and decides). It needs a model that can call tools; one that cannot runs `auto`, and the record says so. It is in the terminal's `/settings` and the web settings. The default is `auto`, and `gemma2:9b`, the default local model, cannot take tools, so a user on it never sees `ask` work.
- **Recaps** have an on/off switch (`session_recaps`) and a place in `/share` (the `recaps` category). How many are read (two) and how much of each (800 characters) are constants in code.
- **Full earlier conversations** have no way in, either way, and no `/share` category.

## Decision

Three settings, a new `/share` category, and one new reader of the session logs. Every one is the user's to choose; the defaults keep today's behaviour.

**1. The recaps' size becomes two settings.** `recap_count` (whole number 1 to 10, default 2) and `recap_chars` (200 to 2000, default 800). They only change how much of what is already read is sent. The room they take is the context budget's to fit (ADR 015): recaps are still the first thing dropped when a prompt does not fit.

**2. `past_chats` (a choice: `off`, `auto`, `ask`; default `off`)** is the same choice `vault_lookup` makes for notes, for the persona's earlier conversations:

- `off`: recaps only, as today.
- `auto`: before each reply Sympose searches the persona's earlier conversations with the same matcher the notes use, and attaches the best matching exchanges (a few, within the budget) under a label saying they are a record of what was said, in their own session and order. No extra model call and no rewrite step.
- `ask`: the persona is given two read-only tools, `search_chats(query)` and `open_chat(id)`, and decides. It runs in the same tool loop as `vault_lookup` and shares its round limit. A model that cannot call tools runs `auto`, visibly, exactly as ADR 040 settled; the check and the fallback are reused, not rebuilt.

**What the persona is shown of a past conversation.** Both sides, because the point is to answer "what was your take?". Her own earlier replies are marked as hers, and the label says they were hers and may have been wrong, so they are never a fact about the user. Only the persona's own conversations are reachable (sessions are per persona), never the one in progress (it is already in the prompt; its folded turns, ADR 055, are a separate later question), and `open_chat` only opens an id taken from the persona's own list of sessions, never a path it was given (the rule of ADR 040's `open_note`).

**Cloud models: a new category, withheld until allowed.** `/share` gains `chats` ("your earlier conversations, word for word"), not approved by default. Everything in a past conversation passes `sharing.gate` before the persona sees it; a withheld result says what was held back and that the user can allow it with `/share`, in the words of ADR 031. The `recaps` category is unchanged: allowing summaries does not allow word-for-word chats. This is the larger of the two: a recap is derived and short, a chat is everything the user and persona said.

**Recorded, never read back (ADR 025).** A turn's `sent` gains the earlier conversations that reached it, by session id and turn number, never text, with how (`auto`, `searched`, `opened`).

**Where the settings live.** The shared registry (ADR 036), in the terminal's `/settings` and the web settings together, in the Context group beside `session_recaps`.

## Why `off` is the default

It is a new path for the user's words to leave the machine (cloud models), it costs prompt room on every turn it fires, and the part most likely to go wrong is the persona stating its own old replies as the user's facts. None of that has been measured. The default moves only after the measurement below. When the setting is offered, `auto` is the one pointed to first.

## To measure before the default or the wording of the setting is final

- That a question like "what did you say about X last time?" finds the right earlier exchange in `auto` and in `ask`, on a tool-capable cloud model and on a tool-capable local model.
- That her own earlier replies are never reported as things the user said or did (the failure measured in ADR 023 and 055), with the label as written and with it removed.
- The cost: prompt tokens added per turn in `auto`, and model calls per turn in `ask` (ADR 040 measured 2.5 to 3 calls for a note question).
- That a withheld chat on a cloud model is reported as withheld and not as "we never talked about it".

## Settled with the user

- `past_chats` is `off` by default. The setting's summary and the settings screens say that `auto` is the one to try first and that `ask` needs a model that can call tools (the default local model cannot), so a user is not left choosing `ask` and wondering why nothing changes.
- A past conversation is shown with both sides, her own replies marked as hers. If the measurement above shows she reports those replies as the user's facts even with the label, the fallback is the user's side only, which is what recaps do.

## Not built

- All of the above. This ADR is the design only.
- Searching a conversation by meaning (embeddings, ADR 027) rather than by the notes' matcher.
- Reaching the folded turns of the conversation in progress.
- Tools that change anything (#21), and `ask` for a persona-by-persona choice (ADR 040 left that too).

## Alternatives rejected

- **A bigger recap instead.** A summary written from the user's messages cannot hold what the persona said, which is what the user asked for.
- **Always attach earlier conversations.** It spends prompt room and a cloud exposure on every turn, for users who never asked.
- **One setting for notes and past chats together.** The two have different risks (a chat holds everything said, a note is the user's own writing) and different `/share` categories; a user may want one and not the other.
- **Making `ask` the default.** Rejected as in ADR 040: it needs a tool-capable model and the default local model is not one.
