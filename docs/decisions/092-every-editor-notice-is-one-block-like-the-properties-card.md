---
type: decision
status: accepted
date: 2026-10-21
projects: [sympose]
concepts: [Persona edits]
amends: [042, 061, 070, 071]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app]
---

# 092 — Every editor notice is one block, drawn like the properties card

> **Summary.** A draft's banner, a persona file's strip, the persona's suggested changes (Accept all, Decline all) and the ones that no longer fit are all one component, `EditorNotice`: the properties card's sibling block (same fill, corners, inset and content gutter), stacked above the card. The toolbar loses its two Accept all and Decline all icons; the Comment icon stays.

> **Status: Accepted (2026-10-21), designed with damiro.** Amends ADR 042 (the note-level Accept and Decline moved from the toolbar to a block), ADR 061 (a persona file's strip), ADR 070 (the strip for changes that no longer fit) and ADR 071 (the draft banner).

## Context

- The editor had four notices drawn four ways: the draft banner (a block since 2026-10-21), a persona file's strip (`bg-chip rounded-md`), the outdated-changes strip (`bg-muted`, a border) and two toolbar icons for the whole note's Accept and Decline. Two of them looked like the card and two did not.
- damiro: editor notices are drawn as a block like the properties card, not as new toolbar icons. A toolbar icon says nothing about how many changes wait, and a user who has not met it does not know it is there.
- stylo's `canvasHeader` is a CodeMirror top panel: it sits above the editor's scroller and never scrolls with the note (measured 2026-10-21 in the real app: the panel's top stayed at the same place while the note scrolled 800 px).

## Decision

- One component, `EditorNotice` (`editor-notice.tsx`): a title, an optional line, actions on the right, optionally more underneath. `DraftBanner`, the persona file's strip and `OutdatedChanges` use it, and so does the new `ReviewNotice`.
- `ReviewNotice` says "<Persona> suggested N changes" with Decline all and Accept all. N counts the changes still in the text; those that no longer fit are in their own notice, with a Decline on each. Accept all applies them as one edit the user can undo and then saves the note (as the toolbar icon did); Decline all forgets every one, outdated ones too. Nothing is drawn when none is waiting.
- The panel hands each notice the same wrapper (`mx-2 mt-2` and `--gutter`, 0.5rem on a phone, 1rem, 1.5rem from `sm`), whether or not the file has a card. Order in the header: banner, the persona's changes, the ones that no longer fit, the card.
- The toolbar keeps the Comment icon (a selection action; the right-click menu has it too). `PendingRewriteDialog` stays a dialog (a diff needs room), opened by Review in a persona file's notice.

## Consequences

- One look for everything the editor tells the user above the text; a new notice is a new use of the component, not a new style.
- The block is always on screen while changes wait, because the header does not scroll. It costs about 3 rem of height on a note with suggestions, and goes away once they are accepted or declined.
- `proposalCount` and `hasPending` (the toolbar's enabled state) are gone.

## Alternatives rejected

- **Keep the toolbar icons and add the block.** Two ways to do one thing. Right only if the block turned out to be too tall on a phone.
- **A pin on the block (his earlier call, 2026-10-21).** Made to keep the block from scrolling out of sight; the header never scrolls, so there is nothing to pin. Open: if the height is a problem, collapse the block to one line when the note is scrolled, or let the user fold it. Not built.
