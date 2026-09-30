import type { VaultNode } from "@/components/sympose"

/**
 * Client for `GET /api/vault/tree` — the vault manifest projected into a
 * nested `VaultNode` tree, scoped to a persona's allowed vault folders. Returns
 * `null` when the backend cannot be reached or answers with an error, so the
 * caller can keep the tree it has and say so; an empty tree from here always
 * means an empty vault, never a failed fetch.
 */
interface VaultTreeResponse {
  persona: string
  tree: VaultNode[]
  /** The master vault directory's basename, for the editor's read-mode
   *  breadcrumb — `null` when `VAULT_PATHS` isn't configured. */
  vaultName: string | null
}

export interface VaultTreeResult {
  tree: VaultNode[]
  vaultName: string | null
}

export async function fetchVaultTree(persona: string): Promise<VaultTreeResult | null> {
  try {
    const res = await fetch(
      `/api/vault/tree?persona=${encodeURIComponent(persona)}`
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as VaultTreeResponse
    return { tree: data.tree ?? [], vaultName: data.vaultName ?? null }
  } catch (err) {
    console.info(`[vault-tree] /api/vault/tree unreachable (${err})`)
    return null
  }
}
