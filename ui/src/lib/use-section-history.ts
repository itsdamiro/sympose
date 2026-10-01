import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"
import type { SlideDirection } from "@/lib/use-slide-swap"

const SECTION_COOKIE = "sympose:shell.section"

/**
 * The highlighted folder or section of the main menu (`active`), with a
 * browser-style visit history over it for the content panel's back and forward
 * buttons.
 *
 * `active` is persisted, since the content panel is usually hidden on phone and
 * should come back pointed where it was left. The menu is driven by the live
 * vault, so a persisted folder id is only reconciled once the tree has loaded
 * (the caller derives the shown section from it; this hook never looks at the
 * tree).
 *
 * The stack and its cursor live in one state value, so the buttons' disabled
 * state is always current, with no ref-plus-forced-rerender. A back or forward
 * click sets `active`, and `navigatingHistory` stops the effect that records a
 * visit from pushing that same change as a new one.
 *
 * `contentDirection` is which way the content panel's body slides on the next
 * `active` change; the caller sets it alongside whatever triggered the change
 * (any pick that is not a back click reads as "forward", the same as a new
 * destination in a browser).
 */
export function useSectionHistory() {
  const [active, setActive] = React.useState<string>(() => getCookie(SECTION_COOKIE) || "")
  React.useEffect(() => {
    setCookie(SECTION_COOKIE, active)
  }, [active])

  const [history, setHistory] = React.useState(() => ({
    stack: [active],
    index: 0,
  }))
  const navigatingHistory = React.useRef(false)
  React.useEffect(() => {
    if (navigatingHistory.current) {
      navigatingHistory.current = false
      return
    }
    setHistory((prev) => {
      if (prev.stack[prev.index] === active) return prev
      const stack = [...prev.stack.slice(0, prev.index + 1), active]
      return { stack, index: stack.length - 1 }
    })
  }, [active])
  const canGoBack = history.index > 0
  const canGoForward = history.index < history.stack.length - 1

  const [contentDirection, setContentDirection] = React.useState<SlideDirection>("forward")
  const goBack = () => {
    if (!canGoBack) return
    navigatingHistory.current = true
    setContentDirection("back")
    setActive(history.stack[history.index - 1])
    setHistory((prev) => ({ ...prev, index: prev.index - 1 }))
  }
  const goForward = () => {
    if (!canGoForward) return
    navigatingHistory.current = true
    setContentDirection("forward")
    setActive(history.stack[history.index + 1])
    setHistory((prev) => ({ ...prev, index: prev.index + 1 }))
  }

  return {
    active,
    setActive,
    canGoBack,
    canGoForward,
    goBack,
    goForward,
    contentDirection,
    setContentDirection,
  }
}
