---
type: decision
status: accepted
date: 2026-10-08
projects: [sympose]
concepts: [Persona edits, Settings]
amends: [78]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/consent, topic/web-app]
---

# 080 — A persona asks for the user's yes to change a setting, on the same card

> **Summary.** The second kind of confirmation request (ADR 078) is a setting: she proposes one change, the chat shows it as a card (what it is, from, to), and nothing changes until the user clicks Accept. It covers the engine settings of `/settings`, the persona's own model, and one category of `cloud_share` at a time. Web app only, tool models only, the persona with the reference library only.

> **Status: Accepted (damiro, 2026-10-08).** Builds on ADR 078 (the card and the request), ADR 036 and 044 (the settings registry and the rules for a value), ADR 046 (a persona's model) and ADR 031 (what a cloud model may receive).

## Context

A user asks "this is slow" or "stop sending my notes to the cloud" and the persona knows the knob (the reference library describes every setting) but can only tell them where it is. ADR 078 built the mechanism for a yes in the chat and left this as the next kind. The user chose the widest scope: the model and `cloud_share` are included, not only the `/settings` list.

## Decision

**1. One setting per card.** Her tool `propose_setting(setting, value)` files a request of kind `setting`. A second proposal for the *same* setting replaces the waiting one (the old card turns to `replaced`); proposals for different settings sit side by side, since "make it faster" can honestly need two.

**2. What `setting` may name.** (a) A key of the engine settings registry (`settings_registry.SETTINGS`), with a value of its kind: true or false, one of its choices, or a number (empty or null puts the default back). (b) `model`: the model of **the persona that is talking**, saved as the model picker does (`persona_model`, ADR 046), the value an id from the list the picker offers. (c) `cloud_share:<category>`: true or false for one category of what a cloud model may receive (ADR 031), saved by `sharing.set_approved`. Nothing else: not `chat_model`, not the vault settings, not a persona's files.

**3. The card** is made of what ADR 078's card already is: a header (the setting's name and a line on what it does), the change as *from → to* in plain words ("Allowed for a cloud model: no → yes"), and Decline and Accept. The user has no choice to make on it except the yes. Two lines are added where the consequence is not in the change itself: for `cloud_share` the description of the category ("parts of your notes that match your message"), and for a model change to a cloud model, that the messages go to it together with any earlier replies in the chat that quote notes (ADR 031's known consequence: history goes whatever is allowed), and that the rest of the vault goes only where Settings allows.

**4. Checked again on Accept.** The request stores the setting name and the value as she gave them. Accepting re-resolves the name, re-parses the value, and applies it through the module that owns the setting (`settings_apply`, `persona_model`, `sharing`), exactly as the Settings page and the terminal do, so a value the owning module refuses is refused here with its reason and leaves the setting as it was (the request stays waiting for a number the module refuses, so she can be asked for another). The card is a view, never the authority.

**5. At proposal time** the tool checks the name, the value's shape and, for a model, that it is on the list, and answers with the first thing wrong so she can fix it. A number's range is the owning module's rule and is only known by trying, so it is checked on Accept.

**6. She learns the outcome** in one line on her next turn, as for a persona: "You proposed changing X to Y: the user accepted it / declined it / it could not be applied."

**7. Who and where.** The persona with the reference library (`sympose_reference`), on a model that can call tools, in the web app, not in `plan` mode: the same rule and the same flag as proposing a persona. The flag is renamed from `proposes_personas` to `proposes` since it now gates both tools.

## Consequences

- Her answer to "stop sending my notes to the cloud" becomes a card with one click, and the click is the user's.
- A hostile note that talks her into proposing `cloud_share:notes` still only produces a card the user can decline, with the category described on it. This is the check that justifies including `cloud_share`.
- Nothing about a setting is decided by the model beyond "this one, to that": every rule stays where the setting lives.

## Alternatives rejected

- **Several settings on one card.** More useful for "make it faster", but a bigger card, a per-setting tick and more rules. Revisit if one-at-a-time proves tedious.
- **Leaving `model` and `cloud_share` out.** The safer scope, and the one recommended; the user chose to include them, with the card as the safeguard.
- **A global `chat_model` change.** The persona's own model is what the user sees and changes in the chat; the global fallback has its own home (`/model`, ADR 036).

## Amendment (2026-10-08): built, and measured on Gemini Flash

**Built** as decided (web app, tool models only). One difference from the text above: a registry setting's card has no second line on what it does, because its label already says it ("Most earlier chat sent per message (history_tokens)"); the model and `cloud_share` cards keep theirs. The warning line is shown only while the card waits.

**Measured** (`tests/live_setting_cases.py`, invented data, `gemini/gemini-flash-latest`, 6 runs per case, 2026-10-08; nothing is changed by a run, and each run also checks that). 15 of 15 cases at 6 of 6: a number by name, a toggle and a choice in words, stop and allow `cloud_share:notes`, her own model, two settings in one message (two cards), a second proposal replacing the waiting one, "replies are slow" (a speed setting, never a sharing one), `chat_model` refused with the reason and `/model` pointed to, and none for questions about a setting, about what goes to a cloud model, a request about notes, or small talk. Read by eye: for "set history_tokens to lots" she asked what number was meant in one run and proposed removing the cap in the other (a card the user can decline). Direction only, one model and 6 runs: `gemma4:e4b` is not measured, and `gemma2:9b` is not given the tool.
