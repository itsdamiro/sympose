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

## Alternatives rejected

- **A sidecar file in the vault** (`Note.md.comments` or a hidden index). Rejected: visible to the user and to sync tools, which is confusing, and it ties Sympose's own state to files the user did not create.
- **Annotations as syntax inside the note** (`==highlight==`, comment markers). Rejected: it changes the user's Markdown and breaks round-trip fidelity with other tools.
- **Anchoring by line number or character offset.** Rejected: the first edit above the passage moves it.
- **Sending only the annotations added since the last message.** Rejected as the default: the persona forgets earlier open comments; the open ones all travel, labelled new or earlier, under a cap.
