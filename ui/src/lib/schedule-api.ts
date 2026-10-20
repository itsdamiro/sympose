import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/schedule` (docs/decisions/091): whether the operating system runs the persona's due jobs while the web
 * app is closed, and switching that on or off. `supported` is false where it cannot be set up (anywhere but macOS). The
 * backend holds every rule; this only asks and reports.
 */
export interface Schedule {
  supported: boolean
  installed: boolean
}

export type ScheduleResult = { ok: true; schedule: Schedule } | { ok: false; error: string }

const BACKEND_DOWN = "Sympose isn't responding. Check that it's still running, then try again."
const failed = async (res: Response, what: string) => (await detailOf(res)) || `Couldn't ${what} (code ${res.status}). Try again.`

/** `GET /api/schedule`. */
export async function fetchSchedule(): Promise<ScheduleResult> {
  try {
    const res = await fetch("/api/schedule")
    if (!res.ok) return { ok: false, error: await failed(res, "read the schedule") }
    return { ok: true, schedule: (await res.json()) as Schedule }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `PUT /api/schedule`: set it up or take it away; answers with the state now. */
export async function switchSchedule(installed: boolean): Promise<ScheduleResult> {
  try {
    const res = await fetch("/api/schedule", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ installed }),
    })
    if (!res.ok) return { ok: false, error: await failed(res, "change the schedule") }
    return { ok: true, schedule: (await res.json()) as Schedule }
  } catch {
    return { ok: false, error: `Couldn't change the schedule: ${BACKEND_DOWN}` }
  }
}
