/**
 * The context meter's figures and words (docs/decisions/018, 044): the same rules as the terminal's
 * (`cli/meter.py`), written again because the two are separate programs. 100% is the prompt budget being
 * reached, the point where the next message starts leaving older turns out.
 */
export const WARN_AT = 70
export const ERROR_AT = 90

export interface ContextFigure {
  /** Tokens in use, and the prompt budget they are measured against. */
  used: number
  limit: number
  /** Worked out without a model call (after a refresh or a model switch), not a reply's own count. */
  estimated: boolean
}

export type MeterLevel = "ok" | "warn" | "error"

/** Whole percent of `limit` in use, never above 100; 100 means the budget is reached, so a hair under it reads 99. */
export function percent(used: number, limit: number): number {
  const pct = Math.min(100, Math.max(0, Math.round((used * 100) / limit)))
  return used >= limit ? pct : Math.min(pct, 99)
}

export function level(pct: number): MeterLevel {
  return pct >= ERROR_AT ? "error" : pct >= WARN_AT ? "warn" : "ok"
}

/** `3,812` (whole tokens, grouped). */
export const tokens = (n: number) => Math.max(0, n).toLocaleString("en-US")

/** What the figure means, one sentence each: shown when the meter is hovered or focused. */
export function explanation(figure: ContextFigure): string[] {
  return [
    `${tokens(figure.used)} of ${tokens(figure.limit)} tokens${figure.estimated ? " (estimated)" : ""}`,
    "100% is where your next message starts leaving the oldest turns out of the conversation.",
    figure.estimated
      ? "Worked out from the conversation so far, without asking the model; it leans low, and your next reply replaces it."
      : "It leans a little high, on purpose, so it warns you early.",
  ]
}
