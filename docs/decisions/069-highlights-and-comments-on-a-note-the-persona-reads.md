# 069 — Highlights and comments on a note: kept out of the vault, sent with the next message, read by the persona

> **Status: Proposed (2026-10-04).** Not built. Part of #21 (a persona that acts on the vault) and the companion of the ADR 042 amendment of the same date: tracked changes are what the persona writes into a note, and this is what the user marks in it for her to read. Turn-based throughout.

## Context

The user wants to discuss a note with the persona by pointing at it: highlight a passage, write a comment on the highlight, and have the persona read both when they talk. Chat alone makes the user quote the passage back, which is slow and loses where in the note it was. The editor already shows the note; what is missing is a way to mark it that the persona can read.

Constraints that shape the design, from the project's own rules:

- Plain text stays canonical: the note's Markdown is the user's, shared with other tools, and is not the place for annotation syntax.
- Files the user did not create must not appear in the vault they browse: a visible sidecar would confuse (ADR 042 amendment, `.trash` being the one deliberate, user-facing exception).
- Anything derived from the vault that a cloud model would receive must be known to and approved by the user, controlled by a setting (ADR 031).
- Cheap by default: no extra model round trip for a feature that can ride a message the user was sending anyway.
- Web app only: the terminal is not expected to create or edit notes.

## Decision

**What an annotation is.** A highlight is a range of a note; a comment is text attached to a highlight, and a persona reply is a comment of the persona's under it. Each has an id, an author (user or persona), a state (open or resolved) and a time.

**Where it lives.** In the persona's own data folder (`profiles/<handle>/`, beside sessions and memory), in a file keyed by the note's vault-relative path. Never in the vault, never in the note's Markdown, never a visible sidecar. Deleting or moving a note in Sympose carries its annotations with it, as the pinned list and the trash index already follow a note.

**How a highlight finds its passage again.** By the quoted text plus a little text before and after it, not by an offset: an offset breaks on the first edit above it. The editor re-finds the passage when the note opens and maps it through the user's edits while it is open. When the quoted text is no longer in the note, the highlight is shown as detached, never silently moved to a guess, and the user can re-attach or resolve it.

**How the editor shows it.** The highlighted passage is tinted, and a marker in the margin, where a line number would otherwise be, shows that a highlight or comment is there; selecting it opens the comment thread over the highlight. Each persona comment carries its own Accept and Decline (Accept keeps it, Decline dismisses it). Drawing this needs extensions on the editor view; ADR 042's amendment names the spike that checks whether that works through stylo's `getView()` or waits for a stylo request.

**How the persona reads it.** Annotations travel with the user's next chat message as context. When the user sends a message, the open annotations on the note that is open in the editor go with it, each with its quoted passage and comment, labelled new since the last message or earlier. The persona answers in chat, may reply under a comment, and may propose a tracked change at the highlight. Either side resolving a comment stops it travelling. Because old open comments travel too, she does not forget what the user flagged two messages ago, and a cap on how many go in one message keeps a long list from inflating every turn (the number is set from measurement, not guessed here).

**Cloud models.** Annotations are vault-derived (the passage and the user's own words about it), so they are a new category in `cloud_share` (ADR 031), named `annotations`, off until the user approves it; a local model receives them freely. With the category withheld the persona is told they were not sent and how to allow them, the same way the other categories do.

## Built (2026-10-04, #21 slice 3b): the editor side

The user selects words and presses the toolbar's Comment button (greyed while nothing is selected), and a box opens on the selection; clicking a highlighted passage opens its thread on the passage. In a thread the user answers, resolves (the answers go with it) or deletes (after a confirmation that says the replies go too). Details settled in the build:

- **The editor sends the text around the selection.** It has the text as the user sees it, which can be ahead of the file and is the note's body only (the frontmatter is not in it), so offsets would not match the file. The request carries the quoted words and the text just before and after them, and the backend keeps that as the anchor without looking for the words in the file; with only half the context it falls back to finding the passage in the note.
- **A reply is about its comment's passage.** `reply_to` names the comment and the passage and context are copied from it; a reply to a reply goes under the comment it is in. Resolving or reopening a comment does the same to the replies under it.
- **One highlight per comment.** Replies share their comment's passage, so only the comment is drawn and counted for the margin dot.
- **Resolved comments are not drawn.** There is no screen yet to see or reopen a resolved one.
- **The persona's name** in a thread is the active persona's display name.
- **Closing on a note change.** A box opened on one note closes when another opens, so a comment written for one is never saved onto the other.
- **The toolbar reserves room for the panel's floating controls** (frontmatter, read and edit, the note menu), which were drawn over the end of the toolbar row and hid its last buttons, Save among them, at the default panel width; the buttons now wrap onto a second row instead.

## Consequences

- A new store in the persona's data folder and a small API for the editor to read and write annotations; the chat request carries the open note's path so the engine can attach its open annotations.
- A new `/share` category and one more block in the prompt, with the same gating, withheld-notice and test pattern as `connections`.
- Passages shown to a model are text the user chose to highlight; the engine treats a comment as the user's own words and the quoted passage as untrusted vault text, as every passage already is.
- Not built for the terminal.

## Open questions

- The cap on annotations per message, and whether older resolved ones are ever summarized; to be set from a measurement on a small and a cloud model.
- Whether a highlight may span several paragraphs or is limited to one block; the first version may limit it to keep re-finding reliable.
- Whether a highlight with no comment still travels (it marks "look at this") or only commented ones do.
- How a note's annotations are cleaned up when a note is permanently deleted from the bin.

## Amendment (2026-10-05): which comments are new since her last reply

ADR 072 said the comments travel "labelled new since the last message or earlier". Built so: each open comment is marked **new** when the comment or any answer in its thread is newer than the previous turn of this conversation (the `timestamp` the session already records for that turn), and **earlier** otherwise; the block reads `On “passage” (new since your last reply):` or `(from before your last reply):`. Times are compared as times (the session's carry fractions of a second, a comment's do not). A comment of hers made during the last turn is earlier. **The first message of a conversation carries no label at all**, since there is nothing to contrast with. Nothing new is stored: the comments' own times and the session's turn times are enough, and a conversation that was compacted or resumed behaves the same because the turns' timestamps remain.

**Measured (2026-10-05, invented notes, four runs each, a throwaway script):** asked "What have I added since your last reply?" with one new and one earlier comment, `gemma2:9b` named the new one 2 of 4 with the labels against 1 of 4 without, and presented the earlier one as new 0 of 4 against 1 of 4; Gemini Flash named it 4 of 4 against 2 of 4, and never presented the earlier one as new either way. So the labels help and cost nothing measured.

## Amendment (2026-10-05): comments inside table cells (stylo 0.20.0)

A decoration cannot reach a table cell, so the highlight of a comment on words inside a table was not drawn (the comment itself saved and attached). Stylo 0.20.0 takes `inPlace.cellMarks(state)` and draws the marks it returns on the characters of a cell, and gives a menu item `run(view, { rect })`. Built: `cellMarks` (`lib/review-extensions.ts`) returns one mark per open comment (the user's amber, hers the brand blue, with `data-comment-id`) and one per edit she has applied, and gives the cell the author's dot in its corner; the Comment item opens its box beside the rectangle stylo gives, where it used to open under the table. The marks use their own class (`sy-hl-persona`), not `sy-by-*`, which also carries the margin-dot rule for plain text and put a stray dot at the cell's edge for every highlighted word. A click on a marked word in a cell did not arrive on 0.20.0 (the press rebuilt the cell as it took focus, so the browser sent no `click`); stylo 0.20.1 keeps the pressed word until after the release, so the thread now opens on a plain click in and out of cells, and the mouseup workaround was removed (checked in real Chrome: a real click on a marked word opens the thread, the cell still goes into editing, and the words carry `data-stylo-cell-mark`). Not covered: a change she proposed inside a table (the struck words, the new ones and their buttons are widgets, not marks); Accept all on the toolbar still applies it.

## Amendment (2026-10-05): Accept and Decline on her comments

**Decided with the user.** A comment of hers can be accepted or declined, one comment at a time, in its thread. **Accept** means the user agrees with her point: the comment is resolved with the verdict `accepted`. **Decline** means they do not: the user must have replied in the thread first, saying why, and then the comment is resolved with the verdict `declined`; the Decline button is greyed until they have, and the server refuses a decline without a reply from the user (`400`, "Reply first, saying why you disagree."). Only a root comment whose author is the persona can be given a verdict (the user's own comments are resolved or deleted as before, and `400` otherwise); a verdict resolves the comment and its answers together, and reopening the comment clears it. The verdict and the time it was given are kept on the comment (`verdict`, `decided`).

**She is told.** What the user decided is carried to her once, in the next message after the decision: the comments she made that were accepted or declined since the previous turn of the conversation (the same "since" as the new/earlier labels above), as `On “passage”: accepted.` or `On “passage”: declined, the user wrote: <their last reply>.`, newest within a small cap. Nothing is sent on the first message of a conversation, nothing when the model may not have comments (the `annotations` category, ADR 031), and a decision is not repeated after that turn. Resolved comments are otherwise not sent.

**Built and checked (2026-10-05).** In a real browser: Accept is offered on her comment, Decline is greyed with a hint until the user has replied, then declines; both resolve the comment and its highlight goes. Real-model check on invented notes (four runs each, `gemma2:9b` and Gemini Flash): asked what she would still flag after the user declined her point about moving the carrots, neither model raised it again, with the decision line or without it (0 of 4 in all four cases), so the scenario did not tell the two apart: the line is not shown to help or to harm. Not built: a way to see a resolved comment's verdict in the thread afterwards.

## Alternatives rejected

- **A sidecar file in the vault** (`Note.md.comments` or a hidden index). Rejected: visible to the user and to sync tools, which is confusing, and it ties Sympose's own state to files the user did not create.
- **Annotations as syntax inside the note** (`==highlight==`, comment markers). Rejected: it changes the user's Markdown and breaks round-trip fidelity with other tools.
- **Anchoring by line number or character offset.** Rejected: the first edit above the passage moves it.
- **Sending only the annotations added since the last message.** Rejected as the default: the persona forgets earlier open comments; the open ones all travel, labelled new or earlier, under a cap.
- **Decline deletes the comment, and Accept only resolves (2026-10-05).** Rejected by the user: a decision should leave a record and teach her, and a deleted comment cannot be looked at again.
- **Decline without a reason.** Rejected by the user: the reason is the point of declining, and it is what she is told.
