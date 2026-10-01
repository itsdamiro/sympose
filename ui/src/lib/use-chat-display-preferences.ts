import { type PrefSpec, useCookiePreferences } from "@/lib/cookie-preferences"

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

const SPEC: PrefSpec<ChatDisplayPreferences> = {
  showGrounding: { cookie: "sympose:chat.showGrounding", kind: "bool", default: true },
  typeStatus: { cookie: "sympose:chat.typeStatus", kind: "bool", default: true },
  showMeter: { cookie: "sympose:chat.showMeter", kind: "bool", default: true },
}

export function useChatDisplayPreferences() {
  return useCookiePreferences(SPEC)
}
