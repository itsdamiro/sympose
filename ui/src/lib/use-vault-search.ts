import * as React from "react"

import { filterTreeByQuery, type VaultNode } from "@/components/sympose"
import { searchVault, type VaultSearchResult } from "@/lib/vault-search-api"

/** How long the search field waits after the last keystroke before firing
 *  `/api/vault/search`. */
const SEARCH_DEBOUNCE_MS = 250
/** A stable reference for "no search results yet or stale": a fresh `[]` literal
 *  per render would make the memos below see a changed dependency each time a
 *  search is idle, defeating their memoization. */
const EMPTY_SEARCH_RESULTS: VaultSearchResult[] = []

const inFolder = (relPath: string, folder: string) =>
  relPath === folder || relPath.startsWith(`${folder}/`)

/** What the backend adds for the folder in view: its content matches (a title or
 *  tag hit inside the folder is already shown instantly by the client-side
 *  filter), and any hit the user hid, which is listed greyed with Unhide. */
export function contentMatchesIn(results: VaultSearchResult[], folder: string) {
  return results.filter(
    (r) => (r.match_type === "content" || r.hidden) && inFolder(r.rel_path, folder)
  )
}

/** Everything outside the folder in view, of every match type, since nothing else
 *  surfaces a title or tag hit on a note living in a different folder. */
export function matchesBeyond(results: VaultSearchResult[], folder: string) {
  return results.filter((r) => !inFolder(r.rel_path, folder))
}

/**
 * Searching the vault from the content panel's toolbar. The field is an
 * icon-toggled one (like new note and new folder): collapsed by default, focused
 * when it opens, and closing it also clears the query so the filtered view resets.
 *
 * Two tiers, both for the folder in view (`resolvedActive`):
 * - A client-side filter of the tree already fetched (round-trip frugality):
 *   `searchedPanelNodes`. Only the vault-folder listing reads it, not the Bin,
 *   Settings or Persona, which the same toolbar sits above.
 * - A backend search, for what the tree does not hold (body text): one debounced,
 *   whole-persona-scope round trip to `/api/vault/search`, never narrowed to a
 *   folder, from which `contentMatches` (the folder in view) and
 *   `beyondFolderMatches` (everything else) are derived. Switching which folder
 *   is in view needs no new fetch.
 *
 * The answer is stored keyed to the query, persona and vault it was fetched for,
 * and read only while that key is current, so retyping the query, switching
 * persona or vault can never display a stale response, in whatever order answers
 * arrive. A section that is not a folder (`isSentinel`) never fetches.
 */
export function useVaultSearch({
  panelNodes,
  resolvedActive,
  isSentinel,
  activePersona,
  vaultRefreshKey,
}: {
  panelNodes: VaultNode[]
  resolvedActive: string
  isSentinel: boolean
  activePersona: string
  vaultRefreshKey: number
}) {
  const [vaultSearch, setVaultSearch] = React.useState("")
  const [searchOpen, setSearchOpen] = React.useState(false)
  const closeSearch = () => {
    setSearchOpen(false)
    setVaultSearch("")
  }
  const searchInputRef = React.useRef<HTMLInputElement>(null)
  React.useEffect(() => {
    if (searchOpen) searchInputRef.current?.focus()
  }, [searchOpen])

  const vaultSearchQuery = vaultSearch.trim()
  const searchedPanelNodes = React.useMemo(
    () => (vaultSearchQuery ? filterTreeByQuery(panelNodes, vaultSearchQuery) : panelNodes),
    [panelNodes, vaultSearchQuery]
  )

  const searchKey = `${vaultSearchQuery}\u0000${activePersona}\u0000${vaultRefreshKey}`
  const [searchState, setSearchState] = React.useState<{
    key: string
    results: VaultSearchResult[]
  }>({ key: "", results: [] })
  React.useEffect(() => {
    if (!vaultSearchQuery || isSentinel) return
    const key = searchKey
    const controller = new AbortController()
    const t = setTimeout(() => {
      searchVault(vaultSearchQuery, activePersona, controller.signal).then((results) => {
        if (!controller.signal.aborted) setSearchState({ key, results })
      })
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      clearTimeout(t)
      controller.abort()
    }
  }, [vaultSearchQuery, isSentinel, activePersona, searchKey])
  const searchResults = searchState.key === searchKey ? searchState.results : EMPTY_SEARCH_RESULTS

  const contentMatches = React.useMemo(
    () => contentMatchesIn(searchResults, resolvedActive),
    [searchResults, resolvedActive]
  )
  const beyondFolderMatches = React.useMemo(
    () => matchesBeyond(searchResults, resolvedActive),
    [searchResults, resolvedActive]
  )

  return {
    vaultSearch,
    setVaultSearch,
    searchOpen,
    setSearchOpen,
    closeSearch,
    searchInputRef,
    vaultSearchQuery,
    searchedPanelNodes,
    contentMatches,
    beyondFolderMatches,
  }
}
