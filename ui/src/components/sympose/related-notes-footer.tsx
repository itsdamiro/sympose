import { Link04Icon } from "@hugeicons/core-free-icons"

import type { RelatedNote } from "@/lib/vault-related-api"
import { GroupCaption } from "@/components/sympose/group-caption"
import { CollapsibleFooterSection } from "@/components/sympose/collapsible-footer-section"
import { RelevanceMeter } from "@/components/sympose/relevance-meter"
import { VaultTreeRow, type RowActions, type VaultNode } from "@/components/sympose/vault-tree"

const NO_EXPANDED = new Set<string>()
const noop = () => {}

const asNode = (note: RelatedNote): VaultNode => ({
  type: "note",
  name: note.rel_path.split("/").pop() ?? note.rel_path,
  path: note.rel_path,
})

/**
 * The notes close in meaning to the open note, as a section of the notes panel's pinned footer (docs/decisions/066):
 * one row per note, drawn with `VaultTreeRow` like the recent notes (so it opens, renames and moves like any note),
 * each with a relevance meter at its end. Notes the user hid from view are not drawn. It shows nothing at all when
 * there is nothing to show, so a note with no neighbour does not leave an empty section; folding is
 * `CollapsibleFooterSection`'s.
 */
export function RelatedNotesFooter({
  related,
  actions,
  selectedPath,
  onSelect,
  hideExtension,
}: {
  related: RelatedNote[]
  actions: RowActions
  selectedPath?: string
  onSelect?: (node: VaultNode) => void
  hideExtension: boolean
}) {
  const shown = related.filter((note) => !note.hidden)
  if (shown.length === 0) return null
  return (
    <CollapsibleFooterSection
      id="related"
      label="related notes"
      caption={<GroupCaption icon={Link04Icon} label="Related" paddingLeft={0} />}
    >
      <div role="tree" className="text-sm">
        {shown.map((note) => (
          <VaultTreeRow
            key={`related:${note.rel_path}`}
            node={asNode(note)}
            closing={false}
            onExitComplete={noop}
            depth={0}
            expanded={NO_EXPANDED}
            onToggle={noop}
            selectedPath={selectedPath}
            onSelect={onSelect}
            actions={actions}
            hideExtension={hideExtension}
            trailing={<RelevanceMeter percent={note.percent} />}
          />
        ))}
      </div>
    </CollapsibleFooterSection>
  )
}
