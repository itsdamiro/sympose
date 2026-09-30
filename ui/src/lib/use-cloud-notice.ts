import * as React from "react"

import { getCookieBool, setCookieBool } from "@/lib/cookies"

/**
 * Whether the user has closed the cloud notice (docs/decisions/044, 031). A cookie, like the other interface
 * preferences, kept in a small store so the notice and the model picker's "what this model may receive" item
 * stay in step. Closing changes only what this page draws, not what is shared. It is cleared whenever the model
 * in use is a local one, so the next switch to a cloud model shows the notice again (the moment ADR 031 says to
 * announce); a switch between two cloud models keeps it closed.
 */
const COOKIE = "sympose:chat.cloudNoticeClosed"

let closed = getCookieBool(COOKIE, false)
const listeners = new Set<() => void>()

function setClosed(value: boolean) {
  if (value === closed) return
  closed = value
  setCookieBool(COOKIE, value)
  for (const l of listeners) l()
}

const subscribe = (cb: () => void) => {
  listeners.add(cb)
  return () => listeners.delete(cb)
}
const read = () => closed

/** `cloud`: whether the model in use is a cloud one, `undefined` while that is not known (nothing is reset then). */
export function useCloudNotice(cloud: boolean | undefined) {
  const isClosed = React.useSyncExternalStore(subscribe, read, read)
  React.useEffect(() => {
    if (cloud === false) setClosed(false)
  }, [cloud])
  const close = React.useCallback(() => setClosed(true), [])
  const reopen = React.useCallback(() => setClosed(false), [])
  return { open: !isClosed, close, reopen }
}
