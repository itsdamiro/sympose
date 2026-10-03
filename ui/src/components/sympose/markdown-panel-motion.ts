import { cn } from "@/lib/utils"

// Module-level, not inline: a stable reference so `<ScrollThumb>`'s effect
// (MutationObserver + ResizeObserver + scroll listener) doesn't tear down and
// rebind on every keystroke, which re-renders this component.
//
// `.cm-scroller` is CodeMirror's own scroll viewport (source/in-place/split);
// preview mode has no CodeMirror instance at all, so it falls through to
// `[data-stylo-mode="preview"]`'s own child — stylo's stable, documented mode
// attribute on its root, one level above the actual scrolling `.preview` div
// (stylo >=0.13.1, once `.preview` got a real `overflow: auto` of its own —
// see `stylo/docs/requests/2026-09-13_preview-missing-scroll-container.md`).
// `.preview` itself is a CSS-module class with no stable selector of its own,
// so this leans on it being that root's only child rather than naming it
// directly — true today (`Preview.tsx` renders exactly one wrapping `<div>`),
// worth a stable `stylo-preview-scroller`-style class from stylo directly if
// that structure ever grows a sibling.
export function getStyloScroller(el: HTMLElement): HTMLElement | null {
  const cmScroller = el.querySelector<HTMLElement>(".cm-scroller")
  if (cmScroller) return cmScroller
  const previewRoot = el.querySelector<HTMLElement>('[data-stylo-mode="preview"]')
  return (previewRoot?.firstElementChild as HTMLElement | null) ?? null
}

/** Applied to `editorScrollRef`'s wrapper (stable across the read/edit
 *  toggle — only its children swap) while `readOnlyExiting`/`readOnlyEntering`
 *  — never once settled (see `readOnlyEntering`'s own doc comment: this
 *  wrapper must go back to carrying neither, or its `.sy-note-chrome` rule
 *  would sit there forever fighting the note-switch slide's own rule on the
 *  same element). Same content scopes (`.cm-scroller`, `.sy-note-preview`)
 *  and `.sy-note-chrome` marker as that note-switch slide in
 *  `use-slide-swap.ts`, but content only crossfades here (it's the same
 *  document either side of the toggle, not a new one sliding in) while the
 *  toolbar/breadcrumb row still slides vertically. Both run on a `duration-100`
 *  one-off (Tailwind's own built-in numeric duration utility, which the
 *  `index.css` comment above `duration-snappy` confirms sets `--tw-duration`
 *  the same way the named tiers do) — this toggle's own timing, kept off
 *  both shared tiers on purpose: `duration-snappy` (150ms) still read as too
 *  slow, and reaching for it anyway would also speed up the frontmatter
 *  rename field and accordion collapses; `duration-thumb` (300ms) drives
 *  vault-tree row entrance, the note-actions/vault-row menus, and the
 *  wikilink hover-card. Content and chrome stay on the same number so they
 *  finish together instead of chrome trailing. The commit/settle below
 *  still only listens for chrome's own `animationend` (never content's),
 *  which stays correct and simplest even with matching durations. Same
 *  literal-class-string reasoning as `use-slide-swap.ts`'s own scoped
 *  selectors (Tailwind's scanner needs each token spelled out). */
export const TOGGLE_CONTENT_EXIT = cn(
  "[&_.cm-scroller]:pointer-events-none [&_.cm-scroller]:animate-out [&_.cm-scroller]:fade-out-0 [&_.cm-scroller]:duration-100 [&_.cm-scroller]:fill-mode-forwards",
  "[&_.sy-note-preview]:pointer-events-none [&_.sy-note-preview]:animate-out [&_.sy-note-preview]:fade-out-0 [&_.sy-note-preview]:duration-100 [&_.sy-note-preview]:fill-mode-forwards",
  "[&_.sy-note-chrome]:pointer-events-none [&_.sy-note-chrome]:animate-out [&_.sy-note-chrome]:duration-100 [&_.sy-note-chrome]:fill-mode-forwards [&_.sy-note-chrome]:slide-out-to-top-1"
)
export const TOGGLE_CONTENT_ENTER = cn(
  "[&_.cm-scroller]:animate-in [&_.cm-scroller]:fade-in-0 [&_.cm-scroller]:duration-100",
  "[&_.sy-note-preview]:animate-in [&_.sy-note-preview]:fade-in-0 [&_.sy-note-preview]:duration-100",
  "[&_.sy-note-chrome]:animate-in [&_.sy-note-chrome]:duration-100 [&_.sy-note-chrome]:slide-in-from-top-1"
)
