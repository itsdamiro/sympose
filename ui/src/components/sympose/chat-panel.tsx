import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { PlusSignIcon, StopIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { ChatPhase } from "@/lib/chat-api"
import type { ChatTurn } from "@/lib/chat-types"
import { ChatMessage } from "@/components/sympose/chat-message"
import { ChatMarkdown } from "@/components/sympose/chat-markdown"
import { ChatSystemLine } from "@/components/sympose/chat-system-line"
import { BusyLine } from "@/components/sympose/busy-line"
import { CloudSent } from "@/components/sympose/cloud-sent"
import { ContextMeter } from "@/components/sympose/context-meter"
import type { ContextFigure } from "@/lib/context-meter"
import { GroundedNotes } from "@/components/sympose/grounded-notes"
import { ModelChip } from "@/components/sympose/model-chip"

interface ChatPanelProps extends React.ComponentProps<"div"> {
  turns: ChatTurn[]
  /** A reply is in flight: shown as a status line above the composer, and a second message is not sent. */
  sending?: boolean
  /** What that reply is doing right now, when the backend says. */
  phase?: ChatPhase | null
  /** The search index build in progress (whole percent) while a reply waits: the reply searches by keyword. */
  indexing?: number | null
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
  /** The context meter's figure (a ring and a percentage in the footer), or `null` for none. */
  contextFigure?: ContextFigure | null
  /** The persona's own witty phrases for the busy line, and whether they are typed out by letters. */
  statusPhrases?: string[]
  typeStatus?: boolean
  /** Shown above the message box, always in view (the cloud notice, ADR 031). */
  notice?: React.ReactNode
  /** Starts a fresh conversation; the control shows once there is something to leave behind. */
  onNewConversation?: () => void
  /** Condenses the earlier part of the conversation into notes (ADR 055); shown beside "New conversation"
   *  once there is a conversation, and says it is working while the notes are written. */
  onCompact?: () => void
  compacting?: boolean
  draft: string
  onDraftChange: (value: string) => void
  onSubmit: () => void
  /** Stop the reply in flight (ADR 054); the Stop button shows only while `sending`, and only when this is given. */
  onStop?: () => void
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
/** The tallest the message box grows to, about eight lines; past that it scrolls inside. */
const MAX_INPUT_PX = 192

function ChatPanel({
  className,
  turns,
  sending = false,
  phase = null,
  indexing = null,
  hasMore = false,
  loadingOlder = false,
  onLoadOlder,
  onOpenNote,
  onWikiLinkClick,
  onNewConversation,
  onCompact,
  compacting = false,
  showGrounding = true,
  contextFigure = null,
  statusPhrases = [],
  typeStatus = true,
  notice,
  draft,
  onDraftChange,
  onSubmit,
  onStop,
  model,
  modelSlot,
  personaName = "Samantha",
  open = true,
  phone = false,
  style,
  ...props
}: ChatPanelProps) {
  const showStop = sending && !!onStop
  const submit = () => {
    if (!draft.trim()) return
    onSubmit()
  }

  // The message box grows with what is typed, up to `MAX_INPUT_PX`, and goes back to one line once it is
  // sent. Measured on the box itself (`scrollHeight`) so wrapped lines count, not only line breaks; measured
  // again when the panel opens (while it is closed the box has no width and even the placeholder wraps) and
  // when the box's width changes (a resize, a dragged panel), since wrapping depends on it.
  const inputRef = React.useRef<HTMLTextAreaElement>(null)
  const fitInput = React.useCallback(() => {
    const box = inputRef.current
    if (!box) return
    box.style.height = "auto"
    box.style.height = `${Math.min(box.scrollHeight, MAX_INPUT_PX)}px`
    box.style.overflowY = box.scrollHeight > MAX_INPUT_PX ? "auto" : "hidden"
  }, [])
  React.useLayoutEffect(fitInput, [fitInput, draft, open])
  React.useEffect(() => {
    const box = inputRef.current
    if (!box || typeof ResizeObserver === "undefined") return
    let width = box.clientWidth
    const watcher = new ResizeObserver(() => {
      if (box.clientWidth === width) return
      width = box.clientWidth
      fitInput()
    })
    watcher.observe(box)
    return () => watcher.disconnect()
  }, [fitInput])

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
            <BusyLine
              phase={phase ?? "asking"}
              phrases={statusPhrases}
              typing={typeStatus}
              className="text-xs text-fg-muted"
            />
          )}
          {sending && indexing !== null && (
            <p data-slot="indexing-notice" role="status" className="text-xs text-fg-muted">
              Still indexing your notes ({indexing}%). Until it is done, searches use keywords.
            </p>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0">
        <div className="mx-auto w-full max-w-[42rem] px-6 pb-6 sm:px-8">
          {notice}
          <div className="relative rounded-lg border border-border bg-background transition-colors focus-within:border-brand">
            <textarea
              ref={inputRef}
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
              className={cn(
                "block w-full resize-none bg-transparent px-3.5 py-3 text-sm outline-none placeholder:text-muted-foreground",
                showStop && "pr-12"
              )}
            />
            {showStop && (
              <button
                type="button"
                onClick={onStop}
                title="Stop the reply"
                aria-label="Stop the reply"
                className="absolute right-2 bottom-2 grid size-7 place-items-center rounded-full bg-foreground text-background transition-opacity hover:opacity-80"
              >
                <HugeiconsIcon icon={StopIcon} className="size-3.5" />
              </button>
            )}
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
              <ContextMeter figure={contextFigure} />
              {onCompact && turns.length > 0 && !sending && (
                <button
                  type="button"
                  onClick={onCompact}
                  disabled={compacting}
                  title="Write short notes in place of the earlier turns, so a long conversation takes less room"
                  className="rounded px-1.5 py-0.5 text-xs text-fg-muted transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-60"
                >
                  {compacting ? "Condensing…" : "Condense"}
                </button>
              )}
              {onNewConversation && turns.length > 0 && (
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
