import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import type { IconSvgElement } from "@hugeicons/react"

import { DropdownMenu, DropdownMenuContent } from "@/components/ui/dropdown-menu"
import { RowActionsTrigger } from "@/components/sympose/row-actions"
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
      <span className="text-xs font-medium tracking-wide text-fg-muted uppercase">{label}</span>

      {menuItems && (
        <DropdownMenu modal={false}>
          <RowActionsTrigger aria-label={`${label} group actions`} onClick={(e) => e.stopPropagation()} />
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
        className="flex items-center gap-1.5 pt-4 pb-1.5 first:pt-0"
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
        className="group/row relative flex items-center gap-1.5 pt-4 pr-8 pb-1.5 first:pt-0"
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
