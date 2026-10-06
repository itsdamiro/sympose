import { CheckListIcon, File02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { GroupCaption } from "@/components/sympose/group-caption"
import { VaultTreeRow, type RowActions, type VaultNode } from "@/components/sympose/vault-tree"
import type { Draft } from "@/lib/persona-changes-api"
import { announceDraftsChanged } from "@/lib/use-drafts"

const NO_EXPANDED = new Set<string>()
const noop = () => {}
const BARE = { persona: undefined } as const

/** What a row ends with: "new" for a note that does not exist yet, else one icon and one number, how many different marks the
 *  note shows (changes and comments together). No words on screen; the label is for a screen reader and a hover. */
function trailing(draft: Draft) {
  return (
    <span className="ms-auto flex shrink-0 items-center gap-2 ps-2 text-xs text-fg-muted">
      {draft.is_new ? (
        "new"
      ) : (
        <span className="flex items-center gap-1" role="img" aria-label={`${draft.items} to review`} title={`${draft.items} to review`}>
          <HugeiconsIcon icon={CheckListIcon} className="size-3.5" aria-hidden />
          {draft.items}
        </span>
      )}
    </span>
  )
}

/** The caption for what is listed: changes waiting, open comments, or both. */
function caption(drafts: Draft[]) {
  const changes = drafts.some((d) => d.count > 0)
  const comments = drafts.some((d) => d.comments > 0)
  return changes && comments ? "Drafts & comments" : comments ? "Comments" : "Drafts"
}

/**
 * The Drafts section at the top of the notes panel (docs/decisions/071): the notes the persona has proposed changes
 * to, the new notes she has proposed, and the notes with an open comment (amended 2026-10-05), above the notes list and Pinned. It is built from the same caption and rows
 * as Pinned. A row for a note that exists has the same menu as any note row (right-click, long-press or the ⋯ button:
 * rename, delete, pin, and so on) when `actions` is given; a new note a persona proposed has none, since it is not a
 * note until it is accepted. A new note is listed under its working name. Nothing is drawn when there are no drafts.
 */
export function DraftsSection({
  drafts,
  selectedPath,
  onOpen,
  hideExtension,
  actions,
}: {
  drafts: Draft[]
  /** The path of the draft open in the editor, if one is. */
  selectedPath?: string
  onOpen: (draft: Draft) => void
  hideExtension: boolean
  /** The vault's note-row actions, for the rows of notes that exist. */
  actions?: RowActions
}) {
  if (drafts.length === 0) return null
  // A rename or delete moves or drops the note's pending changes and comments with it, so the list is read again.
  const noteActions: RowActions = actions
    ? {
        ...actions,
        onRenamed: (from, to) => {
          actions.onRenamed?.(from, to)
          announceDraftsChanged()
        },
        onDeleted: (path) => {
          actions.onDeleted?.(path)
          announceDraftsChanged()
        },
      }
    : BARE
  const byPath = new Map(drafts.map((d) => [d.path, d]))
  return (
    <div data-slot="drafts-section" role="tree" className="flex flex-col pt-1 pb-3 text-sm">
      <GroupCaption icon={File02Icon} label={caption(drafts)} paddingLeft={0} />
      {drafts.map((draft) => {
        const node: VaultNode = { name: draft.is_new && draft.name ? `${draft.name}.md` : (draft.path.split("/").pop() ?? draft.path), path: draft.path, type: "note" }
        return (
          <VaultTreeRow
            key={`draft:${draft.path}`}
            node={node}
            closing={false}
            onExitComplete={noop}
            depth={0}
            expanded={NO_EXPANDED}
            onToggle={noop}
            selectedPath={selectedPath}
            onSelect={(n) => onOpen(byPath.get(n.path)!)}
            actions={draft.is_new ? BARE : noteActions}
            hideExtension={hideExtension}
            showPath={!draft.is_new}
            trailing={trailing(draft)}
          />
        )
      })}
    </div>
  )
}
