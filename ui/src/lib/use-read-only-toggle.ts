import * as React from "react"

/**
 * The read/edit toggle's swap, sequenced so the outgoing toolbar row (stylo's bar or the breadcrumb)
 * finishes its own slide-out before `readOnly` actually flips, then the incoming row slides in and the
 * enter classes are dropped again. The same "exit, commit, enter, settle" shape as `useSlideSwap`, but a
 * separate machine on purpose (ADR 053, second amendment): it starts from a click, not from a changed
 * key; it cannot freeze an opaque payload, because what it animates is stylo's live toolbar and what it
 * commits is a boolean; and it ends on a different `animationend` filter (the chrome row only).
 *
 * - `exiting` is true while the outgoing half plays (the target `readOnly` is held until it ends).
 * - `entering` is true only for the incoming half's own animation, then cleared the moment it finishes.
 *   Without that, the enter classes would sit on the editor's wrapper forever after settling, and fight
 *   the note-switch slide's classes on the very same `.sy-note-chrome` element (equal-specificity rules
 *   setting the same `animation` property, one of them silently losing) the next time the user navigates
 *   while idle.
 * - `toggle` starts the exit half instead of flipping `readOnly` directly (the button is disabled while
 *   `exiting`).
 * - `onAnimationEnd` goes on the element that carries the exit/enter classes. Only the chrome row's own
 *   `animationend` counts: it commits the exit and settles the enter. `undefined` when idle.
 */
export function useReadOnlyToggle(readOnly: boolean, setReadOnly: (value: boolean) => void) {
  const [pending, setPending] = React.useState<boolean | null>(null)
  const [entering, setEntering] = React.useState(false)
  const exiting = pending !== null

  const toggle = React.useCallback(() => setPending(!readOnly), [readOnly])

  const commit = React.useCallback(() => {
    setPending((target) => {
      if (target !== null) {
        setReadOnly(target)
        setEntering(true)
      }
      return null
    })
  }, [setReadOnly])

  const settle = React.useCallback(() => setEntering(false), [])

  const onAnimationEnd =
    exiting || entering
      ? (e: React.AnimationEvent) => {
          if (!(e.target as HTMLElement).closest(".sy-note-chrome")) return
          if (exiting) commit()
          else settle()
        }
      : undefined

  return { exiting, entering, toggle, onAnimationEnd }
}
