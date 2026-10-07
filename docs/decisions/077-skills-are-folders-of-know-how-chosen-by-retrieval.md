# 077 — Skills are folders of know-how, chosen by retrieval

> **Status: Proposed (design agreed with damiro, 2026-10-07); not built.** Closes the design half of #22. Nothing is built until the baseline run below is done.

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
