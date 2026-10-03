import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"
import { File01Icon, Message01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { BinPreferences } from "@/lib/use-bin-section-preference"
import { TrashList } from "@/components/sympose/trash-list"
import { ConversationBin } from "@/components/sympose/conversation-bin"

type Section = BinPreferences["section"]

const SECTIONS: { value: Section; label: string; icon: IconSvgElement }[] = [
  { value: "notes", label: "Notes", icon: File01Icon },
  { value: "conversations", label: "Conversations", icon: Message01Icon },
]

/**
 * The two pills that choose which half of the Bin is listed, drawn inline with the page's title at its right
 * edge (docs/decisions/060). The choice is kept by the caller, in a cookie.
 */
function BinSectionPills({ section, onChange, className }: { section: Section; onChange: (next: Section) => void; className?: string }) {
  return (
    <div role="group" aria-label="What the bin lists" className={cn("flex shrink-0 items-center gap-1", className)}>
      {SECTIONS.map((s) => (
        <button
          key={s.value}
          type="button"
          aria-pressed={section === s.value}
          onClick={() => onChange(s.value)}
          className={cn(
            "inline-flex h-6 items-center gap-1 rounded-full border px-2.5 text-xs transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
            section === s.value
              ? "border-border bg-accent text-foreground"
              : "border-transparent text-fg-muted hover:bg-accent/60 hover:text-foreground"
          )}
        >
          <HugeiconsIcon icon={s.icon} aria-hidden className="size-3" />
          {s.label}
        </button>
      ))}
    </div>
  )
}

/**
 * The Bin: what was deleted, in one place, with notes and conversations apart (ADR 045, 057). `section` chooses
 * which of the two is listed (the pills are `BinSectionPills`, in the page's title row); each owns its own list,
 * its restore and its delete for good.
 */
function BinView({
  persona,
  section,
  refreshKey,
  conversationsKey,
  onNoteRestored,
  onConversationRestored,
  className,
}: {
  persona: string
  section: Section
  /** The vault changed (a note was deleted from the editor): the notes are read again. */
  refreshKey: number
  /** A conversation was deleted from the list: the deleted conversations are read again. */
  conversationsKey: number
  onNoteRestored: (originalPath: string) => void
  onConversationRestored: () => void
  className?: string
}) {
  return (
    <div className={className}>
      {section === "notes" ? (
        <TrashList persona={persona} refreshKey={refreshKey} onRestored={onNoteRestored} />
      ) : (
        <ConversationBin persona={persona} refreshKey={conversationsKey} onRestored={onConversationRestored} />
      )}
    </div>
  )
}

export { BinView, BinSectionPills }
