import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { PersonaFileInfo } from "@/lib/persona-files-api"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { chipClass } from "@/components/sympose/model-chip"

const PENDING = "A rewrite is waiting for review"

/**
 * The persona's own files in one chip and one list (docs/decisions/061): Soul, Profile, Context and Decisions, each
 * with a line on what it is, opening in the editor when chosen. The chip is the model chip's size and look, in
 * capitals, and carries an amber mark when a rewrite of the profile or the context is waiting for review, so that
 * shows without opening the list; the entry itself carries the same mark. Not offered until the files are known.
 */
export function PersonaFilesMenu({
  files,
  onOpen,
  className,
}: {
  files: PersonaFileInfo[]
  onOpen: (name: string) => void
  className?: string
}) {
  const waiting = files.some((f) => f.pending)
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger
        aria-label="Persona files"
        disabled={files.length === 0}
        className={cn(
          chipClass,
          "relative cursor-default text-fg-muted uppercase tracking-wide transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-60 data-popup-open:text-foreground",
          className
        )}
      >
        Files
        <HugeiconsIcon icon={ArrowDown01Icon} aria-hidden className="size-3" />
        {waiting && (
          <span data-slot="persona-files-pending" aria-hidden className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-amber-500" />
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
        {files.map((f) => (
          <DropdownMenuItem key={f.name} onClick={() => onOpen(f.name)} className="items-start">
            <span className="flex min-w-0 flex-col">
              <span className="text-foreground">{f.label}</span>
              <span className="text-xs text-fg-muted">{f.description}</span>
            </span>
            {f.pending && <span role="img" aria-label={PENDING} title={PENDING} className="mt-1.5 ml-auto size-1.5 shrink-0 rounded-full bg-amber-500" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
