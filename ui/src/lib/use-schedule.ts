import * as React from "react"

import { notify } from "@/lib/notify"
import { fetchSchedule, switchSchedule, type Schedule } from "@/lib/schedule-api"

/**
 * Whether jobs run while the web app is closed (docs/decisions/091), read once and switched. A refusal is an error toast
 * and the switch keeps what the backend last said. `null` until it is read, or when it could not be.
 */
export function useSchedule() {
  const [schedule, setSchedule] = React.useState<Schedule | null>(null)

  React.useEffect(() => {
    let cancelled = false
    void fetchSchedule().then((result) => {
      if (!cancelled && result.ok) setSchedule(result.schedule)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const set = React.useCallback(async (installed: boolean) => {
    const result = await switchSchedule(installed)
    if (!result.ok) {
      notify.error(result.error)
      return false
    }
    setSchedule(result.schedule)
    return true
  }, [])

  return { schedule, set }
}
