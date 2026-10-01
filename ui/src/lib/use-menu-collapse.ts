import * as React from "react"

import { getCookie, getCookieBool, setCookieBool } from "@/lib/cookies"
import type { Breakpoint } from "@/lib/use-breakpoint"

const AUTO_COLLAPSE_COOKIE = "sympose:pref.autoCollapseMenu"
const collapsedCookie = (breakpoint: Breakpoint) => `sympose:pref.menuCollapsed.${breakpoint}`

/** What the user last chose for this window size, or `null` when they never did (or the cookie is not a
 *  `1`/`0`, e.g. hand-edited). */
function savedChoice(breakpoint: Breakpoint): boolean | null {
  const raw = getCookie(collapsedCookie(breakpoint))
  return raw === "1" ? true : raw === "0" ? false : null
}

/**
 * Whether the main menu is a rail. Each window size (phone, tablet, desktop) remembers the user's own choice
 * for it, in a cookie: fold the menu on desktop, go to a tablet-sized window and back, and it is still folded.
 * A size the user never chose for takes the default (if the "auto-collapse" preference is on, as it is by
 * default): a rail on a small window, the full menu on desktop. The menu stays fully draggable on every size.
 * `collapsed` is `undefined` until the window size first changes, which leaves the menu to its own saved width.
 *
 * The menu reports every flip of its own width through `onCollapsedChange`, including the one that follows a
 * default set here; only a change that differs from what this hook already holds is the user's, and only that
 * is saved, so a default is never mistaken for a choice.
 *
 * The preference is read once, when the shell mounts. The state is adjusted on a size change during render
 * (React's "derive from a changing prop" pattern), so the menu never paints one frame in the old shape.
 */
export function useMenuCollapse(breakpoint: Breakpoint) {
  const autoCollapsePref = React.useMemo(
    () => getCookieBool(AUTO_COLLAPSE_COOKIE, true),
    []
  )
  const [menu, setMenu] = React.useState<{
    collapsed: boolean | undefined
    bp: Breakpoint
  }>({ collapsed: undefined, bp: breakpoint })
  if (breakpoint !== menu.bp) {
    const saved = savedChoice(breakpoint)
    const fallback = autoCollapsePref ? breakpoint !== "desktop" : menu.collapsed
    setMenu({ collapsed: saved ?? fallback, bp: breakpoint })
  }

  const onCollapsedChange = (collapsed: boolean) => {
    if (collapsed === menu.collapsed) return // the menu following what was set here, not the user
    setCookieBool(collapsedCookie(menu.bp), collapsed)
    setMenu((m) => ({ ...m, collapsed }))
  }

  return { collapsed: menu.collapsed, onCollapsedChange }
}
