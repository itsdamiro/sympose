export type ActionKind = "WRITE_NOTE" | "APPEND_NOTE" | "SEARCH"

export interface ChatAction {
  kind: ActionKind
  detail?: string
}

/** What a system line is telling the user, as in the terminal chat: a confirmation ("Now talking to …"),
 *  an error ("couldn't reply: …"), a notice (trim, cloud, memory) or the output of a command. */
export type SystemKind = "confirmation" | "error" | "notice" | "output"

export interface ChatTurn {
  id: string
  role: "user" | "persona" | "system"
  /** `role: "system"` only. */
  kind?: SystemKind
  /** Persona handle — `role: "persona"` only. */
  handle?: string
  body: string
  timestamp?: string
  /** TTFT/latency readout — `role: "persona"` only. */
  latency?: string
  streaming?: boolean
  actions?: ChatAction[]
}
