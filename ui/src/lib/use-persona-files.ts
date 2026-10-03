import * as React from "react"

import { listPersonaFiles, type PersonaFileInfo } from "@/lib/persona-files-api"

/**
 * The persona's own files (docs/decisions/061) with what is known of each: whether it exists, whether the soul is
 * the user's own copy, whether a rewrite is waiting for review. Read when the persona changes and again on
 * `refresh()`, after a save or a resolved rewrite changed something. Only the answer to the newest read is kept,
 * and another persona's files are never shown for this one while its own load.
 */
export function usePersonaFiles(handle: string) {
  const [loaded, setLoaded] = React.useState<{ handle: string; files: PersonaFileInfo[] } | null>(null)
  const files = loaded?.handle === handle ? loaded.files : []
  const newest = React.useRef(0)

  const refresh = React.useCallback(async () => {
    const mine = ++newest.current
    const next = await listPersonaFiles(handle)
    if (next && mine === newest.current) setLoaded({ handle, files: next })
  }, [handle])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  return { files, refresh }
}
