---
type: decision
status: accepted
date: 2026-10-02
projects: [sympose]
concepts: [Context budget]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 059 — How long a model call may wait: a limit that grows with the prompt, and a `model_timeout` setting

> **Status: Accepted (2026-10-02).** Closes #124. Builds on ADR 013 (the first-word wait is what the user feels), ADR 015 (the prompt budget) and ADR 055 (compaction shortens a long chat but does not remove the problem).

## Context

Every model call is given 120 seconds (`_REQUEST_TIMEOUT_SECONDS` in `engine/model.py`), which bounds a hung request so it fails with a message instead of holding a persona's turn forever. The limit is one number against a wait that grows with the prompt and with the machine: on `gemma2:9b`, one machine, a cold start took about 100 s at 4.8k tokens (about 50 tokens a second read), so a chat near the 6.1k budget goes past 120 s and fails with "couldn't reach the model" when the model was only slow. A probe with a 4.9k prompt hit it.

The limit that matters is the one for the first word. The call streams, and the timeout is the longest the connection may stay silent between pieces of the reply; after the first word the pieces come every fraction of a second, so in practice only the first-word wait ever reaches it. (A silent gap later in a reply is bounded by the same number, which is fine: a stuck model still fails.)

## Decision

**The wait grows with the prompt.** `engine/model_wait.py` gives a call `120 s + 1 s for every 40 tokens of the prompt` (the tokens estimated at 4 characters each, no model needed). A 4.8k prompt is given 240 s, the measured 100 s with more than twice the room; a 6.1k prompt 272 s; a short one still 120 s, so a hung request fails as fast as it did.

**The user can set it: `model_timeout`** (whole seconds, 30 to 3600; empty is automatic, which is the rule above). It is the whole wait, not an addition to the automatic one, so a user on a slow machine sets the number they want, and a user who wants a dead model to fail sooner can lower it. A value out of range, or not a whole number, is automatic. It is in the shared settings registry (ADR 036), in the Context group, in the terminal's `/settings` and the web settings.

**The error says what happened.** A call that ran out of time is reported as that, with how long it waited and what to do: "No answer from `<model>` in N seconds. A long conversation on a slow computer can need longer: `model_timeout` sets the wait." Any other failure keeps its message.

## Consequences

- A long cold prompt on a slow machine waits instead of failing; a model that is really stuck still fails, after a wait that is larger for a larger prompt (at most about 5 minutes at the budget, unless the user chose more).
- A persona's turn can now be held for longer behind a hung request, until the wait ends. The stop button (ADR 054) is not affected: it ends the call whatever the limit.
- The estimate is a guess about the prompt, not a measurement of the machine. A machine slower than about 40 tokens a second reading a cold prompt needs the setting; that is why it exists.
- The recaps, the compaction notes and the other background calls go through the same function and get the same rule.

## Alternatives rejected

- **A watchdog that only times the first word** (a long wait for the first word, a short one after): `litellm` and `httpx` give one read timeout per call; separating the two needs our own timer thread closing the stream, for a gap that was never the problem.
- **Measure the machine's speed and scale from it.** Needs a calibration call or history to keep; the setting does the job for the few who need it.
- **Only a setting, with the fixed 120 s as default.** Leaves the failure in place for everyone who does not find it.
