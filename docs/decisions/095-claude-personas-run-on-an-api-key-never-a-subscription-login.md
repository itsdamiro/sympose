---
type: decision
status: accepted
date: 2026-10-30
projects: [sympose]
concepts: [Chat engine, Cloud privacy]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/engine, topic/privacy]
---

# 095 — A Claude persona runs on an API key, never on a subscription login

> **Summary.** A persona may run on a Claude model through an API key from the Console organization that a Max plan's monthly API credits are linked to, so a Max subscriber can use Claude in Sympose without paying outside the plan. Sympose never signs in with the subscription and never runs Claude Code as its model. No code is written first: the key and the model entries already exist, so the first slice is measuring on a real key. When the credit is used up requests stop and nothing is charged, and Sympose has to say so in one plain line.

## Context

- damiro asked (2026-10-30) whether a persona can use his Claude subscription so that he spends nothing outside it. A subscription is not an API: a Claude plan covers claude.ai and Claude Code, and Sympose calls models through litellm with a provider key (ADR 007).
- Anthropic's terms bar routing requests through a Free, Pro or Max login on someone's behalf; an app built on the Agent SDK is to use an API key. A subscription login or a `claude -p` subprocess as Sympose's model is therefore not a route (read 2026-10-30, [Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)).
- There is a second route that is allowed. Max and Team plans include monthly API credits: Max 5x $100, Max 20x $200, Team $20 per standard seat and $100 per premium seat, pooled and capped at $500. They are claimed in claude.ai under Settings, Billing, API credits, by linking one Console organization (7 days on the plan first). Any API key of that organization draws from the balance, and the balance covers the Messages API, Managed Agents and the Agent SDK. It does not cover interactive Claude Code. It resets each billing cycle with no rollover; when it is gone requests stop until the next cycle, and the plan is never charged (read 2026-10-30, [Monthly API credits for Max and Team plans](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-and-team-plans)). Pro, Free and Enterprise are not eligible.
- Anthropic's pages disagree on one point: the Agent SDK article still describes a June billing change as paused. This record rests only on the credits article and on the API key route, and neither depends on that change.
- What exists: `ANTHROPIC_API_KEY` in `.env` and two Claude entries in the picker (`anthropic/claude-sonnet-5`, and Claude Haiku 4.5 through OpenRouter, which spends OpenRouter money and not the credit). The ids in `model_options.py` were never run with a real Anthropic key, so they may not resolve.
- What a Claude turn would do that a local one cannot: call tools (ADR 040), and follow the vault-grounding rule better than the small local models (ADR 072, 081). Neither is measured on Claude yet. ADR 031 already says what a cloud model may receive, and Claude is a cloud model.
- Unattended runs (ADR 091 jobs, and Slack) use the same key. A job with a model of Claude spends the credit with nobody watching.

## Decision

1. **The only route is a Console API key.** The user claims the credits, creates a key in the linked organization and puts it in `.env` as `ANTHROPIC_API_KEY`, as for every other provider (ADR 007). Sympose does not ask for the key in chat, does not take a subscription login, and does not start Claude Code or the Agent SDK as a model backend.
2. **No code before a measurement.** The first slice runs real turns on a Max 5x key and reports, as figures from a stated number of runs: whether each Claude id in the picker resolves; the cost and the wait of one turn, with and without tools; whether Claude calls tools for `vault_lookup` `"ask"`; the grounding cases in `tests/live_prompt_cases.py` against `gemma4:e4b`; and what an unattended job costs. Code changes only where that shows a gap.
3. **Running out is a stop, and Sympose says it plainly.** When the credit is used up, the provider's refusal reaches the person as one line that says the credit is used up and when the next cycle starts if known, not a raw litellm error. This holds in the web app, the terminal, Slack and a job's log. The measurement checks what the refusal looks like and the line is written from that.
4. **Sympose never turns on auto-reload or buys credit.** That is a choice in the Console, and the reference note says that leaving it off is what keeps spending inside the plan.
5. **Nothing about privacy changes.** A Claude model receives what ADR 031 lets a cloud model receive, no more.
6. **Claude is not recommended, and does not join a measured list, until it is measured.** `lookup.MEASURED` (tool use) and `web_access.WATCHERS` (video) are joined by measurement only, as ADR 089 says. Anthropic's own web search and page reading are not used by this record; a persona on Claude gets captions for a video and no way to read a page, like any non-Google model.

## Consequences

- A Max subscriber can run a persona on Claude and, with the credit, pay nothing beyond the plan, as long as the credit lasts; it is lost if unused, so there is no reason to ration it.
- A user on Pro or Free gets nothing from this record: for them Claude is the same pay-per-token provider it already was.
- The rule leaves no trick open: if the credits change or the terms do, the route is still an API key, and only the figures in Context are out of date.
- Unattended work can use up the month's credit while nobody looks. Decision 3 makes the stop visible; it does not prevent the spend. Whether a job's cap (ADR 091) should be able to read a balance is left open, because Anthropic's pages do not say the balance can be read by key.
- The picker's two Claude rows may need a different id or a replaced row once measured. That is a data change, not a design one.
- The reference note `Choosing a model` and the retrieval eval are updated in the slice that changes what Sympose says about Claude, not in this one.

## Alternatives rejected

- **Sign in with the subscription, or run `claude -p` or the Agent SDK as the model.** Against the terms for an app that is not Claude Code itself, and it would hand the turn to an agent loop with its own system prompt and tools, so grounding and the single-shot cost could no longer be guaranteed (CLAUDE.md: vault grounding is zero-hallucination). Right only if Anthropic offered a supported subscription login for third-party apps.
- **Route Claude through OpenRouter.** It works today, but it spends OpenRouter money and not the plan's credit. Right for a user with no Max plan.
- **Buy API credit.** Does what the user asked not to do.
- **Build Claude-specific features now (prompt caching, Anthropic's web tools, a balance meter).** No measurement says they are needed. Each is right once the first slice shows a cost or a gap that it would fix.
- **Do nothing and leave it undocumented.** The entries and the key already exist, but nobody would know that a Max plan pays for them, nor that the other route is closed.

## Amendment (2026-11-05): the first measurement

Decision 2's measurement was run once on damiro's own Console key, on scratch data only (the fixture vault, a copy of the shipped Samantha persona, a temporary settings file). Single runs: each figure is one sample, and cost is litellm's estimate, not a Console reading.

- **The ids resolve.** `anthropic/claude-sonnet-5` and `anthropic/claude-sonnet-5-5` both answered; the picker row needs no change. A Sonnet 5.5 row is not added.
- **One chat turn costs about half a cent** ($0.004 to $0.008, about 1,900 input tokens) and waits 1 to 3 seconds on Claude. The 53 calls of the 35 prompt cases cost $0.24 (mean wait 2.6 s).
- **Tool use works.** In `vault_lookup` `"ask"`, Claude looked a note up on 8 of 9 turns that needed one and looked nothing up on 6 of 7 that needed none; 34 calls cost $0.27. Both cases it passed cited the right note.
- **Grounding held.** No reply invented a source or a fact about the vault. Of 35 prompt cases 33 passed on the first run, and of 18 `ask` cases 17. One failure is a stale case, not a fault: `sympose-not-built-is-said-plainly` expects "not yet" for Slack, which is built (ADR 093). The other is a mild leak that the case `general-knowledge-with-no-notes` forbids: after a correct general-knowledge answer Claude added a remark about the vault ("Nothing in your vault came up for this", "No need to dig through your notes"), in both modes.
- **An unattended job costs about 11 cents a run:** five model calls, 38,153 tokens in and 3,506 out, 39 seconds. A second run the same day was refused by the cloud default of one run a day (ADR 091) before any model call. At that cap a daily job is about $3.30 a month and a weekly one about 45 cents. The job's output waited as a draft and the vault was untouched. The draft's text was not read.
- **Not measured:** whether these calls drew on the plan's API credit or were charged to the organization's own balance (the response does not say; only the Console shows it), `tests/live_prompt_cases.py` against `gemma4:e4b` in the sense the decision meant (the cases were run on Claude itself), and what the used-up-credit refusal looks like (it was not provoked: that would spend the whole credit). Decision 3's one line is therefore not written.
- **Not changed:** `Choosing a model.md`, the reference library and the retrieval eval still say nothing about Claude; Claude stays out of `lookup.MEASURED` until a larger sample (decision 6).
