import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { resolvePersonaVisuals, type LivePersona } from "@/lib/personas"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { SlackDot } from "@/components/sympose/slack-dot"

/**
 * The footer pinned under the Persona panel, as the Settings footer is: one icon per persona on the far left, each the
 * size of the persona icon in the main menu, and on the far right the Slack dot while the active persona is connected
 * to Slack (docs/decisions/093). The icons are the switch ("Switch persona" is the group's name for a screen reader).
 * Hovering or focusing an icon shows the persona's name and short description in the app's floating-info surface
 * (docs/decisions/060). The active persona is marked and is not a switch target.
 */
function PersonaSwitcher({
  personas,
  active,
  onSwitch,
  slack = false,
  className,
}: {
  personas: LivePersona[]
  active: string
  onSwitch: (handle: string) => void
  /** The active persona is connected to Slack now: the dot at the far right. */
  slack?: boolean
  className?: string
}) {
  return (
    <div data-slot="persona-switcher" className={cn("flex w-full items-center justify-between gap-2", className)}>
      <div role="group" aria-label="Switch persona" className="flex flex-wrap items-center gap-2">
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
      {slack && <SlackDot />}
    </div>
  )
}

export { PersonaSwitcher }
