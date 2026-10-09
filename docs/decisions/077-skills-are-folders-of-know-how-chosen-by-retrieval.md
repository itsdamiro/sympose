---
type: decision
status: accepted
date: 2026-10-08
projects: [sympose]
concepts: [Skills]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/retrieval]
---

# 077 — Skills are folders of know-how, chosen by retrieval

> **Summary.** Skills are folders with a `SKILL.md` in Anthropic's Agent Skills format, bundled in `sympose/skills/` or the user's own in `profiles/<handle>/skills/`, and chosen by retrieval. A persona had knowledge, powers and identity but no written procedures for recurring jobs, and the soul cannot hold them. In `auto` mode a prompt grows by at most one skill body, bounded by `skill_cap`; `ask` and `use_skill` are built (second amendment), not yet measured.

> **Status: Accepted; `auto` built (2026-10-08), `ask` and `use_skill` built (2026-10-09), `ask` not yet measured.** Design agreed with damiro, 2026-10-07. See the amendment for what was built and measured.

## Context

A persona has knowledge (the reference library, ADR 019), powers (the vault tools, ADR 072) and identity (the soul, ADR 012; voice only). What it lacks is know-how: a written procedure for a recurring job ("derive a persona's soul from a historical figure", "draft a note in a folder's style"). Putting procedures in the soul is ruled out by ADR 012; putting them in the engine prompt costs tokens on every turn and weakens small models. Legacy solved selection with phrase lists, which break on the first unexpected wording.

## Decision

**1. Format: Anthropic's Agent Skills.** A skill is a folder with a `SKILL.md`: frontmatter `name` (lowercase, hyphens, gerund form) and `description` (third person: what it does and when, in words people say), then the body. Optional extra files sit beside it. Bundled skills live in `sympose/skills/`; the user's own in `profiles/<handle>/skills/`. `persona.yaml`'s existing `skills:` list (read but unused today) names the ones a persona carries. Only Samantha ships with baseline skills (never-break rule: no other persona's content is committed).

**2. No script is ever run.** A skill is text. It tells the persona what to do with the tools she already has; it cannot add a tool or execute anything. A skill copied in from elsewhere is untrusted text: shown to the user before it is enabled, size-capped, never installed automatically.

**3. Selection, with no phrase lists.** A setting `skill_lookup`, in the manner of `vault_lookup`, with two modes:

- `auto` (default, and the only mode for a model without tools): the existing retrieval index covers each skill's name and description. The best match's body joins the prompt; when nothing clears a threshold, none does. No extra call.
- `ask` (tool-capable models): the prompt lists names and descriptions and the model calls `use_skill(name)`; one extra round trip, which is the dial CLAUDE.md allows users to turn for reliability.

A setting `skill_cap` bounds the body that is loaded (small models). Extra files of a skill load only in `ask`.

**4. Powers.** A skill follows its steps with the tools the persona has (lookups, `propose_note`, `propose_edit`, `comment_on`, `show_note`, `remember`). Every write still waits for the user's Accept (ADR 072). A `tools:` line in the header names what the skill needs; Sympose checks it against the persona and the model and does not offer a skill the persona cannot carry out. New powers (MCP tools, scheduled runs) are separate slices, each driven by a skill that needs them.

**5. How skills are written and tested** (adapted from the user's playbook, "Claude Skills in Production"):

- Progressive disclosure with tighter caps than the playbook's: description short, body under `skill_cap`, detail in extra files.
- Degrees of freedom: the Accept gate is the low-freedom step; the rest may be loose.
- Short checklists with go-back lines; a strict output template with two examples.
- Feedback loops live in the engine: validation returns a specific error the model can act on (as `table_spans.problem` does), not a longer prompt.
- Hooks do not apply: the never-break rules live in code.
- **Evals first.** Each skill ships `evals/evals.json` with at least three scenarios, run on `gemma2:9b`, a tool model (`gemma4:e4b`) and Gemini Flash. Writes are the critical tier. Vault grounding must not regress: a skill that makes a model invent vault content is rejected.
- Release audit: the playbook's checklist plus ours (size cap, no scripts, security review of any copied-in skill, reference library updated).

**6. First skills.** Selection is only measurable with at least two, so two ship first:

- `deriving-a-persona-soul`: voice only, about 1.5 KB, per ADR 012. Scenarios: a named historical figure; a vague request; a request to put engine rules or capabilities in the soul (refused); a request to put user details in it (refused).
- `drafting-a-note-in-a-folders-style`: looks up the folder's definition note, follows its template, `propose_note` into the folder.

Later candidates: defining a folder (#23), a synthesis note with sources, reviewing a period, splitting a long note.

## Order of work

1. Baseline run (no skills) of the scenarios on the three models, to know what a skill must beat. A cloud run needs the user's go-ahead each time, with invented data only.
2. Build loading, `skill_lookup`, `skill_cap`, `use_skill`, the `tools:` check.
3. Write the two skills and measure them against the baseline; record the numbers in an amendment here.
4. Reference library entry and a Settings row for the two knobs.

## Not in this ADR

Scheduled or unattended runs (a scheduler, a headless `run_turn`, reporting into Drafts, a cost guard for cloud models; related to Slack #36) and MCP tools for a persona. Both go to the backlog.

## Consequences

- A persona's prompt grows by at most one skill body per turn in `auto`, none when nothing matches; the cost is bounded by `skill_cap`.
- Selection quality rests on the retrieval index and the descriptions, so descriptions are tested, not assumed.
- The user can write and share skills without touching code; the price is that a copied-in skill is a prompt-injection surface, hence the review step.

## Amendment (2026-10-08): `auto` built and measured

**Built.** `engine/skills.py` reads the skill folders (`parse` refuses a header that is missing, names the skill other than its folder, is not lowercase letters, digits and hyphens, has no description, a description over 400 characters, a `tools` that is not a list, or no steps; a file over 20,000 bytes is not read), `carried` gives a persona the bundled skills its `persona.yaml` names plus every skill in its own `skills/` folder (its own replaces a bundled one of the same name), `select` picks the best match by the strict retriever over name and description (none when nothing matches), and `text_for` cuts the body at a line within `skill_cap` (default 3000, least 500). The skill goes into the user's turn right before the message, under a one-line label. Settings `skill_lookup` (`auto` default, `off`) and `skill_cap`. `tools:` is checked against what the turn gives: the editing tools when she may propose changes, the lookup tools when she looks notes up herself; a skill whose tools are missing is not offered. 19 unit tests; 15 of 15 mutants of the rules caught.

**Measured** (`tests/live_skill_cases.py`, invented recipes vault, 3 runs per case, a run that errored counts as a fail; the same code with `SKILLS=off` is the baseline). Final wording of the label, skills off then on, passes of 3:

| Case | `gemma2:9b` | `gemma4:e4b` | Gemini Flash |
|---|---|---|---|
| soul, a historical figure | 3, 2 | 1, 1 | 2, 3 |
| soul, a vague request | 3, 3 | 3, 3 | 3, 3 |
| soul, engine rules kept out | 1, 3 | 1, 3 | 1, 3 |
| soul, user details kept out | 1, 1 | 1, 3 | 0, 3 |
| near miss: a note about personas | 3, 3 | 2, 3 | 3, 3 |
| near miss: a folder's description | 3, 3 | 3, 3 | 3, 3 |
| small talk gets no skill | 3, 3 | 3, 3 | 3, 3 |
| draft in a folder's style | 0, 0 | 0, 0 | 2, 2 |
| draft keeps the section order | 0, 0 | 0, 0 | 0, 0 |

What it shows: selection was right whenever a skill was due and never fired for small talk. The soul skill helps (most on keeping engine rules and user details out of the soul) on all three models, least on `gemma2:9b`'s user-details case. The drafting skill shows no gain with the final wording (earlier runs with other wording went from 0 of 3 to 3 of 3 and back to 1 of 3 on the same model, which is the noise of a sample of 3), so it is not carried. Samples of 3 are for direction, not for a figure.

**What the label taught.** The line in front of the skill's steps has to say both things. "Follow its steps" made the soul skill fire on a near miss ("write a note about my persona research" shares *write* and *persona* with the description, and the strict retriever passes on two shared words). "Follow them if the message asks for what the skill is for" fixed the near misses but made `gemma2:9b` ask questions instead of writing (historical figure 3 of 3 down to 0 of 3). "...do it now, without asking first; if the message asks for something else, ignore the skill" kept both (near misses 3 of 3 on every model, `gemma2:9b` historical figure 2 of 3). Ask mode (the model chooses) is the real answer to near misses.

**Findings that changed the build.** A first rule that offered the drafting skill only to a model with lookup tools hid it from `gemma4:e4b`, which gets the folder's definition note from the search Sympose does for it; the skill now requires only `propose_note`. A cloud model cannot read the folder's definition note unless `notes` is approved (ADR 031); it said so honestly, so the harness approves it for invented data. The code review (high) found: a cut that fell on a line end dropped a whole line and said nothing (now cut after a whole line, with a line saying the rest was left out); the skill text of a persona's own skill reached a cloud model without the gate (now only a local model is given one; the bundled skills are public); the header was fragile (a byte-order mark, a `----` line, non-ASCII names; fixed); every turn parsed all the bundled skills (now only the ones named). Declined, with the reason: the skill is not sacrificed by the fitting loop (it is sent only when the message called for that job, and `skill_cap` can be lowered for a small window); the chosen skill is not recorded in the turn record and a follow-up message does not carry it (no new surface; ask mode can keep a skill across turns).

**Grounding regression.** `live_prompt_cases.py` with skills on, `gemma2:9b`, 34 cases: none of their messages selects a skill, even with every tool available, so their prompts are what they were before; the cases that fail there (for example `wrong-premise-is-corrected` 0 of 3) fail for the model, not for skills. Retrieval eval, default mode: 62/68, as before.

**Decision.** Samantha carries `deriving-a-persona-soul` only. `drafting-a-note-in-a-folders-style` ships in `sympose/skills/` but is not in her list until it is reliable (a larger sample, and a step 2 that does not invite lookups to run out, or an engine-side check that a draft reached `propose_note`). 

**Next, in order (not this slice).**
1. ~~`ask` and `use_skill(name)`, and more than one skill per message~~ (built, below).
2. Creating a persona: a power (a `propose_persona` tool, staged in Drafts, written only on Accept, validated by the engine: handle, icon, colours, folders, a soul that is voice only) and the skill that uses it; the soul skill grows into it.
3. Changing a setting: a power (`propose_setting`, the user's Accept; `cloud_share` and the model always ask), so the persona who explains every setting from the reference library can also change it. The `tools:` line already keeps a skill that names a tool nobody has from being offered.
4. A Skills page in the web app, with the review of a copied-in skill before it is enabled.
5. Scheduled runs and MCP tools, as in the backlog.

## Amendment (2026-10-09): `ask` and `use_skill` built

**Built.** `skill_lookup` has a third value, `ask`. When the persona carries skills and the model can call tools, the turn gives the model one tool, `use_skill(name)` (`engine/skill_tools.py`, the name restricted to the offered ones), and lists the offered skills by name and description right before the message, under its own label ("take it up and do the work now ... take up more than one if the message needs it ... take up none" for anything else). The tool gives back the skill's body cut by `skill_cap`; called again it gives another, so several skills per message needs nothing more. What is offered is what `auto` could pick from: the `tools:` check and the rule that a model that is not local sees only the bundled skills (a name outside the list is refused with the list). A model that cannot call tools, or a turn where the tool-calling attempt was refused, gets `auto`. The round trip `use_skill` costs is the dial CLAUDE.md allows, so `auto` stays the default. The reply's footer says which skill was taken up (`followed the skill "..."`); a skill call does not count as a lookup. Tests: `tests/test_engine_skill_tools.py`, three cases in `tests/test_engine_turn_skills.py`, one in `ui/src/lib/grounded.test.ts`.

**Measured** (`SKILLS=ask python tests/live_skill_cases.py 3 <model>`, same cases and sample of 3 as above; passes of 3, `auto` with skills on from the table above, then `ask`):

| Case | `gemma4:e4b` | Gemini Flash |
|---|---|---|
| soul, a historical figure | 1, 2 | 3, 3 |
| soul, a vague request | 3, 2 | 3, 3 |
| soul, engine rules kept out | 3, 3 | 3, 3 |
| soul, user details kept out | 3, 2 | 3, 3 |
| near miss: a note about personas | 3, 3 | 3, 3 |
| near miss: a folder's description | 3, 3 | 3, 3 |
| small talk gets no skill | 3, 3 | 3, 3 |
| draft in a folder's style | 0, 0 | 2, 0 |
| draft keeps the section order | 0, 0 | 0, 0 |

What it shows: `ask` is as good as `auto` on Gemini Flash for the soul skill (it never used a skill for small talk or a near miss), and on `gemma4:e4b` it is within the noise of a sample of 3 (two cases a run lower, one higher; the failures were the persona's reply ending in a stray "(Self-Correction/Review)" note or praising instead of finishing, not a wrong skill). The near misses were already 3 of 3 under the final `auto` label, so `ask` has no gain to show there; it is no worse. `gemma2:9b` was not run: it is not given tools, so it gets `auto`.

**A cost found.** `use_skill` is a tool call, so it spends one of the turn's lookups (`vault_lookup_rounds`, 3 by default). Gemini Flash on the drafting case took the skill, then looked up the folder's definition and notes, and used its three lookups without writing (3 errors of 3; `auto` gave 2 of 3 there). The soul skill needs no lookups, so it was not hit. Not changed here (the drafting skill is not carried): the options are not to count `use_skill` against the rounds, or to raise the default. To decide when a carried skill needs lookups.

**Decision.** `auto` stays the default; `ask` ships as a choice with no measured gain, in line with the round-trip dial, until a skill exists where choosing beats matching.
