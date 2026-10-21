import * as React from "react"

import { fetchSlackConnected } from "@/lib/slack-api"

/** How often the dot looks again while the page is in view; the backend's own heartbeat is every 20 seconds. */
export const SLACK_POLL_MS = 20_000

/**
 * Whether the persona is connected to Slack now (docs/decisions/093), read when `watching` turns on or the persona changes,
 * then every `SLACK_POLL_MS` while the window is visible and again when it comes back into view. Not read at all while
 * `watching` is false (the persona page is not open). A read for another persona is never shown for this one.
 */
export function useSlackConnected(persona: string | null | undefined, watching: boolean): boolean {
  const [seen, setSeen] = React.useState<{ persona: string; connected: boolean } | null>(null)

  React.useEffect(() => {
    if (!persona || !watching) return
    let cancelled = false
    const read = () => {
      if (document.visibilityState === "hidden") return
      void fetchSlackConnected(persona).then((connected) => {
        if (!cancelled) setSeen({ persona, connected })
      })
    }
    read()
    const timer = window.setInterval(read, SLACK_POLL_MS)
    document.addEventListener("visibilitychange", read)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      document.removeEventListener("visibilitychange", read)
    }
  }, [persona, watching])

  return watching && seen !== null && seen.persona === persona && seen.connected
}
