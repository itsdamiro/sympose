import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { PlusSignIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { ChatPhase } from "@/lib/chat-api"
import type { ChatTurn } from "@/lib/chat-types"
import { ChatMessage } from "@/components/sympose/chat-message"
import { ChatMarkdown } from "@/components/sympose/chat-markdown"
import { ChatSystemLine } from "@/components/sympose/chat-system-line"
import { CloudSent } from "@/components/sympose/cloud-sent"
import { GroundedNotes } from "@/components/sympose/grounded-notes"
import { ModelChip } from "@/components/sympose/model-chip"

/** What a reply in flight is doing, in words: the same texts the terminal chat shows (ADR 043). */
const PHASE_TEXT: Record<ChatPhase, string> = {
  searching: "Searching your notes…",
  reading: "Reading a note…",
  asking: "Thinking about your message…",
}

interface ChatPanelProps extends React.ComponentProps<"div"> {
  turns: ChatTurn[]
  /** A reply is in flight: shown as a status line above the composer, and a second message is not sent. */
  sending?: boolean
  /** What that reply is doing right now, when the backend says. */
  phase?: ChatPhase | null
  /** Older turns of this conversation exist and are loaded when the user scrolls to the top. */
  hasMore?: boolean
  loadingOlder?: boolean
  onLoadOlder?: () => void
  /** Opens a note named under a reply (the notes it was based on). */
  onOpenNote?: (path: string) => void
  /** A `[[wikilink]]` inside a reply was clicked. */
  onWikiLinkClick?: (target: string) => void
  /** The "Based on ..." line under a reply that used notes (a web display knob, on by default). */
  showGrounding?: boolean
  /** Shown above the message box, always in view (the cloud notice, ADR 031). */
  notice?: React.ReactNode
  /** Starts a fresh conversation; the control shows once there is something to leave behind. */
  onNewConversation?: () => void
  draft: string
  onDraftChange: (value: string) => void
  onSubmit: () => void
  /** Model label shown in the composer footer chip. */
  model?: string
  /** Replaces the chip with the model picker, once the backend has said which models there are. */
  modelSlot?: React.ReactNode
  /** Active persona's display name, for the empty-state copy and placeholder. */
  personaName?: string
  /** Revealed when true (default), collapsed when false — same contract as
   *  `<ContentPanel>`/`<MarkdownPanel>`. Always mounted either way so the
   *  open/close transition can play. */
  open?: boolean
  /** Phone shell: one surface at a time, absolute crossfade layer. */
  phone?: boolean
}

/**
 * The third stage panel — chat, transparent over the ambient nebula (no
 * `.sy-frosted-panel`, matching the menu rail's own treatment; see
 * `index.css`'s carve-out). Unlike content/editor it has no drag handle and
 * no persisted width: its reading column is capped at a fixed measure and
 * self-centers, so a wider stage slot only changes dead side-gutter, not
 * usable room — it's always `flex-1`, with `flex-grow` snapped instantly
 * (not transitioned) between 0 and 1 on open/close, since there's no dragged
 * size to animate from/to the way `<ContentPanel>`/`<MarkdownPanel>` do. The
 * open/close motion itself is bottom-up rather than side-to-side: the panel's
 * content fades and rises into place instead of sweeping in with its width.
 */
function ChatPanel({
  className,
  turns,
  sending = false,
  phase = null,
  hasMore = false,
  loadingOlder = false,
  onLoadOlder,
  onOpenNote,
  onWikiLinkClick,
  onNewConversation,
  showGrounding = true,
  notice,
  draft,
  onDraftChange,
  onSubmit,
  model,
  modelSlot,
  personaName = "Samantha",
  open = true,
  phone = false,
  style,
  ...props
}: ChatPanelProps) {
  const submit = () => {
    if (!draft.trim() || sending) return
    onSubmit()
  }

  // Keep the newest turn (and the status line) in view as they arrive, but not when older turns are
  // added above: then the view stays where it was, so what the user was reading does not jump. The
  // height to keep is taken when the older turns are asked for, not after each render, since the
  // panel's height is still changing while it opens and a stale figure would misplace the view. The
  // browser's own scroll anchoring is off on the scroller (`[overflow-anchor:none]`), so this is the
  // only thing that moves the view when turns are added above.
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const endRef = React.useRef<HTMLDivElement>(null)
  const lastTurnId = React.useRef<string | undefined>(undefined)
  const firstTurnId = React.useRef<string | undefined>(undefined)
  const heightAtRequest = React.useRef<number | null>(null)
  React.useLayoutEffect(() => {
    const box = scrollRef.current
    const first = turns[0]?.id
    const last = turns[turns.length - 1]?.id
    const prepended =
      heightAtRequest.current !== null && first !== firstTurnId.current && last === lastTurnId.current
    if (box && prepended && heightAtRequest.current !== null) {
      box.scrollTop += box.scrollHeight - heightAtRequest.current
      heightAtRequest.current = null
    } else {
      endRef.current?.scrollIntoView?.({ block: "end" })
    }
    firstTurnId.current = first
    lastTurnId.current = last
  }, [turns, sending, phase])

  const nearTop = () => {
    const box = scrollRef.current
    if (box && hasMore && !loadingOlder && box.scrollTop < 80) {
      heightAtRequest.current = box.scrollHeight
      onLoadOlder?.()
    }
  }

  // The flex space this panel reserves in the row. On open it's claimed
  // synchronously (same render, no extra paint) so the fade/rise-in
  // animation has full-width room to play in from the first frame. On close
  // it stays claimed until the fade/rise-out animation has actually finished
  // — driven by the transition's own `onTransitionEnd`, not a guessed
  // duration, so it can't drift out of sync with `duration-mode`'s real CSS
  // value the way a hardcoded timeout could (the same reasoning
  // `use-slide-swap.ts`'s `onExitComplete`/`onAnimationEnd` contract already
  // documents for its own animation). Otherwise the box would collapse to
  // zero width instantly while the content was still mid-fade, clipping it
  // invisible before the animation ever had anything to show.
  const [reserveSpace, setReserveSpace] = React.useState(open)
  if (open && !reserveSpace) setReserveSpace(true)

  return (
    <div
      data-slot="chat-panel"
      data-state={open ? "open" : "closed"}
      data-phone={phone || undefined}
      // z-0: the bottom of the stage stack — `<MarkdownPanel>`'s own wrapper
      // comment already names "the chat slot (z-0)" for exactly this, ahead
      // of this component existing.
      //
      // Unlike content/editor (which slide in horizontally, tracking a
      // dragged width), chat reveals bottom-up: `flex-grow` itself is never
      // transitioned (it snaps straight to its open/closed value, so the
      // space it reserves in the row appears/disappears instantly rather
      // than sweeping in from the side) — the actual motion the user sees is
      // the panel's own content fading in and rising up from a slight
      // downward offset via `opacity`/`translate`.
      className={cn(
        "z-0 flex min-w-0 flex-col transition-[opacity,translate] duration-mode ease-mode",
        phone ? "absolute inset-0" : "relative overflow-hidden",
        !open && "translate-y-3",
        open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        className
      )}
      style={
        phone
          ? style
          : {
              flexGrow: reserveSpace ? 1 : 0,
              flexBasis: "0%",
              flexShrink: 1,
              ...style,
            }
      }
      // `e.target === e.currentTarget` so a bubbled transition from a child
      // (the composer border's `focus-within` color transition, the attach
      // button's hover state) can't fire this early — only the wrapper's own
      // opacity/translate transition ending collapses the reserved space.
      onTransitionEnd={(e) => {
        if (e.target === e.currentTarget && !open) setReserveSpace(false)
      }}
      {...props}
    >
      <div ref={scrollRef} onScroll={nearTop} className="min-h-0 flex-1 overflow-y-auto [overflow-anchor:none]">
        <div className="mx-auto flex min-h-full w-full max-w-[42rem] flex-col justify-end gap-6 px-6 pt-14 pb-8 sm:px-8">
          {loadingOlder && (
            <div role="status" className="text-center text-xs text-fg-muted">
              Loading earlier messages…
            </div>
          )}
          {turns.length === 0 ? (
            <div className="grid flex-1 place-items-center px-6 text-center text-sm text-fg-muted">
              Ask {personaName} anything about your vault.
            </div>
          ) : (
            turns.map((turn) =>
              turn.role === "system" ? (
                <ChatSystemLine key={turn.id} kind={turn.kind ?? "notice"}>
                  {turn.body}
                </ChatSystemLine>
              ) : turn.role === "user" ? (
                <ChatMessage key={turn.id} role="user" timestamp={turn.timestamp}>
                  {turn.body}
                </ChatMessage>
              ) : (
                <ChatMessage
                  key={turn.id}
                  role="persona"
                  handle={turn.handle}
                  model={model}
                  timestamp={turn.timestamp}
                  streaming={turn.streaming}
                  actions={turn.actions}
                  grounding={
                    <>
                      {showGrounding && <GroundedNotes sent={turn.sent} onOpenNote={onOpenNote} />}
                      <CloudSent sent={turn.sent} />
                    </>
                  }
                >
                  <ChatMarkdown onWikiLinkClick={onWikiLinkClick}>{turn.body}</ChatMarkdown>
                </ChatMessage>
              )
            )
          )}
          {sending && (
            <div role="status" className="text-xs text-fg-muted motion-safe:animate-pulse">
              {phase ? PHASE_TEXT[phase] : PHASE_TEXT.asking}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0">
        <div className="mx-auto w-full max-w-[42rem] px-6 pb-6 sm:px-8">
          {notice}
          <div className="rounded-lg border border-border bg-background transition-colors focus-within:border-brand">
            <textarea
              rows={1}
              value={draft}
              onChange={(e) => onDraftChange(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault()
                  submit()
                }
              }}
              placeholder={`Ask ${personaName}.`}
              aria-label="Message"
              className="block w-full resize-none bg-transparent px-3.5 py-3 text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <div className="mt-2 flex items-center justify-between px-1">
            <button
              type="button"
              disabled
              title="Attachments — coming soon"
              aria-label="Add attachment"
              className="grid size-7 place-items-center rounded-full border border-border text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
            >
              <HugeiconsIcon icon={PlusSignIcon} className="size-4" />
            </button>
            <div className="flex items-center gap-2">
              {onNewConversation && turns.length > 0 && !sending && (
                <button
                  type="button"
                  onClick={onNewConversation}
                  className="rounded px-1.5 py-0.5 text-xs text-fg-muted transition-colors hover:bg-accent hover:text-foreground"
                >
                  New conversation
                </button>
              )}
              {modelSlot ?? (model && <ModelChip model={model} />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export { ChatPanel }
