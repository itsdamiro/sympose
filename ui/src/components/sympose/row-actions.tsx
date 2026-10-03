import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { MoreHorizontalIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

/**
 * The look of the control a row shows on hover: a small button that is hidden until its row (`group/row`) is hovered
 * or the control is focused, then eases in as a tinted button. The vault tree's rows, a conversation's row, a group
 * caption and the Bin's restore and delete buttons all take it from here, so the pointer reacts the same in every
 * list and a theme change reaches them together (docs/decisions/060).
 */
export const rowActionClass =
  "grid size-6 shrink-0 scale-75 place-items-center rounded text-fg-muted opacity-0 transition-[opacity,transform] duration-thumb ease-snappy hover:bg-accent hover:text-foreground group-hover/row:scale-100 group-hover/row:opacity-100 focus-visible:scale-100 focus-visible:opacity-100 data-popup-open:scale-100 data-popup-open:opacity-100"

/** The `⋯` button that opens a row's menu, pinned to the row's right edge. */
export function RowActionsTrigger({ className, ...props }: React.ComponentProps<typeof DropdownMenuTrigger>) {
  return (
    <DropdownMenuTrigger className={cn("absolute top-1/2 right-1 -translate-y-1/2", rowActionClass, className)} {...props}>
      <HugeiconsIcon icon={MoreHorizontalIcon} className="size-3.5" />
    </DropdownMenuTrigger>
  )
}
