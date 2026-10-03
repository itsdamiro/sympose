import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { UserIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { resolvePersonaVisuals, type LivePersona } from "@/lib/personas"
import { EmptyState } from "@/components/sympose/empty-state"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ModelChip } from "@/components/sympose/model-chip"
import { PersonaFilesMenu } from "@/components/sympose/persona-files-menu"
import type { PersonaFileInfo } from "@/lib/persona-files-api"

interface PersonaCardProps {
  /** Live roster from `GET /api/personas`. */
  personas: LivePersona[]
  /** Handle of the active persona. */
  active: string
  /**
   * Phone shell: the containing panel is padded `px-4 py-6` instead of the
   * desktop `p-8`, so the accent band's bleed margins change to match.
   */
  phone?: boolean
  /** The persona's own files (ADR 061), listed in the FILES chip beside the model chip; `onOpenFile` opens one in the
   *  editor. */
  files?: PersonaFileInfo[]
  onOpenFile?: (name: string) => void
  /** Replaces the plain model chip with the model picker, the same one as in the chat's footer, so the model can be
   *  changed here too (ADR 044, 046); the plain chip stays until the backend has said which models there are. */
  modelSlot?: React.ReactNode
  /** The cloud notice (what a cloud model may receive), shown under the model row when the model was picked here. */
  notice?: React.ReactNode
  /** The persona's conversations (ADR 057), shown under the model row. */
  conversations?: React.ReactNode
  className?: string
}

/**
 * The Persona panel — identity of the active persona (the switch to another is `PersonaSwitcher`, pinned under the
 * panel). Soul
 * and Memory open the persona's markdown; both are disabled until their
 * endpoints land (`GET /api/personas/{handle}/soul|memory`). The persona's
 * conversations are listed under the model row (ADR 057). The header band is tinted with the persona's own accent,
 * the same `--persona-accent` custom property `<PersonaPill>` uses, so
 * runtime-created personas that are not in the static roster still get a
 * stable colour.
 */
function PersonaCard({
  personas,
  active,
  phone = false,
  files = [],
  onOpenFile,
  modelSlot,
  notice,
  conversations,
  className,
}: PersonaCardProps) {
  const current = personas.find((p) => p.handle === active) ?? personas[0]

  if (!current) {
    return (
      <EmptyState
        className={className}
        icon={UserIcon}
        title="No personas found"
        description="Check the API at /api/personas."
      />
    )
  }

  const visuals = resolvePersonaVisuals(current.handle)

  return (
    <div
      className={cn("flex w-full flex-col gap-4", className)}
      style={
        {
          "--persona-accent": visuals.accent,
          "--persona-accent-dark": visuals.accentDark,
        } as React.CSSProperties
      }
    >
      {/* accent band — bleeds to the panel edges by cancelling the panel's own
          gutter (`p-8` desktop / `px-4 py-6` phone); the panel's rounded top
          corners + overflow clip it */}
      <div
        className={cn(
          "h-28 rounded-tl-lg rounded-tr-lg bg-(--persona-accent) dark:bg-(--persona-accent-dark)",
          phone ? "-mx-4 -mt-6" : "-mx-8 -mt-8"
        )}
        aria-hidden
      />

      {/* identity — the 64px avatar straddles the band's bottom edge (centre on
          the edge, half in / half below). `border-4` (border-box) keeps its
          visual bounds equal to its box. The name/title column is nudged down
          (`pt-2`) so the name settles inside the band and the title clears the
          band edge by the same gap that sits between name and title. */}
      <div className="-mt-12 flex items-start gap-3">
        <Avatar className="size-16 shrink-0 border-4 border-panel">
          <AvatarFallback
            className="text-background"
            style={{ background: visuals.accent }}
          >
            <HugeiconsIcon icon={visuals.icon} className="size-7" />
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 pt-1.5">
          <h2 className="truncate font-heading text-lg leading-tight font-semibold text-background">
            {current.name}
          </h2>
          <p className="mt-3 text-sm leading-snug text-balance text-fg-muted">
            {current.title}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        {modelSlot ?? <ModelChip model={current.model} />}
        <PersonaFilesMenu files={files} onOpen={(name) => onOpenFile?.(name)} />
      </div>

      {notice}

      {conversations && (
        <>
          <hr className="border-border" />
          {conversations}
        </>
      )}

    </div>
  )
}

export { PersonaCard }
