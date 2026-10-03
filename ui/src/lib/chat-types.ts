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

/** One lookup she made herself in `ask` mode, or a `remember` (ADR 040, 041, 056): what she asked for and how many
 *  passages it found, never their text. */
export interface SentLookup {
  tool: string
  query?: string
  path?: string
  id?: string
  found?: number
  /** `remember` only: whether it was written. */
  saved?: boolean
}

/** What reached the model besides the messages, for one reply, as the session log records it (ADR 025): the same
 *  record the terminal's `/grounded` reads. Everything but `notes` is left out when it does not apply. */
export interface SentRecord {
  notes: SentNote[]
  /** Exchanges of earlier conversations, when `past_chats` attached or looked up any. */
  chats?: SentChat[]
  /** The conversations whose recaps were sent. */
  recaps?: string[]
  /** Which of her memory files were sent: `profile`, `context`, `decisions`. */
  memory?: string[]
  /** What she looked up or remembered herself. */
  lookups?: SentLookup[]
  /** `ask` for notes, when chosen; `auto` when the model could not take tools and Sympose searched instead. */
  mode?: string
  /** The same, for earlier conversations (`past_chats`). */
  chats_mode?: string
  /** How many older turns were left out of the prompt. */
  history_dropped?: number
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
  /** `role: "system"` only: a heading for a longer passage (the notes that stand in for condensed turns), so it is not mistaken for a reply. */
  title?: string
  /** Persona handle — `role: "persona"` only. */
  handle?: string
  body: string
  timestamp?: string
  /** The model that made this reply — `role: "persona"` only; each reply keeps its own, so an old one does not take
   *  on a model chosen later. */
  model?: string
  /** TTFT/latency readout — `role: "persona"` only. */
  latency?: string
  streaming?: boolean
  actions?: ChatAction[]
  /** What grounded this reply — `role: "persona"` only. */
  sent?: SentRecord | null
}
