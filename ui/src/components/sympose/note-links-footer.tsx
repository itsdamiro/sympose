import { cn } from "@/lib/utils"

/** The note's outbound `[[wikilinks]]`, as pills under the document. */
export function NoteLinksFooter({
  links,
  phone,
  onWikiLinkClick,
}: {
  links: string[]
  phone: boolean
  onWikiLinkClick?: (target: string) => void
}) {
  return (
    <div
      className={cn(
        // Same established gutter as the frontmatter card above and
        // every other panel (`<ChatPanel>`, `<ContentPanel>`).
        // `sy-note-footer`: matched by `slideExitClassName`/
        // `slideEnterClassName`'s `scopeToCmScroller` branch (see
        // `useSlideSwap`) so a note switch slides this bar the same
        // horizontal direction as the canvas instead of leaving it
        // frozen mid-transition. The plain fade-in below is only for
        // a mount with no switch in play (first link typed into an
        // already-open note) — a re-render with the same links
        // doesn't remount it, so it won't replay on every keystroke.
        "flex shrink-0 flex-wrap items-center gap-2 border-t border-border py-3",
        "sy-note-footer animate-in fade-in-0 duration-thumb",
        phone ? "px-4" : "px-6 sm:px-8"
      )}
    >
      <span className="font-mono text-xs text-fg-muted uppercase">
        Links
      </span>
      {links.map((target) => (
        <button
          key={target}
          type="button"
          onClick={() => onWikiLinkClick?.(target)}
          // Keyed on `target`, so only a genuinely new pill mounts
          // (and animates in) — existing ones just re-render.
          className="animate-in fade-in-0 zoom-in-95 rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors duration-thumb hover:text-foreground"
        >
          {target}
        </button>
      ))}
    </div>
  )
}
