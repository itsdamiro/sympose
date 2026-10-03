import * as React from "react"

import { fetchPersonaFile, savePersonaFile } from "@/lib/persona-files-api"
import type { PanelFile } from "@/components/sympose/markdown-panel"

/**
 * Which of a persona's own files the editor shows, if any (docs/decisions/061): a file is opened from the Persona
 * page's FILES menu and replaces the vault note in the editor until a note is opened again (`close`). `path` is the
 * key the editor is given for it, `persona:<handle>/<name>`, which is never a vault path, so it can never be taken
 * for a note of the same name. A file of the persona before is forgotten when the persona changes.
 * `file` carries the load and save the editor uses in place of the vault's; `reload` makes it read the file again
 * (after a reset or an accepted rewrite changed it on disk), and a save asks for the file list again, because saving
 * the soul makes the user's own copy.
 */
export function usePersonaFileEditor({
  handle,
  personaName,
  refreshFiles,
}: {
  handle: string
  personaName: string
  refreshFiles: () => void
}) {
  const [opened, setOpened] = React.useState<{ handle: string; name: string } | null>(null)
  const [reloadToken, setReloadToken] = React.useState(0)
  const current = opened?.handle === handle ? opened : null

  const open = React.useCallback((name: string) => setOpened({ handle, name }), [handle])
  const close = React.useCallback(() => setOpened(null), [])
  const reload = React.useCallback(() => setReloadToken((n) => n + 1), [])

  const name = current?.name
  const file: Omit<PanelFile, "banner"> | undefined = React.useMemo(
    () =>
      name
        ? {
            title: `${personaName} · ${name}`,
            load: async () => {
              const found = await fetchPersonaFile(handle, name)
              return found && { content: found.content, mtime: found.mtime ?? undefined }
            },
            save: async (_path, text, mtime) => {
              const saved = await savePersonaFile(handle, name, text, mtime)
              if (saved.ok) refreshFiles()
              return saved
            },
          }
        : undefined,
    [handle, name, personaName, refreshFiles]
  )

  return { current, path: current ? `persona:${handle}/${current.name}` : undefined, open, close, reload, reloadToken, file }
}
