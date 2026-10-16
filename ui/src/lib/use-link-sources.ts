import * as React from "react"

import type { VaultNode } from "@/components/sympose"
import type { NebulaGraph } from "@/lib/nebula-graph"
import { matchWikilinkTargets } from "@/lib/vault-wikilink-completions"
import { matchTagTargets } from "@/lib/vault-tag-completions"
import { resolveEmbed } from "@/lib/resolve-embed"
import { resolveImageSource } from "@/lib/resolve-image"

/**
 * What the editor asks the shell for while a note is typed or previewed:
 * `[[wikilink]]` and `#tag` completions, `![[embed]]` resolution and the
 * vault's images (`openNotePath` is where a relative image path starts).
 *
 * stylo reads each of these once, at mount, so the function handed to `<Stylo>`
 * must keep its identity across a tree refetch (a new persona, a new note)
 * instead of being rebuilt every render. A ref carries the live value and the
 * callback itself never changes. `activePersona` gets a ref too because a
 * persona switch alone does not remount `<Stylo>`, and so does the open
 * note's path. Tag candidates come from
 * `buildMasterGraph`'s pre-indexed tag hubs (`nebula-graph.ts`), not a
 * separate scan of the vault.
 */
export function useLinkSources(
  vaultTree: VaultNode[],
  nebulaGraph: NebulaGraph,
  activePersona: string,
  openNotePath = ""
) {
  const vaultTreeRef = React.useRef(vaultTree)
  const nebulaGraphRef = React.useRef(nebulaGraph)
  const activePersonaRef = React.useRef(activePersona)
  const openNotePathRef = React.useRef(openNotePath)
  React.useEffect(() => {
    vaultTreeRef.current = vaultTree
    nebulaGraphRef.current = nebulaGraph
    activePersonaRef.current = activePersona
    openNotePathRef.current = openNotePath
  })

  const wikiLinkSource = React.useCallback(
    (query: string) => matchWikilinkTargets(vaultTreeRef.current, query),
    []
  )
  const tagSource = React.useCallback(
    (query: string) => matchTagTargets(nebulaGraphRef.current, query),
    []
  )
  const embedSource = React.useCallback(
    (ref: string) => resolveEmbed(vaultTreeRef.current, activePersonaRef.current, ref, openNotePathRef.current),
    []
  )
  const imageSource = React.useCallback(
    (src: string, alt: string) => resolveImageSource(activePersonaRef.current, openNotePathRef.current, src, alt),
    []
  )
  return { wikiLinkSource, tagSource, embedSource, imageSource }
}
