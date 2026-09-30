import * as React from "react"

import { cn } from "@/lib/utils"
import type { SystemKind } from "@/lib/chat-types"

interface ChatSystemLineProps extends React.ComponentProps<"div"> {
  kind: SystemKind
}

/**
 * A line the app itself says between the turns, as the terminal chat does: a confirmation, an error, a
 * notice or a command's output. Plain text, centered under the persona column's width, so it reads as
 * the app talking and not as either side of the conversation. Errors use the danger color and are
 * announced to assistive tech; the rest are polite status text.
 */
function ChatSystemLine({ className, kind, children, ...props }: ChatSystemLineProps) {
  return (
    <div
      data-slot="chat-system-line"
      data-kind={kind}
      role={kind === "error" ? "alert" : "status"}
      className={cn(
        "max-w-[74ch] whitespace-pre-wrap text-xs leading-relaxed",
        kind === "error" ? "text-danger" : "text-fg-muted",
        kind === "output" && "font-mono",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export { ChatSystemLine }
