import * as React from "react"

/**
 * The counter that makes everything scoped to "the active vault" fetch again:
 * the tree, the graph, the hidden list, a live search and the bin. `refresh` is
 * called after a note is created, renamed, moved, deleted or restored, after a
 * vault is switched or added, and after the hidden list changes (the server does
 * the marking). A persona switch refetches on its own.
 */
export function useVaultRefresh() {
  const [vaultRefreshKey, setVaultRefreshKey] = React.useState(0)
  const refreshVault = React.useCallback(() => setVaultRefreshKey((k) => k + 1), [])
  return { vaultRefreshKey, refreshVault }
}
