---
type: decision
status: accepted
date: 2026-10-31
projects: [sympose]
concepts: [Chat engine, Cloud privacy]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/engine, topic/privacy]
---

# 096 — A Gemini persona runs on an API key, and the plan's Cloud credit may pay for it

> **Summary.** The rule of ADR 095 holds for Gemini: a persona runs on an API key, never on a subscription login, a Gemini CLI token or an Antigravity login. A Google AI Pro or Ultra plan includes a monthly Google Cloud credit that can pay for API calls through a Cloud billing account, but unlike Claude's credit it is not a closed allowance: a billing account with a card can keep charging after the credit is gone. So the first slice measures where the money goes before anyone relies on it, and the reference note tells the user to set a budget cap first.

## Context

- damiro asked (2026-10-30) whether his Gemini subscription can be used the way a Max plan's API credit can (ADR 095), without an API key.
- A Gemini subscription is not an API. No sanctioned way for a third-party app to sign in with a Google AI Pro or Ultra login was found: a developer-forum post (2026-07-21) says none exists and has no reply from Google, and secondary sources say Google treats subscription logins in third-party tools as against its terms and points to an AI Studio key instead. Google's own pages that were read (the Google AI credits help article, the Developer Program plans page) say nothing on the point either way, so this is not confirmed from Google's side.
- What Google's own page does confirm: Google AI Pro includes $10 a month of credit, Google AI Ultra $40 (20TB plan) or $100 (30TB plan), usable in AI Studio and the Gemini platform ([plans and pricing](https://developers.google.com/program/plans-and-pricing), read 2026-10-31). What it does not say, and only secondary sources do ([SmartScope](https://smartscope.blog/en/blog/gemini-api-pro-ultra-monthly-credits-2026/), 2026-10-09): that the credit is applied by hand to a Cloud billing account, that it expires after a year and rolls over monthly until then, and that calls stop when the prepaid balance reaches zero. None of that is verified here.
- The difference from Claude that matters: Anthropic says that when the credit is used up requests stop and the plan is never charged. A Google Cloud billing account has a payment method, so what happens at zero is not known to be a stop.
- What exists: `GEMINI_API_KEY` in `.env` (ADR 007), the Gemini Flash and Pro rows in the picker, and Gemini Flash as the one model that watches video and reads pages (ADR 089, `web_access.WATCHERS`). ADR 089 measured the cost on a paid key: a plain turn costs a fraction of a cent in tokens, a page read about a cent, a turn that searches 1.5 to 3 cents (nine tenths of it the searches), and prices double on 2027-01-01. It also found that Google's free tier has no search grounding, and that a user on it gets Google's refusal, said as Google's words.
- ADR 031 already says what a cloud model may receive. Google's free tier may use prompts to improve its products (secondary source); a paid project's prompts are not used for training.

## Decision

1. **The only route is an API key.** The user makes the key in AI Studio or Cloud, on a project they choose, and puts it in `.env` as `GEMINI_API_KEY`. Sympose does not ask for it in chat, takes no Google login, and does not start the Gemini CLI or Antigravity as a model backend.
2. **The plan's credit is a funding source, not a feature.** Sympose does not claim, apply or watch the credit, and does not touch billing. The reference note says how a user with Google AI Pro or Ultra can point the credit at the project the key belongs to, with the steps checked in the measurement below.
3. **Measure before writing it down.** The first slice, with damiro's go-ahead, makes a key on a project with the credit applied and checks, from the billing report and not from the plan page: that a real turn draws from the credit and not from a card; the cost of a plain turn, a page read and a search against the figures of ADR 089; whether and how requests fail when the credit is gone and the account has a card; and whether the claims taken from secondary sources (applied by hand, a year's expiry, rollover) are true on his account. Nothing in the product or the reference library says any of it until then.
4. **A cap before the credit.** The note tells the user to set a budget alert and a cap in the Cloud Console before using the credit, because this is the one provider here where running out may mean a charge. Sympose does not set it for them and has no way to see a balance.
5. **When Google refuses, it says so in Google's words**, as ADR 089 already does for the free tier. A used-up-credit line like ADR 095's is written only if the measurement shows a refusal to write it for.
6. **Nothing about privacy changes** (ADR 031). The note says that a project without billing is the free tier, which has no search grounding and may use prompts to improve Google's products.

## Consequences

- A user with Google AI Pro can fund Gemini Flash use with the plan's $10 without anyone's login being used. At the ADR 089 figures that is a few hundred searching turns, or far more plain ones, a month; this is arithmetic from a measurement on a paid key, not a figure for a real month.
- A Google AI Ultra user has a larger credit. A user with neither has the pay-per-token and free-tier options they had.
- The risk the ADR cannot remove: a card on the billing account. Decision 4 puts the caution in the note; the cap is theirs to set.
- Prices change on 2027-01-01 (ADR 089); the figures here must be taken again after that.
- Nothing in the code changes in this record. A refusal line, a model row or a note edit comes only from the measurement.

## Alternatives rejected

- **Sign in with the subscription, or run the Gemini CLI or Antigravity as the model.** Not a sanctioned path for another app, and it would hand the turn to an agent loop that Sympose does not control, which puts vault grounding at risk (CLAUDE.md). Right only if Google offers a supported login for third-party apps; the forum thread above is where to look for it.
- **Build a credit meter or an auto-applying step.** Balances are kept at the billing-account level and the page that was read does not say a key can read them. Right once the measurement shows a documented way to read one.
- **Fold this into ADR 095.** That record is about one provider's terms and one closed allowance; this one is about a credit that is not closed. Merged, one of the two would be wrong.
- **Say nothing and rely on the free tier.** It has no search grounding and may train on prompts; for a companion that reads a private vault it should be a choice the user is told about.
