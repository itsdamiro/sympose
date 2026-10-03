import { HugeiconsIcon } from "@hugeicons/react"
import { CloudIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { SentRecord } from "@/lib/chat-types"
import { cloudWords } from "@/lib/grounded"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

/**
 * A cloud model's reply, marked in its header beside the avatar, where the model's name used to be (docs/decisions/060):
 * a small cloud icon, with an amber mark when something was held back, so that case shows without opening it. On
 * hover or keyboard focus, and on a tap on a touch screen, it opens which model answered and what was sent to it and
 * held back from it (ADR 031), in plain words. Drawn only for a reply whose record names cloud data.
 */
export function CloudSentIcon({ sent, model, className }: { sent: SentRecord; model?: string; className?: string }) {
  const sentWords = cloudWords(sent.cloud)
  const heldWords = cloudWords(sent.withheld)
  const held = heldWords.length > 0
  return (
    <Popover>
      <PopoverTrigger
        openOnHover
        delay={150}
        aria-label="What was sent to the cloud model"
        data-held={held || undefined}
        className={cn(
          "relative grid size-6 shrink-0 place-items-center rounded text-fg-muted outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50",
          className
        )}
      >
        <HugeiconsIcon icon={CloudIcon} aria-hidden className="size-3.5" />
        {held && <span aria-hidden className="absolute top-0.5 right-0.5 size-1.5 rounded-full bg-amber-500" />}
      </PopoverTrigger>
      <PopoverContent side="bottom" align="start" className="space-y-1">
        {model && <p>Answered by {model}</p>}
        {sentWords.length > 0 && <p>Sent to the cloud model: {sentWords.join(", ")}</p>}
        {held && <p>Held back: {heldWords.join(", ")}</p>}
      </PopoverContent>
    </Popover>
  )
}
