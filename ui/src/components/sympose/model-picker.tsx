import { HugeiconsIcon } from "@hugeicons/react"
import { CloudIcon, ComputerIcon, Tick02Icon } from "@hugeicons/core-free-icons"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import type { ModelsState } from "@/lib/models-api"

/**
 * The model chip in the composer footer, as a picker (docs/decisions/044): the persona's model now, and the
 * models on offer. A pick is saved on the persona, from here or from the terminal's `/model`, so it is kept.
 * "Use the default" appears only while the persona has a model of its own to clear. Local models get the same
 * quiet on-device mark as `ModelChip`, cloud ones a cloud glyph.
 */
function ModelPicker({
  state,
  onChoose,
  className,
}: {
  state: ModelsState | null
  onChoose: (model: string | null) => void
  className?: string
}) {
  if (!state) return null
  const listed = state.models.find((m) => m.id === state.current)
  const short = listed?.short ?? state.current.split("/").pop() ?? state.current
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Model: ${short}. Change`}
        data-slot="model-picker"
        data-tier={state.currentCloud ? "cloud" : "local"}
        className={cn(
          "inline-flex h-5 w-fit shrink-0 items-center gap-1 rounded-md bg-chip px-1.5 font-mono text-[11px] whitespace-nowrap transition-colors hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none [&>svg]:size-3",
          state.currentCloud ? "text-fg-muted" : "text-ok",
          className
        )}
        title={state.currentCloud ? "Cloud model — change" : "On-device — private. Change"}
      >
        <HugeiconsIcon icon={state.currentCloud ? CloudIcon : ComputerIcon} />
        {short}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="top" className="w-auto min-w-64">
        {state.models.map((m) => (
          <DropdownMenuItem key={m.id} onClick={() => m.id !== state.current && onChoose(m.id)}>
            <HugeiconsIcon icon={m.cloud ? CloudIcon : ComputerIcon} className="text-fg-muted" />
            <span className="min-w-0 flex-1 truncate">{m.label}</span>
            {m.id === state.current && <HugeiconsIcon icon={Tick02Icon} className="shrink-0" />}
          </DropdownMenuItem>
        ))}
        {state.own !== null && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => onChoose(null)}>
              <span className="min-w-0 flex-1 truncate">Use the default ({state.fallback})</span>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export { ModelPicker }
