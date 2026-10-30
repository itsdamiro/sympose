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
