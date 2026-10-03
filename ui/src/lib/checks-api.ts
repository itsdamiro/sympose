import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for the Settings footer's two checks (docs/decisions/063): `GET /api/doctor` and `POST /api/doctor/fix`
 * (the installation) and `GET /api/vault/health` (the notes, read as the default persona). The backend decides what
 * counts as a problem and how it is worded; the browser draws what comes back.
 */
export type DoctorState = "needs_you" | "fixable" | "fixed" | "failed"

export interface DoctorFinding {
  problem: string
  state: DoctorState
  /** What Fix would do (or did); `null` when nothing automatic can. */
  fix: string | null
  error: string
}

export interface DoctorReport {
  /** The lines the terminal prints first: the models in use and what leaves the computer. */
  models: string[]
  findings: DoctorFinding[]
}

export interface HealthCheck {
  heading: string
  /** `false`: an offer or an observation, not a fault. */
  problem: boolean
  findings: { note: string; message: string }[]
}

export interface HealthReport {
  persona: string
  notes: number
  problems: number
  limits: string
  checks: HealthCheck[]
}

export type CheckResult<T> = { ok: true; report: T } | { ok: false; error: string }

const BACKEND_DOWN = "the Sympose backend is not reachable"

async function call<T>(url: string, init?: RequestInit): Promise<CheckResult<T>> {
  try {
    const res = await fetch(url, init)
    if (res.ok) return { ok: true, report: (await res.json()) as T }
    return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** Looks only; changes nothing. */
export const fetchDoctor = () => call<DoctorReport>("/api/doctor")

/** Does what `sympose doctor --fix` does, then answers with where each finding stands. */
export const fixDoctor = () => call<DoctorReport>("/api/doctor/fix", { method: "POST" })

export const fetchHealth = () => call<HealthReport>("/api/vault/health")

/** Findings still wrong after a run: a fixed one is done. */
export const leftOver = (report: DoctorReport) => report.findings.filter((f) => f.state !== "fixed")

/** Findings `Fix` can correct right now. */
export const fixable = (report: DoctorReport) => report.findings.filter((f) => f.state === "fixable")
