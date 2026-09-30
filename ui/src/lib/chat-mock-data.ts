export type ActionKind = "WRITE_NOTE" | "APPEND_NOTE" | "SEARCH"

export interface ChatAction {
  kind: ActionKind
  detail?: string
}

export interface ChatTurn {
  id: string
  role: "user" | "persona"
  /** Persona handle — `role: "persona"` only. */
  handle?: string
  body: string
  timestamp?: string
  /** TTFT/latency readout — `role: "persona"` only. */
  latency?: string
  streaming?: boolean
  actions?: ChatAction[]
}
