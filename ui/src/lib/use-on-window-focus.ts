import * as React from "react"

/**
 * Calls `callback` each time the window comes back into focus: how the app notices what another program did while it was away
 * (the terminal, Slack's Accept, an editor). The latest `callback` is the one called, so it may use current props and state
 * without being a dependency, and the listener is added once.
 */
export function useOnWindowFocus(callback: () => void): void {
  const latest = React.useRef(callback)
  React.useEffect(() => {
    latest.current = callback
  })
  React.useEffect(() => {
    const again = () => latest.current()
    window.addEventListener("focus", again)
    return () => window.removeEventListener("focus", again)
  }, [])
}
