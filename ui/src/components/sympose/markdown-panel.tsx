import * as React from "react"
import {
  Stylo,
  type EmbedSource,
  type StyloHandle,
  type TagSource,
  type TaskToggleInfo,
  type ToolbarItem,
  type WikiLinkSource,
} from "@damiro/stylo"
import { languages as CODE_LANGUAGES } from "@codemirror/language-data"
import "@damiro/stylo/styles.css"
import "@damiro/stylo/katex.css"
import { HugeiconsIcon } from "@hugeicons/react"
import { File01Icon, Alert02Icon, BookOpen01Icon, PencilEdit01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { EmptyState } from "@/components/sympose/empty-state"
import { getCookieBool, setCookieBool } from "@/lib/cookies"
import { useSlideSwap, slideEnterClassName, slideExitClassName } from "@/lib/use-slide-swap"
import { getUnsavedGuard } from "@/lib/unsaved-guard"
import { useReadOnlyToggle } from "@/lib/use-read-only-toggle"
import { extractWikilinks } from "@/lib/extract-wikilinks"
import { openMarkdownLink } from "@/lib/open-markdown-link"
import { usePanelSizing } from "@/lib/use-panel-sizing"
import { useNoteDocument, type PanelFile } from "@/lib/use-note-document"
import type { Proposal } from "@/lib/persona-changes-api"
import { usePersonaChanges } from "@/lib/use-persona-changes"
import { announceDraftsChanged } from "@/lib/use-drafts"
import { applyProposals, classify, clearApplied, pendingIds, reviewExtensions, setReviewData, type ReviewData } from "@/lib/review-extensions"
import { useEditMode } from "@/lib/use-edit-mode"
import { OutdatedChanges } from "@/components/sympose/outdated-changes"
import { CommentPopover, type CommentBox } from "@/components/sympose/comment-popover"
import { setOpenNoteSource } from "@/lib/open-note-source"
import { commentMenuItem, commentToolbarItem, reviewToolbarItems } from "@/components/sympose/review-toolbar"
import type { EditorPreferences } from "@/lib/use-editor-preferences"
import { FrontmatterCard } from "@/components/sympose/frontmatter-card"
import { NoteActionsMenu } from "@/components/sympose/note-actions-menu"
import { PanelCollapseButton } from "@/components/sympose/panel-collapse-button"
import { ScrollThumb } from "@/components/sympose/scroll-thumb"
import { CodeBlockCopyButtons } from "@/components/sympose/code-block-copy-button"
import { NoteLinksFooter } from "@/components/sympose/note-links-footer"
import { NoteBreadcrumb } from "@/components/sympose/note-breadcrumb"
import { TOOLBAR_ICONS } from "@/components/sympose/markdown-toolbar-icons"
import { TOGGLE_CONTENT_ENTER, TOGGLE_CONTENT_EXIT, getStyloScroller } from "@/components/sympose/markdown-panel-motion"

export type { PanelFile }

interface MarkdownPanelProps extends React.ComponentProps<"div"> {
  storageKey?: string
  /** Relative vault path of the note to load. `undefined` shows the empty state. */
  path?: string
  /** Persona handle to scope the `/api/vault/note` request to. */
  persona?: string
  /** What the persona is called where her comments are shown (a thread under a comment); the handle when omitted. */
  personaName?: string
  /** The active vault's absolute path — not resolved against, just compared
   *  against its own previous value, to tell "the active vault changed"
   *  apart from an ordinary note switch when this panel's `path` closes
   *  (see the leave-note flush below). `null`/`undefined` when no vault is
   *  configured. */
  vaultPath?: string | null
  /** Fires when the reader clicks a `[[wikilink]]` in the canvas. */
  onWikiLinkClick?: (target: string) => void
  /** Supplies `[[wikilink]]` autocomplete candidates (stylo `>=0.7.0`) — omit
   *  to leave the feature off. Read once, at mount, per stylo's own contract;
   *  the caller is responsible for a stable function identity that reads live
   *  data off a ref rather than being rebuilt on every vault-tree refetch. */
  wikiLinkSource?: WikiLinkSource
  /** Supplies `#tag` autocomplete candidates (stylo `>=0.12.0`) — same
   *  read-once-at-mount contract as `wikiLinkSource` above; omit to leave the
   *  feature off. */
  tagSource?: TagSource
  /** Resolves `![[ref]]` embeds — reactive in `preview`, read-once-at-mount
   *  on the in-place canvas (stylo `>=0.13.x`); omit to leave `![[ref]]`
   *  literal. */
  embedSource?: EmbedSource
  /** The open note was renamed — value is its new vault-relative path. */
  /** Bumped each time a note is opened from the chat: the editor then shows it in preview (read) mode. */
  previewRequest?: number
  onRenamed?: (newPath: string) => void
  /** The open note was moved to trash. */
  onDeleted?: () => void
  /** Is the open note pinned — feeds the toolbar `⋯` menu's Pin/Unpin row,
   *  the same local-only prep state the vault-tree row menu toggles. */
  isPinned?: (path: string) => boolean
  /** Toggle the open note's pinned state. */
  onTogglePin?: (path: string) => void
  /** Read mode's folder breadcrumb passes the open note's top-level vault
   *  folder here when clicked — the only segment with anywhere to navigate
   *  to today (the content panel can only jump to root-level vault
   *  sections). Wire straight to `selectSection`. */
  onNavigateToRootFolder?: (rootPath: string) => void
  /** The vault root's display name, leading the read-mode breadcrumb — `null`
   *  (backend has no `VAULT_PATHS` configured, or it hasn't loaded yet)
   *  drops that leading segment entirely rather than showing a placeholder. */
  vaultName?: string | null
  /** Editing surface/decoration preferences — Settings > Markdown editor. */
  preferences: EditorPreferences
  /** The toolbar's button set — Settings > Markdown editor >
   *  `<StyloToolbarSettings>`. */
  toolbarItems: ToolbarItem[]
  /** Collapses the editor; its button is the first icon of the toolbar, at the far left. Omit where it cannot collapse. */
  onCollapse?: () => void
  /**
   * A file that is not a vault note (a persona's own file, docs/decisions/061): its load and save in place of the
   * vault's, and none of the note chrome (no actions menu, frontmatter card or links footer). `path` is then an
   * opaque key the file's functions understand (never a vault path), `title` is shown where the vault path would be,
   * and `banner` sits at the top of the document with what is particular to this file.
   */
  file?: PanelFile
  /** Changed from outside to read the open file again (after a reset or an accepted rewrite changed it on disk). */
  reloadToken?: number
  /**
   * Revealed when true (default), collapsed when false. The panel stays mounted
   * either way and transitions its width / opacity / offset, so it fades and
   * slides in from the left on reveal and back out on hide.
   */
  open?: boolean
  /**
   * Grow into the leftover stage width (in addition to the dragged basis) —
   * used when nothing sits to the editor's right, so it occupies the chat's
   * area. No resize handle in this mode. Only meaningful while `open`.
   */
  fill?: boolean
  /**
   * Phone shell: fill the view (no dragged width, no handle) and drop the card
   * — no `bg-panel`, no rounding, no elevation — so the editor reads on the same
   * plain background as the chat.
   */
  phone?: boolean
}

/** Whether the frontmatter card is expanded or collapsed — a global
 *  preference (like the shell rail / auto-collapse cookies in
 *  `app-shell.tsx`), not per-note: it's a viewing convenience, not part of
 *  the note's own state. */
const FRONTMATTER_VISIBLE_COOKIE = "sympose:pref.frontmatterExpanded"

/** Whether the panel is locked to stylo's rendered `preview` mode — a global
 *  viewing preference (see `FRONTMATTER_VISIBLE_COOKIE` above), not per-note.
 *  Off (editable) by default, so existing notes open exactly as before. */
const NO_IDS: string[] = []
const NOTE_READ_ONLY_COOKIE = "sympose:pref.noteReadOnly"

/**
 * The markdown editor / reader — the middle stage panel, between `<ContentPanel>`
 * and the chat. When another panel sits to its right its right edge is a drag
 * handle (width free between a third and two-thirds of the stage, cookie-backed
 * via `storageKey`); when nothing does, pass `fill` and it takes the leftover
 * width instead.
 *
 * The editing surface is `stylo` (`@damiro/stylo`) in its default `in-place`
 * mode — frontmatter, headings, and wikilinks render inline in the canvas, so
 * there is no separate read-only mock to keep in sync with the real document.
 * `toolbar.sticky` is deliberately left unset: the panel already gives stylo a
 * bounded height (`min-h-0 flex-1`), so its own toolbar stays pinned as a plain
 * flex sibling of the scrolling canvas — no `position: fixed`, no watchdog.
 *
 * The toolbar's read/edit toggle flips `<Stylo>` to its `mode="preview"` —
 * stylo's separate rendered-Markdown view, real `<a>` tags and all — rather
 * than just setting `readOnly` on the in-place canvas. Two independent
 * reasons, the second decisive: under in-place's `reveal: "never"` a click on
 * a plain `[text](url)` link only opens its edit popup rather than
 * navigating (stylo's link-click plumbing doesn't gate on `readOnly` at all
 * — `@damiro/stylo/src/inplace/link-click.ts`); worse, in-place's right-click
 * menu and floating selection bar don't check `readOnly` either, and their
 * commands really do `view.dispatch()` real document changes rather than
 * silently no-op (`@damiro/stylo/src/inplace/menu-plugin.ts`,
 * `selection-bar.ts`) — so `readOnly` there is not actually a safe
 * read-only guarantee today, only a keyboard-input block. `preview` has no
 * CodeMirror instance at all, so none of that surface exists to misfire.
 * Preview's own typography not matching in-place's is a separate, tracked
 * gap (`stylo/docs/requests/`), not a reason to reconsider this. Because
 * stylo only calls
 * `toolbar.render` outside preview mode, the frontmatter/read-edit/`⋯`
 * buttons can't live inside that callback exclusively — they're rendered
 * once (`noteToolbarButtons`) and placed in two spots depending on mode: the
 * overlay on stylo's own bar in every other mode, or a plain row that
 * doubles as a clickable folder breadcrumb in preview mode, since stylo
 * mounts no toolbar of its own there.
 *
 * Loading is wired to the vault (`GET /api/vault/note`); saving goes back
 * through `PUT /api/vault/note`. `onSave` recombines the frontmatter
 * card's `---` block with stylo's body and writes the whole note verbatim —
 * driven by the toolbar `save` button and `⌘/Ctrl-S`, or automatically a beat
 * after typing stops when Settings › Markdown editor › Autosave is on.
 */
function MarkdownPanel({
  className,
  storageKey,
  path,
  persona = "samantha",
  personaName,
  vaultPath = null,
  onWikiLinkClick,
  wikiLinkSource,
  tagSource,
  embedSource,
  onRenamed,
  onDeleted,
  previewRequest = 0,
  isPinned,
  onTogglePin,
  onNavigateToRootFolder,
  vaultName,
  preferences,
  toolbarItems,
  onCollapse,
  file,
  reloadToken = 0,
  open = true,
  fill = false,
  phone = false,
  style,
  ...props
}: MarkdownPanelProps) {
  const wrapRef = React.useRef<HTMLDivElement>(null)
  const editorScrollRef = React.useRef<HTMLDivElement>(null)
  const { size, dragging, handleProps, availW, fillToggling } = usePanelSizing(wrapRef, fill, storageKey)

  // `accept` mode (docs/decisions/072): her edits applied to the editor's text stay pending on the server until the note
  // is saved. `appliedRef` is what the editor last reported; the document hook asks `heldRef` before an automatic save.
  const appliedRef = React.useRef<{ ids: string[]; untouched: boolean }>({ ids: [], untouched: true })
  const heldRef = React.useRef<() => boolean>(() => false)
  const savedRef = React.useRef<() => void>(() => {})
  const { note, frontmatter, setFrontmatter, body, setBody, frontmatterEditedRef, loadedPathRef, saveNote } =
    useNoteDocument({
      path,
      persona,
      vaultPath,
      file,
      reloadToken,
      autosave: preferences.autosave,
      holdAutomaticSave: () => heldRef.current(),
      onSaved: () => savedRef.current(),
    })
  React.useEffect(() => {
    heldRef.current = () => appliedRef.current.ids.length > 0 && appliedRef.current.untouched && !frontmatterEditedRef.current
  })
  // The chat sends the note as the editor holds it, with the user's message (docs/decisions/072). Not for a persona's
  // own file or a draft (`file`): there is no vault note to propose changes to.
  const bodyRef = React.useRef(body)
  React.useEffect(() => {
    bodyRef.current = body
  })
  React.useEffect(() => {
    if (!path || file) return
    setOpenNoteSource(() => (loadedPathRef.current === path ? { path, text: bodyRef.current } : null))
    return () => setOpenNoteSource(null)
  }, [path, file, loadedPathRef])
  // Expanded/collapsed state of the frontmatter card — toggled from the `⋯`
  // row, persisted globally (same convention as `app-shell.tsx`'s rail /
  // auto-collapse cookies).
  const [frontmatterVisible, setFrontmatterVisible] = React.useState(() =>
    getCookieBool(FRONTMATTER_VISIBLE_COOKIE, true)
  )
  React.useEffect(() => {
    setCookieBool(FRONTMATTER_VISIBLE_COOKIE, frontmatterVisible)
  }, [frontmatterVisible])
  // Read/edit toggle — locks the canvas to stylo's `preview` mode so a stray
  // keystroke or link click can't touch the note (see the doc comment above
  // for why that's `preview` rather than in-place `readOnly`).
  const [readOnly, setReadOnly] = React.useState(() =>
    getCookieBool(NOTE_READ_ONLY_COOKIE, false)
  )
  // A note opened from the chat (a link under a reply) is shown in preview mode: each new `previewRequest`
  // switches to it. Set at once rather than through the animated swap below, which only completes when the
  // toolbar row it animates is on screen; a note that is still loading, or a panel that was closed, has none.
  const [seenPreviewRequest, setSeenPreviewRequest] = React.useState(previewRequest)
  if (previewRequest !== seenPreviewRequest) {
    setSeenPreviewRequest(previewRequest)
    if (previewRequest > 0) setReadOnly(true)
  }
  React.useEffect(() => {
    setCookieBool(NOTE_READ_ONLY_COOKIE, readOnly)
  }, [readOnly])
  // The toolbar-row swap (stylo's bar <-> the breadcrumb): the outgoing row finishes its slide-out before
  // `readOnly` flips (see `useReadOnlyToggle`).
  const {
    exiting: readOnlyExiting,
    entering: readOnlyEntering,
    toggle: toggleReadOnly,
    onAnimationEnd: onToggleAnimationEnd,
  } = useReadOnlyToggle(readOnly, setReadOnly)
  const { surface, reveal, selectionUI, tableEditing, focusOutline } = preferences

  // The persona's suggested changes and the user's comments on this note (docs/decisions/070): drawn in the text by
  // extensions handed to stylo, with each change's own Accept and Decline there and the whole note's on the toolbar.
  // A persona's own file has none. The extensions array is memoized (stylo reconfigures the live editor when it
  // changes, so a new array per render would redo that every keystroke); what they read is kept in refs.
  const styloRef = React.useRef<StyloHandle>(null)
  const { changes, resolve: resolveChanges, refresh: refreshChanges } = usePersonaChanges({ path, persona, enabled: !file })
  const [commentBox, setCommentBox] = React.useState<CommentBox | null>(null)
  // A box opened on one note is closed when another is opened, or a comment written for one could be saved onto the other.
  const [commentBoxPath, setCommentBoxPath] = React.useState(path)
  if (commentBoxPath !== path) {
    setCommentBoxPath(path)
    setCommentBox(null)
  }
  // Her edits already applied to the text are not waiting any more: they are drawn as applied, not as tracked changes,
  // and are not listed as outdated now that their old words are gone.
  // Counts the editors made (stylo makes its editor after a lazy load, possibly after everything else has arrived).
  const [editorMade, setEditorMade] = React.useState(0)
  const [applied, setApplied] = React.useState<{ path?: string; ids: string[] }>({ ids: [] })
  const appliedIds = applied.path === path ? applied.ids : NO_IDS
  const reviewData = React.useMemo<ReviewData>(
    () => ({
      proposals: (changes?.proposals ?? []).filter((p) => !appliedIds.includes(p.id)),
      annotations: changes?.annotations ?? [],
    }),
    [changes, appliedIds]
  )
  const reviewDataRef = React.useRef(reviewData)
  const resolveRef = React.useRef(resolveChanges)
  const pathRef = React.useRef(path)
  React.useEffect(() => {
    reviewDataRef.current = reviewData
    resolveRef.current = resolveChanges
    pathRef.current = path
  })
  // Another note: nothing is applied there yet. (After the cleanups of the effects above have run, so a leave-note flush
  // still sees what was held.)
  React.useEffect(() => {
    appliedRef.current = { ids: [], untouched: true }
  }, [path])
  // The note was written: what she applied is accepted now, so the server forgets it and the marks end.
  React.useEffect(() => {
    savedRef.current = () => {
      const view = styloRef.current?.getView()
      const ids = new Set([...(view ? clearApplied(view) : []), ...appliedRef.current.ids])
      appliedRef.current = { ids: [], untouched: true }
      setApplied({ path: pathRef.current, ids: [] })
      if (ids.size > 0) void resolveRef.current([...ids])
    }
  })
  const reviewExt = React.useMemo(
    () =>
      // eslint-disable-next-line react-hooks/refs -- the two callbacks run when the editor is made and when a change is accepted or declined, never during render
      reviewExtensions({
        initial: () => reviewDataRef.current,
        onResolve: (ids) => void resolveRef.current(ids),
        onReady: () => setEditorMade((n) => n + 1),
        onApplied: (ids, untouched) => {
          appliedRef.current = { ids, untouched }
          setApplied({ path: pathRef.current, ids })
        },
        onOpenComment: (id, rect) => setCommentBox({ kind: "thread", id, rect }),
      }),
    []
  )
  // New data reaches an editor that is already open; one that opens later starts from `initial`.
  React.useEffect(() => {
    styloRef.current?.getView()?.dispatch({ effects: setReviewData.of(reviewData) })
  }, [reviewData, reviewExt])
  // `accept`: her placed, waiting edits go into the text as soon as they are here, once the editor holds the note. Run
  // when any of that changes, and when the editor itself is made (it can come last, after a lazy load).
  const { info: editInfo } = useEditMode(persona, persona)
  const acceptMode = editInfo?.mode === "accept" && !readOnly && !file
  React.useEffect(() => {
    const view = styloRef.current?.getView()
    if (!acceptMode || !view || note.status !== "ready" || loadedPathRef.current !== path) return
    applyProposals(view, pendingIds(view.state))
  }, [acceptMode, note.status, path, loadedPathRef, reviewData, body, editorMade])
  const outdatedProposals = React.useMemo(() => classify(body, reviewData.proposals).outdated, [body, reviewData])
  // Accepting the whole note changes the text, and the save writes what the text is by then: it waits for the
  // change to reach `body` (`saveNote` closes over it) instead of saving the text from before.
  const saveAfterAcceptRef = React.useRef(false)
  React.useEffect(() => {
    if (!saveAfterAcceptRef.current) return
    saveAfterAcceptRef.current = false
    void saveNote()
  }, [body, saveNote])
  const hasProposals = reviewData.proposals.length > 0
  const acceptNote = React.useCallback(() => {
    saveAfterAcceptRef.current = true
  }, [])
  const declineNote = React.useCallback(() => void resolveRef.current("all"), [])
  const commentItem = React.useMemo(() => commentToolbarItem((target) => setCommentBox({ kind: "compose", target })), [])
  const commentMenu = React.useMemo(() => [commentMenuItem((target) => setCommentBox({ kind: "compose", target }))], [])
  const toolbarWithReview = React.useMemo<ToolbarItem[]>(
    () => [
      ...toolbarItems,
      "|",
      commentItem,
      // eslint-disable-next-line react-hooks/refs -- the two callbacks run when a toolbar button is pressed, never during render
      ...(hasProposals ? ["|" as const, ...reviewToolbarItems({ onAcceptNote: acceptNote, onDeclineNote: declineNote })] : []),
    ],
    [toolbarItems, commentItem, hasProposals, acceptNote, declineNote]
  )

  // stylo's `canvasHeader` (>=0.11.0) is read once, at mount — same contract
  // as `inPlace`/`wikiLinkSource` (see `wikiLinkSource` prop doc above). The
  // function identity handed to `<Stylo>` has to survive `frontmatter`/
  // `onWikiLinkClick`/`phone` changing without a remount, so it reads them
  // off a ref kept current every render instead of closing over them directly.
  const frontmatterCardStateRef = React.useRef({
    frontmatter,
    onWikiLinkClick,
    phone,
    frontmatterVisible,
    readOnly,
    banner: file?.banner,
    outdated: [] as Proposal[],
    onDecline: (() => {}) as (ids: string[]) => void,
  })
  // Deliberately synchronous, not effect-deferred: `canvasHeader()` below is
  // invoked directly in this component's own render (the read-only branch
  // further down), in the same pass — an effect-deferred write would still
  // be showing last render's values by the time that call reads the ref.
  // eslint-disable-next-line react-hooks/refs -- see comment above
  frontmatterCardStateRef.current = {
    frontmatter,
    onWikiLinkClick,
    phone,
    frontmatterVisible,
    readOnly,
    banner: file?.banner,
    outdated: readOnly || file ? [] : outdatedProposals,
    onDecline: (ids: string[]) => void resolveChanges(ids),
  }
  const canvasHeader = React.useCallback(() => {
    const { frontmatter, onWikiLinkClick, phone, frontmatterVisible, readOnly, banner, outdated, onDecline } =
      frontmatterCardStateRef.current
    // A persona's file has no frontmatter card; what is particular to it (docs/decisions/061) takes the place.
    if (banner) return <div className={cn("mt-2", phone ? "px-2" : "px-4 sm:px-6")}>{banner}</div>
    const outdatedStrip =
      outdated.length > 0 ? <OutdatedChanges proposals={outdated} onDecline={onDecline} className={cn("mt-2", phone ? "mx-2" : "mx-4 sm:mx-6")} /> : null
    if (frontmatter === null) return outdatedStrip
    // Animate via `grid-template-rows` rather than `max-height` — it tweens
    // to the card's real content height with no guessed cap, and (unlike a
    // hardcoded `max-height`) never needs revisiting if the card's content
    // grows a row. The `overflow-hidden` inner wrapper is what actually
    // clips it; the outer grid is what animates.
    return (
      <>
        <div
          className={cn(
            "grid transition-[grid-template-rows] duration-mode ease-mode",
            frontmatterVisible ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          )}
        >
          <div className="overflow-hidden">
            <FrontmatterCard
              raw={frontmatter}
              onChange={(raw) => {
                // A real card edit — from here on the block is re-serialised on
                // save rather than kept verbatim.
                frontmatterEditedRef.current = true
                setFrontmatter(raw)
              }}
              onLinkClick={onWikiLinkClick}
              readOnly={readOnly}
              className={cn("mt-2", phone ? "px-2" : "px-4 sm:px-6")}
            />
          </div>
        </div>
        {outdatedStrip}
      </>
    )
  }, [frontmatterEditedRef, setFrontmatter])

  // Outbound `[[wikilinks]]` for the footer — derived from the note as loaded,
  // not from live keystrokes, so typing never re-scans the whole document.
  const links = React.useMemo(
    () => (note.status === "ready" && !file ? extractWikilinks(note.content) : []),
    [note, file]
  )

  // The frontmatter/read-edit/note-actions buttons — a single stable overlay
  // (see the render tree below) that never unmounts across the read/edit
  // toggle, so the icons themselves never animate or flicker; only the
  // content behind them (stylo's bar vs. the breadcrumb) swaps.
  const noteToolbarButtons = path && (
    <>
      {frontmatter !== null && (
        <button
          type="button"
          aria-label={frontmatterVisible ? "Hide frontmatter" : "Show frontmatter"}
          aria-pressed={frontmatterVisible}
          onClick={() => setFrontmatterVisible((v) => !v)}
          className={cn(
            "grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
            frontmatterVisible && "bg-accent text-foreground"
          )}
        >
          {TOOLBAR_ICONS.frontmatter}
        </button>
      )}
      <button
        type="button"
        aria-label={readOnly ? "Switch to edit mode" : "Switch to read mode"}
        aria-pressed={readOnly}
        // Starts the exit half of the swap rather than flipping `readOnly`
        // directly — the exiting row's own `animationend` (`onToggleAnimationEnd`)
        // is what actually changes it.
        onClick={toggleReadOnly}
        disabled={readOnlyExiting}
        className={cn(
          "grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-60",
          readOnly && "bg-accent text-foreground"
        )}
      >
        <HugeiconsIcon
          icon={readOnly ? PencilEdit01Icon : BookOpen01Icon}
          className="size-4"
        />
      </button>
      {!file && (
        <NoteActionsMenu
          path={path}
          persona={persona}
          onRenamed={async (next) => {
            // The file has moved: save this note's unsaved edits to its new path now, while the buffer still
            // belongs to it, instead of letting the leave-note flush PUT to the old path (404, edits lost).
            if (path) await getUnsavedGuard()?.retarget(path, next)
            onRenamed?.(next)
          }}
          onDeleted={() => {
            // Nothing to save to: the flush would PUT to a path that no longer exists.
            loadedPathRef.current = undefined
            onDeleted?.()
          }}
          pinned={!!isPinned?.(path)}
          onTogglePin={onTogglePin}
        />
      )}
    </>
  )

  const breadcrumb = file ? (
    <div className="flex min-w-0 flex-1 items-center overflow-hidden font-mono text-xs text-fg-muted">
      <span className="truncate text-foreground">{file.title}</span>
    </div>
  ) : (
    <NoteBreadcrumb path={path} vaultName={vaultName} onNavigateToRootFolder={onNavigateToRootFolder} />
  )

  // Clicking a task checkbox in read mode (stylo >=0.15.0, `preview`-only —
  // it's a no-op prop outside that mode) splices the new marker straight
  // into `body`. This is the one deliberate mutation read mode allows: unlike
  // the stray-keystroke/link-popup/menu-command misfires the doc comment
  // above explains `preview` was chosen to avoid, a checkbox click is exactly
  // as scoped and intentional as the read/edit toggle button itself. It rides
  // the same persistence path as any other edit (autosave if on, otherwise
  // the explicit save button or the leave-note flush) rather than a
  // special-cased immediate write.
  const handleTaskToggle = React.useCallback(({ start, end, checked }: TaskToggleInfo) => {
    setBody((prev) => prev.slice(0, start) + (checked ? "[x]" : "[ ]") + prev.slice(end))
  }, [setBody])

  // Built once and placed in one of two tree positions below depending on
  // `readOnly` (bare, or nested one level inside the `.sy-note-preview`
  // wrapper) rather than duplicated across two JSX branches with the same
  // long prop list.
  const styloElement = (
    <Stylo
      ref={styloRef}
      key={`${path}:${surface}:${reveal}:${selectionUI}:${tableEditing}:${readOnly}`}
      value={body}
      onChange={setBody}
      onSave={() => void saveNote()}
      onWikiLinkClick={onWikiLinkClick}
      wikiLinkSource={wikiLinkSource}
      tagSource={tagSource}
      embedSource={embedSource}
      onLinkClick={openMarkdownLink}
      onTaskToggle={handleTaskToggle}
      mode={readOnly ? "preview" : surface}
      softBreaks
      inPlace={{ reveal, selectionUI, table: tableEditing, ...(file ? {} : { contextMenu: { items: commentMenu } }) }}
      canvasHeader={readOnly ? undefined : canvasHeader}
      extensions={readOnly || file ? undefined : reviewExt}
      toolbar={{
        items: readOnly || file ? toolbarItems : toolbarWithReview,
        // One row: what does not fit folds into a trailing `⋯` menu instead of wrapping (stylo >=0.18.0).
        overflow: "menu",
        render: (bar) => (
          // stylo's toolbar row. The note-actions overlay used to live here
          // too; it's now the fixed sibling above, so this only ever wraps
          // `bar` itself. `min-h-9.25` matches the read-mode breadcrumb
          // row's own floor (see below) — belt-and-braces, since `bar`'s
          // natural height already comes out the same. Only ever rendered
          // outside preview mode — stylo doesn't call this at all once
          // `mode` above resolves to "preview". `bar`'s own bottom border is
          // switched off (`[role="toolbar"]` in index.css) in favor of this
          // outer shell's — a static `border-b` that isn't part of the
          // animation, same split as the breadcrumb row below. The inner
          // `.sy-note-chrome` marker carries no classes of its own — both
          // the read/edit toggle and a note switch drive its vertical slide
          // from `editorScrollRef`'s wrapper below (`TOGGLE_CONTENT_EXIT`/
          // `_ENTER`) and the note-switch wrapper (`slideExitClassName`/
          // `slideEnterClassName`) respectively, via scoped descendant
          // selectors — the same one marker serves both animations.
          <div className={cn("min-h-9.25 border-b border-border", onCollapse && "ps-7.5", path && "pe-24")}>
            <div className="sy-note-chrome">{bar}</div>
          </div>
        ),
      }}
      icons={TOOLBAR_ICONS}
      codeLanguages={CODE_LANGUAGES}
      placeholder="Start writing…"
      className="h-full min-h-0 flex-1"
    />
  )

  // Sideways slide keyed on the open note — there's no back/forward concept
  // for the editor (unlike the content panel), so every note switch (a
  // wikilink, a vault-tree pick, a new note) reads as "forward": it's always
  // pushing a new destination. Sequential rather than a crossfade: the
  // outgoing note finishes sliding out before the incoming one starts
  // sliding in (see `useSlideSwap`).
  const noteBody = (
    <>
      {note.status === "empty" && (
        <EmptyState icon={File01Icon} title="No note open" description="Select a note to open it here." />
      )}

      {note.status === "loading" && (
        <div className="grid flex-1 place-items-center px-6 text-center text-sm text-fg-muted">
          Loading…
        </div>
      )}

      {note.status === "error" && (
        <EmptyState icon={Alert02Icon} title="Couldn't load this note" />
      )}

      {note.status === "ready" && (
        // stylo owns its own toolbar + scrolling canvas as one bounded flex
        // column (`min-h-0` here is what lets its `flex: 1 1 auto` surface
        // scroll internally instead of the toolbar scrolling away with it).
        // The key remounts on a note switch (so CodeMirror's undo history and
        // selection never leak from one note into another) and on a surface/
        // reveal/selectionUI/tableEditing change from Settings — `inPlace`
        // config and mode are both applied-at-mount, per stylo's own
        // documented contract.
        //
        // Full panel width, no reading-column cap — the frontmatter card
        // shares it. The frontmatter card rides `canvasHeader` (stylo
        // >=0.11.0), which docks it *inside* the editing surface, under
        // CodeMirror's own find/replace panel and above the document body
        // — the toolbar row (with the note-actions `⋯`) stays a separate,
        // non-scrolling sibling above the whole canvas.
        <div
          ref={editorScrollRef}
          data-focus-outline={focusOutline}
          // Drives the read/edit toggle's content-vs-chrome split
          // (`TOGGLE_CONTENT_EXIT`/`_ENTER`, via `readOnlyExiting`/
          // `readOnlyEntering`) and catches its `onAnimationEnd` — this
          // wrapper is stable across the toggle (only its children swap),
          // unlike the note-switch slide below, which instead rides its own
          // outer key'd wrapper. Both sets of scoped selectors target the
          // same `.cm-scroller`/`.sy-note-preview` (content) and
          // `.sy-note-chrome` (toolbar/breadcrumb) descendants, so it's
          // essential this only ever carries `TOGGLE_CONTENT_ENTER` for the
          // entering animation's own actual duration (`readOnlyEntering`) —
          // never indefinitely once settled — or its `.sy-note-chrome` rule
          // would permanently fight the note-switch slide's own rule on that
          // same element (see `readOnlyEntering`'s own doc comment above).
          className={cn(
            "group/scroll-thumb relative flex min-h-0 w-full flex-1 flex-col text-sm leading-relaxed",
            readOnlyExiting
              ? TOGGLE_CONTENT_EXIT
              : readOnlyEntering && TOGGLE_CONTENT_ENTER
          )}
          // Chrome is the sole trigger for both the commit and settling the enter phase (see
          // `useReadOnlyToggle`).
          onAnimationEnd={onToggleAnimationEnd}
        >
          {path && (
            // The frontmatter/read-edit/`⋯` buttons — a fixed overlay that
            // never unmounts across the read/edit toggle (unlike the content
            // behind it, which swaps between stylo's own bar and the
            // breadcrumb below), so the icons themselves never animate.
            // `top-1`: centers a 28px (`size-7`) button in the 37px row both
            // variants below are pinned to.
            <div className="absolute top-1 right-1.5 z-10 flex items-center gap-0.5">
              {noteToolbarButtons}
            </div>
          )}
          {readOnly && path && (
            // Read mode's stand-in for stylo's own (hidden, per the file doc
            // comment) formatting toolbar — the note's vault path. A sibling
            // of `.sy-note-preview` below, not nested inside it: nesting it
            // would drag the breadcrumb along with that box's own horizontal
            // note-switch slide, when it's meant to move only vertically
            // (`.sy-note-chrome`, see `TOGGLE_CONTENT_EXIT`/`_ENTER` above
            // and `slideExitClassName`/`slideEnterClassName` in
            // `use-slide-swap.ts`). `min-h-9.25` matches stylo's own
            // `.toolbar` row exactly (28px buttons + 4px padding top/bottom
            // + 1px border) so toggling never jumps the canvas below it —
            // same value the edit-mode wrapper pins to. The border lives on
            // this outer row, which carries no classes of its own driving an
            // animation — it's mounted for as long as this branch is
            // (through the whole read/edit exit sequence, since `readOnly`
            // doesn't flip until the exit's `animationend` commits it), so the line
            // itself never slides or fades; only the `.sy-note-chrome`
            // breadcrumb inside does.
            <div className={cn("flex min-h-9.25 shrink-0 items-center border-b border-border pr-24", onCollapse ? "pl-9" : "pl-1.5")}>
              <div className="sy-note-chrome flex min-w-0 flex-1">
                {breadcrumb}
              </div>
            </div>
          )}
          {readOnly ? (
            // A plain flex column standing in for `<Stylo>`'s own toolbar+
            // canvas column below, not `<Stylo>` itself — the icon overlay
            // above and the breadcrumb row above both stay outside it on
            // purpose (see their own comments).
            <div className="sy-note-preview flex min-h-0 flex-1 flex-col">
              {/* eslint-disable-next-line react-hooks/refs -- frontmatterCardStateRef
                  is written synchronously just above in this same render, see its
                  comment; this read is always current, never stale. */}
              {canvasHeader()}
              {styloElement}
            </div>
          ) : (
            styloElement
          )}
          <ScrollThumb containerRef={editorScrollRef} getScroller={getStyloScroller} />
          <CodeBlockCopyButtons containerRef={editorScrollRef} active={readOnly} />
          {links.length > 0 && (
            <NoteLinksFooter links={links} phone={phone} onWikiLinkClick={onWikiLinkClick} />
          )}
        </div>
      )}
    </>
  )
  // `hasToolbar`/`chromeAnimates` ride frozen alongside the note they
  // describe — an exiting "ready" note must still know to scope its
  // slide-out to `.cm-scroller` (and whether its chrome row was the
  // breadcrumb or stylo's own toolbar) once the live `note.status`/`readOnly`
  // have already moved past it.
  const {
    displayKey: noteDisplayKey,
    displayPayload: notePayload,
    exitDirection: noteExitDirection,
    enterDirection: noteEnterDirection,
    onExitComplete: onNoteExitComplete,
    onEnterComplete: onNoteEnterComplete,
  } = useSlideSwap(
    path ?? "__empty__",
    { node: noteBody, hasToolbar: note.status === "ready", chromeAnimates: readOnly },
    "forward"
  )
  // Stylo bundles its own toolbar and the CodeMirror canvas into one mounted
  // tree (`toolbar`/`inplace` panes under one shared root — see its
  // stylesheet), so sliding the whole ready-state block would drag the
  // toolbar along with the document. `.cm-scroller` is CodeMirror's own
  // stable, public scroll-viewport class (already relied on for
  // `<ScrollThumb>` above) — scoping the slide to it keeps the toolbar
  // planted while just the document surface moves. In `readOnly` (preview)
  // there's no `.cm-scroller` at all — `.sy-note-preview` (the wrapper
  // above, around the breadcrumb + rendered body) is the equivalent target
  // `slideExitClassName`/`slideEnterClassName` also scope to, which is what
  // makes browsing the vault while read-only slide instead of sitting
  // frozen (no matching descendant to animate at all, previously).
  const noteSlideScope = notePayload.hasToolbar
  // Only the breadcrumb's content (the vault path) actually changes across a
  // note switch — stylo's own edit-mode toolbar renders the same buttons for
  // every note, so animating it on every switch was motion with nothing
  // behind it to justify it (see `slideExitClassName`'s `animateChrome` doc).
  const noteChromeAnimates = notePayload.chromeAnimates

  return (
    <div
      ref={wrapRef}
      data-slot="markdown-panel"
      data-state={open ? "open" : "closed"}
      data-dragging={dragging || undefined}
      data-phone={phone || undefined}
      className={cn(
        // same wrapper insets as <ContentPanel>: py-2 top/bottom margin, pe-2
        // right margin — so the gap to <ContentPanel> (its pe-2), the gap to the
        // chat (this pe-2), and the panel's top/bottom margins are all one step.
        // z-10: sits below <ContentPanel> (z-20) but above the chat slot (z-0),
        // so a parked panel is always hidden behind its left-hand neighbour and
        // appears to slide out from that neighbour's right edge.
        "group/md z-10 min-w-0 data-dragging:select-none",
        phone
          ? // phone: one surface at a time — an absolute layer that crossfades
            // and slides a touch from the left on reveal
            "absolute inset-0 flex flex-col transition-[opacity,translate] duration-mode ease-mode"
          : cn(
              "relative shrink-0 py-2 pe-2 transition-[margin,opacity] duration-mode ease-mode data-dragging:transition-none",
              // max-width only transitioned while `fill` flips — otherwise it
              // follows the live measurement so the editor glides with a
              // neighbour's slide rather than lagging it
              fillToggling && "transition-[margin,opacity,max-width]"
            ),
        phone && !open && "-translate-x-3",
        // explicit both ways — the stage it sits in is `pointer-events-none`
        // so the ambient nebula (always the bottom of the stack) can be
        // clicked through any *other* empty stretch of it.
        open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        className
      )}
      style={
        phone
          ? style
          : {
              // Always growable, but clamped: to the dragged width normally, to
              // the space actually free to its right when filling. Both are real
              // measured pixels, so animating the clamp tweens the editor across
              // the whole distance as the content panel comes and goes. (An
              // oversized clamp like `100vw` would burn most of the duration
              // invisibly, then snap — the old jerk.)
              flexBasis: size,
              flexGrow: 1,
              maxWidth: fill ? availW || size : size,
              marginInlineStart: open ? 0 : -size,
              ...style,
            }
      }
      {...props}
    >
      {/* the working surface — a raised panel card on the stage (frosted over
          the ambient nebula); on phone it drops to the plain background */}
      <div
        className={cn(
          "relative flex h-full w-full flex-col overflow-hidden",
          phone
            ? "text-foreground"
            : "rounded-lg sy-frosted-panel text-panel-foreground"
        )}
      >
        <div
          key={noteDisplayKey}
          className={cn(
            "flex h-full w-full flex-col",
            noteExitDirection
              ? slideExitClassName(noteExitDirection, noteSlideScope, noteChromeAnimates)
              : noteEnterDirection &&
                  slideEnterClassName(noteEnterDirection, noteSlideScope, noteChromeAnimates)
          )}
          // Content (`.cm-scroller`/`.sy-note-preview`/`.sy-note-footer`,
          // `duration-thumb`) is the sole trigger for both completion
          // callbacks — `.sy-note-chrome`'s own faster `duration-snappy`
          // slide (see `slideExitClassName`/`slideEnterClassName`) settles
          // first and must never fire either one early, which would commit
          // the swap (or drop `entered`) while content is still mid-slide.
          onAnimationEnd={(e) => {
            // Only the slot itself or the three scoped content elements count;
            // chrome and any other descendant's animation must not commit.
            const target = e.target as HTMLElement
            if (
              target !== e.currentTarget &&
              !target.matches(".cm-scroller, .sy-note-preview, .sy-note-footer")
            ) {
              return
            }
            if (noteExitDirection) onNoteExitComplete()
            else if (noteEnterDirection) onNoteEnterComplete()
          }}
        >
          {notePayload.node}
        </div>
        {onCollapse && (
          // The collapse button: the far-left counterpart of the note's own buttons at the far right, a fixed overlay
          // on the card itself (not inside the slide-swapped note) so it stays put across a note switch, the read/edit
          // toggle, and an empty or loading editor. The toolbar and the read-mode path row are inset to clear it.
          <div className="absolute top-1 left-1.5 z-10">
            <PanelCollapseButton label="Collapse the editor" onClick={onCollapse} />
          </div>
        )}
      </div>

      {/* right-edge resize handle — mirrors <ContentPanel>; gone when filling
          or on phone (full-view, no dragged width) */}
      {!fill && !phone && (
        <div
          {...handleProps}
          aria-label="Resize editor"
          className="group/md-handle absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize touch-none"
        >
          <span className="absolute inset-y-0 right-0 w-px bg-transparent transition-colors group-hover/md-handle:bg-border group-focus-visible/md-handle:bg-brand group-data-dragging/md:bg-brand" />
        </div>
      )}
      {/* comments on the open note (docs/decisions/069): opens on the selected words or on a highlighted passage; a
          persona's own file has none */}
      {path && !file && (
        <CommentPopover
          key={path}
          box={commentBox}
          annotations={reviewData.annotations}
          personaName={personaName ?? persona.charAt(0).toUpperCase() + persona.slice(1)}
          path={path}
          persona={persona}
          onClose={() => setCommentBox(null)}
          onChanged={() => {
            refreshChanges()
            announceDraftsChanged() // the note may now (no longer) have an open comment
          }}
        />
      )}
    </div>
  )
}

export { MarkdownPanel, TOOLBAR_ICONS }
