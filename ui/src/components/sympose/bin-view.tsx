import * as React from "react"

import { cn } from "@/lib/utils"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import { TrashList } from "@/components/sympose/trash-list"
import { ConversationBin } from "@/components/sympose/conversation-bin"

type Section = "notes" | "conversations"

/**
 * The Bin: what was deleted, in one place, with notes and conversations apart (ADR 045, 057). A switch chooses
 * which of the two is listed; each owns its own list, its restore and its delete for good.
 */
function BinView({
  persona,
  refreshKey,
  conversationsKey,
  onNoteRestored,
  onConversationRestored,
  className,
}: {
  persona: string
  /** The vault changed (a note was deleted from the editor): the notes are read again. */
  refreshKey: number
  /** A conversation was deleted from the list: the deleted conversations are read again. */
  conversationsKey: number
  onNoteRestored: (originalPath: string) => void
  onConversationRestored: () => void
  className?: string
}) {
  const [section, setSection] = React.useState<Section>("notes")
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <SegmentedControl
        aria-label="What the bin lists"
        size="sm"
        value={section}
        onValueChange={setSection}
        options={[
          { value: "notes", label: "Notes" },
          { value: "conversations", label: "Conversations" },
        ]}
      />
      {section === "notes" ? (
        <TrashList persona={persona} refreshKey={refreshKey} onRestored={onNoteRestored} />
      ) : (
        <ConversationBin persona={persona} refreshKey={conversationsKey} onRestored={onConversationRestored} />
      )}
    </div>
  )
}

export { BinView }
