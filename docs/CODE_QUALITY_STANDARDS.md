# Code Quality Standards

> Drop this file in as `docs/CODE_QUALITY_STANDARDS.md` in a new project. `CLAUDE.md` and `GEMINI.md` both point here so the two assistants follow the same process. It is the part every task needs. The part that only matters when the task changes or reviews code is `docs/reference/CODE_REVIEW_STANDARDS.md` (§§1 to 6, plus four code rules from §0): read it then, not before.

Every rule either caught a real bug, closed a real gap, or prevented a real kind of wasted effort on Sympose or Stylo (2026-09). Add a rule once it has paid for itself, not on theory.

## Contents

0. Before you write any code
1. Tooling through 6. Type safety (narrow rules, review tiers, triage): moved to `docs/reference/CODE_REVIEW_STANDARDS.md`
7. Verification discipline: no claiming done without evidence
8. Commit hygiene
9. Lightweight decision records
10. Communication style
11. Zero-bloat, applied to tooling too
12. Enforce by code, not by wording
13. Using subagents

## 0. Before you write any code

These are standing working-practice rules, not audit findings — they apply to every task, not just a cleanup pass.

- **Think before coding.** Ask 1–3 clarifying questions on ambiguous requests instead of guessing — no more; over-asking is its own way of stalling. State the implementation steps before executing them on anything non-trivial, and surface any edge cases or conflicts with the existing architecture up front, before they turn into a mid-task surprise. Treat a design critique or question as a discussion prompt, not an order to go implement something — confirm scope first.
- **Touch only what the task requires.** A bug fix doesn't need surrounding cleanup bundled in; a one-shot change doesn't need a new abstraction built around it. If a rule-set adoption or similar task genuinely requires fixing a few small pre-existing issues to start clean (see §2), say so explicitly and keep it small — that's a stated exception, not a license for drive-by refactors.
- **Diagnose before guessing.** When an implementation fails or stalls, find the actual root cause before changing anything else. Trial-and-error edits made without understanding *why* the last one didn't work tend to compound rather than converge.
- **Simplest solution, fewest lines.** Default to the most direct implementation that satisfies the request. Prefer composing existing primitives over adopting a new framework or pattern for one use case.
- **No new dependency without a decision record.** This is the hard-gate version of §9 below, specifically for dependencies: don't add one because it's convenient. Before proposing one, check it's modular (no pulling in a large tool to use one function) and license-compatible with the project; the resulting decision record must weigh it against at least one lighter alternative, not just justify the choice made.

## 7. Verification discipline — no claiming done without evidence

- Every gate the project has must pass before any change is reported complete — typecheck, lint, the full test suite, and the build, not whichever subset is quickest to run. Re-run them after every meaningful edit, not only once at the very end.
- If there's a build step, it must succeed — and for anything UI-facing, actually load the feature and interact with it, don't just trust a green build.
- If you can't verify something yourself (no browser available, can't run the affected service, etc.), **say so explicitly** rather than inferring success from static checks alone. "Typecheck and lint are clean; I couldn't click through the UI myself — can you take a look?" beats a confident claim that can't be backed up.
- Read the actual diff before it's committed, not just a summary of the intended change — this is what catches anything that slipped in beyond the stated scope.

## 8. Commit hygiene

- Split commits by logical concern (e.g. frontend vs. backend, mechanical cleanup vs. judgment-based bug fixes) — the way a reviewer would want to read the history, not one giant commit for a multi-day cleanup.
- Commit messages explain **why**, not just what — the failure mode a fix closes, the reasoning behind a tooling choice — not a restatement of the diff.
- Respect the repo's own attribution conventions (e.g. no AI co-author trailer, if that's the standing preference). Check for a project or personal standing instruction before defaulting to a harness's generic behavior.

## 9. Lightweight decision records for anything durable

- Any new dependency, or any decision that outlives the current task (a new lint standard, a security-hardening approach, an architecture change), gets a short written record: **Context, Decision, Consequences, Alternatives rejected.**
- The "Alternatives rejected" section is not boilerplate. It's where you write down what you deliberately did *not* do, and why — so a future reader (including future-you) doesn't have to re-litigate it or wonder whether it was simply overlooked.
- Keep an index of these records (even a single markdown table) so they're discoverable, not buried in commit history.

## 10. Communication style while doing this work

- Plain-language explanations for a non-coder stakeholder — translate a rule code or a stack trace into what it actually means ("this piece of state was accidentally shared between every instance instead of being separate per object"), not just the label.
- Clearly distinguish "I fixed X" (verified) from "I'm flagging X for your judgment" (a real risk or tradeoff, not a clear-cut bug).
- Ask before large, risky, or hard-to-reverse changes (a mechanical reformat touching every file, a new standing dependency). A short confirmation costs little; redoing unwanted work costs a lot.
- State findings and decisions directly. Skip narrating the process ("I'm now going to...") — say what you found and what you did about it.

## 11. Zero-bloat, applied to tooling too

- Don't add abstractions, dependencies, or automation beyond what the current, real need justifies — including these standards themselves. Adopt the rule categories that found real problems on *this* codebase, not the ones that merely sound thorough.
- When turning on a new standard against an existing codebase, fix whatever small pre-existing issues it surfaces first, so the standard starts from a clean baseline instead of shipping with day-one exceptions nobody will ever get around to.
## 12. Enforce by code, not by wording

An instruction is followed most of the time; a script or a hook runs every time. Pick the layer by what one violation costs, not by how easy the sentence is to write:

| One violation costs | Enforce with | Example |
|---|---|---|
| Little: cosmetic, easily fixed | Wording in `CLAUDE.md` / these standards | Tone of a message, a naming habit |
| Something: wrong, but caught before it ships | A gate or validator that fails loudly (`scripts/gates`) | Lint, tests, a build that must be fresh |
| A lot: irreversible, lost work, a leak, a published mistake | A hook that blocks the action (`hooks/git_safety.py`) | `git checkout -- <file>`, `git add .`, an attribution trailer, a force-push |

Rules for the code that enforces:

- **Say what to do next.** A block that only says "denied" gets worked around. Name the safe alternative.
- **Test both paths.** Every hook and gate has a test that it blocks what it should and lets the normal case through.
- **A gate that cannot fail is not a gate.** A command that checks nothing (a type-check pointed at no files, a test glob that matches none) must be found and removed, or fixed to check something.
- **A recurring procedure is a script, not a paragraph.** If the same steps are rewritten each time (a mutation check, a scratch server, a seed), commit the script. Prose recipes are for what a script cannot hold.
- **Keep them few.** Each hook adds latency and upkeep; reserve them for the "never" rules.

## 13. Using subagents

Subagents are allowed on any project, for development work. They are a tool for fresh eyes and for breadth, not a way to skip the checks in this document. (A product's own rule about agents delegating to agents, if it has one, is a product decision and is unrelated to how the project is built.)

**Good fits:** an independent review of a diff (the author is the worst reader of their own work); broad read-only searches that would otherwise fill the main context with file dumps; investigations that can run in parallel; the handoff check (`checking-a-handoff`); verifying a claim the author is invested in. **Poor fits:** a small edit; anything that depends on decisions made only in the conversation; work whose result cannot be checked.

Rules:

- **Brief it like a colleague who has seen nothing**: the goal, the files, the constraints, what "done" looks like, and the shape of the report. It does not see the conversation.
- **Read-only unless the task is to edit, and then it owns its files.** Two writers on one file lose work. For parallel edits use separate worktrees. A mutation run owns the file it mutates, so never two at once on one file.
- **It does not commit, push, or change shared state** (settings, data folders, a port in use). The owner's go-ahead rule and the git-safety hook apply to it as to you. Scratch servers get their own port, and it stops only its own.
- **Its report is a claim, not evidence.** Verify what matters (§7) before relying on it or repeating it as fact; they overclaim and miss things like anyone.
- **Spend what the task earns.** Each agent costs a full context; fan out when the work is independent and large, not by habit. Prefer one focused agent over five vague ones.
- **Write outcomes to files.** Findings that matter go into the decision record, the gotchas file or the handoff, not only into a conversation that will be summarized away.
