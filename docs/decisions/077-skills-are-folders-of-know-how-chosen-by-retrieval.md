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

> **Summary.** Skills are folders with a `SKILL.md` in Anthropic's Agent Skills format, bundled in `sympose/skills/` or the user's own in `profiles/<handle>/skills/`, and chosen by retrieval. A persona had knowledge, powers and identity but no written procedures for recurring jobs, and the soul cannot hold them. In `auto` mode a prompt grows by at most one skill body, bounded by `skill_cap`; `ask` and `use_skill` were tried and removed (second amendment).

> **Status: Accepted; `auto` built (2026-10-08), `ask` and `use_skill` tried and removed (2026-10-09).** Design agreed with damiro, 2026-10-07. See the amendment for what was built and measured.

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
1. `ask` and `use_skill(name)`, and more than one skill per message: tried and removed (second amendment); to be taken up again only when a persona carries many skills.
2. Creating a persona: a power (a `propose_persona` tool, staged in Drafts, written only on Accept, validated by the engine: handle, icon, colours, folders, a soul that is voice only) and the skill that uses it; the soul skill grows into it.
3. Changing a setting: a power (`propose_setting`, the user's Accept; `cloud_share` and the model always ask), so the persona who explains every setting from the reference library can also change it. The `tools:` line already keeps a skill that names a tool nobody has from being offered.
4. A Skills page in the web app, with the review of a copied-in skill before it is enabled.
5. Scheduled runs and MCP tools, as in the backlog.

## Amendment (2026-10-09): `ask` and `use_skill` tried, measured, and removed

**Tried.** `skill_lookup=ask` gave a tool model one tool, `use_skill(name)` (the name restricted to the offered skills), and listed the offered skills by name and description before the message; calling it again gave another skill, so several skills per message needed nothing more; a model without tools got `auto`. It was built, tested and pushed, then removed the same day (a revert; the code is in the history, commits `76ac202` and `79ac8bc`).

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

What it showed: on Gemini Flash `ask` matched `auto` on every soul and near-miss case; on `gemma4:e4b` it was within the noise of a sample of 3. Near misses were already 3 of 3 under the final `auto` label, so there was no mistake for `ask` to fix. In the terminal script `gemma4:e4b` took the skill up in 3 of 5 runs of the Marie Curie request; in the web app, where `propose_persona` is also offered, it took it in 0 of 4 and went straight to that tool.

**Why it was removed.** With one carried skill there is nothing to choose between, so `ask` bought an extra round trip and a weaker result on a small model. Left in, it would also have been offered as a choice in Settings, described in the reference library (which the persona quotes as truth) and proposable by the persona through `propose_setting`, each of which would move a user to a mode that is not better: a regression to fix, not a tradeoff.

**For when it is taken up again.** `use_skill` is a tool call, so it spends one of the turn's lookups (`vault_lookup_rounds`, 3 by default). Gemini Flash on the drafting case took the skill, looked up the folder's definition and notes, and used its three lookups without writing (3 errors of 3, where `auto` gave 2 of 3); the call should not count against the rounds. The case for `ask` is a persona with many skills, where matching on a description gets shakier; measure it then, on a larger sample.

## Amendment (2026-10-09): the drafting skill made reliable on a tool model, not yet carried

**What the measurement had hidden.** The drafting cases passed on prose: her reply, read together with the note, had to match, so telling the user "I've drafted it" with the text beneath counted. They now pass only when a note reached `propose_note` and that note, read alone, has its properties between `---` lines, the sections in the folder's order, and nothing the user did not say (`tags:` and `rating:` empty). Also, the scratch persona in `live_skill_cases.py` copied Samantha's `persona.yaml`, so the drafting skill, not in her list, was never in the earlier "skill on" runs of it.

**What the strict test found** (`gemma4:e4b`, 4 runs per case, before any change): 3 of 4 on the first case and 1 of 4 on the second. The notes that were filed had no opening `---`, a `## Properties` heading, `Prep Time` for `time`, and `tags: pesto, vegetarian, summer, dinner` from nothing; in other runs she said she had drafted a note and filed none. The search had found no notes for "add a recipe: mushroom risotto", so the folder's template reached the model only if it looked it up. `gemma2:9b` never filed a note (0 of 3 on both cases), even when the prompt was fixed and the folder's notes were handed to it, which matches ADR 072 (a marker proposal is right about half the time and every further line costs it edits).

**Built.** (1) `skill_folder.shape_for`: when the skill's header says `context: folder`, the engine picks the one top-level folder the message names (by its name, plural or not, or by a constant of its template such as `type: recipe`; none when two fit equally or none does) and puts its definition note and its fullest note into the skill's text exactly as stored, each cut after a whole line at 1500 and 1800 characters. No model call, no round trip, real vault content only; a cloud model gets them only when `cloud_share` allows `notes`. (2) The pseudo-tool `tool_calls` in a skill's `tools:` line: the model must call tools rather than write markers, so the drafting skill is not offered to `gemma2:9b`, which keeps its plain answer (the precedent is ADR 078's persona creation). (3) `edit_tools.fenced`: a new note whose text starts with property lines and either a closing `---` or at least two of them, but no opening `---`, is filed with the fence lines added (the commonest failure above); nothing else is touched. (4) The skill's steps say to copy the shape character for character, to leave ungiven properties empty, and to say "drafted" only after the call. 19 new unit tests; the mutants of each rule are caught.

**Measured** (strict test, `gemma4:e4b`, run alone; a first run with another measurement going at the same time gave 1 of 6 and 0 of 6 because the tool-support probe timed out and the skill was withheld, which is the gate working on a bad probe, not a result): drafts in the folder's style 6 of 6, keeps the section order 5 of 6 (the miss added `tags: [vegetarian]`). The full set with both skills carried, 3 runs: 3 of 3 and 2 of 3 on the drafting cases, near misses 3 of 3 and 3 of 3, small talk 3 of 3, the soul cases as before (1, 2, 2, 3 of 3). Samples of 6 and 3 are direction, not a figure.

**Decision.** `drafting-a-note-in-a-folders-style` stayed out of Samantha's list until it was measured on Gemini Flash (see the next amendment). Left open: a model that says it has drafted a note and files none (3 of 12 here, caught by the strict test, not by the engine), and the tool-support probe timing out under load, which silently turns a tool model into a marker model for that turn.

## Amendment (2026-10-09): the drafting skill measured on Gemini Flash and carried

**Measured** (strict test, `python tests/live_skill_cases.py -v 3 gemini/gemini-flash-latest`, damiro's go-ahead, invented data only): drafts in the folder's style 3 of 3, keeps the section order 3 of 3, the soul cases 3 of 3 in each of the four, near misses 3 of 3 and 3 of 3, small talk 3 of 3. Every filed note had its properties between `---` lines, `rating:` and `tags:` empty, and nothing the user did not say. In a re-measure on `gemma4:e4b` (5 runs, skills on against off): drafting cases 4 of 5 and 4 of 5 with the skill, 0 of 5 and 0 of 5 without; the misses were a reply that said it could not save notes and one empty reply (the model-layer problem of ADR 080). Samples of 3 to 5 are direction, not a figure.

**Decision.** Samantha carries `drafting-a-note-in-a-folders-style` next to `deriving-a-persona-soul`. It is offered only to a model that calls tools, so `gemma2:9b`, the default local model, answers as before. The reference library (`Settings.md`, `skill_lookup`) says so.
