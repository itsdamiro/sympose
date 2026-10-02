export type ActionKind = "WRITE_NOTE" | "APPEND_NOTE" | "SEARCH"

export interface ChatAction {
  kind: ActionKind
  detail?: string
}

/** What a system line is telling the user, as in the terminal chat: a confirmation ("Now talking to …"),
 *  an error ("couldn't reply: …"), a notice (trim, cloud, memory) or the output of a command. */
export type SystemKind = "confirmation" | "error" | "notice" | "output"

/** One note or passage that reached the model for a reply, as the session log records it (ADR 025): where it
 *  came from, never its text. */
export interface SentNote {
  path: string
  heading: string
  /** `"vault"` for the user's own notes, `"sympose"` for the built-in reference library. */
  source: string
  /** How it was found, when known: by meaning, named in full, by a property value, or a persona's lookup. */
  via?: "embedding" | "name" | "value" | "search" | "opened"
  /** For a hit found by meaning only: how close it was, 0 to 1. */
  similarity?: number
}

/** One exchange of an earlier conversation that reached the model word for word (ADR 056): which, never its text. */
export interface SentChat {
  session: string
  turn: number
  how: string
}

/** What reached the model besides the messages, for one reply: only what the grounded view reads. */
export interface SentRecord {
  notes: SentNote[]
  /** Exchanges of earlier conversations, when `past_chats` attached or looked up any. */
  chats?: SentChat[]
  /** The query a follow-up was rewritten into, when that is what found the notes. */
  searched?: string | null
  /** A cloud model's turn only (ADR 031): the categories of the vault that were sent, and those held back. */
  cloud?: string[]
  withheld?: string[]
}

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
  /** What grounded this reply — `role: "persona"` only. */
  sent?: SentRecord | null
}
