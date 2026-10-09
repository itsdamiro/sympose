# SOP: check a handoff with a fresh reader

For any assistant. The point is to find what a new session would have to guess. The checker must not see this conversation: use a new session, a subagent, or another model, and give it only the repository path.

## Steps

1. Give the checker only `docs/HANDOFF.md` and the files it points at, one level down. No chat history.
2. It answers the six questions below, each with the file and line it relied on.
3. Compare each answer with what is true (`git log -1`, `scripts/gates`, the actual next step).
4. Every wrong, hesitant or "not stated" answer is a defect in the handoff: fix the handoff, not the answer.
5. Run again from step 1 until all six are right. If an answer is right only because the checker read something the handoff does not point to, add the pointer and return to step 1.

## The six questions

1. What is the next action, exactly, and what is it done when?
2. How do I run every gate, and what does a pass look like?
3. What must I not do (the never-break rules)?
4. What is waiting on the owner, and what do I recommend?
5. Where do I look for a decision, a trap, a recipe?
6. Is anything in the handoff out of date? Check each claim against the repo; a claim that cannot be checked is a defect too.

## Also check

- Under 60 lines. Volatile facts only: no test counts, no commit hashes, nothing copied from a decision record.
- One term per concept throughout.
- "Waiting on the owner" says `None.` when empty.

Report as: question, the answer given, what was true, the fix. Do not edit the handoff until the owner has seen the list, unless they asked you to.
