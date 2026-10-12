---
type: decision
status: accepted
date: 2026-10-12
projects: [sympose]
concepts: [Persona edits, Grounding]
amends: [40]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/small-models]
---

# 083 — A late Ollama is asked again once, and then taken to have tools

> **Summary.** The question "does this local model take tools?" was given two seconds, and any failure to answer sent it to litellm's table, which does not know a newly pulled model and says no. Under load that ran a tool model as a marker-writing one for a turn, with no word to the user. A timeout is now asked once more with ten seconds; if that is late too, the model is given tools for the minute, and the existing refusal path corrects a wrong yes.

> **Status: Accepted (damiro, 2026-10-12).**

## Context

ADR 077 and ADR 082 each saw a first measurement run of `gemma4:e4b` give 0 of 12 with "I can't write notes" replies that did not repeat. The likely cause is in `tool_support._ollama_says_tools` (a timeout was not seen in those runs, so this is not proven): a `/api/show` that takes longer than two seconds (a model loading, another run in flight) raised, the failure was treated like "Ollama is not running", and `can_call_tools` fell to `litellm.supports_function_calling`, which is `False` for a model litellm does not list. The turn then ran in the marker path, which cannot draft notes (ADR 078), for a model that does take tools. Nothing was shown to the user.

The two wrong answers are not equal. A wrong "yes" costs one failed call that the turn re-runs without tools and one strike (`note_refusal`, ADR 040); two in a row and the model is marked unable. A wrong "no" costs the feature, silently.

## Decision

1. A timeout from a running Ollama (a `TimeoutError`, or a `URLError` that wraps one) is asked once more with `_OLLAMA_SLOW_TIMEOUT_SECONDS` (10) in place of `_OLLAMA_TIMEOUT_SECONDS` (2). Any other failure (refused, not JSON) is not retried and is left to litellm's table as before.
2. If the second ask is late too, the model is taken to have tools (`_ollama_says_tools` says `True`) and the minute of silence of ADR 040 applies: it is not asked again within the minute and keeps saying yes, and after it the question is put again and a real answer replaces the guess. A refusal after a late answer clears the guess.
3. An answer from Ollama is kept for the process as before.

## Consequences

- A busy Ollama no longer turns a tool model into a marker model for a turn. Cost: the first turn after a start can wait up to twelve seconds for the answer when Ollama is slow, once per minute at most.
- A local model that does not take tools, asked while Ollama is too slow to say, is given tools once: its call fails, the turn is re-run without them and it takes a strike. Two such turns in a row mark it unable until restart, which is correct for it.
- Not measured live: the late-Ollama state is hard to produce on demand; the behaviour is pinned by tests (retry, limits, the wrapped timeout, the minute, the clearing after a refusal), each seen to fail when the code is changed.

## Alternatives rejected

- **Stay unknown: take no answer and keep asking every turn.** The turn still needs a yes or a no, so "unknown" has to resolve to one of them; asking every turn puts the delay on every message.
- **A longer first timeout only.** Ten seconds on every first ask also delays the common case where Ollama is not running at all (a refused connection fails at once, but a dead route does not); the retry keeps the usual case at two seconds.
- **Take a timeout as "no tools" and say so.** Right for a model that cannot take tools, and the loud version of the bug for one that can.
