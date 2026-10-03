import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { BubbleChatIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * The stage's top-right chat toggle, parked as a sibling of the panels beside `<NebulaModeToggle>`, so it stays
 * reachable whether or not the chat panel is open. Its chip look (`bg-secondary` pill around `size-7` icon buttons) is
 * the one recipe for a small cluster of stage controls: more buttons can join it, and it is kept for other uses. The
 * button's label is "Chat", matching `<TopBar>`'s identical phone entry point, and its icon a plain chat bubble: the
 * bubble with a plus is the composer's "New conversation", and this only shows or hides the panel.
 */
interface ChatActionGroupProps extends React.ComponentProps<"div"> {
  chatOpen?: boolean
  onToggleChat?: () => void
}

function ChatActionGroup({
  className,
  chatOpen = false,
  onToggleChat,
  ...props
}: ChatActionGroupProps) {
  return (
    <div
      data-slot="chat-action-group"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md bg-secondary p-0.5",
        className
      )}
      {...props}
    >
      <button
        type="button"
        aria-label="Chat"
        aria-pressed={chatOpen}
        onClick={onToggleChat}
        className="grid size-7 place-items-center rounded-sm text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none aria-pressed:bg-background aria-pressed:text-foreground"
      >
        <HugeiconsIcon icon={BubbleChatIcon} className="size-4" />
      </button>
    </div>
  )
}

export { ChatActionGroup }
