import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import type { IconSvgElement } from "@hugeicons/react"
import { MoreHorizontalIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu"

/**
 * A group caption ("Pinned", "Recent", …) above a run of same-purpose rows,
 * styled to match `VaultContentSearch`'s "N matches beyond {folder}" row
 * (same icon-plus-label treatment) so every such grouping reads as one
 * visual language. `menuItems`, when given, wires the same two-way access a
 * row's own menu offers (`VaultRowMenu`): a hover-revealed `⋯` button, and
 * right-click / long-press anywhere on the caption. Omit it for a plain,
 * non-interactive caption.
 */
export function GroupCaption({
  icon,
  label,
  paddingLeft,
  menuItems,
}: {
  icon: IconSvgElement
  label: string
  paddingLeft: number
  menuItems?: React.ReactNode
}) {
  const inner = (
    <>
      <HugeiconsIcon icon={icon} className="size-3 text-fg-muted" />
      <span className="text-xs text-fg-muted">{label}</span>

      {menuItems && (
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger
            aria-label={`${label} group actions`}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              "absolute top-1/2 right-1 grid size-6 -translate-y-1/2 place-items-center rounded text-fg-muted",
              "opacity-0 transition-opacity hover:bg-accent hover:text-foreground",
              "group-hover/section-caption:opacity-100 focus-visible:opacity-100 data-popup-open:opacity-100"
            )}
          >
            <HugeiconsIcon icon={MoreHorizontalIcon} className="size-3.5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
            {menuItems}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </>
  )

  if (!menuItems) {
    return (
      <div
        data-slot="group-caption"
        className="flex items-center gap-1.5 pt-2 pb-1"
        style={{ paddingLeft: `${paddingLeft}px` }}
      >
        {inner}
      </div>
    )
  }

  return (
    <ContextMenu>
      <ContextMenuTrigger
        data-slot="group-caption"
        className="group/section-caption relative flex items-center gap-1.5 pt-2 pr-8 pb-1"
        style={{ paddingLeft: `${paddingLeft}px` }}
      >
        {inner}
      </ContextMenuTrigger>
      <ContextMenuContent className="duration-thumb ease-snappy">
        {menuItems}
      </ContextMenuContent>
    </ContextMenu>
  )
}
