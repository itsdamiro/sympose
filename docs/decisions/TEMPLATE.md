---
type: decision
status: proposed        # proposed | accepted | superseded | removed
date: YYYY-MM-DD
projects: [<project>]
concepts: []            # at least one: names of notes in the vault's Concepts/, in sentence case (docs/VAULT_CONVENTIONS.md)
amends: []              # ADR numbers
supersedes: []
tags: [type/decision, status/proposed, project/<project>]   # add 1 to 3 topic/<word> tags: questions to filter by, from the vault's Tags.md, never a concept's own name
---

# NNN — Title as a sentence   (the number matches the file name)

> **Summary.** Three lines at most: what was decided, why, and what it costs.

## Context

What forced the choice. Facts and numbers, with where they came from.

## Decision

What we do, in the order someone would carry it out.

## Consequences

What this makes easier, what it makes harder, what it leaves open.

## Alternatives rejected

- **The option.** Why not, in one or two lines. This section is where ideas are kept for later; write the condition under which the option would become right.

## Amendment (YYYY-MM-DD): title

A dated change to the decision above, in the same file. The decision text stays current; this records the change.
