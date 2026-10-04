import { File02Icon } from "@hugeicons/core-free-icons"

import { GroupCaption } from "@/components/sympose/group-caption"
import { VaultTreeRow, type VaultNode } from "@/components/sympose/vault-tree"
import type { Draft } from "@/lib/persona-changes-api"

const NO_EXPANDED = new Set<string>()
const noop = () => {}
const BARE = { persona: undefined } as const

/** What a draft's row ends with: "new" for a note that does not exist yet, else how many changes are waiting. */
function trailing(draft: Draft) {
  return <span className="ms-auto shrink-0 ps-2 text-xs text-fg-muted">{draft.is_new ? "new" : draft.count}</span>
}

/**
 * The Drafts section at the top of the notes panel (docs/decisions/071): the notes the persona has proposed changes
 * to, and the new notes she has proposed, above the notes list and Pinned. It is built from the same caption and rows
 * as Pinned, with no row menu (a draft is not a note until it is accepted). A new note is listed under its working
 * name. Nothing is drawn when there are no drafts.
 */
export function DraftsSection({
  drafts,
  selectedPath,
  onOpen,
  hideExtension,
}: {
  drafts: Draft[]
  /** The path of the draft open in the editor, if one is. */
  selectedPath?: string
  onOpen: (draft: Draft) => void
  hideExtension: boolean
}) {
  if (drafts.length === 0) return null
  const byPath = new Map(drafts.map((d) => [d.path, d]))
  return (
    <div data-slot="drafts-section" role="tree" className="flex flex-col pt-1 pb-3 text-sm">
      <GroupCaption icon={File02Icon} label="Drafts" paddingLeft={0} />
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
            actions={BARE}
            hideExtension={hideExtension}
            showPath={!draft.is_new}
            trailing={trailing(draft)}
          />
        )
      })}
    </div>
  )
}
