---
type: decision
status: accepted
date: 2026-11-02
projects: [sympose]
concepts: [Persona edits]
amends: [70, 71, 72]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app, topic/engine]
---

# 098 — A persona changes a new-note draft in place, as tracked changes inside it

> **Summary.** A persona could edit a note open in the editor and propose a new note, but not change a draft of a new note: the editor never told the chat a draft was open, and her edit tool is keyed to a note. Asked to edit a draft she said, correctly, that Sympose does not let her. The draft now counts as the open note under its own key, her `propose_edit` becomes a change stored inside the draft, and the editor draws it as it does in a note, with a change's Accept and Decline and the review notice. Nothing reaches the vault until the draft is accepted.

## Context

- damiro (2026-11-02) asked Samantha to edit an existing draft and she answered that she cannot modify drafts or change notes once they are staged. That was true, not a hallucination: `markdown-panel.tsx` registered the open note for the chat only for a vault note ("not for a persona's own file or a draft"), so she never saw a draft's text and had no call that targeted it. `propose_note` makes a new draft, and a second one that repeats the first is refused (`_same_draft`, ADR 082).
- ADR 072 says her first version "edits the open note and makes new notes"; editing a draft was not in scope, and no record rules it out. The store (ADR 070) keeps proposals per note key, and a new-note draft already has one (`new/<id>.md`) that holds its `create` proposal, so an `edit` proposal can sit in the same entry.
- The animation for an applied change (old words shrink away, new ones typed in, ADR 072 amendments) lives in `reviewExtensions` and `cellMarks`; a draft's own first-open reveal is `revealOnOpen`, which shares the same reveal field.
- damiro chose this over replacing the draft's whole text (no per-change review) and over leaving drafts as hers to propose only (2026-11-02, "do your reco").

## Decision

- **The draft is the open note.** While a draft is open in the editor the chat is sent its text as the editor holds it, under the draft's key (`new/<id>.md`), which is not a vault path. The persona is told it is "a new note you drafted that is not in the vault yet (the user decides whether it is made)" in place of a path she cannot use.
- **Her change is a proposal inside the draft.** `propose_edit` stores an `edit` proposal in the draft's entry, found in the draft's text by its quote and context as in a note. A change that overlaps one already waiting is refused, as in a note. The draft's `create` proposal and its text are not touched by her.
- **The editor draws it as it does in a note.** A draft takes the review extensions (tracked changes, a change's own Accept and Decline, the review notice with Accept all and Decline all, changes that no longer fit) together with the first-open reveal. In `accept` mode her change is applied to the draft's text at once, with the same reveal; the draft's save keeps it in her folder, never the vault. A change in a table cell is drawn as in a note.
- **Accepting a change changes the draft's text only.** It is saved in the persona's folder like the user's own edits to a draft (ADR 071). The vault is written only when the draft itself is accepted, as before.
- **Accepting or declining the draft forgets the changes still waiting inside it.** Accept makes the note from the draft's text as it stands, so a change not yet decided is not part of it and is dropped; Decline drops everything. The same holds for Accept and Decline in Slack (ADR 093), which show the draft's text and not the waiting changes.
- **One item in the Drafts list.** A draft with changes inside it is still one row, counted once, listed by its working name; its time is that of the latest change. The changes are read when the draft is open, as for a note.
- **No comments on a draft.** A comment needs a note on disk (ADR 069), so a draft has no Comment button or menu entry, and `comment_on` has nothing to anchor to. Not built; a later slice may add it.
- **Not Slack.** Slack has no editor, so she is not given an open draft there.

## Found in use (2026-11-02)

- damiro, in `accept` mode, saw her change land in the draft, opened another note and came back to the draft: the change was gone. Cause, already there for notes: the panel kept its list of applied changes for a path after leaving it, so on coming back the change the server still held was taken as applied and hidden. The list is now cleared when another note is opened; a test for a note and for a draft.
- He also saw no animation. The reveal ran (checked in the real app), but a one-sentence change lasts about 0.3 s at 4 ms a removed character and 10 ms a typed one (`REMOVE_MS`, `TYPE_MS`), so it reads as appearing. The speed stays his call (ADR 072): first a 450 ms minimum, then, as that still read as instant to him, a pace of its own for a change of words, a second at least (ADR 072 amendment of 2026-11-03).

## Consequences

- The store, the routes and the finder are unchanged but for a read of a draft's changes against the draft's own text (`get_changes`), the removal of waiting changes when a draft is decided (`note_changes.discard_draft`), and the count in `drafts()`.
- The persona's reference library says she can change a draft (`Creating notes.md`, `The web app.md`), checked by the retrieval eval.
- Measured on `gemma4:e4b` or any model: nothing new. The edit tool is the one measured in ADR 072; a draft changes only where the note's text comes from. A prompt with a draft open was not run against a real model in this slice.

## Alternatives rejected

- **She replaces the draft's whole text.** Rejected: no per-change review, and a whole rewrite lands at once, against the rule that a persona's work is reviewed by the user before it counts.
- **Leave drafts to the user and have her say so.** Rejected by damiro: a draft is her work, and asking her to revise it is the commonest next request.
- **A second proposal kind, "revise draft", with its own card.** Rejected: a new surface for what the tracked changes already do (damiro's rule: fewer surfaces).
