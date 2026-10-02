import type { ChatPhase } from "@/lib/chat-api"

/**
 * The web chat's busy line: the same rules as the terminal's (`cli/background_status.py`, ADR 043, 044). A
 * reply in flight shows what it is doing in words; from 3 seconds it starts alternating with one of the
 * persona's own witty phrases, the literal text again every other 3-second slot, and a witty pick is never the
 * one just shown; each phrase is typed out one letter at a time. A pure function of the phase, the time and
 * the phrases, so it is tested with a scripted clock; the constants are the terminal's, declared again because
 * the two are separate programs.
 */
export const PHASE_TEXT: Record<ChatPhase, string> = {
  searching: "Searching your notes…",
  reading: "Reading a note…",
  asking: "Thinking about your message…",
  queued: "Waiting for the other conversation’s reply…",
}

export const ROTATE_AFTER_SECONDS = 3
export const ROTATE_INTERVAL_SECONDS = 3
export const CHARS_PER_SECOND = 40
const SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
const FRAMES_PER_SPINNER_STEP = 3

/** Characters per second for the typing: `0` (whole phrases) when the user turned it off or their browser asks
 *  for reduced motion. */
export function typingSpeed(typing: boolean): number {
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  return typing && !reduced ? CHARS_PER_SECOND : 0
}

export class StatusLine {
  private phase: ChatPhase | null = null
  private started = 0
  private slot = 0
  private phrase = ""
  private phraseAt = 0
  private lastWitty = ""
  private ticks = 0

  private readonly random: () => number

  constructor(random: () => number = Math.random) {
    this.random = random
  }

  private witty(phrases: string[], fallback: string): string {
    const others = phrases.filter((p) => p !== this.lastWitty)
    const pool = others.length > 0 ? others : phrases
    if (pool.length === 0) return fallback
    this.lastWitty = pool[Math.floor(this.random() * pool.length)]
    return this.lastWitty
  }

  private set(phrase: string, now: number) {
    this.phrase = phrase
    this.phraseAt = now
  }

  /** The whole line for this moment (spinner, the typed part of the phrase), `""` when no reply is in flight.
   *  `now` is in seconds; `cps` is the typing speed, `0` showing each phrase whole. */
  line(phase: ChatPhase | null, phrases: string[], now: number, cps: number): string {
    if (phase !== this.phase) {
      this.phase = phase
      this.started = now
      this.slot = 0
      this.set(phase ? PHASE_TEXT[phase] : "", now)
    } else if (phase) {
      const slot = Math.floor((now - this.started - ROTATE_AFTER_SECONDS) / ROTATE_INTERVAL_SECONDS) + 1 // 0 until the threshold
      if (slot !== this.slot) {
        this.slot = slot
        this.set(slot % 2 === 0 ? PHASE_TEXT[phase] : this.witty(phrases, PHASE_TEXT[phase]), now)
      }
    }
    if (!phase) return ""
    const shown = cps <= 0 ? this.phrase : this.phrase.slice(0, Math.floor((now - this.phraseAt) * cps) + 1)
    const frame = SPINNER[Math.floor(this.ticks / FRAMES_PER_SPINNER_STEP) % SPINNER.length]
    this.ticks += 1
    return `${frame} ${shown}`
  }
}
