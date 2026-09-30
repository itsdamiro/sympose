import * as React from "react"

import { getCookieBool, setCookieBool } from "@/lib/cookies"

/**
 * How the web chat draws things (docs/decisions/044). These are the web's own display knobs, kept in cookies
 * like the other interface preferences: they change nothing the engine does, so they are not backend
 * settings and the terminal's own display settings do not touch them.
 */
export interface ChatDisplayPreferences {
  /** The "Based on ..." line under a reply that used notes (the terminal's `show_grounding`). */
  showGrounding: boolean
  /** The busy line above the message box types each phrase out by letters (ADR 043, 044; the terminal's
   *  `status_typing`). Off shows whole phrases; a browser that asks for reduced motion gets them anyway. */
  typeStatus: boolean
  /** The context meter (a ring and a percentage) in the composer's footer (ADR 018, 044; the terminal's
   *  `show_context_meter`). */
  showMeter: boolean
}

const COOKIES = { showGrounding: "sympose:chat.showGrounding", typeStatus: "sympose:chat.typeStatus", showMeter: "sympose:chat.showMeter" } as const
const DEFAULTS: ChatDisplayPreferences = { showGrounding: true, typeStatus: true, showMeter: true }

const read = (): ChatDisplayPreferences => ({
  showGrounding: getCookieBool(COOKIES.showGrounding, DEFAULTS.showGrounding),
  typeStatus: getCookieBool(COOKIES.typeStatus, DEFAULTS.typeStatus),
  showMeter: getCookieBool(COOKIES.showMeter, DEFAULTS.showMeter),
})

export function useChatDisplayPreferences(): readonly [
  ChatDisplayPreferences,
  <K extends keyof ChatDisplayPreferences>(key: K, value: ChatDisplayPreferences[K]) => void,
] {
  const [prefs, setPrefs] = React.useState<ChatDisplayPreferences>(read)
  const setPref = React.useCallback(
    <K extends keyof ChatDisplayPreferences>(key: K, value: ChatDisplayPreferences[K]) => {
      setCookieBool(COOKIES[key], value)
      setPrefs((prev) => ({ ...prev, [key]: value }))
    },
    []
  )
  return [prefs, setPref] as const
}
