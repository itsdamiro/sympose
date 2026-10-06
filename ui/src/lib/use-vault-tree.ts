import * as React from "react"

import type { VaultNode } from "@/components/sympose"
import { notify } from "@/lib/notify"
import { isHiddenByUser, pruneHidden } from "@/lib/prune-hidden"
import { fetchVaultTree } from "@/lib/vault-tree-api"
import {
  NO_HIDDEN,
  fetchHidden,
  hidePath,
  unhidePath,
  type HiddenResult,
  type HiddenState,
} from "@/lib/vault-hidden-api"

/**
 * The vault browser's data: the persona-scoped directory tree
 * (`GET /api/vault/tree`), re-fetched when the active persona changes so the
 * sandbox follows the switcher and whenever `vaultRefreshKey` is bumped, and the
 * list of what the user hid from view (docs/decisions/037).
 *
 * - `fullTree` is every node the server sent, each marked `hidden` where the
 *   user hid it; `isHidden(path)` reads it, so a remembered note that has since
 *   been hidden does not reopen.
 * - `vaultTree` is what the user sees and what everything else reads (menus,
 *   lists, `[[wikilink]]` and embed resolution): the same tree with everything
 *   marked left out.
 * - `vaultName` is the vault root's display name (the master vault directory's
 *   basename), the leading segment of the editor's breadcrumb: `null` until the
 *   first answer lands, or for good if the backend has no vault configured.
 * - Hide, unhide and the definition-notes switch each answer with the whole
 *   hidden state; then everything scoped to the vault is re-pulled through
 *   `refreshVault`, since the server does the marking.
 *
 * A failed tree fetch is not an empty vault. A refresh keeps the tree that is
 * shown; after a persona switch the old tree is another persona's, so it goes.
 * Either way the user gets one notice, not a stack.
 */
export function useVaultTree({
  activePersona,
  vaultRefreshKey,
  refreshVault,
}: {
  activePersona: string
  vaultRefreshKey: number
  refreshVault: () => void
}) {
  const [fullTree, setVaultTree] = React.useState<VaultNode[]>([])
  const vaultTree = React.useMemo(() => pruneHidden(fullTree), [fullTree])
  const [hiddenState, setHiddenState] = React.useState<HiddenState>(NO_HIDDEN)
  const [vaultName, setVaultName] = React.useState<string | null>(null)

  const treeOfPersona = React.useRef(activePersona)
  React.useEffect(() => {
    let alive = true
    fetchVaultTree(activePersona).then((result) => {
      if (!alive) return
      const samePersona = treeOfPersona.current === activePersona
      if (!result) {
        notify.error("Couldn't load the vault. Check that Sympose is running, then try again.", { id: "vault-tree" })
        if (!samePersona) {
          setVaultTree([])
          setVaultName(null)
          treeOfPersona.current = activePersona
        }
        return
      }
      treeOfPersona.current = activePersona
      setVaultTree(result.tree)
      setVaultName(result.vaultName)
    })
    return () => {
      alive = false
    }
  }, [activePersona, vaultRefreshKey])
  React.useEffect(() => {
    let alive = true
    fetchHidden().then((state) => {
      if (alive) setHiddenState(state)
    })
    return () => {
      alive = false
    }
  }, [vaultRefreshKey])

  const changeHidden = React.useCallback(
    async (change: Promise<HiddenResult>, done?: string) => {
      const res = await change
      if (!res.ok) {
        notify.error(res.error)
        return
      }
      setHiddenState(res.state)
      refreshVault()
      if (done) notify.success(done)
    },
    [refreshVault]
  )
  const hideFromView = React.useCallback(
    (path: string) =>
      changeHidden(hidePath(path), "Hidden from view — Settings brings it back"),
    [changeHidden]
  )
  // One path, or every entry that hides a search hit (its own, and the folders
  // above it): one after another, each reads and rewrites the list.
  const unhideFromView = React.useCallback(
    async (paths: string | string[]) => {
      let last: HiddenResult | undefined
      for (const path of Array.isArray(paths) ? paths : [paths]) {
        last = await unhidePath(path)
        if (!last.ok) break
      }
      if (last) await changeHidden(Promise.resolve(last))
    },
    [changeHidden]
  )
  const isHidden = React.useCallback(
    (path: string | undefined) => isHiddenByUser(fullTree, path),
    [fullTree]
  )

  return {
    vaultTree,
    vaultName,
    hiddenState,
    isHidden,
    changeHidden,
    hideFromView,
    unhideFromView,
  }
}
