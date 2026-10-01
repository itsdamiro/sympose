import * as React from "react"

import {
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  MENU_TRASH_ID,
  type MainMenuItem,
} from "@/components/sympose"
import { getCookieBool, setCookieBool } from "@/lib/cookies"
import { isSentinelSection } from "@/lib/shell-sections"
import type { Panels } from "@/lib/use-panels"
import type { SlideDirection } from "@/lib/use-slide-swap"

const RAIL_COOKIE = "sympose:shell.rail"

/**
 * Moving around the shell: which section the content panel shows, and, on a
 * phone, the vault view (the menu rail and the content panel, which move
 * together).
 *
 * - `resolvedActive` is derived, not synced: `active` holds the user's last
 *   explicit pick, and a persisted folder id that no longer exists (after
 *   switching to a persona with a narrower sandbox) falls back to the first
 *   entry of the menu.
 * - `menuShown` is the phone's vault view, remembered in a cookie.
 * - `revealMenu` toggles it: opening remembers what was on screen (phone caps the
 *   stage at one panel, so editor and chat are never both open when this is
 *   read) so `closeVault` can return there, and lands on a folder, never on a
 *   section such as Settings.
 * - `selectSection` is every menu pick: it slides the content panel forward,
 *   opens a root note in the editor, drops a half-typed create-input on the bin,
 *   closes the panel when the section already showing is picked again and, on a
 *   phone, keeps `menuShown` in step with it (#84).
 */
export function useShellNavigation({
  isPhone,
  panels,
  active,
  setActive,
  setContentDirection,
  menuItems,
  noteIds,
  selectNote,
  closeCreate,
}: {
  isPhone: boolean
  panels: Panels
  active: string
  setActive: (id: string) => void
  setContentDirection: (direction: SlideDirection) => void
  menuItems: MainMenuItem[]
  noteIds: Set<string>
  selectNote: (path: string) => void
  closeCreate: () => void
}) {
  const [menuShown, setMenuShown] = React.useState(() => getCookieBool(RAIL_COOKIE, false))
  React.useEffect(() => {
    setCookieBool(RAIL_COOKIE, menuShown)
  }, [menuShown])

  const beforeVault = React.useRef<"editor" | "chat" | null>(null)

  const isSentinel = isSentinelSection(active)
  const resolvedActive =
    isSentinel || menuItems.some((i) => i.id === active)
      ? active
      : (menuItems[0]?.id ?? active)

  // Close the vault view — rail out, content panel out, back to the prior panel.
  const closeVault = () => {
    setMenuShown(false)
    panels.close("content")
    if (beforeVault.current) panels.open(beforeVault.current)
    beforeVault.current = null
  }

  const revealMenu = () => {
    if (menuShown) {
      closeVault()
      return
    }
    // toggle open — rail in, content panel in (on a folder, never a sentinel)
    beforeVault.current = panels.isOpen("chat")
      ? "chat"
      : panels.isOpen("editor")
        ? "editor"
        : null
    if (isSentinel && menuItems.length > 0) {
      setActive(menuItems[0].id)
    }
    panels.open("content")
    setMenuShown(true)
  }

  const selectSection = (id: string) => {
    // On phone, jumping to Settings / Persona from the TopBar slides the menu away
    // (folder picks keep it, so its highlight stays visible next to the panel).
    if (isPhone && (id === MENU_SETTINGS_ID || id === MENU_ACCOUNT_ID)) {
      setMenuShown(false)
    }
    // A root note row (README.md) also selects it in the tree.
    if (noteIds.has(id)) selectNote(id)
    // Leaving the tree for the bin: drop any half-typed create-input name.
    if (id === MENU_TRASH_ID) closeCreate()
    if (id === resolvedActive && panels.isOpen("content")) {
      panels.close("content")
      // Phone: the rail and content are one view, so closing content this way
      // must also drop `menuShown` — otherwise the TopBar toggle's next click
      // sees a stale `menuShown` and reads as a close on an already-closed view
      // instead of reopening it (#84).
      if (isPhone) setMenuShown(false)
    } else {
      setContentDirection("forward")
      setActive(id)
      panels.open("content")
    }
  }

  return { menuShown, isSentinel, resolvedActive, revealMenu, selectSection }
}
