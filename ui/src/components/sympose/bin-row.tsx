import * as React from "react"
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { ResultText } from "@/components/sympose/result-text"
import { RowActionsTrigger } from "@/components/sympose/row-actions"
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu"

export interface BinAction {
  label: string
  icon: IconSvgElement
  onSelect: () => void
  destructive?: boolean
  disabled?: boolean
}

/**
 * One row of the Bin, whatever it holds (a note, a folder, a conversation): the list's own row text, and its actions
 * (Restore, Delete permanently) in a menu that opens from the row's `⋯` button and from a right click or a long
 * press, as every other list's rows do (docs/decisions/060). The two menus share one list of actions. A row that
 * opens something (a folder's files) takes `onClick`; a row that does not has no hover colour on its title.
 */
export function BinRow({
  icon,
  title,
  detail,
  trailing,
  label,
  actions,
  onClick,
  expanded,
}: {
  icon: IconSvgElement
  title: React.ReactNode
  detail?: React.ReactNode
  trailing?: React.ReactNode
  /** What the row is called, for the `⋯` button's name: "Actions for <label>". */
  label: string
  actions: BinAction[]
  onClick?: () => void
  expanded?: boolean
}) {
  const items = actions.map((a) => (
    <DropdownMenuItem key={a.label} variant={a.destructive ? "destructive" : undefined} disabled={a.disabled} onClick={a.onSelect}>
      <HugeiconsIcon icon={a.icon} />
      {a.label}
    </DropdownMenuItem>
  ))
  const text = <ResultText icon={icon} title={title} detail={detail} trailing={trailing} />
  return (
    <ContextMenu>
      <ContextMenuTrigger className="group/row relative flex items-center">
        {onClick ? (
          <button
            type="button"
            onClick={onClick}
            aria-expanded={expanded}
            className={cn(
              "group/result flex min-w-0 flex-1 rounded-md py-1 pr-8 text-left",
              "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            )}
          >
            {text}
          </button>
        ) : (
          <div className="flex min-w-0 flex-1 py-1 pr-8">{text}</div>
        )}
        <DropdownMenu modal={false}>
          <RowActionsTrigger aria-label={`Actions for ${label}`} />
          <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
            {items}
          </DropdownMenuContent>
        </DropdownMenu>
      </ContextMenuTrigger>
      <ContextMenuContent className="duration-thumb ease-snappy">{items}</ContextMenuContent>
    </ContextMenu>
  )
}
