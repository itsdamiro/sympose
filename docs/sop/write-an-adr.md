# SOP: write a decision record (ADR) before the code

For any assistant. Write one when a change adds a dependency, or a decision will outlive the current task (an architecture change, a security approach, what is deliberately deferred). The record comes first; no code for the decision until the owner has accepted it.

## Steps

1. **Take the next number.** Look at `docs/decisions/README.md`; use the next unused number, three digits.
2. **Copy the template.** `docs/decisions/TEMPLATE.md` to `docs/decisions/NNN-short-slug.md`. The file name, frontmatter, summary and sections follow `docs/VAULT_CONVENTIONS.md`; `concepts` takes at least one name of a note in the vault's `Concepts/` folder, and `docs/sop/rename-a-concept.md` covers a new concept.
3. **Write the summary and the sections.** Three lines at most for the summary: what was decided, why, what it costs. Context carries facts and numbers, with where they came from; Decision is in the order someone would carry it out; Consequences say what is easier, harder and left open; each Alternatives rejected entry says when it would become right. When the owner explains why in the conversation, put the reason in the record in their words (a short quote or a close paraphrase, marked as theirs): the conversation is not kept, and the intent behind a choice is what the next session cannot rebuild.
4. **Fill the frontmatter** last, once the record says what it decides: `status: proposed`, `date`, `concepts`, `amends` and `supersedes`, and one or more `topic/` tags in `tags` (usually one to three). A topic is a question to filter by (privacy, cost, the web app) and cuts across concepts: take it from the list in the vault's `Tags.md`, never reuse a concept's name as a topic, and if nothing fits, ask the owner to list a new one with the question it answers.
5. **Get the owner's word** on anything that is theirs to decide. Ask; do not guess. Change `status` to `accepted` (and the `status/` tag) only when they have said so, and add one line saying what was accepted and when.
6. **Add the index row** to `docs/decisions/README.md`. The shape check (`scripts/adr_check.py`, a gate) fails on a record without frontmatter, a field, a summary, a `topic/` tag or an index row, and on a topic that only repeats one of the record's concepts.
7. **Then start the code.** If a real choice turns up mid-slice, stop and return to step 1.

## Changing a record later

- **Amend:** add `## Amendment (YYYY-MM-DD): title` at the end of the same file. The decision text stays current; the amendment records the change. Do not create a new file for an amendment.
- **Supersede:** new record with `supersedes: [NNN]`; set the old one's status to `superseded` and link the new one.
- **Remove:** set `status: removed` with the date and one line saying why. Do not delete the file silently.

## Do not

- Write the code first and the record afterwards. A record written after the fact explains what was done, not what was weighed.
- Leave "Alternatives rejected" empty. It is where ideas are kept for later.
