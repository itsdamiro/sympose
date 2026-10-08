---
type: decision
status: accepted
date: 2026-09-27
projects: [sympose]
concepts: [Settings]
amends: [6]
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 032 — The speed of the reply reveal is a setting: `reply_reveal`, words per second, 50 by default

> **Status: Accepted.** Amends ADR 006 (the reply is revealed word by word in the CLI). Closes #73.

## Context

The terminal chat receives a reply whole and then reveals it one word every 50 ms (20 words per second), a literal in `sympose/cli/turns.py`. A 600-word answer takes about 30 seconds to appear although it has already arrived, so the reveal is now slower than the model itself (roughly 25 to 60 words per second, depending on the model). Some users will want it faster, some instant, and a shipped default a user could plausibly change belongs in the settings store, not in a constant. Each tick also rebuilds and redraws the whole text so far, so the redraw rate matters as much as the speed.

## Decision

- **A `reply_reveal` setting: words per second, default 50, `0` shows the whole reply at once.** Read on each reply, so an edit applies to the next one. Only a number that is not a bool and is finite and not negative counts; anything else (a hand-edited `"fast"`, `null`, `true`, a negative, infinity) leaves the default, so a malformed value never changes the speed by accident.
- **The redraw rate stays at 20 frames per second** (a 50 ms tick, as before). Each frame shows the words the chosen speed has reached by then (`ceil(speed × frames ÷ 20)`), so 50 words per second shows two or three words per frame, 20 shows one (as today), and a speed below 20 still advances on time. A faster reveal therefore costs no more redraws than the old one.
- **No cap on the total time.** Speed plus "instant" cover both preferences; a second knob would be more code for little gain.
- The code that turns the setting into a number of words lives in `sympose/cli/reveal.py`, so `turns.py`, which is at the 200-line cap, grows by a few lines only.
- Changed in the settings file for now; the CLI `/settings` screen was still canned (#25, built in docs/decisions/036, where `reply_reveal` is a row), and a slash command per knob is not added (as in ADR 015).

## Consequences

- **Measured** (a 600-word reply revealed in the app, headless, scratch settings): 12.0 s at the default of 50, 0.1 s at `0`, 30.4 s at 20 (the old speed). The redraw rate is the same in all three (20 frames per second). A 50-word reply takes about one second at the default.
- `cli/turns.py` is two lines over the 200-line cap (202), left as it is under the rule that a few lines over is fine when cutting is not practical.
- Real token streaming (ADR 006, "Alternatives rejected") is still not built; when it exists this reveal has no job and the setting goes with it.

## Alternatives rejected

- **One word per tick with the tick interval set from the speed** (20 ms at 50 words per second): the simplest code, but it multiplies the redraws of the whole text by 2.5 and the cost grows with the length of the reply.
- **A cap on the total reveal time** (say 8 seconds): a second knob and more code; a user who wants a reply at once sets `0`.
- **Keeping 20 words per second and only making it a setting:** keeps a default that is slower than the model.
- **Showing the whole reply at once until streaming exists:** removes the feel of a reply being written, which ADR 006 chose on purpose.
