import { HugeiconsIcon } from "@hugeicons/react"
import { Comment01Icon, File02Icon } from "@hugeicons/core-free-icons"

import { GroupCaption } from "@/components/sympose/group-caption"
import { VaultTreeRow, type VaultNode } from "@/components/sympose/vault-tree"
import type { Draft } from "@/lib/persona-changes-api"

const NO_EXPANDED = new Set<string>()
const noop = () => {}
const BARE = { persona: undefined } as const

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`

/** What a row ends with: "new" for a note that does not exist yet, else the changes waiting (a number) and the open
 *  comments (a number after a small comment icon), each only when there are any. */
function trailing(draft: Draft) {
  return (
    <span className="ms-auto flex shrink-0 items-center gap-2 ps-2 text-xs text-fg-muted">
      {draft.is_new ? (
        "new"
      ) : (
        <>
          {draft.count > 0 && <span aria-label={`${plural(draft.count, "change")} waiting`}>{draft.count}</span>}
          {draft.comments > 0 && (
            <span className="flex items-center gap-1" aria-label={`${plural(draft.comments, "open comment")}`}>
              <HugeiconsIcon icon={Comment01Icon} className="size-3.5" aria-hidden />
              {draft.comments}
            </span>
          )}
        </>
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
