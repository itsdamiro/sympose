import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { getCookieBool, setCookieBool } from "@/lib/cookies"

/**
 * One section of the notes panel's pinned footer (docs/decisions/060): a caption row with a fold button, and a body
 * that is as tall as its content (so a knob that sets how many rows it has sets its height), flexing: only when the
 * panel has no more room for it does the body scroll inside, the notes above keeping a small floor. The footer is meant to hold
 * several such sections, so each remembers whether it is open under its own cookie, `sympose:footer.<id>.open` (open by
 * default); folded, only the caption row stays, with the way back. `caption` is whatever heads the section (a
 * `GroupCaption`, with its own menu if it has one).
 */
export function CollapsibleFooterSection({
  id,
  label,
  caption,
  children,
  className,
}: {
  /** Names the section's cookie, so it must be stable and unique among the footer's sections. */
  id: string
  /** What the section is, for a screen reader and the fold button ("recent notes"). */
  label: string
  caption: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  const cookie = `sympose:footer.${id}.open`
  const [open, setOpen] = React.useState(() => getCookieBool(cookie, true))
  const toggle = () => {
    setCookieBool(cookie, !open)
    setOpen(!open)
  }
  return (
    <section data-slot="footer-section" data-section={id} aria-label={label} className={cn("flex min-h-0 flex-col", className)}>
      <div className="flex items-center justify-between">
        <div className="min-w-0 flex-1">{caption}</div>
        <button
          type="button"
          aria-expanded={open}
          aria-label={`${open ? "Fold" : "Show"} ${label}`}
          onClick={toggle}
          className="rounded-md p-1 text-fg-muted transition-colors hover:text-foreground"
        >
          <HugeiconsIcon icon={ArrowDown01Icon} className={cn("size-4 transition-transform", open && "rotate-180")} />
        </button>
      </div>
      {open && <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>}
    </section>
  )
}
