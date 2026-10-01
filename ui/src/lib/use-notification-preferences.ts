import * as React from "react"

import { type PrefSpec, readPreferences, writePreference } from "@/lib/cookie-preferences"

export type NotifyEnabled = "on" | "off"
/** How a *recoverable* destructive action (move-to-Bin) asks first. */
export type ConfirmStyle = "dialog" | "inline" | "none"
export type ToastPosition =
  | "top-left"
  | "top-center"
  | "top-right"
  | "bottom-left"
  | "bottom-center"
  | "bottom-right"

export interface NotificationPreferences {
  /** Feedback toasts ("Saved", "Moved to bin", errors). `"off"` silences them. */
  enabled: NotifyEnabled
  /**
   * The prompt shown before a recoverable delete. `"none"` runs it straight
   * away — the file still goes to the Bin, so it stays recoverable. Permanent
   * actions ("Delete forever", "Empty bin") always confirm regardless.
   */
  confirm: ConfirmStyle
  /** Where feedback toasts and the inline confirm appear. */
  position: ToastPosition
}

export const TOAST_POSITIONS: ToastPosition[] = [
  "top-left",
  "top-center",
  "top-right",
  "bottom-left",
  "bottom-center",
  "bottom-right",
]

const SPEC: PrefSpec<NotificationPreferences> = {
  enabled: { cookie: "sympose:notify.enabled", kind: "enum", default: "on", values: ["on", "off"] },
  confirm: { cookie: "sympose:notify.confirm", kind: "enum", default: "dialog", values: ["dialog", "inline", "none"] },
  position: { cookie: "sympose:notify.position", kind: "enum", default: "bottom-right", values: TOAST_POSITIONS },
}

// A module-level store, not `useState` seeded per hook: the imperative `notify`
// and `confirm` helpers (`lib/notify`, `lib/confirm`) read the current prefs
// without a React context, and every `useNotificationPreferences()` caller
// stays in sync through `useSyncExternalStore`.
let store: NotificationPreferences = readPreferences(SPEC)
const listeners = new Set<() => void>()

export function getNotificationPreferences(): NotificationPreferences {
  return store
}

export function setNotificationPreference<
  K extends keyof NotificationPreferences,
>(key: K, value: NotificationPreferences[K]): void {
  writePreference(SPEC, key, value)
  store = { ...store, [key]: value }
  for (const l of listeners) l()
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function useNotificationPreferences(): readonly [
  NotificationPreferences,
  <K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K]
  ) => void,
] {
  const snapshot = React.useSyncExternalStore(
    subscribe,
    getNotificationPreferences,
    getNotificationPreferences
  )
  return [snapshot, setNotificationPreference] as const
}
