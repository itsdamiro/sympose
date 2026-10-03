import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { resolvePersonaVisuals, type LivePersona } from "@/lib/personas"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { ControlRow } from "@/components/sympose/control-section"

/**
 * "Switch persona" as a settings-style row, pinned under the Persona panel as the Settings footer is: the label on
 * the left and one icon per persona on the right, each the size of the persona icon in the main menu. Hovering or
 * focusing an icon shows the persona's name and short description in the app's floating-info surface
 * (docs/decisions/060). The active persona is marked and is not a switch target.
 */
function PersonaSwitcher({
  personas,
  active,
  onSwitch,
  className,
}: {
  personas: LivePersona[]
  active: string
  onSwitch: (handle: string) => void
  className?: string
}) {
  return (
    <ControlRow label="Switch persona" className={cn("w-full", className)}>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {personas.map((p) => {
          const visuals = resolvePersonaVisuals(p.handle)
          const isActive = p.handle === active
          return (
            <Tooltip key={p.handle}>
              <TooltipTrigger
                render={
                  <button
                    type="button"
                    aria-label={p.name}
                    aria-pressed={isActive}
                    onClick={() => !isActive && onSwitch(p.handle)}
                    className={cn(
                      "rounded-full outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                      isActive ? "ring-2 ring-foreground/30 ring-offset-2 ring-offset-panel" : "transition-transform hover:scale-105"
                    )}
                  />
                }
              >
                <Avatar size="sm">
                  <AvatarFallback className="text-background" style={{ background: visuals.accent }}>
                    <HugeiconsIcon icon={visuals.icon} className="size-3.5" />
                  </AvatarFallback>
                </Avatar>
              </TooltipTrigger>
              <TooltipContent side="top" align="end" className="flex-col items-start gap-0.5">
                <span className="font-medium text-foreground">{p.name}</span>
                {p.title && <span>{p.title}</span>}
              </TooltipContent>
            </Tooltip>
          )
        })}
      </div>
    </ControlRow>
  )
}

export { PersonaSwitcher }
