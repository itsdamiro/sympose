import * as React from "react"

import { notify } from "@/lib/notify"
import { fetchNoteTemplate, type NoteTemplate } from "@/lib/vault-definition-api"
import { createVaultFolder, createVaultNote } from "@/lib/vault-note-api"

/** Which kind the open name field is for. */
export type CreateKind = "note" | "folder"

/**
 * The toolbar's "new note" and "new folder" name fields. At most one is open
 * (`pendingCreate`, with what is typed in `createName`); like search they are
 * icon-toggled fields that auto-hide. Toggling one open moves focus into it. The
 * two inputs are one element each that persists across the "note"/"folder" switch
 * (no remount), so a plain `autoFocus` would fire only once: re-focusing on every
 * open goes through an effect.
 *
 * Kept apart from the submit (`useCreateSubmit`) because navigation closes the
 * field on its way to the Bin, and the submit needs to know which folder is in
 * view, which navigation decides.
 */
export function useCreateField() {
  const [pendingCreate, setPendingCreate] = React.useState<CreateKind | null>(null)
  const [createName, setCreateName] = React.useState("")
  const [creating, setCreating] = React.useState(false)
  const closeCreate = () => {
    setPendingCreate(null)
    setCreateName("")
  }
  /** The icon button: opens that field blank, or closes it when it is the open one. */
  const toggleCreate = (kind: CreateKind) => {
    setCreateName("")
    setPendingCreate((v) => (v === kind ? null : kind))
  }
  const noteInputRef = React.useRef<HTMLInputElement>(null)
  const folderInputRef = React.useRef<HTMLInputElement>(null)
  React.useEffect(() => {
    if (pendingCreate === "note") noteInputRef.current?.focus()
    else if (pendingCreate === "folder") folderInputRef.current?.focus()
  }, [pendingCreate])
  return {
    pendingCreate,
    createName,
    setCreateName,
    creating,
    setCreating,
    closeCreate,
    toggleCreate,
    noteInputRef,
    folderInputRef,
  }
}

/**
 * Creating what the open field names, in the folder in view (`folder`, empty for
 * the vault root, which is where a root note being the active surface puts it).
 * A new note opens in the editor; a new folder just refreshes the tree.
 *
 * A folder typed with no slash, made at the root, is a root folder for a persona
 * that sees the whole vault. The server says whether it can have a definition (a
 * persona's first folder, `Templates` and ignored folders cannot), and the setup
 * step (`folderSetup`, docs/decisions/038) opens only when it can. Both fields of
 * it are optional and nothing is written on Skip.
 */
export function useCreateSubmit({
  field,
  folder,
  activePersona,
  refreshVault,
  selectNote,
  openEditor,
}: {
  field: Pick<
    ReturnType<typeof useCreateField>,
    "pendingCreate" | "createName" | "creating" | "setCreating" | "closeCreate"
  >
  folder: string
  activePersona: string
  refreshVault: () => void
  selectNote: (path: string) => void
  openEditor: () => void
}) {
  const [folderSetup, setFolderSetup] = React.useState<{
    folder: string
    template: NoteTemplate
  } | null>(null)

  const submitCreate = async () => {
    const kind = field.pendingCreate
    const name = field.createName
      .trim()
      .replace(/\.md$/i, "")
      .replace(/^\/+|\/+$/g, "")
    if (!kind || !name || field.creating) return
    const target = folder ? `${folder}/${name}` : name
    field.setCreating(true)
    const result =
      kind === "note"
        ? await createVaultNote(target, activePersona)
        : await createVaultFolder(target, activePersona)
    field.setCreating(false)
    if (!result.ok) {
      notify.error(result.error)
      return
    }
    field.closeCreate()
    refreshVault()
    if (kind === "note") {
      selectNote(`${target}.md`)
      openEditor()
    }
    notify.success(`Created ${name}`)
    if (kind === "folder" && !folder && !/[\\/]/.test(name)) {
      const template = await fetchNoteTemplate(name, activePersona)
      if (template?.definable) setFolderSetup({ folder: name, template })
    }
  }
  const closeFolderSetup = () => setFolderSetup(null)

  return { submitCreate, folderSetup, closeFolderSetup }
}
