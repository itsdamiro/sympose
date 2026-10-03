import { cn } from "@/lib/utils"
import type { SentRecord } from "@/lib/chat-types"
import { cloudWords, hasCloudSent } from "@/lib/grounded"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ModelChip } from "@/components/sympose/model-chip"

interface ReplyModelChipProps {
  /** The model that made this reply. */
  model: string
  sent?: SentRecord | null
  /** The web display knob for the cloud mark (`showCloudSent`); off leaves the plain chip. */
  showCloudSent?: boolean
}

/**
 * The model chip in a persona reply's header. On a cloud model's reply that sent or held back vault data it also
 * carries the privacy summary (docs/decisions/060): an amber mark when something was held back, so that case shows
 * without opening it, and on hover, keyboard focus or a tap a popup of what was sent to the model and what was held
 * back (ADR 031), in plain words.
 */
export function ReplyModelChip({ model, sent, showCloudSent = true }: ReplyModelChipProps) {
  if (!showCloudSent || !sent || !hasCloudSent(sent)) return <ModelChip model={model} />
  const sentWords = cloudWords(sent.cloud)
  const heldWords = cloudWords(sent.withheld)
  const held = heldWords.length > 0
  return (
    <Popover>
      <PopoverTrigger
        openOnHover
        role="button"
        delay={150}
        aria-label={`${model}: what was sent to the cloud model`}
        data-held={held || undefined}
        render={<ModelChip model={model} />}
        className={cn(
          "relative cursor-default outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
        )}
      >
        {held && <span aria-hidden className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-amber-500" />}
      </PopoverTrigger>
      <PopoverContent side="bottom" align="start" className="space-y-1">
        {sentWords.length > 0 && <p>Sent to the cloud model: {sentWords.join(", ")}</p>}
        {held && <p>Held back: {heldWords.join(", ")}</p>}
      </PopoverContent>
    </Popover>
  )
}
