import * as React from "react"
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

/**
 * A persona's header, as the Persona panel draws it: a band in her accent colour with her avatar straddling its bottom
 * edge, and her name and title beside it. The panel (`PersonaCard`) and the card a persona's request for a new persona
 * makes in the chat (docs/decisions/078) both draw this one. `bandClass` sets the band's height and, in the panel, how
 * far it bleeds to the panel's edges; `className` is for the name row.
 */
function PersonaHeader({
  name,
  title,
  icon,
  accent,
  accentDark,
  bandClass,
  className,
}: {
  name: string
  title: string
  icon: IconSvgElement
  accent: string
  accentDark: string
  bandClass?: string
  className?: string
}) {
  return (
    <div
      className="flex flex-col gap-4"
      style={{ "--persona-accent": accent, "--persona-accent-dark": accentDark } as React.CSSProperties}
    >
      {/* accent band: in the panel it bleeds to the panel's edges by cancelling the panel's own gutter (`p-8` desktop /
          `px-4 py-6` phone); the panel's rounded top corners + overflow clip it */}
      <div
        className={cn("h-28 rounded-tl-lg rounded-tr-lg bg-(--persona-accent) dark:bg-(--persona-accent-dark)", bandClass)}
        aria-hidden
      />

      {/* identity: the 64px avatar straddles the band's bottom edge (centre on the edge, half in / half below).
          `border-4` (border-box) keeps its visual bounds equal to its box. The name/title column is nudged down
          (`pt-2`) so the name settles inside the band and the title clears the band edge by the same gap that sits
          between name and title. */}
      <div className={cn("-mt-12 flex items-start gap-3", className)}>
        <Avatar className="size-16 shrink-0 border-4 border-panel">
          <AvatarFallback className="text-background" style={{ background: accent }}>
            <HugeiconsIcon icon={icon} className="size-7" />
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 pt-1.5">
          <h2 className="truncate font-heading text-lg leading-tight font-semibold text-background">{name}</h2>
          <p className="mt-3 text-sm leading-snug text-balance text-fg-muted">{title}</p>
        </div>
      </div>
    </div>
  )
}

export { PersonaHeader }
