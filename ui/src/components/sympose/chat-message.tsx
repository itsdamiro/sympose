import * as React from "react"
import { Attachment01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { resolvePersonaVisuals } from "@/lib/personas"
import type { ChatAction } from "@/lib/chat-types"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ActionBadge } from "@/components/sympose/action-badge"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

/** A blinking caret at the tail of a mid-stream persona reply. */
function StreamingCaret({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden
      className={cn(
        "ml-0.5 inline-block h-[1.1em] w-0.5 translate-y-[0.15em] bg-brand motion-safe:animate-pulse",
        className
      )}
      {...props}
    />
  )
}

interface ChatMessageProps extends React.ComponentProps<"div"> {
  role: "user" | "persona"
  /** Persona handle — `role: "persona"` only. */
  handle?: string
  /** Marks the reply in its header, beside the avatar (the reply's model chip, with the cloud mark on a cloud model's reply, ADR 060) — `role: "persona"` only. */
  indicator?: React.ReactNode
  timestamp?: string
  /** How many passages of the open note were attached to this message, shown as a paperclip beside the time — `role: "user"` only. */
  attached?: number
  /** How long the model took to start answering (time to first token), as "0.82s" — `role: "persona"` only, shown before the time. */
  latency?: string
  streaming?: boolean
  actions?: ChatAction[]
  /** What grounded this reply (the notes it was based on) — `role: "persona"` only, under the text. */
  grounding?: React.ReactNode
}

/**
 * One turn in the chat transcript. User turns are a right-aligned filled
 * bubble; persona turns are a left-aligned identity header (avatar, an optional
 * indicator, the time) over plain flowing text — distinction by alignment, not by two
 * different bubble styles.
 */
function ChatMessage({
  className,
  role,
  handle,
  indicator,
  timestamp,
  attached,
  latency,
  streaming = false,
  actions,
  grounding,
  children,
  ...props
}: ChatMessageProps) {
  if (role === "user") {
    return (
      <div
        data-slot="chat-message"
        data-role="user"
        className={cn("flex flex-col items-end gap-1", className)}
        {...props}
      >
        <div className="max-w-[80%] rounded-tl-lg rounded-br-lg rounded-bl-lg bg-panel px-4 py-3 text-sm leading-relaxed text-muted-foreground">
          {children}
        </div>
        {(timestamp || attached) && (
          <span className="flex items-center gap-1.5 font-mono text-xs text-fg-muted tabular-nums">
            {attached ? (
              <span
                role="img"
                data-slot="attached-mark"
                className="flex items-center gap-0.5"
                aria-label={attached === 1 ? "1 passage of the note attached" : `${attached} passages of the note attached`}
                title={attached === 1 ? "1 passage of the note attached" : `${attached} passages of the note attached`}
              >
                <HugeiconsIcon icon={Attachment01Icon} className="size-3" aria-hidden />
                {attached > 1 && attached}
              </span>
            ) : null}
            {timestamp}
          </span>
        )}
      </div>
    )
  }

  const visuals = resolvePersonaVisuals(handle ?? "")

  return (
    <div
      data-slot="chat-message"
      data-role="persona"
      className={cn("flex flex-col gap-1.5", className)}
      {...props}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Avatar size="sm">
          <AvatarFallback
            className="text-background"
            style={{ background: visuals.accent }}
          >
            <HugeiconsIcon icon={visuals.icon} className="size-3.5" />
          </AvatarFallback>
        </Avatar>
        {indicator}
        {latency && (
          <Tooltip>
            <TooltipTrigger
              render={<button type="button" />}
              className="cursor-default rounded font-mono text-xs text-fg-muted tabular-nums outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              TTFT {latency}
            </TooltipTrigger>
            <TooltipContent>Time to first token: how long the model took to start answering</TooltipContent>
          </Tooltip>
        )}
        {latency && timestamp && (
          <span aria-hidden className="text-xs text-fg-muted">
            ·
          </span>
        )}
        {timestamp && (
          <span className="font-mono text-xs text-fg-muted tabular-nums">
            {timestamp}
          </span>
        )}
      </div>
      <div className="max-w-[74ch] text-sm leading-relaxed text-muted-foreground">
        {children}
        {streaming && <StreamingCaret />}
      </div>
      {grounding}
      {actions && actions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {actions.map((a, i) => (
            <ActionBadge key={i} action={a.kind} detail={a.detail} />
          ))}
        </div>
      )}
    </div>
  )
}

export { ChatMessage, StreamingCaret }
