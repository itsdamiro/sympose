---
concepts: [Grounding]
---

# 068 — A note named in full joins a note the search found when their titles read the same

> **Status: Accepted, built (2026-10-04), from the Workspaces failure in ADR 067.** Amends ADR 030 ("A note named in full": the rescue changed nothing when the search found a note). Builds on ADR 067.

## Context

ADR 067 left one failure standing: "what does the Workspaces note link to?" was answered with the *Workspace* note's links in 8 of 8 replies. The prompt held correct, labelled facts, so this was not the model misreading them. It was **retrieval**: in the default search mode the message found one note by meaning (Workspace, 0.773), the margin rule dropped the rest, and the rule that attaches a note named in full ran only when the search found *nothing* (ADR 030). The message said "Workspaces" in full, and that note was never in the prompt. She answered, faithfully, from the only note she had.

The other message about the same two notes ("does the Workspaces note link to the Workspace note?") found nothing by meaning, so the naming rule fired and both notes were attached; the asymmetry is why one question failed and its sibling did not.

The first idea (attach the named note whenever the message names one) was measured and rejected: on the public Obsidian documentation it moved passing 48 to 45 and messages with junk 11 to 14, and on a personal vault 63 to 59, junk 6 to 10, top-1 47 to 40, for +2 recall on one vault and 0 on the other. A note named in full is often not what the message is about, which is why ADR 030 left a successful search alone.

## Decision

**Only a twin joins.** When the search found notes, a note the message names in full (by the same rule and guards as before) that the search did not find is added only if its title reads the same as the title of a note the search *did* find, after the index's own word reduction (the other number of a word, filler words). "Workspace" and "Workspaces" are twins; "Budget" and "Trip" are not. The twin is added **after** the found notes and as its first passage only, so the search's order and the count of notes it chose do not change; the turn's limit still applies.

**Why this and not more.** The failure has one shape: two notes the vault itself tells apart only by a letter, the search picks one, and the message asks about the other. A note with an unlike title that the search missed is a different question (retrieval recall) and stays as measured in ADR 030. A twin is the case where the search cannot be trusted to have chosen between them, and the message has said which.

**A consequence worth stating:** the index reads "flight" and "flights" as one name, so saying either names both notes. When the search found one of them, the other is added too. The title is ambiguous and one extra passage is cheap; it is the intended behaviour, not an accident.

## Measured (2026-10-04, `gemma2:9b`, `nomic-embed-text`)

| | before | after |
|---|---|---|
| "what does the Workspaces note link to?", right answer from the right note (n=8) | 0 of 8 | 8 of 8 |
| "does Workspaces link to Workspace?" (true: no), wrong (n=8) | 2 | about 3 |
| "is Workspace linked from Workspaces?" (true: no), wrong (n=8) | 2 | 2 |
| synthetic vault, auto: 51/59 and no-body 13/13 | | identical |
| public documentation vault (79 messages): pass, junk, recall | 48, 11, 56 | 48, 11, 56 |
| personal vault (76 messages): pass, junk, recall, top-1 | 63, 6, 50, 47 | 63, 6, 50, 47 |

No labelled message in any set exercises a twin, so the sets show the rule costs nothing where it does not apply; they do not show it helps. The yes/no questions are unchanged within the noise of 8 replies: when both notes were already in the prompt the failure was the model's, and this does not touch it.

## Consequences

- A question about a note whose title differs from another's by a letter is answered from the note it names.
- A message that names one of two twins brings both, one extra passage.
- ADR 030's promise that the rescue "changes nothing when the search found a note" now has this one exception.
- The model's own confusion between two near-identical titles when both are in the prompt (the yes/no questions) is still there, at the rate ADR 067 measured. On Gemini Flash (a cloud model, the English Obsidian help docs, 8 replies per direction) the two questions were answered correctly 16 of 16, so the confusion belongs to the small local model.

## Alternatives rejected

- **Attach every note a message names in full, even when the search found others** (the first, measured version). Costs precision for next to no recall; see Context.
- **Put the twin first.** It lowered top-1 in the broad variant and nothing here needs it first.
- **Detect "the message names two notes" in the wording of the question.** That is the phrase-list kind of fix the project avoids; the structural fact (the titles read the same) needs no wording.
- **A setting.** It is a grounding guarantee for a narrow structural case, not a taste.
