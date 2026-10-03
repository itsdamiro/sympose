import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Alert02Icon,
  CheckmarkCircle02Icon,
  InformationCircleIcon,
  Notebook01Icon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { SystemKind } from "@/lib/chat-types"

interface ChatSystemLineProps extends React.ComponentProps<"div"> {
  kind: SystemKind
  /** A heading for a longer passage, such as the notes that stand in for condensed turns. */
  title?: string
}

const ICONS = {
  error: Alert02Icon,
  confirmation: CheckmarkCircle02Icon,
  notice: InformationCircleIcon,
  output: InformationCircleIcon,
} as const

/**
 * A line the app itself says between the turns, as the terminal chat does: a confirmation, an error, a
 * notice or a command's output. It is drawn as a small bordered card with an icon, set apart from both sides
 * of the conversation, so it cannot be mistaken for part of a reply; a passage with a `title` (the condensed
 * notes) keeps its text in the body's prose, under the heading. Errors use the danger color and are announced
 * to assistive tech; the rest are polite status text.
 */
function ChatSystemLine({ className, kind, title, children, ...props }: ChatSystemLineProps) {
  const prose = Boolean(title)
  return (
    <div
      data-slot="chat-system-line"
      data-kind={kind}
      role={kind === "error" ? "alert" : "status"}
      className={cn(
        "flex max-w-[74ch] items-start gap-2 rounded-lg border px-3 py-2 text-xs leading-relaxed",
        kind === "error" ? "border-danger/40 bg-danger/5 text-danger" : "border-border bg-chip/40 text-fg-muted",
        className
      )}
      {...props}
    >
      <HugeiconsIcon icon={title ? Notebook01Icon : ICONS[kind]} aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="pb-0.5 font-medium tracking-wide text-foreground">{title}</p>}
        <div className={cn("whitespace-pre-wrap", kind === "output" && !prose && "font-mono")}>{children}</div>
      </div>
    </div>
  )
}

export { ChatSystemLine }
