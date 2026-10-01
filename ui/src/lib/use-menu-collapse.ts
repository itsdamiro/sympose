import * as React from "react"

import { getCookieBool } from "@/lib/cookies"
import type { Breakpoint } from "@/lib/use-breakpoint"

const AUTO_COLLAPSE_COOKIE = "sympose:pref.autoCollapseMenu"

/**
 * Whether the main menu is a rail. On a small breakpoint it snaps to the rail
 * (if the "auto-collapse" preference is on, as it is by default) but stays fully
 * draggable, and a trip back to desktop restores the expanded width unless the
 * user has since collapsed it themselves. `forced` remembers that the rail came
 * from the breakpoint, not from the user. `collapsed` is `undefined` until the
 * breakpoint first changes, which leaves the menu to its own saved width.
 *
 * The preference is read once, when the shell mounts. The state is adjusted on a
 * breakpoint change during render (React's "derive from a changing prop"
 * pattern), so the menu never paints one frame in the old shape.
 */
export function useMenuCollapse(breakpoint: Breakpoint) {
  const autoCollapsePref = React.useMemo(
    () => getCookieBool(AUTO_COLLAPSE_COOKIE, true),
    []
  )
  const [menu, setMenu] = React.useState<{
    collapsed: boolean | undefined
    forced: boolean
    bp: Breakpoint
  }>({ collapsed: undefined, forced: false, bp: breakpoint })
  if (breakpoint !== menu.bp) {
    if (breakpoint !== "desktop" && autoCollapsePref) {
      setMenu({ collapsed: true, forced: true, bp: breakpoint })
    } else if (breakpoint === "desktop" && menu.forced) {
      setMenu({ collapsed: false, forced: false, bp: breakpoint })
    } else {
      setMenu((m) => ({ ...m, bp: breakpoint }))
    }
  }

  /** The user dragged the menu open or shut: from then on it is theirs. */
  const onCollapsedChange = (collapsed: boolean) =>
    setMenu((m) => ({
      ...m,
      collapsed,
      forced: collapsed ? m.forced : false,
    }))

  return { collapsed: menu.collapsed, onCollapsedChange }
}
