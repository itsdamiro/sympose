# 067 — A grounded note states its links, and says when it has none

> **Status: Accepted, built (2026-10-04), from the follow-up found while measuring ADR 066; it helps and does not finish the job (see Measured).** Builds on ADR 035 (mechanical connections), ADR 031 (what a cloud model may receive; the `connections` category) and ADR 066 (the "possibly related" line).

## Context

Measuring ADR 066 turned up a grounding weakness that the new feature did not cause: asked whether one note links to another, a small model says yes when the two only have similar titles. On the Obsidian help docs, "Workspaces" (a plugin) and "Workspace" (the interface) do not link either way. In six replies to three questions about them, three were wrong: "Workspaces is connected to Workspace in the vault", "The Workspace note links to Obsidian CLI, Mobile app and Ribbon" (another note's list, said of the wrong note) and "they are, at least based on those titles". The two replies that were right quoted the line they were given, so she reads it correctly when she attends to it.

Two facts about today's prompt make the guess easy:

- **There is no statement of links, only a mixed bag.** The "Connected to" line (ADR 035) puts explicit links, shared tags or aliases and the same top-level folder in one list of three, without saying which is which or in which direction. "Connected to (by a link, a shared tag, or the same folder): Obsidian CLI; Command palette; Core plugins" reads as "links to" to a small model.
- **No links is silence.** A note with no connection of any kind has no line at all, so "not linked" and "the line was left out" look the same, and the title is the only evidence she has left.

Grounding is zero-hallucination (CLAUDE.md); a link that is not there is a made-up claim about the vault, so this is a regression to restore, not a tradeoff.

## Decision

**A separate, always-present fact for a grounded note's links.** Every note's own passage (the text or title passage that already carries `connections`) gets a `links` field read from the same link graph: the notes it links to and the notes that link to it, real notes only (the graph already leaves out links to nothing and to notes the persona cannot see). It is rendered as one line that names the note in every sentence (several notes' passages sit side by side in the prompt, and a bare "it" was read as the wrong note), the two directions as separate sentences, and a direction with nothing says "no note":

> Links of Workspaces (read from the vault): Workspaces links to Command palette; Core plugins. Workspaces is linked from Tabs; Obsidian CLI. Workspaces has no link with a note not named here, however alike the titles.

The last sentence is left out when a direction was cut off at its cap, since a note not named may then be linked.

**A pointer when the note also has neighbours by meaning (added after the first measurement, see Measured).** "No links" is the whole answer to a question about links, and a question about what is *connected* has more to say. When the same note carries a "possibly related" line (ADR 066), the links line ends with "Notes close in meaning to X, which are not links, are listed below as possibly related." It adds nothing when there are no neighbours.

**A second passage of a note says so.** A note found through two passages was printed as two bullets under one identical label ("Marathon Training Log (Marathon Training Log.md)"), and she read them as two notes: "you've got Marathon Training Log listed twice", "linked to itself". The second and later passages of a note are labelled "another passage of the same note".

**Stated once per note.** The line (and "Also connected") is carried by a note's first passage only, not repeated under each passage of the same note, where the lines of two notes with alike titles interleaved. It also counts the note once, not once per passage, when a cloud model has not been allowed them.

It is present for every grounded note, including one with no links at all, so that "none" is a statement she can quote instead of an absence she must guess from.

**The "Connected to" line stops repeating links.** It keeps shared tags, aliases and folder, which are real but are not links, and its label says so ("shares a tag, an alias or a folder, not a link"). A note already named in the links line is not named again, so the two lines never overlap, and a note stated as a link is never offered as "possibly related" either (ADR 066).

**Shown names are capped, the facts are not.** At most 5 notes per direction are named, then "and N more", so a hub note does not fill the prompt; the cap is a measured convention, not a preference, and is not a setting.

**Privacy.** Links are what the `connections` category already covers (ADR 035); the line is stripped, and counted as withheld, under the same approval as `connections` and `related`. A cloud model that has not been allowed to receive them gets neither the links nor the "none", the same silence as today, so the claim "not linked" is never made on facts she was not given.

**Parity.** The prompt is built by the engine, so the terminal and the web app are identical.

## Measured (2026-10-04, `gemma2:9b`, the Obsidian help docs in a scratch copy, replies read by hand)

"Does the Workspaces note link to the Workspace note?" and "is the Workspace note linked from the Workspaces note?" (true answer: no, either way), wrong answers:

| | first | second |
|---|---|---|
| before (n=3 each) | 3 of 3 | 2 of 3 |
| line as first written, "it links to...; it is linked from...;" (n=3 each) | 3 of 3 | 2 of 3 |
| named note, separate sentences, stated once (n=8 each) | 2 of 8 | 2 of 8 |
| the same, under every passage (n=8 each) | 3 of 8 | 0 of 8 |

The first wording was no better than nothing: the bare "it" and a `;` that separated both names and directions made her attach one note's list to another. "Does Workspaces link to Core plugins?" (true) stayed right in 3 of 3 before and after. The once-versus-everywhere gap is inside the noise, so the simpler (once) was kept.

**Not fixed: "what does the Workspaces note link to?"** She answers with the Workspace note's links (Mobile app, Ribbon, Sidebar, Status bar, Tabs) in 8 of 8 replies, and did before (3 of 3), with both notes labelled. With two near-identical titles in front of it, a 9B model picks the wrong note for a question that asks for a list. The facts are in the prompt and correct; the model attributes them wrongly. A larger or cloud model was not measured.

**A cost found:** asked "which notes are connected to my marathon training log?", a note with no links but a note close in meaning (ADR 066) now gets "it has no links, nothing links to it" in most replies (4 of 6 at n=6, against 0 of 6 before) and the neighbour is left unmentioned, where before she offered it. The answer is true; it is less helpful. The "possibly related" line is right beside it in the prompt.

**The pointer (n=6 per case, `tests/live_related_cases.py`).** Asked "which notes are connected to my marathon training log?", the reply names the neighbour by meaning 2 of 6 before the pointer (8 of 9 and 5 of 6 in the two runs before ADR 067) and 3 of 6 and 4 of 6 with it; "what is related to my sourdough starter" 6 of 6, the link-trap case 6 of 6, the line-off control 0 of 6. Two of the three remaining misses are a different fault: the same note appears as two bullets with the same title (two passages), and she says it is "listed twice". Safety, 32 replies each to the two Workspaces yes/no questions with and without the pointer, read by hand: 5 to 6 wrong without, 5 to 7 with; no sign it makes her state a link that is not there.

**Another passage of the same note (n=12, the connected-to-marathon question).** The misreading as two notes with one title was 1 of 12 before (2 of 6 in an earlier run) and 0 of 12 after; naming the neighbour by meaning 5 of 12 before, 7 of 12 after. The misses left are replies that truthfully say there are no links and do not mention the neighbour.

**A stronger pointer (n=12 per run, the connected-to-marathon question).** The pointer now tells her what to do, not only where the line is: "If asked what is connected to {title}, also name the notes listed below as possibly related, saying they are a guess from the text and not links." Naming the neighbour by meaning went from 8 of 12 (the same run, old wording, measured just before) to 11 of 12 and 10 of 12. Safety, 12 replies each to the sourdough question and the link-trap question, read by hand: no reply states a link that is not there; the one reply to the starter question that missed the neighbour named none, and the trap-case misses flagged by the loose `forbid` pattern are all correct "no link" answers it does not recognise ("doesn't directly link to").

## Consequences

- A few tokens per grounded note (about 20 to 40), always present; the prompt-fitting loop drops the line with its note, as it does `connections`.
- A question of the form "does A link to B" has a literal answer in the prompt, true or false.
- The "Connected to" line becomes "Also connected", shorter and no longer readable as links.
- A question about "connected" notes is answered about links first; the pointer brings the neighbour by meaning back most of the time (about 10 of 12 with the stronger wording, Measured), not always.
- A grounding gap remains for list questions about a note whose title is nearly another's (Measured); a structural answer is the second option below, if it is wanted.
- A vault whose links cannot be read (no link graph) says "no note" for both, which would be wrong; the graph is rebuilt from the snapshot the notes already come from, so this cannot happen without the note itself missing.

## Alternatives rejected

- **Attach the second note when a message names two notes** (the other option raised with damiro). It needs to detect "names two notes" in free text, which is the phrase-list kind of fix the project avoids, and it spends a whole passage where a short fact is enough. It stays possible later for questions that compare two notes' content.
- **A rule in the soul ("never say two notes are linked from their titles").** A small model has been seen to ignore such rules; a fact to quote is stronger than a ban. A short reminder sits on the line itself.
- **Leaving "no links" silent.** The measured failure is exactly the silence.
- **A setting to switch it off.** It is mechanical, cheap and a grounding guarantee, not a taste.
