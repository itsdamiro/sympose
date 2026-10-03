import { HugeiconsIcon } from "@hugeicons/react"
import { SidebarLeft01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * The button that collapses a stage panel (the content panel, the editor): the first icon of that panel's toolbar,
 * at its far left. It takes the toolbar buttons' own size, tone and hover, and the main menu's Collapse icon, so every
 * panel's collapse reads as one control and a theme change reaches them together.
 */
export function PanelCollapseButton({
  label,
  onClick,
  className,
}: {
  label: string
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
        className
      )}
    >
      <HugeiconsIcon icon={SidebarLeft01Icon} className="size-4" />
    </button>
  )
}
