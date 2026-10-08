---
type: decision
status: accepted
date: 2026-09-24
projects: [sympose]
concepts: [Context budget]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 018 — A context meter under the chat box

> **Summary.** A one-line meter under the chat box shows how much of the prompt budget (window minus reply room) is in use, capped at 100%. It answers how long until the conversation starts forgetting, which the runtime's own count cannot show. The number is an estimate that leans high and moves once per turn, not while typing.

> **Scope: the counting is the engine's own estimate (ADR 015), measured against Ollama's real counts on `gemma2:9b` only** (prose under-counted by 2 to 4 percent, code by 12, Japanese over-counted by 64, before the 15 percent safety margin). So the percentage is an estimate that leans high, and how close it is on cloud models and other local models is unmeasured.

## Context

ADR 015 made the engine fit every prompt to the model's window, dropping the oldest turns and then the weakest grounding passages when it does not fit, and the header says so after the fact (`3 older turns out of context`). What the user still cannot see is how close a conversation is to that point before it happens. The runtime's own token count cannot show it, because it is measured after the runtime has cut an overflowing prompt (ADR 015). The engine's own count is taken before the call, so it can.

## Decision

**A one-line meter under the chat box:** `context ██████░░░░ 62%`, dim, in the line the composer already leaves free below it, so the screen does not grow.

- **What 100% means.** The share of the *prompt budget* in use: the window minus the room kept for the reply (ADR 015). At 100% the next turn starts leaving older turns out, so the number answers "how long until it forgets", not "how full is the raw window" (which could never reach 100% because the reply room is always reserved). The bar and the percentage never exceed 100: once trimming has started the header's notice says how much was left out.
- **Rounding.** To the nearest whole percent, except that a hair under the budget reads 99: 100 means the budget is reached (the next turn may start dropping), so it is never shown while there is still room.
- **What is counted.** The prompt the model was sent on the last turn (soul, rules, grounding, the kept history, the message) plus the reply it wrote, counted by the same function and with the same 15 percent margin as the fitting (`budget.count_tokens`), so the meter and the trimming can never disagree. It is the size of the conversation as the next turn will start from it, plus that turn's own grounding block (which does not carry over), so it leans slightly high. The engine returns it on the turn result as the tokens used and the budget it was measured against; nothing is stored in the session record.
- **When it is shown.** After each reply, for the conversation in front of the user. It is empty before the first reply of a chat (nothing was sent, and the model's window may not even be looked up yet), and it is cleared when the persona or the model is switched, since the number belongs to the previous model's window, and comes back with the next reply. A turn that fails leaves it as it was. A reply that was already being produced when the model or persona was switched is ignored when it lands (each reset bumps a counter the reply captured when it was sent), so an old model's percentage never shows against the new window. It is not shown when the model's window is unknown (then nothing is trimmed either).
- **Colour.** The theme's own colours: normal below 70%, warning from 70%, error from 90%.
- **A knob.** `show_context_meter` in the settings file, on by default, only an explicit `false` turns it off (the same rule as the other display knobs). No slash command for it: there is no settings screen yet and one command per knob does not scale.
- **Where the code lives.** `cli/meter.py` holds the widget, the formatting and the knob; `turns.py` hands it the turn result. The web dashboard's version waits for the dashboard's chat panel, and reuses the same two numbers from the result.

## Checked

Live on `gemma2:9b` through the real CLI with a 1024-token window (prompt budget 768): five turns showed 44%, 47%, 46%, 56% and 76%, the second and fifth beside a follow-up rewrite (ADR 017). Turn 3 reads a point lower than turn 2 because turn 2 carried a grounding block that does not carry over. The meter sits on the screen's last row directly under the composer with the composer's total height unchanged. Counting the reply adds about 0.3 ms per 1,500 words. Not measured: how close the percentage is to the real prompt on cloud models and other local models.

## Consequences

The number is an estimate that leans high (the margin), so a conversation can look nearly full while the model still has room; that is the safe direction, since the failure it warns about is silent loss. It moves in steps, once per turn, not while typing: the size of a message being written is not counted until it is sent. A long conversation on a large window climbs slowly, so most short chats will show a small percentage most of the time; that is the honest picture.

## Not built yet

- Nothing outstanding. Counting the message being typed is **rejected**, as under "Alternatives rejected" below (settled by damiro, 2026-10-01, closing #27). The web meter and restoring the meter on resume were built in the web chat (ADR 044, "the context meter"); the terminal has no way to resume a saved session, so has nothing to restore.

## Alternatives rejected

- **The runtime's reported prompt token count.** Post-cut: it can never show the overflow the meter is for (ADR 015).
- **A percentage of the raw window.** It tops out at the reserve line and would show 75 percent for a conversation that is already dropping turns.
- **Counting the typed message live.** A token count on every keystroke, for a number that only matters once the message is sent.
- **A status bar or header line instead of under the composer.** The header already carries per-reply facts (TTFT, notes, trim notice), which is what fills its width; the meter describes the conversation, not one reply, so it sits by the box the user types into.

## Update: raw counts, `/context`, and a figure right after a model switch (#27)

- **Raw counts beside the percentage.** The line reads `context ██████░░░░ 62% · 3.8k of 6.1k`: the tokens in use and the prompt budget, rounded to a tenth of a thousand from 1,000 up. No knob of its own: it is part of the meter and goes with `show_context_meter`.
- **`/context` explains the number.** It prints, in the chat, the figures in full (`3,812 of 6,144 tokens`), what 100% means, what is counted, and that the figure leans high. Before any figure exists it says the meter fills after the first reply (or why it is empty: the knob is off, or the model's window is unknown). The figures are read back from what the meter shows, never recomputed.
- **A figure right after a model switch.** Instead of blanking, the meter shows an estimate for the new model at once: the persona's system prompt (soul, rules, the vault map when this model may receive it) plus the conversation's kept history, counted with the new model's tokenizer against the new model's prompt budget, the oldest turns left out when they do not fit exactly as a real turn would (`engine/context_estimate.py`, no model call), so it never reads above the budget. It stays blank when the conversation has no reply yet (nothing to count) or the window is unknown. The next real reply replaces it.
  - **What it leaves out.** The next message's grounding block and any recaps, which the real figure includes, so the estimate leans *low* where the real figure leans high. `/context` says "estimated" while an estimate is showing, so the user is not shown an estimate as the measured figure.
  - **Stale results.** It runs off the interface thread, in a small pool of its own so it never queues behind a chat turn waiting on a model (a tokenizer can be slow the first time it loads), and lands through the same epoch check as a reply: a second switch, or a persona switch, while it runs makes it stale and it is dropped. A reply still in flight from the old model is ignored as before; the estimate then misses that one turn until the next reply corrects it.
  - **Persona switches are unchanged**: a new persona starts a fresh session, so the meter is blank.
- **Alternative rejected: keep the figure and only re-divide it by the new window.** The tokenizer is model-specific (`budget.count_tokens` takes the model), so the same text counts differently on the new model; dividing the old count by the new window would be wrong in the way the meter exists to avoid.

**Update (docs/decisions/027):** the line also carries a notice at its far right while the search index is being built, `indexing 40%`, with its own knob `show_index_notice`, independent of `show_context_meter`.
