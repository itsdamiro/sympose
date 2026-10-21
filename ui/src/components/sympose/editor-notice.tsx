import * as React from "react"

import { cn } from "@/lib/utils"
import { toolbarButtonClass } from "@/components/sympose/panel-collapse-button"

/** A notice's button: the same small text button wherever a notice has one. */
export const noticeActionClass = cn(toolbarButtonClass, "size-auto h-6 px-2 text-xs text-foreground")

/**
 * The one block every editor notice is drawn as: a title, a line under it, the actions on the right, and optionally
 * more under them. It is the properties card's sibling (same fill, corners and content gutter, which the panel sets in
 * `--gutter`), so a draft's banner, a persona file's strip, the persona's suggested changes and the ones that no longer
 * fit all read as one kind of thing above the text.
 */
export function EditorNotice({
  title,
  mono,
  children,
  actions,
  below,
  role,
  compact,
}: {
  title: React.ReactNode
  /** The title is a file's name, set in the monospace face. */
  mono?: boolean
  /** The line under the title. */
  children?: React.ReactNode
  actions?: React.ReactNode
  /** More, under the whole row (a list the notice is about). */
  below?: React.ReactNode
  role?: "status"
  /** Folded to one short line: the title and the actions, none of the room around them. */
  compact?: boolean
}) {
  return (
    <div role={role} className={cn("sy-frontmatter-panel rounded-lg px-(--gutter,1rem) text-xs text-fg-muted", compact ? "py-1.5" : "py-4")}>
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className={cn("truncate text-foreground", mono ? "font-mono" : "font-medium")}>{title}</span>
          {children ? <span>{children}</span> : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
      </div>
      {below}
    </div>
  )
}
