import * as React from "react"

import { GENERIC_PHRASES, fetchStatusPhrases, type StatusPhrases } from "@/lib/status-phrases-api"

/**
 * The persona's busy-line phrases (docs/decisions/044), read when the persona changes (which is also what
 * starts their one-time generation on the backend) and again each time a reply ends while the persona still has
 * only the generic ones, so its own appear once they exist. Never `null` for the caller: the generic phrases
 * stand in until, or when, the backend cannot say. A read for another persona is never shown for this one.
 */
export function useStatusPhrases(persona: string | null | undefined, sending: boolean): string[] {
  const [loaded, setLoaded] = React.useState<{ persona: string; value: StatusPhrases } | null>(null)
  const own = loaded !== null && loaded.persona === persona && loaded.value.own

  React.useEffect(() => {
    if (!persona || sending || own) return
    let cancelled = false
    void fetchStatusPhrases(persona).then((value) => {
      if (!cancelled && value) setLoaded({ persona, value })
    })
    return () => {
      cancelled = true
    }
  }, [persona, sending, own])

  return loaded && loaded.persona === persona ? loaded.value.phrases : GENERIC_PHRASES
}
