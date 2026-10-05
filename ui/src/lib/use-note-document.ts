import * as React from "react"
import { splitFrontmatter } from "@damiro/stylo"

import { notify } from "@/lib/notify"
import { AUTOSAVE_DELAY, joinNote, syncInlineTags, type NoteLoadState } from "@/lib/markdown-note"
import { setUnsavedGuard } from "@/lib/unsaved-guard"
import { fetchVaultNote, saveVaultNote, type SaveVaultNoteResult } from "@/lib/vault-note-api"

/**
 * A file that is not a vault note (a persona's own file, docs/decisions/061): its load and save in place of the
 * vault's. See `MarkdownPanel`'s `file` prop.
 */
export interface PanelFile {
  load: (path: string) => Promise<{ content: string; mtime?: number } | null>
  save: (path: string, text: string, mtime?: number) => Promise<SaveVaultNoteResult>
  title: string
  banner?: React.ReactNode
}

/**
 * The open note's document: loading it from the vault (or a persona's file), the frontmatter and body buffers, saving
 * them back (the toolbar button, `⌘/Ctrl-S`, autosave and the flush on leaving the note), and what the vault switcher
 * asks before it changes the vault under the editor (`unsaved-guard`). `MarkdownPanel` draws it; every way the
 * document is written goes through `saveNote`, so a persona writing to a note (docs/decisions/042) attaches here.
 */
export function useNoteDocument({
  path,
  persona,
  vaultPath,
  file,
  reloadToken,
  autosave,
  holdAutomaticSave,
  onSaved,
}: {
  path?: string
  persona: string
  vaultPath: string | null
  file?: PanelFile
  reloadToken: number
  autosave: string
  /** True while the buffer holds only what the persona applied (docs/decisions/072, `accept` mode): autosave, the
   *  leave-note flush and a rename's save then wait, so her edit never reaches the file without the user touching the
   *  note. The user's own save, and "Save and switch", still write. */
  holdAutomaticSave?: () => boolean
  /** The buffer was written to the file. */
  onSaved?: () => void
}) {
  // "empty" is derived straight from `path`, not effect-driven state — nothing
  // to synchronize with an external system until there's a path to fetch. On a
  // note switch the previous note's content is left showing (no loading flash)
  // until the new fetch resolves — the same convention `fetchVaultTree` uses.
  const [fetch, setFetch] = React.useState<Exclude<NoteLoadState, { status: "empty" }>>(
    { status: "loading" }
  )
  const note: NoteLoadState = React.useMemo(
    () => (path ? fetch : { status: "empty" }),
    [path, fetch]
  )
  // The frontmatter card owns the `---` block entirely — stylo's own value
  // never sees it, so editing a pill never touches CodeMirror's undo history.
  const [frontmatter, setFrontmatter] = React.useState<string | null>(null)
  const [body, setBody] = React.useState("")
  // The note text as last persisted (in `joinNote` form, so the dirty check
  // compares like with like). A save-in-flight guard keeps a slow write or a
  // fast typist from stacking overlapping `PUT`s. `loadedPathRef` is the path
  // whose content is actually in `body`/`frontmatter` right now — on a note
  // switch `path` changes a frame before the fetch resolves, and saving in that
  // gap would write the old body to the new note.
  const savedTextRef = React.useRef<string>("")
  const savingRef = React.useRef(false)
  const loadedPathRef = React.useRef<string | undefined>(undefined)
  // Counts the notes loaded into the buffer. A save that finishes after another note was loaded must not write its
  // text or mtime over what that note's own load set (a rename keeps the same note, so it does not count).
  const loadCountRef = React.useRef(0)
  // The on-disk mtime this buffer was loaded from or last saved as; a save presents it so a change made
  // elsewhere (Obsidian, sync, the persona) is refused instead of overwritten. `reloadKey` refetches.
  const mtimeRef = React.useRef<number | undefined>(undefined)
  const [reloadKey, setReloadKey] = React.useState(0)
  // Which vault `loadedPathRef`'s content was actually fetched from — set
  // alongside it, same "only moves once the fetch lands" contract. The
  // leave-note flush below compares this against `vaultPath`'s *current*
  // value (via `currentVaultPathRef`) to tell a vault switch apart from an
  // ordinary note switch.
  const loadedVaultPathRef = React.useRef<string | null>(null)
  const currentVaultPathRef = React.useRef(vaultPath)
  // Assigned during render, not in an effect: an effect's cleanup for the
  // *previous* render fires before this render's own effects do, so only a
  // plain render-time assignment guarantees the ref already reads the
  // incoming `vaultPath` by the time that cleanup runs.
  // eslint-disable-next-line react-hooks/refs -- mirrors a prop for a cleanup to read live, see comment above
  currentVaultPathRef.current = vaultPath
  // The note's exact `---`…`---` prefix as loaded, and whether the frontmatter
  // card has since edited a field — together these let a body-only save keep
  // the original YAML block byte-for-byte (see `joinNote`).
  const originalPrefixRef = React.useRef<string | null>(null)
  const frontmatterEditedRef = React.useRef(false)

  // The file's functions are read off a ref, so a new object each render never refetches; the effects below depend on
  // `path`, which is what names the file.
  const fileRef = React.useRef(file)
  const holdRef = React.useRef(holdAutomaticSave)
  const savedRef = React.useRef(onSaved)
  React.useEffect(() => {
    fileRef.current = file
    holdRef.current = holdAutomaticSave
    savedRef.current = onSaved
  })

  React.useEffect(() => {
    if (!path) return
    let alive = true
    const opening = fileRef.current ? fileRef.current.load(path) : fetchVaultNote(path, persona)
    opening.then((result) => {
      if (!alive) return
      if (!result) {
        setFetch({ status: "error" })
        return
      }
      const split = fileRef.current ? null : splitFrontmatter(result.content) // a persona's file is all body
      const fm = split ? split.frontmatter : null
      const bd = split ? split.body : result.content
      const prefix = split
        ? result.content.slice(0, result.content.length - split.body.length)
        : null
      setFrontmatter(fm)
      setBody(bd)
      originalPrefixRef.current = prefix
      frontmatterEditedRef.current = false
      savedTextRef.current = joinNote(fm, bd, prefix, false)
      loadedPathRef.current = path
      loadCountRef.current += 1
      mtimeRef.current = result.mtime
      loadedVaultPathRef.current = currentVaultPathRef.current
      setFetch({ status: "ready", content: result.content })
    })
    return () => {
      alive = false
    }
    // `vaultPath` is a dependency (not just read via the ref above) so a
    // vault switch always refetches, even on the rare coincidence that the
    // new vault's own last-open note happens to share the old one's exact
    // relative path — otherwise this effect would see no `path` change and
    // go on showing the previous vault's content under the new vault's name.
  }, [path, persona, vaultPath, reloadKey, reloadToken])

  // Persist the current frontmatter + body to the vault. Shared by the toolbar
  // `save` button, `⌘/Ctrl-S` (both via stylo's `onSave`), autosave, and the
  // leave-note flush below. `silent` keeps autosave (and the flush) from
  // toasting on every idle pause / note switch. `syncTags` is separate from
  // `silent` — it defaults to "explicit save" (`!silent`) but the flush
  // overrides it back on, since leaving a note silently is still a
  // deliberate-enough moment to finalize its tags (see the flush effect below
  // for why autosave itself must stay excluded). Resolves `true` when the note
  // is saved or had nothing to save, `false` when a save failed or was busy.
  const saveNote = React.useCallback(
    async ({
      silent = false,
      syncTags = !silent,
      automatic = false,
    }: {
      silent?: boolean
      syncTags?: boolean
      /** Not the user's act (autosave, the flush, a rename): waits while the buffer holds only the persona's edits. */
      automatic?: boolean
    } = {}): Promise<boolean> => {
      // Targets `loadedPathRef.current` — the note `body`/`frontmatter`
      // state actually holds — rather than the `path` prop directly. On a
      // note switch `path` moves to the next note a frame before its fetch
      // resolves; targeting `path` there would write the *old* body onto
      // the *new* note. `loadedPathRef` only updates once a fetch actually
      // lands, so during that gap it still correctly names the note this
      // state belongs to — which is exactly what the leave-note flush below
      // needs to call this mid-switch without racing it.
      const targetPath = loadedPathRef.current
      if (!targetPath) return true
      if (automatic && holdRef.current?.()) return true
      if (savingRef.current) return false

      // Autosave's 1.5s debounce fires on any typing pause, including
      // mid-word inside a tag the user hasn't finished typing yet (`#cs` on
      // the way to `#css`); syncing there would permanently bake in the
      // half-typed fragment, since the merge is additive-only and never
      // removes a tag once added.
      const synced = syncTags
        ? syncInlineTags(frontmatter, body)
        : { frontmatter, changed: false }
      if (synced.changed) {
        frontmatterEditedRef.current = true
        setFrontmatter(synced.frontmatter)
      }

      const text = joinNote(
        synced.frontmatter,
        body,
        originalPrefixRef.current,
        frontmatterEditedRef.current
      )
      if (text === savedTextRef.current) return true

      savingRef.current = true
      const loadedAtStart = loadCountRef.current
      const saving = fileRef.current
        ? fileRef.current.save(targetPath, text, mtimeRef.current)
        : saveVaultNote(targetPath, text, persona, mtimeRef.current)
      const result = await saving
      savingRef.current = false
      if (result.ok && loadCountRef.current !== loadedAtStart) return true // written; the buffer is another note's by now
      if (result.ok) {
        savedTextRef.current = text
        mtimeRef.current = result.mtime
        // Refresh `note.content` from the just-written text so the wikilink
        // footer (derived from `note`, not the live buffer) picks up any
        // `[[links]]` added since the last load — without rescanning on
        // every keystroke.
        setFetch({ status: "ready", content: text })
        savedRef.current?.()
        if (!silent) notify.success(fileRef.current ? "Saved" : "Note saved")
        return true
      }
      if (result.conflict) {
        notify.error(result.error, {
          action: { label: "Discard my edits and reload", onClick: () => setReloadKey((k) => k + 1) },
        })
      } else {
        notify.error(result.error)
      }
      return false
    },
    [persona, frontmatter, body]
  )

  // `saveNote` gets a new identity on every keystroke (it closes over
  // `frontmatter`/`body`) — the leave-note flush below needs to call
  // whichever version is current *without* re-running its own effect on
  // every edit, so it reads through this ref (updated every render, a plain
  // assignment — cheap) instead of taking `saveNote` as a dependency.
  const saveNoteRef = React.useRef(saveNote)
  React.useEffect(() => {
    saveNoteRef.current = saveNote
  })

  // What the vault switcher asks before it changes the vault under this editor (`unsaved-guard`).
  const isDirtyRef = React.useRef<() => boolean>(() => false)
  React.useEffect(() => {
    isDirtyRef.current = () =>
      !!loadedPathRef.current &&
      joinNote(frontmatter, body, originalPrefixRef.current, frontmatterEditedRef.current) !== savedTextRef.current
  })
  React.useEffect(() => {
    setUnsavedGuard({
      name: () => (loadedPathRef.current ?? "").split("/").pop()?.replace(/\.md$/, "") ?? "",
      isDirty: () => isDirtyRef.current(),
      save: () => saveNoteRef.current({ silent: true, syncTags: true }),
      retarget: async (oldPath, newPath) => {
        if (loadedPathRef.current !== oldPath) return
        loadedPathRef.current = newPath
        await saveNoteRef.current({ silent: true, syncTags: false, automatic: true })
      },
    })
    return () => setUnsavedGuard(null)
  }, [])

  // Flush a save when leaving this note — switching to another one, or the
  // panel unmounting entirely — so
  // an edit isn't lost just because autosave is off (its default) and the
  // save button never got hit. `path`/`vaultPath` are the only dependencies,
  // so the cleanup fires exactly on a note switch, a vault switch, or an
  // unmount, never on every keystroke; by the time it runs, `saveNoteRef.
  // current` already targets `loadedPathRef.current` (see above), which
  // still names the *leaving* note during the gap before the next note's
  // fetch resolves.
  //
  // A vault switch is not a normal "flush to the vault" moment: by the time a
  // `PUT` from this cleanup landed, the backend would already have switched
  // vaults and the edit would be written over whatever file sits at the same
  // relative path in the new one. The switcher asks first and saves while the
  // old vault is still active (`unsaved-guard`, ADR 004 amendment), so when the
  // vault did change here (another window, the terminal) nothing is written.
  //
  // This stays silent (no toast — a background flush, not something the user
  // asked for). Tag-syncing happens because leaving a note for another in the
  // same vault is a real "I'm done with this one" signal, not a mid-word
  // coincidence as autosave's blind timer is.
  React.useEffect(() => {
    return () => {
      if (loadedVaultPathRef.current !== currentVaultPathRef.current) return
      void saveNoteRef.current({ silent: true, syncTags: true, automatic: true })
    }
  }, [path, vaultPath])

  // Autosave — a trailing debounce on every body/frontmatter change. Off by
  // default (Settings › Markdown editor); the explicit save paths stay live
  // regardless. Re-armed on each edit, cancelled on unmount / note switch.
  React.useEffect(() => {
    if (autosave !== "on" || note.status !== "ready") return
    const id = window.setTimeout(() => void saveNote({ silent: true, automatic: true }), AUTOSAVE_DELAY)
    return () => window.clearTimeout(id)
  }, [autosave, note.status, saveNote])

  return { note, frontmatter, setFrontmatter, body, setBody, frontmatterEditedRef, loadedPathRef, saveNote }
}
