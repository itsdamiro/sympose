import * as React from "react"
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"

/**
 * The one empty placeholder (docs/decisions/060): an icon in a circle, a title, an optional line under it and an
 * optional action (a "Try again"). Every list or panel with nothing to show, and every one that could not load,
 * draws it, so they look and read the same: the Bin's lists, the vault folder, the conversation list, the empty
 * chat, a search with no matches. `accent` colours the tile for a persona's own icon (her accent, as her avatar);
 * `compact` is the smaller padding for a list that sits inside another panel.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  accent,
  compact = false,
  className,
}: {
  icon: IconSvgElement
  title: React.ReactNode
  description?: React.ReactNode
  action?: React.ReactNode
  accent?: string
  compact?: boolean
  className?: string
}) {
  return (
    <Empty className={cn("border-0", compact ? "p-4" : "p-8", className)}>
      <EmptyHeader>
        <EmptyMedia variant="icon" className={cn("rounded-full", accent && "text-background")} style={accent ? { background: accent } : undefined}>
          <HugeiconsIcon icon={icon} />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        {description && <EmptyDescription>{description}</EmptyDescription>}
      </EmptyHeader>
      {action}
    </Empty>
  )
}

/** The action under a failed load: the same small button wherever a list asks to be read again. */
export function EmptyAction({ children, ...props }: React.ComponentProps<"button">) {
  return (
    <button
      type="button"
      className="rounded-md px-2 py-1 text-xs text-fg-muted transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      {...props}
    >
      {children}
    </button>
  )
}
