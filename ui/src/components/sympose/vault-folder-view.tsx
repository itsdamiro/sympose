import * as React from "react"
import { Folder01Icon, Search01Icon } from "@hugeicons/core-free-icons"

import { EmptyState } from "@/components/sympose/empty-state"
import { cn, stripMdExtension } from "@/lib/utils"
import { vaultScopedKey } from "@/lib/cookies"
import { folderIconFor } from "@/lib/vault-folders"
import { useBinPreferences } from "@/lib/use-bin-section-preference"
import { isNoteDrag, readNoteDrag } from "@/lib/vault-drag"
import type { VaultSearchResult } from "@/lib/vault-search-api"
import {
  SearchResultRow,
  BinView,
  BinSectionPills,
  VaultTree,
  collectFolderPaths,
  searchMatchDetail,
  type VaultNode,
} from "@/components/sympose"

/**
 * The content panel for a vault folder or the Bin: the folder's name as a heading
 * (a drop target, to move a note to the root of the folder in view), then either
 * the Bin, or the folder's tree with its pinned and recent notes, and, while
 * searching, the content matches in the folder ("Also found in") and the matches
 * beyond it. Hides nothing itself: what the user hid is already left out of the
 * nodes it is given (docs/decisions/037), apart from search hits, which are
 * listed greyed with Unhide.
 *
 * `dragOverRootHeading` highlights that heading while a note is dragged over it:
 * `<VaultTree>` only ever renders the folder's own subtree, never a row for the
 * folder itself to drop onto.
 */
export function VaultFolderView({
  trashView,
  conversationBinKey,
  onConversationRestored,
  activeLabel,
  activeRootFolder,
  moveNote,
  activePersona,
  vaultPath,
  vaultRefreshKey,
  refreshVault,
  vaultTreeEmpty,
  panelEmpty,
  vaultSearchQuery,
  searchedPanelNodes,
  contentMatches,
  beyondFolderMatches,
  pinnedNodes,
  pinnedShowPath,
  recentNodes,
  vaultTreeActions,
  unhideFromView,
  selectNote,
  openEditor,
}: {
  trashView: boolean
  /** Bumped when a conversation was deleted from the list, so the Bin's conversations are read again (ADR 057). */
  conversationBinKey: number
  /** A conversation was put back from the Bin: the persona's list is read again. */
  onConversationRestored: () => void
  activeLabel: string
  activeRootFolder: VaultNode | undefined
  moveNote: (path: string, destFolder: string) => unknown
  activePersona: string
  vaultPath: string | null
  vaultRefreshKey: number
  refreshVault: () => void
  /** The vault has nothing in scope at all (not just this folder). */
  vaultTreeEmpty: boolean
  panelEmpty: boolean
  vaultSearchQuery: string
  searchedPanelNodes: VaultNode[]
  contentMatches: VaultSearchResult[]
  beyondFolderMatches: VaultSearchResult[]
  pinnedNodes: VaultNode[]
  pinnedShowPath: boolean
  recentNodes: VaultNode[]
  vaultTreeActions: Omit<
    React.ComponentProps<typeof VaultTree>,
    "nodes" | "pinnedNodes" | "pinnedShowPath" | "recentNodes" | "defaultExpanded" | "storageKey"
  >
  unhideFromView: (paths: string | string[]) => unknown
  selectNote: (path: string) => void
  openEditor: () => void
}) {
  const [dragOverRootHeading, setDragOverRootHeading] = React.useState(false)
  const [bin, setBin] = useBinPreferences()
  return (
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
        <h2
          className={cn(
            "-mx-2 min-w-0 truncate rounded-md px-2 font-heading text-2xl font-semibold text-fg-strong transition-colors",
            dragOverRootHeading &&
              "bg-accent/60 ring-1 ring-inset ring-brand/60"
          )}
          onDragOver={
            activeRootFolder
              ? (e) => {
                  if (!isNoteDrag(e)) return
                  e.preventDefault()
                  e.dataTransfer.dropEffect = "move"
                }
              : undefined
          }
          onDragEnter={
            activeRootFolder
              ? (e) => {
                  if (!isNoteDrag(e)) return
                  setDragOverRootHeading(true)
                }
              : undefined
          }
          onDragLeave={
            activeRootFolder
              ? () => setDragOverRootHeading(false)
              : undefined
          }
          onDrop={
            activeRootFolder
              ? (e) => {
                  const path = readNoteDrag(e)
                  if (!path) return
                  e.preventDefault()
                  setDragOverRootHeading(false)
                  moveNote(path, activeRootFolder.path)
                }
              : undefined
          }
        >
          {trashView ? "Bin" : activeLabel || "Vault"}
        </h2>
        {trashView && <BinSectionPills section={bin.section} onChange={(next) => setBin("section", next)} />}
        </div>
        {trashView ? (
          <BinView
            persona={activePersona}
            section={bin.section}
            refreshKey={vaultRefreshKey}
            conversationsKey={conversationBinKey}
            onNoteRestored={() => refreshVault()}
            onConversationRestored={onConversationRestored}
          />
        ) : vaultTreeEmpty ? (
          <EmptyState
            icon={Folder01Icon}
            title="No notes in scope"
            description="Check that the API is reachable and the persona has vault folders."
          />
        ) : (
          <>
            {panelEmpty && (
              <EmptyState icon={Folder01Icon} title="This folder is empty" />
            )}
            {!panelEmpty &&
              vaultSearchQuery &&
              searchedPanelNodes.length === 0 &&
              contentMatches.length === 0 && (
                <EmptyState
                  icon={Search01Icon}
                  title={`No matches for "${vaultSearchQuery}"`}
                  description={`in ${activeLabel}`}
                />
              )}
            {(searchedPanelNodes.length > 0 ||
              pinnedNodes.length > 0 ||
              recentNodes.length > 0) && (
              <VaultTree
                // Remounts between browsing and searching so a search's
                // matching folders start expanded (`defaultExpanded`, a
                // one-time seed) without disturbing the persisted
                // expanded-folders cookie used the rest of the time. Also
                // remounts on a vault switch, which has its own cookie.
                key={`${vaultPath}:${vaultSearchQuery ? "search" : "browse"}`}
                nodes={searchedPanelNodes}
                pinnedNodes={pinnedNodes}
                pinnedShowPath={pinnedShowPath}
                recentNodes={recentNodes}
                listLabel={activeLabel ? `Notes in ${activeLabel}` : undefined}
                listIcon={folderIconFor(activeLabel)}
                defaultExpanded={
                  vaultSearchQuery
                    ? collectFolderPaths(searchedPanelNodes)
                    : []
                }
                storageKey={
                  vaultSearchQuery
                    ? undefined
                    : vaultScopedKey(
                        "sympose:vault.expanded",
                        vaultPath
                      )
                }
                {...vaultTreeActions}
              />
            )}
            {vaultSearchQuery && contentMatches.length > 0 && (
              <div className="mt-4">
                <p className="mb-1.5 text-xs font-medium tracking-wide text-fg-muted uppercase">
                  Also found in {activeLabel}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {contentMatches.map((r) => (
                    <li key={r.rel_path}>
                      <SearchResultRow
                        label={stripMdExtension(r.file_name)}
                        hidden={r.hidden}
                        onUnhide={() => unhideFromView(r.hidden_by ?? r.rel_path)}
                        unhides={r.hidden_by}
                        onSelect={() => {
                          selectNote(r.rel_path)
                          openEditor()
                        }}
                        detail={searchMatchDetail(r)}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {vaultSearchQuery && beyondFolderMatches.length > 0 && (
              <div className="mt-4">
                <p className="mb-1.5 text-xs font-medium tracking-wide text-fg-muted uppercase">
                  {beyondFolderMatches.length} match
                  {beyondFolderMatches.length === 1 ? "" : "es"} beyond{" "}
                  {activeLabel}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {beyondFolderMatches.map((r) => (
                    <li key={r.rel_path}>
                      <SearchResultRow
                        label={stripMdExtension(r.rel_path)}
                        hidden={r.hidden}
                        onUnhide={() => unhideFromView(r.hidden_by ?? r.rel_path)}
                        unhides={r.hidden_by}
                        onSelect={() => {
                          selectNote(r.rel_path)
                          openEditor()
                        }}
                        detail={searchMatchDetail(r)}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
  )
}
