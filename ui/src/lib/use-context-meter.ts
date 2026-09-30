import * as React from "react"

import { fetchContextEstimate } from "@/lib/chat-api"
import type { ContextFigure } from "@/lib/context-meter"

/**
 * The figure the context meter shows (docs/decisions/044, 018): the last reply's own count while it belongs to
 * the model now in use, otherwise, once the conversation has replies, an estimate for that model from the
 * backend (a refresh that resumed a conversation, a model switch). Nothing for an empty conversation or when
 * no figure can be had. A figure belongs to the model that measured it, so a switch drops the real one; an
 * answer that arrives after the persona, the conversation or the model changed is never shown.
 */
export function useContextMeter({
  persona,
  sessionId,
  model,
  real,
  hasReplies,
}: {
  persona: string | null | undefined
  sessionId: string | undefined
  /** The model the persona runs on now. */
  model: string | undefined
  /** The last reply's count and the model that made it. */
  real: { used: number; limit: number; model: string } | undefined
  hasReplies: boolean
}): ContextFigure | null {
  const usable = real && model && real.model === model ? real : undefined
  const key = !usable && persona && sessionId && model && hasReplies ? `${persona}|${sessionId}|${model}` : null
  const [estimate, setEstimate] = React.useState<{ key: string; used: number; limit: number } | null>(null)

  React.useEffect(() => {
    if (!key || !persona || !sessionId) return
    let cancelled = false
    void fetchContextEstimate(persona, sessionId).then((figures) => {
      if (!cancelled && figures) setEstimate({ key, ...figures })
    })
    return () => {
      cancelled = true
    }
  }, [key, persona, sessionId])

  if (usable) return { used: usable.used, limit: usable.limit, estimated: false }
  if (key && estimate && estimate.key === key) return { used: estimate.used, limit: estimate.limit, estimated: true }
  return null
}
