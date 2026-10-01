import * as React from "react"

import { askToSaveFirst } from "@/lib/ask-to-save-first"
import { notify } from "@/lib/notify"
import { resolveSelectedNoteFor } from "@/lib/use-selected-note"
import { addVault, fetchVaults, setActiveVault, type VaultsState } from "@/lib/vaults-api"

/**
 * The workspace switcher's list (ADR 003, 004): every configured vault plus which
 * one is active. Read before the pinned and recent notes, which key their own
 * cookies off `vaultsState.active` so they do not leak across a vault switch.
 */
export function useVaults() {
  const [vaultsState, setVaultsState] = React.useState<VaultsState>({
    vaults: [],
    active: null,
  })
  React.useEffect(() => {
    let alive = true
    fetchVaults().then((state) => {
      if (alive) setVaultsState(state)
    })
    return () => {
      alive = false
    }
  }, [])
  return { vaultsState, setVaultsState }
}

/**
 * Switching to a vault, or adding one (which activates it in the same round trip):
 * persist the choice, then re-pull everything scoped to "the active vault" with a
 * `refreshVault`. Both ask to save an edited note first (`askToSaveFirst`) and
 * carry on once it is dealt with.
 *
 * The note to open is resolved synchronously, in the same batch as `setVaultsState`,
 * rather than left to `useVaultScopedState`'s own reseed effect: otherwise
 * `<MarkdownPanel>` sees the new `vaultPath` one render before the note catches up,
 * and fetches the outgoing vault's note path against the already-switched backend.
 *
 * `handleAddVault` resolves `false` on failure (or when it had to ask first) so the
 * switcher's input keeps the typed path instead of clearing it.
 */
export function useVaultSwitching({
  setVaultsState,
  setSelectedNote,
  refreshVault,
}: {
  setVaultsState: (state: VaultsState) => void
  setSelectedNote: (path: string | undefined) => void
  refreshVault: () => void
}) {
  const switchVaultNow = React.useCallback(
    async (path: string) => {
      const res = await setActiveVault(path)
      if (res.ok) {
        setVaultsState(res.state)
        setSelectedNote(resolveSelectedNoteFor(res.state.active))
        refreshVault()
        const name = res.state.vaults.find((v) => v.path === path)?.name
        notify.success(name ? `Switched to ${name}` : "Vault switched")
      } else {
        notify.error(res.error)
      }
    },
    [setVaultsState, setSelectedNote, refreshVault]
  )
  const handleSwitchVault = React.useCallback(
    async (path: string) => {
      if (askToSaveFirst(() => void switchVaultNow(path))) return
      await switchVaultNow(path)
    },
    [switchVaultNow]
  )

  const addVaultNow = React.useCallback(
    async (path: string) => {
      const res = await addVault(path)
      if (res.ok) {
        setVaultsState(res.state)
        setSelectedNote(resolveSelectedNoteFor(res.state.active))
        refreshVault()
        const name = res.state.vaults.find((v) => v.path === res.state.active)?.name
        notify.success(name ? `Added ${name}` : "Vault added")
        return true
      }
      notify.error(res.error)
      return false
    },
    [setVaultsState, setSelectedNote, refreshVault]
  )
  const handleAddVault = React.useCallback(
    async (path: string) => {
      if (askToSaveFirst(() => void addVaultNow(path))) return false // asked; the typed path stays until it is added
      return addVaultNow(path)
    },
    [addVaultNow]
  )

  return { handleSwitchVault, handleAddVault }
}
