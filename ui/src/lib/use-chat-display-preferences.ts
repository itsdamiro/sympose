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
}

const COOKIES = { showGrounding: "sympose:chat.showGrounding" } as const
const DEFAULTS: ChatDisplayPreferences = { showGrounding: true }

const read = (): ChatDisplayPreferences => ({
  showGrounding: getCookieBool(COOKIES.showGrounding, DEFAULTS.showGrounding),
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
