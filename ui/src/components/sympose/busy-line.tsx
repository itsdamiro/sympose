import * as React from "react"

import type { ChatPhase } from "@/lib/chat-api"
import { PHASE_TEXT, StatusLine, typingSpeed } from "@/lib/status-line"

/** How often the line is looked at, so typed letters look smooth (the terminal's line does the same). */
const FRAME_MS = 40

/**
 * The line above the message box while a reply is in flight (docs/decisions/043, 044): what it is doing in
 * words, from 3 seconds alternating with one of the persona's own witty phrases, each typed out one letter at a
 * time. Mounted only while a reply is in flight, so every reply starts it afresh. The letters change under a
 * screen reader's feet, so it hears the phase's own text once instead (`sr-only`), not every keystroke.
 */
function BusyLine({
  phase,
  phrases,
  typing,
  className,
}: {
  phase: ChatPhase
  phrases: string[]
  /** Type each phrase out by letters (a browser that asks for reduced motion gets whole phrases regardless). */
  typing: boolean
  className?: string
}) {
  const [line] = React.useState(() => new StatusLine())
  const latest = React.useRef({ phase, phrases, typing })
  React.useEffect(() => {
    latest.current = { phase, phrases, typing }
  })
  const [text, setText] = React.useState(() => line.line(phase, phrases, performance.now() / 1000, typingSpeed(typing)))

  React.useEffect(() => {
    const id = window.setInterval(() => {
      const now = latest.current
      const next = line.line(now.phase, now.phrases, performance.now() / 1000, typingSpeed(now.typing))
      setText(next) // React skips the redraw when it is the text already shown
    }, FRAME_MS)
    return () => window.clearInterval(id)
  }, [line])

  return (
    <div role="status" data-slot="busy-line" className={className}>
      <span className="sr-only">{PHASE_TEXT[phase]}</span>
      <span aria-hidden>{text}</span>
    </div>
  )
}

export { BusyLine }
