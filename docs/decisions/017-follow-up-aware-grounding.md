---
type: decision
status: accepted
date: 2026-09-24
projects: [sympose]
concepts: [Grounding]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/retrieval]
---

# 017 — Follow-up-aware grounding: rewrite a search-less message from recent turns

> **Summary.** When a message grounds nothing and the chat has earlier turns, the engine can rewrite the message from the recent turns and search again, controlled by a `grounding_followups` setting whose default `rewrite` mode is the only one besides `off` that is built. A follow-up like "why did we pick it?" has no searchable words. It costs one extra model call on a miss, and a small local model can write a poor rewrite.

> **Status: Accepted.** Built as `off` and `rewrite`; the other two modes below are reserved, not built. **Scope of the live measurements: Ollama and `gemma2:9b` only**, on the synthetic fixture vault (nine follow-up cases, several runs each). Cloud models and other local models are unmeasured: they may write better or worse rewrites and have different latency, so the rewrite prompt and the number of recent turns are worth re-checking per model.

## Context

The grounding retriever (ADR 014) reads only the current message. A follow-up such as "why did we pick it?" has no searchable words and no way to say what "it" is, so nothing is grounded even though the notes were found one turn earlier. The model still sees the earlier conversation (the history is in the prompt), but the note text does not carry over: a reason that lives in the vault and not in the chat is either reported as not found or guessed. The same holds for "and the budget one?", "go on", "can you expand on that?". This is a retrieval gap, not a context-window gap (ADR 015): the window has room; the search step never sees the earlier turns.

How this is commonly handled: rewrite the question into a standalone one using the chat so far before searching (accurate, costs a model call); search on the last few turns together (crude, cheap); let the model search for itself in a loop (most reliable, costs round trips and needs a model that is good with tools); summarize old chat. The first and second fit this project's cost stance; the third depends on tool-calling, which is not built.

## Decision

**Retrieve first; only on a miss, and only with history, look at the earlier turns.** The current message is searched exactly as today. If that grounds nothing and the chat has earlier turns, the follow-up step runs. Most turns pay nothing extra. The trigger is mechanical (an empty first pass and history exists), not a list of phrases: no wording of a follow-up is enumerated.

**A knob,** the `grounding_followups` setting (a user-facing default belongs in `settings_store`), settings file only for now (there is no settings screen, and no slash command per knob):
- `rewrite` (default): a model call, given the last two exchanges, returns one standalone search query, or `NONE` when the message has no topic of its own (thanks, a greeting, small talk, a change of subject). Retrieval is then run again on that query. A wrong rewrite finds nothing rather than inventing evidence, because the rewrite only feeds the search and the retriever's precision gates (ADR 014) still decide what reaches the model.
- `off`: today's behavior, no extra call. Only an explicit `off` turns it off; any other or malformed value leaves the default, the same rule as the other knobs.
- `recent-words` (**reserved, not built**): no model call; the previous exchange's search terms reused at lower weight. Free, but it attaches the old topic's notes on a topic change, and with `rewrite` measured this good there was no case for building a weaker mode yet. It stays as the option for someone who wants no extra call on a small local model.
- `model-searches` (**retired, superseded by ADR 040**): the model asks for notes itself. It is not a value of this setting: who searches at all is a separate setting, `vault_lookup` (ADR 040, proposed), since this one decides how a missed search is retried. Any value other than `off` still means `rewrite`.

**What the rewrite sees.** The last two exchanges (four messages), assistant replies included, each message cut to 300 characters. The reply often holds the noun a bare "it" refers to ("You decided on SQLite for the Atlas prototype…"), and the tail of a long reply is not needed to find it. The same model as the chat runs it, with the same window (`num_ctx`), so a local model is not reloaded for the extra call, and its own reply is capped at 60 tokens. There is no separate rewrite-model setting: the warm cost was measured small enough (below) that a second model would add a knob and a load without a measured need.

**When the rewrite does not happen or fails, the turn goes on as before, ungrounded by it.** No history, the knob off, a persona with no vault (nothing a query could find), the prompt not fitting the window (sized by the same budget code as the main call, ADR 015), a model error, an empty reply, a reply cut off at its 60-token limit (a query cut mid-word could ground the wrong note), or `NONE`: each means "no rewrite", never a failed turn. A rewrite is never saved as a turn and never shown to the model as something the user said; it only feeds retrieval.

**The rewrite is visible.** The rewritten query is carried on the turn result and shown at the end of the reply header, after the grounded-notes segment (ADR 016), as `searched "…"`, cut at its end to what fits the line. On a narrow line the note's path gives up room first (keeping its filename, as ADR 016 does), and the query is left out when even that leaves it no readable room; on an 80-column line it shows as `from …Atlas.md · searched "why we pick…"`. It only appears when the rewrite is what grounded the reply, so a wrong rewrite that found a wrong note can be seen and a rewrite that found nothing says nothing (an ungrounded reply already says so in its text). It follows the same `show_grounding` knob as the notes segment.

**Where it lives.** A small module, `engine/followup.py`, holds the rewrite prompt, the call and the orchestration (`ground` = first pass, then the rewrite and a second pass), reusing `grounding.ground` and `model.call_model`; `turn.py` calls it in place of `grounding.ground`. The rewriter is a parameter, so retrieval can be tested with a fake one and no model.

## Measured (Ollama, `gemma2:9b`)

Nine cases over the fixture vault: five follow-ups that need a rewrite ("why did we pick it?", "and when is the launch?", "go on", "can you expand on that?", "where are we staying?"), and four that must not attach the old topic (thanks, "how are you today?", "ok let's talk about something else", a standalone question about a note the vault does not have). Each was run several times.

- **First prompt (no way to say "no topic"): 8 of 9 classes right, one wrong every time.** "thanks, that helps!" was rewritten into "Atlas database decision" and attached the Atlas note, the stale-topic failure this ADR was worried about. An empty reply also occurred once (handled as "no rewrite").
- **Adding `NONE` for messages with no topic of their own fixed that**, but the model then dropped the project name from "why did we pick it?" ("why we picked SQLite"), which the retriever's precision gate rejects (one matching word, not in the title). Telling it to always include the specific names involved (the project, person, place or note title) plus the question's own key words fixed that: **45 of 45 runs correct** (nine cases, five runs each), all the topic changes and small talk returning `NONE` or an unchanged query that grounds nothing.
- **Latency, warm (model loaded):** about 0.4 to 0.7 s per rewrite, 1.5 to 2 s for the first one after another prompt. Cold latency (model not loaded) is the same as any first call and is not extra, since the chat model is the one that runs.
- **A reasoning model cannot do this step (`qwen3:8b`).** It spends the whole 60-token limit thinking and writes nothing: 8.7 to 11 s wasted per miss. Given 512 tokens it finished in 20 to 50 s (and failed on one of four), given 2048 in 35 to 130 s. That is far too slow to be worth it, so the limit stays small and a model that uses it up without answering is remembered for the rest of the process and not asked again (its turns go on ungrounded by a rewrite; the knob can also turn the step off). Other models were not measured.
- A standalone question the first pass misses (`NONE` returned for "how long do I bake the sourdough?" in the test that ran the rewrite on every message) never reaches the rewriter in the real flow: the first pass finds it. And when the first pass finds nothing for a question that does stand alone, `NONE` is the same as today.

## Consequences

One extra model call on a miss when the mode is `rewrite`, about half a second for the call itself on the measured local model (one to one and a half seconds on the whole turn in the live check below): the reliability-versus-cost dial ADR 014 left for this slice, with a knob to turn it off. A small local model can still write a poor rewrite, which the precision gates contain but do not fix. A rewrite grounded on the wrong note is visible in the header, not silent.

The time the user waits is the rewrite call plus the chat call, and the TTFT in the header (ADR 013) only covers the chat call, so a rewritten turn looks a little faster than it felt. Ollama also keeps one prompt's processing per slot and reuses it only while the next prompt starts the same way; the rewrite call in between is a different prompt, so a rewritten turn may also pay to process its main prompt again. Both are small on the measured setup and are only on missed turns (see the live check below).

## Live check (real engine, `gemma2:9b` through Ollama, the fixture vault)

Five turns in one chat, the knob on and then off: "what did we decide about the database for Atlas?", "why did we pick it?", "thanks, that helps!", "how are you today?", "and what's the launch target?".

- **The follow-up was grounded and the answer came from the vault.** With the knob on, "why did we pick it?" was rewritten into "why choose SQLite Atlas database", grounded on the Atlas note, and answered "It needs zero setup." (what the note says). With the knob off it grounded nothing and the model answered "because it's lightweight and self-contained", a reason that is in no note: the same gap as before, and the reason for this slice.
- **Nothing stale was attached.** "thanks, that helps!" and "how are you today?" both ran with the knob on and grounded nothing; "and what's the launch target?" grounded on its own (a first-pass hit) and did not run a rewrite.
- **Cost, wall time of the whole turn for the follow-up:** about 4.0 s, 3.5 s and 4.3 s with the rewrite against about 2.9 s and 2.7 s without in the quiet runs, so roughly one to one and a half seconds more. The machine was not quiet for all runs (the chat's own TTFT swung between 0.4 and 5.7 s in both modes), so this is an indication, not a benchmark.

## Amended by ADR 021

The rewrite step also runs when the first search is *weak* (every hit rests on one matched word), with or without earlier conversation, and a `NONE` answer then drops the weak hits. The mixed-topic risk listed below is seen in practice: a rewrite of "what did we talked about last time?" carried "our table" over from an earlier turn.

## Not built yet

- A settings screen and a slash command for the knob. **Update (docs/decisions/036):** the settings screen is built and lists `grounding_followups`; there is still no command of its own for it.
- A mixed query (a topic change whose rewrite drags in the old topic's name, "Atlas tax filing deadline") is possible from a small model and was not seen in the measured cases; the query is visible in the header and the retriever's gates still apply.
- Any measurement on cloud or other local models (#14).

## Decided not to build (2026-10-14, #10)

> **Status: Accepted (damiro handed the call to the assistant, 2026-10-14; he can reopen any line).**

Each was a leftover in this record's "Not built yet" list. None has evidence behind it, and each costs more than it earns:

- **The `recent-words` mode** is rejected below (it attaches stale notes on a topic change), and `model-searches` is what `vault_lookup: ask` is (ADR 040). The two reserved values are retired.
- **A separate, cheaper model for the rewrite.** The call runs on the chat's own model on purpose: on a local setup a second model is a reload of seconds (ADR 015), against a rewrite that costs about a second on the model already loaded. For a cloud model the saving is a fraction of one short call; nobody has measured a cost worth a second setting.
- **Showing that a rewrite ran but found nothing.** A notice for something the user cannot act on. `sent.rewrite` (ADR 025) already records that the call was made, for measuring.
- **Counting the rewrite call in the time the header shows.** The header's time is the chat model's own time to first token, which every figure in the decision records is compared against; adding the search and the rewrite to it would make those figures stop meaning what they say.
- **Skipping the call for small talk.** It would take a guess about wording, which this project does not do; the call answers `NONE` in about a second and only on a message that grounded nothing or only weakly.
- **Rewriting in the same call as the chat.** The query has to exist before the evidence does, so a single call cannot do both (see the alternatives below).

## Alternatives rejected

- **Rewrite on every turn.** Costs a call per turn to fix the minority of turns that miss; retrieve-first pays only when needed.
- **Enumerating follow-up phrases** ("why did we", "what about"). Wording-dependent and brittle; the trigger is structural.
- **Only searching on the last few turns concatenated.** Kept as the free `recent-words` idea, not built, because it attaches stale notes on a topic change.
- **Model-driven search as the first step.** Needs tool-calling and round trips; reserved as the fourth mode.
- **Letting the rewrite run without a way to say "no topic".** Measured: it invents a query from the old topic for small talk.

## Measured (2026-10-15): a follow-up about Sympose that needs a passage the first reply did not carry, on Gemini Flash

Four two-turn conversations about Sympose in `tests/live_lookup_cases.py` (`sympose-follow-up-*`): how much history is sent and then "what is the lowest I can set it to?"; the edit modes and then "which one is the default?"; opening a note and then "what if the model can't use tools?"; `/default` and then "and where is that remembered?". Each answer is in a library passage the first question did not bring. Flash, 4 runs per case, `vault_lookup` `auto` and `ask`, with keyword search and again with the shipped meaning search (`LOOKUP_SEARCH=auto`).

**Result: 1 of 16 in `auto` and 0 of 16 in `ask`, both ways of searching.** Every miss is an honest "I don't know that about Sympose from the documentation"; no reply invented a setting, a default or a file. The earlier four follow-up cases (ADR 072) passed 14 and 16 of 16 because their answers were already in the first reply.

**Why.** The rewrite works (Flash writes `lowest setting for conversation history sent to model`, `persona default edit mode`), but the library is searched with it by words only (`reference.ground`, the rewrite is searched with `refine=False`, written for the short keyword rewrites `gemma2:9b` gives). Searched by words that rewrite does not find the passage with `500` or `manual`; searched by meaning it does for 3 of the 4 (the fourth, "what if the model can't use tools?", is not rewritten into a message about opening notes, so neither way finds it). In `ask` there is no rewrite at all (`turn_evidence`: the vault is not searched for the message and nothing is rewritten), so the library is searched with the follow-up's own words, which find nothing, and the model's own vault lookups find nothing about Sympose.

**Not changed.** Searching the rewrite by meaning as well is a change to the search (retrieval eval before and after, and the keyword rewrites of `gemma2:9b`, the four in `tests/reference_cases.py`, kept working). Not built here; this is the measurement.

## Built (2026-10-15): the rewrite is searched by meaning too, five library passages for a follow-up, and `ask` reaches the library through its own search

Three changes, from the traces of the measurement above (Flash, the same four cases, 4 runs, the shipped meaning search):

- **The rewrite is refined by meaning like the message** (`reference._search` no longer has a `refine=False`): the earlier reason (written for the short keyword rewrites of `gemma2:9b`) did not hold, the four keyword rewrites of `tests/reference_cases.py` still find their passages in both search modes, and the five vault follow-ups that have a rewrite still attach nothing from the library in `auto`.
- **A follow-up has five library passages, not three** (`MAX_WITH_REWRITE`): the message and its rewrite take turns, and with three slots the answer to "which one is the default?" (the `edit_mode` passage with `manual`) was fifth of five and never reached the model. A message with no rewrite keeps three.
- **In `ask` the library is also searched by `search_notes`, and the prompt says so** (ADR 040, amendment): nothing rewrites a follow-up there, but the query the persona writes is standalone; Flash did not call `search_notes` on these four cases (0.0 lookups per turn), where the prompt told it the reference comes with the message. A library persona's prompt now ends the reference part with one line saying `search_notes` also searches it.
- The library names `show_note_marker` (Settings, and the web app's opening-notes answer), which no passage did before.

**Result, Flash, 4 runs per case, meaning search:** `auto` 10 of 16 (was 1), `ask` 9 of 16 (was 0): the default 4 and 4, where it is remembered 3 and 3, without tools 3 and 0, the lowest 0 and 2. The misses are honest "I don't know" again except where the model answers a fair reading of an ambiguous question (in `ask` "what if the model can't use tools?" is taken to be about `vault_lookup`, and the `show_note_marker` passage was found in only one run); none of the first 190 characters of each reply (all the harness prints) invented a setting. In `auto` the lowest setting fails because Flash's rewrite varies in wording from run to run (`history limit` finds nothing, `history sent to model` finds `history_tokens`): a limit of searching by one rewrite, not tuned further.

**Cost and regressions.** `ask`'s default case set on Flash, 3 runs, with the new line and with it blanked: 50 of 54 and 51 of 54, calls and lookups per turn the same case by case (the one extra miss is a recap named in small talk with no lookup, a variation of the model's, not of this change); the cases that need no note looked nothing up 15 of 21 both ways. The follow-up cases now cost 2.0 to 3.4 calls per turn in `ask` (one to two lookups the model chooses to make), where they cost 1.0 and gave up. The library's own eval is unchanged at 113 of 119 at the shipped 0.72.

**Review (`/code-review xhigh` of this change, 9 findings).** Fixed, each test failing without its fix: a library passage already attached is not listed again when `search_notes` returns it (`lookup.merge_hits` in `turn.py`), a library hit gets no properties passage from the vault's index and keeps its own `via`, and the library text no longer states a test figure. Left, as measured gaps: the second embedding call a follow-up now makes is on the turn's critical path (its latency was not measured); the `ask` line ends "before you say you don't know", which may add a lookup on a question the library does not cover (the default set did not show it, but holds few such questions); and five passages was chosen from one case, where ranking the merged list by meaning score might need no fixed cap.

## Measured (2026-10-16): the second embedding call a follow-up makes

**What.** Since `68c4e74` a follow-up searches the library by meaning for the rewrite as well as for the message, so it embeds one more short string (the message's own vector is cached per message, so only the rewrite is new). Timed through `embeddings.embed`, one query string per call, `nomic-embed-text` on local Ollama, damiro's Mac, quiet machine: 30 calls with the model loaded, then one call after unloading it.

**Result.** Loaded: median 11 ms, 90th percentile 14 ms, slowest 16 ms. After Ollama unloaded the model: 312 ms for the first call, 15 ms for the next. The cold load falls on the message's own embed (it runs first), not on the rewrite's, so the second call adds the loaded figure, about 11 to 15 ms, against 0.4 to 2 s for the rewrite model call it follows and 1 to 1.5 s the whole follow-up path adds (above).

**What it says.** The second call is under 1 percent of a follow-up's extra cost on a local embedder; skipping it when the first search attached a note would save little and risk the follow-up that needs a new library passage (the case `68c4e74` fixed), so nothing changes. Not measured: a cloud embedder (a network round trip, probably 100 to 300 ms; the library search sends the message to it only when the user approved sharing notes with that model, ADR 031), a slow disk or a busy machine.
