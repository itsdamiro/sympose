import * as React from "react"
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"

import { cn } from "@/lib/utils"

/**
 * The text of one row in a list of things the user can open: a small icon, a title that wraps to two lines in the
 * entity colour (brighter on hover of the row's `group/result`), and a muted detail line indented under the title.
 * The search results, the persona's conversations and the Bin all draw their rows from this, so the lists read as
 * one family and cannot drift apart. `trailing` follows the title on its line (a status such as "replying…").
 */
export function ResultText({
  icon,
  iconLabel,
  title,
  detail,
  trailing,
  emphasized = false,
}: {
  icon: IconSvgElement
  /** Names the icon for a reader when it carries meaning (a pin), instead of being hidden as decoration. */
  iconLabel?: string
  title: React.ReactNode
  detail?: React.ReactNode
  trailing?: React.ReactNode
  /** The row the user is in (the conversation on screen): marked by the weight of its title, not a box. */
  emphasized?: boolean
}) {
  return (
    <span data-slot="result-text" className="flex w-full min-w-0 flex-col items-start gap-0.5">
      <span
        className={cn(
          "flex w-full items-start gap-1.5 text-sm text-entity/85 transition-colors group-hover/result:text-entity",
          emphasized && "font-medium text-entity"
        )}
      >
        <HugeiconsIcon
          icon={icon}
          aria-label={iconLabel}
          aria-hidden={iconLabel ? undefined : true}
          className="mt-0.5 size-3.5 shrink-0 text-fg-muted"
        />
        <span className="line-clamp-2 min-w-0 flex-1">{title}</span>
        {trailing}
      </span>
      {detail && <span className="flex w-full min-w-0 items-center gap-1 pl-5 text-xs text-fg-muted">{detail}</span>}
    </span>
  )
}
