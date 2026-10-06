import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { EditModeId, EditModeInfo } from "@/lib/edit-mode-api"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { chipClass } from "@/components/sympose/model-chip"

const LABELS: Record<EditModeId, string> = { plan: "Plan", manual: "Manual", accept: "Accept edits", auto: "Auto" }

/**
 * What the persona does on the user's notes before the user's Accept (docs/decisions/072), as a chip beside FILES: it
 * reads the current mode, with "(default)" when she follows the Settings page's mode instead of having her own, and
 * opens the four modes with a line each. Choosing one saves it for her; "Use the default" clears her own. The note
 * about the model she uses, for Accept edits and Auto, is shown by the caller when one is chosen. Not offered until
 * the mode is known.
 */
export function PersonaEditMenu({
  info,
  onChoose,
  className,
}: {
  info: EditModeInfo | null
  onChoose: (mode: EditModeId | null) => void
  className?: string
}) {
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger
        aria-label="What this persona may do to your notes"
        disabled={!info}
        className={cn(
          chipClass,
          "cursor-default text-fg-muted uppercase tracking-wide transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-60 data-popup-open:text-foreground",
          className
        )}
      >
        {info ? `${LABELS[info.mode]}${info.source === "global" ? " (default)" : ""}` : "Edits"}
        <HugeiconsIcon icon={ArrowDown01Icon} aria-hidden className="size-3" />
      </DropdownMenuTrigger>
      {info && (
        <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
          <DropdownMenuRadioGroup value={info.mode} onValueChange={(value) => onChoose(value as EditModeId)}>
            {info.modes.map((m) => (
              <DropdownMenuRadioItem key={m.id} value={m.id} className="items-start">
                <span className="flex min-w-0 flex-col pr-2">
                  <span className="text-foreground">{LABELS[m.id]}</span>
                  <span className="max-w-64 text-xs text-fg-muted">{m.summary}</span>
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
          {info.source === "persona" && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onChoose(null)}>Use the default</DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      )}
    </DropdownMenu>
  )
}
