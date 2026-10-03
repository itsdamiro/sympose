import { RecentSectionCaption, VaultTreeRow, type RowActions, type VaultNode } from "@/components/sympose/vault-tree"
import { CollapsibleFooterSection } from "@/components/sympose/collapsible-footer-section"

const NO_EXPANDED = new Set<string>()
const noop = () => {}

/**
 * The recently opened notes, as a section of the notes panel's pinned footer (docs/decisions/060): below the scroll
 * surface, so always in reach and never between the folder's title and its notes. Its height follows the "Recent notes
 * shown" knob; folding and the height cap are `CollapsibleFooterSection`'s.
 */
export function RecentNotesFooter({
  nodes,
  actions,
  selectedPath,
  onSelect,
  hideExtension,
  onRemoveFromRecents,
  onClearRecents,
}: {
  nodes: VaultNode[]
  actions: RowActions
  selectedPath?: string
  onSelect?: (node: VaultNode) => void
  hideExtension: boolean
  onRemoveFromRecents?: (path: string) => void
  onClearRecents?: () => void
}) {
  return (
    <CollapsibleFooterSection
      id="recent"
      label="recent notes"
      caption={<RecentSectionCaption paddingLeft={0} onClearRecents={onClearRecents} />}
    >
      <div role="tree" className="text-sm">
        {nodes.map((node) => (
          <VaultTreeRow
            key={`recent:${node.path}`}
            node={node}
            closing={false}
            onExitComplete={noop}
            depth={0}
            expanded={NO_EXPANDED}
            onToggle={noop}
            selectedPath={selectedPath}
            onSelect={onSelect}
            actions={actions}
            hideExtension={hideExtension}
            onRemoveFromRecents={onRemoveFromRecents ? () => onRemoveFromRecents(node.path) : undefined}
          />
        ))}
      </div>
    </CollapsibleFooterSection>
  )
}
