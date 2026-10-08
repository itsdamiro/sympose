---
type: decision
status: accepted
date: 2026-10-02
projects: [sympose]
concepts: [Conversation history]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 056 — What the persona may reach from earlier conversations, and how: recap knobs and a `past_chats` setting

> **Summary.** Three settings let the persona reach earlier conversations: `recap_count` and `recap_chars` for the recaps' size, and `past_chats` (`off`, `auto` or `ask`) with a new `/share chats` category and a reader of the session logs. A persona knew an earlier chat only through its recap, so she said truthfully that films did not come up. The defaults keep today's behaviour.

> **Status: Accepted (design); the recap settings are built; the second slice (`past_chats` `off` and `auto`, `/share chats`, the reader) and the third (`ask`, with `search_chats` and `open_chat`) are built and measured on a small local model and a cloud model.** Builds on ADR 023 (recaps), ADR 031 (what a cloud model may receive), ADR 040 (the persona looks up notes itself) and ADR 025 (what is recorded). It is the design for #18's "search across past sessions"; the durable-facts half of #18 is ADR 041.

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

## As built (2026-10-02, first slice: the recap settings)

`recap_count` (whole number 1 to 10, default 2) and `recap_chars` (200 to 2000, default 800) are in the shared settings registry, Context group, so the terminal's `/settings` and the web settings list them together. They are read by `recap.read_count()` and `recap.read_chars()`; a value out of range or not a whole number is the default. A caller that names its own count (the memory rewrite reads six) is not changed by `recap_count`; the size cut applies to both. Measured with `gemma2:9b` on a scratch install of three recapped conversations: asked which earlier conversations she remembered, she named the two newest with `recap_count` 2 and all three with 3. The reference notes describe both settings.

## As built (2026-10-03, second slice: `past_chats` `off` and `auto`)

Built before the tools, so what the persona does with a past exchange is measured with the real model first, and `ask` is added on a proven path.

- **The reader** (`engine/past_chats.py`) takes the persona's saved conversations, leaves out the one in progress and anything in the Bin, and cuts each into exchanges: one user message and the reply that answered it. An id is only ever one the persona's own session list gave. It keeps what it parsed until a file changes, and a file that is not text is skipped.
- **The matcher** is the notes' own word handling (`index_terms`: no filler, plurals folded), weighted by how rare a word is among the persona's exchanges. It prefers no exchange to a wrong one, as the notes do. An exchange is used when it holds at least two of the message's informative words and at least half of them. **One word is enough only when the message says it is about an earlier conversation** (a word such as "last", "earlier", "said", "suggested", "remember") **and that word is in one conversation only**: a conversation about a topic repeats the topic's words in every exchange, so what marks a word as specific is how few conversations hold it, not how few exchanges. Those words of asking about the past are never searched, as "note" and "vault" are not for notes. Up to 3 exchanges, each side cut to 600 characters, shown in the order they were held. Both numbers are constants for now. A message that uses other words to ask about the past falls back to the two-word rule; finding it anyway is what `ask` is for.
- **The prompt** gets a block after the recaps: each exchange is dated and numbered, the user's side is labelled `User`, hers `You`, and the label says hers was what she said then, may have been wrong, and is never something the user said. The budget drops the exchanges before the recaps when the prompt is too full (they travel at the end of the recaps' list through the fitting, so `budget.fit` did not change).
- **Cloud models:** the exchanges pass `sharing.gate` under a new category `chats` ("your earlier conversations, word for word"), not approved by default; `recaps` does not allow it. When exchanges matched and were held back, **the line saying so goes with the user's message**, not in the system prompt: with the line in the system prompt the persona said she could not use earlier conversations with this model and how to allow it 4 times in 20, with it beside the message 16 in 20 (below).
- **The record** (`sent`) gets `chats`: session id, message number and `auto`, never text. `/grounded` in the terminal says how many exchanges were sent.
- **The setting** `past_chats` (`off`, `auto`; `ask` joins when its tools are built), default `off`, Context group of the shared registry, so the terminal's `/settings` and the web settings list it together; the reference notes and the privacy notes describe it.

### Measured (2026-10-03, `gemma2:9b`, invented conversations only)

Four invented conversations of 14 messages each (56 exchanges), each holding a fact the user gave, a suggestion the persona made and a claim she made up (a saved birthday, a reservation name, a reminder time, a run time), asked about from a new conversation in the words of someone asking about last time.

- **Finding the exchange (no model).** The matcher attached something for 20 of 20 questions, with the exchange holding the answer among them for 16 of 20 (the four it missed use other words than the conversation did, such as "coming" for "with my friend"). 0 of 15 unrelated messages ("thanks, that helps!", "what should I cook tonight") attached anything. The first rule (two words, or a one-word message) attached for 10 of 20; letting any word found in few exchanges count on its own attached for 20 of 20 but also for 8 of 15 unrelated messages, and was dropped.
- **What she says (one run each question).** With `past_chats` off: the user's facts 0 of 12, her own earlier suggestions 0 of 4, and her made-up claims never repeated (4 of 4, because she had nothing). With `auto`: the user's facts **8 of 12**, her own suggestions **4 of 4**, her made-up claims repeated 2 of 4 times. The 4 facts missed were the ones the matcher missed or an answer she did not give. Mean prompt size 1661 tokens against 1439 off, about 220 more per turn on average (nothing is added when nothing matches).
- **Her old inventions come back.** With the label as written, 3 runs of all four questions (12 answers) repeated what she once made up 6 times, 3 for each of two of the claims (a birthday she was never given, a booking she cannot make): the birthday as a plain fact ("It's March 3rd", 3 of 3, and in earlier runs "you said March 3rd", so as the user's own word), the booking as hers ("I booked it under the name Silva"). **Removing the label changed nothing** (2 of 4 each way); calling her side by her name made it worse (3 of 12), and a longer label ("You answered, and may have been wrong") did not help (6 of 12). Her suggestions were found and reported as hers 10 of 12 times in every variant. So the label does not stop a small local model repeating what she once made up; this is the failure the ADR named, and it is why the default stays `off`.
- **A held-back chat on a cloud model** was never reported as "we never talked about it" (0 of 40). Run on a local model with the gate made to withhold: 4 of 20 said she could not use earlier conversations with this model and that `/share` allows it with the line in the system prompt, 16 of 20 with the line beside the message; most of the rest said she had no access to past conversations or found nothing in the notes.
- **The same questions on a cloud model (`gemini-3.8-flash`, 3 runs of all 20, `chats` allowed, invented data only).** Her own suggestions 12 of 12, and her made-up claims never repeated as fact (12 of 12): asked about the birthday, it said "I told you it was March 3rd", added that the user had never given a date, and that it might have pulled it "out of thin air"; asked about the booking, it said no reservation name had come up. So **the small model, not the design, is behind the repeated inventions**. The user's facts were 17 of 36, and every miss was an exchange the matcher did not attach (it then looked in the notes and said so) or something never said in the conversation (the error of a crashing script, which it correctly said was not recorded). One side effect of a scratch install that keeps its own questions: it sometimes mentioned having been asked the same thing on an earlier day, correctly.
- **Not measured yet:** a tool-capable local model, and `ask`.

**Open (the user's call):** the ADR's fallback for a persona that repeats her own inventions despite the label is to show the user's side only. The cloud run above says the label works for a capable model and not for `gemma2:9b`, so both sides stays the build, behind `past_chats` (default `off`), with the warning in the reference note. Whether to show the user's side only when the model is a small local one is not decided.

## As built (2026-10-03, third slice: `ask`)

`past_chats` gains `ask`: the persona decides whether to look in earlier conversations, with two read-only tools. It is built on ADR 040's loop and fallback, not beside them.

- **Independent of `vault_lookup`.** Each setting is checked on its own against the model (`persona_tools.resolve`): a user may let her search notes herself and have earlier conversations attached automatically, or the other way round. The tools of both go in one list and one dispatcher; a chat tool only runs when `past_chats` is `ask` this turn, as a vault tool only runs when `vault_lookup` is.
- **`search_chats(query)`** runs the reader's matcher on a query she writes. Because the call itself says the question is about the past, one word held by a single conversation is enough, as for a message that says so. It returns up to 3 exchanges, each with the conversation's id, its date and the message number. **`open_chat(id)`** returns the whole of one earlier conversation (up to 12000 characters, cut with a marker), by an id taken from the persona's own list of conversations: never a path, never the conversation in progress, never one in the Bin; any other id is "not found" without saying why. Both are shown the way `auto` shows an exchange: user's side and hers, hers marked as hers and possibly wrong.
- **Cloud models:** every result passes `sharing.gate` under `chats`; a withheld result is a tool message saying so and how to allow it, so she neither shows the text nor says nothing was said. The tool descriptions carry no conversation content.
- **A model that cannot call tools runs `auto`, visibly**, as ADR 040 settled: the record says `chats_mode: auto`, and `/grounded` says "You chose ask, but this model can't call tools, so Sympose searched for the message". A refused first call re-runs the turn without tools, with the same strike rule as `ask` for notes (`tool_support`).
- **In `ask` Sympose does not attach exchanges** for the message; she is told she has the two tools and when to use them (the user asks what was said or decided before, or refers to an earlier conversation) and that nothing she found there is a fact about the user unless the user's side says it.
- **The rounds are shared** with `vault_lookup_rounds`; the busy line shows searching and reading as for notes.
- **Recorded:** `sent.chats` entries carry `how`: `auto`, `searched` or `opened`, by session id and message number, never text; the tool calls are in `sent.lookups` as for notes (a count, never text).
- **Not built:** a persona-by-persona choice.

### Measured: `ask` (2026-10-03, invented conversations only)

Same four conversations and questions, `gemini/gemini-3.8-flash`, 2 runs of all 20 questions (40) and 6 messages that need nothing from before, `chats` allowed, `vault_lookup` `auto`.

- **She looks when she should and not otherwise.** Every one of the 40 questions made at least one `search_chats` call (mean 2.0 calls, up to 3 searches and an `open_chat`), and none of the 6 small-talk messages made any.
- **Answers.** The user's facts 18 of 24 (against 17 of 36 for `auto` on the same model: she rewrites a search that found nothing and opens the whole conversation when an exchange is not enough), her own suggestions 8 of 8, her made-up claims kept apart 8 of 8: for the birthday she said she had told the user March 3rd, that the user had never given a date and that she had made it up; for a run time, that she cannot run scripts and had made it up. The 6 misses are searches whose words did not meet the conversation's (a budget, "coming with me", a log volume), where she said she found nothing, and once a date the conversation never held.
- **Cost.** About 2 calls a turn instead of 1, and a mean prompt of 2914 tokens against 1651 for `auto` (a tool result and the replayed calls are sent with every later call).
- **A tool-capable local model, `qwen3:8b`, 1 run of the 8 questions about what she said or made up, and the 6 small-talk messages.** It looked in earlier conversations for 3 of the 8 (all three about what she had suggested, and it answered them correctly as hers); for the other 5 it searched nothing and said it had found nothing in the vault, once guessing "I might have mentioned Anki or Quizlet". It made nothing up as the user's, and looked up nothing on small talk (0 of 6). So it under-searches: `ask` on a small tool-capable model misses what `auto` would have attached, and `auto` stays the one to point a small local model to. A model that cannot call tools (the default `gemma2:9b`) runs `auto` and the record says so (`chats_mode`), covered by tests with a fake model.

- **The matcher's misses, answered with the settings row (2026-10-03).** `auto` missed 4 of 20 questions on wording. A further matcher rule was not added: the second slice showed two cheaper rules attaching 10 of 20 and 8 of 15 wrong, and a rule tuned on 20 invented questions would be tuned to them. Instead the row's own summary in the terminal's `/settings` and the web settings now says "(auto: local, ask: cloud)", as much as an 80-column terminal row holds, the pointer this ADR already promised, and the reference notes say it in full with the measured reason. The summary carries it because a hint on a choice row is shown by neither screen.

- **The web chat shows them too (2026-10-03, found in the pre-#21 review).** `chats` was in the record but the web chat's "Based on" line read only the notes, so a reply built from earlier conversations looked ungrounded there while the terminal's `/grounded` listed them. The line now counts the exchanges ("Based on Atlas and 2 earlier exchanges") and the expanded list says "2 exchanges from earlier conversations, word for word", the terminal's words. Not shown on the web yet, and also missing from the web record: the lookups of an `ask` turn, the recaps and the persona's memory files; the terminal lists those.

## Not built

- Searching a conversation by meaning (embeddings, ADR 027) rather than by the notes' word matching.
- Reaching the folded turns of the conversation in progress.
- Tools that change anything (#21), and `ask` for a persona-by-persona choice (ADR 040 left that too).

## Alternatives rejected

- **A bigger recap instead.** A summary written from the user's messages cannot hold what the persona said, which is what the user asked for.
- **Always attach earlier conversations.** It spends prompt room and a cloud exposure on every turn, for users who never asked.
- **One setting for notes and past chats together.** The two have different risks (a chat holds everything said, a note is the user's own writing) and different `/share` categories; a user may want one and not the other.
- **Making `ask` the default.** Rejected as in ADR 040: it needs a tool-capable model and the default local model is not one.
