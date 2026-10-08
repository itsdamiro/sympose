import * as React from "react"

import { cn } from "@/lib/utils"
import { useBreakpoint } from "@/lib/use-breakpoint"
import { usePanels } from "@/lib/use-panels"
import { useNebulaStage } from "@/lib/use-nebula-stage"
import { useSelectedNote } from "@/lib/use-selected-note"
import { usePersonaFileEditor } from "@/lib/use-persona-file-editor"
import { useDraftEditor } from "@/lib/use-draft-editor"
import { useEditMode } from "@/lib/use-edit-mode"
import { useDrafts } from "@/lib/use-drafts"
import { usePersonaFiles } from "@/lib/use-persona-files"
import { useVaults, useVaultSwitching } from "@/lib/use-vaults"
import { useMenuCollapse } from "@/lib/use-menu-collapse"
import { useMenuItems } from "@/lib/use-menu-items"
import { useShellNavigation } from "@/lib/use-shell-navigation"
import { SECTION_LABELS, sectionAfterFolderMove } from "@/lib/shell-sections"
import { useSectionHistory } from "@/lib/use-section-history"
import { useVaultRefresh } from "@/lib/use-vault-refresh"
import { useCreateField, useCreateSubmit, type CreateKind } from "@/lib/use-create-flow"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import { deleteVaultFolder } from "@/lib/vault-note-api"
import { useChatSession } from "@/lib/use-chat-session"
import { useSessionList } from "@/lib/use-session-list"
import { usePersonaRoster } from "@/lib/use-persona-roster"
import { useConfirmations } from "@/lib/use-confirmations"
import { announceSettingsChanged } from "@/lib/settings-changed"
import { PersonaRequestCard } from "@/components/sympose/persona-request-card"
import { SettingRequestCard } from "@/components/sympose/setting-request-card"
import { useNoteChanges } from "@/lib/use-note-changes"
import { announceFolderMoved } from "@/lib/folder-moved"
import { useFolderView } from "@/lib/use-folder-view"
import { useVaultSearch } from "@/lib/use-vault-search"
import { useVaultTree } from "@/lib/use-vault-tree"
import { useActivePersona } from "@/lib/use-active-persona"
import { useEditorPreferences } from "@/lib/use-editor-preferences"
import { useToolbarItems } from "@/lib/use-toolbar-items"
import { usePinnedNotes } from "@/lib/use-pinned-notes"
import { useRecentNotes } from "@/lib/use-recent-notes"
import { useNotificationPreferences } from "@/lib/use-notification-preferences"
import { useChatDisplayPreferences } from "@/lib/use-chat-display-preferences"
import { useNebulaPreferences } from "@/lib/use-nebula-preferences"
import { useNebulaGraph } from "@/lib/use-nebula-graph"
import { useBrandMarkLabel } from "@/lib/use-brand-mark-preference"
import { useNoteOpening } from "@/lib/use-note-opening"
import { useLinkSources } from "@/lib/use-link-sources"
import { useRelatedNotes } from "@/lib/use-related-notes"
import {
  ConversationList,
  PersonaCard,
  PersonaFileBanner,
  PersonaEditMenu,
  DraftBanner,
  ChatActionGroup,
  ContentPanel,
  ContentSlot,
  ContentToolbar,
  SettingsView,
  VaultFolderView,
  CloudNotice,
  AttachedChips,
  ModelPicker,
  FolderSetupDialog,
  FolderMoveDialog,
  RootCreateDialog,
  MainMenu,
  MarkdownPanel,
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  MENU_TRASH_ID,
  NebulaModeToggle,
  RecentNotesFooter,
  RelatedNotesFooter,
  SettingsChecks,
  ThemeToggle,
  PersonaSwitcher,
  TopBar,
} from "@/components/sympose"

// Lazy — pulls in `react-force-graph` / `d3-force`. Mounted only after first
// paint (see the idle gate below) so it never delays the shell's TTFT.
const AmbientNebula = React.lazy(() =>
  import("@/components/sympose/ambient-nebula").then((m) => ({
    default: m.AmbientNebula,
  }))
)

// Lazy — the chat stays out of the first page load (docs/decisions/044).
const ChatPanel = React.lazy(() =>
  import("@/components/sympose/chat-panel").then((m) => ({ default: m.ChatPanel }))
)

/**
 * `<MainMenu>` mounted as the real app shell — full viewport height, no demo
 * frame. The three stage panels (content, editor, chat) toggle independently;
 * tablet caps the stage at two (oldest-evicted, rightmost fills), phone at one.
 * All visibility + widths persist to cookies globally and are clamped to the
 * breakpoint on load.
 *
 * Phone keeps the exact tablet layout — a docked menu rail beside the stage —
 * with two changes: a fixed `<TopBar>` carries the brand mark, the vault
 * button, Settings, the account, and the chat actions; and the menu is hidden
 * by default, sliding in and out (the same park/reveal the panels use) from
 * that vault button.
 *
 * This file only composes: each concern (history, navigation, tree, search, create,
 * note changes, chat, ...) is its own hook in `lib/` and each block of markup its
 * own component in `components/sympose/` (docs/decisions/053).
 */
export function AppShell() {
  const rootRef = React.useRef<HTMLDivElement>(null)
  const breakpoint = useBreakpoint(rootRef)
  const panels = usePanels(breakpoint)
  const isPhone = breakpoint === "phone"

  const {
    active,
    setActive,
    canGoBack,
    canGoForward,
    goBack,
    goForward,
    contentDirection,
    setContentDirection,
  } = useSectionHistory()

  const menu = useMenuCollapse(breakpoint)

  const contentOpen = panels.isOpen("content")
  const editorOpen = panels.isOpen("editor")
  const chatOpen = panels.isOpen("chat")
  // On a desktop the three panels fit together, so the chat is always there and has no toggle; on a tablet it shares
  // the stage with one other panel, and on a phone it is one of the views, so those keep theirs.
  const chatPinned = breakpoint === "desktop"
  // Editor grows into the content panel's area when that's closed — but only
  // on the smaller breakpoints, where screen room is scarce, and only when
  // chat isn't also open to claim that same freed space. On desktop the
  // editor keeps its dragged, cookie-persisted width and the resize handle
  // stays live so that width is the user's to set. Content never grows — it
  // is navigation, it keeps its dragged width even when alone.
  const editorFill = editorOpen && !chatOpen && breakpoint !== "desktop"

  // Persona picker — the active persona is client state (a cookie), and the
  // roster is fetched once. Both feed the `MENU_ACCOUNT_ID` panel; the handle
  // is lifted here so the vault panels can scope their `?persona=` calls to it
  // once those land.
  const [activePersona, setActivePersona] = useActivePersona()
  const {
    chat,
    models,
    modelInUse,
    statusPhrases,
    contextFigure,
    switchModel,
    sharingState,
    setShared,
    cloudNotice,
  } = useChatSession(activePersona)
  const sessionList = useSessionList(activePersona, chat)
  // The conversation on screen, once it has been saved (a first reply is still in flight before that), so it can be pinned.
  const currentSession = sessionList.sessions.find((row) => row.current)
  const [editorPrefs, setEditorPref] = useEditorPreferences()
  const [toolbarItems, setToolbarItems] = useToolbarItems()

  const { vaultsState, setVaultsState } = useVaults()
  const [brandMarkLabel, setBrandMarkLabel] = useBrandMarkLabel()

  const { isPinned, togglePin, unpinMany, remapPin, remapPinFolder, pinnedPaths } = usePinnedNotes(
    vaultsState.active
  )
  const {
    recentPaths,
    shownCount,
    setShownCount,
    enabled: recentsEnabled,
    setEnabled: setRecentsEnabled,
    recordVisit,
    removeFromRecents,
    remapRecent,
    remapRecentFolder,
    clearRecents,
  } = useRecentNotes(vaultsState.active)
  const [notifyPrefs, setNotifyPref] = useNotificationPreferences()
  const [nebulaPrefs, setNebulaPref] = useNebulaPreferences()
  const [chatDisplayPrefs, setChatDisplayPref] = useChatDisplayPreferences()
  // Bumped after a note is created, or the active vault is switched, to
  // re-pull the tree, the nebula graph, and any live search so they follow
  // without a persona switch (a persona switch itself re-pulls them too).
  const { vaultRefreshKey, refreshVault } = useVaultRefresh()
  // Lifted here (not called inside `<AmbientNebula>`) so the one fetch also
  // backs `tagSource` below — the ambient layer and the editor's `#tag`
  // autocomplete share the same master graph instead of each hitting
  // `GET /api/vault/graph` on its own. Re-fetches when `vaultRefreshKey`
  // bumps or the active persona changes — the graph is scoped to the
  // persona's allowed folders (ADR 010).
  const { graph: nebulaGraph, source: nebulaGraphSource } = useNebulaGraph(
    vaultRefreshKey,
    vaultsState.active,
    activePersona
  )
  const explore = nebulaPrefs.interaction === "explore"
  // Explore is the one thing that hides the chat on a desktop (it clears the whole stage for the nebula); out of it,
  // the chat is always there, and is opened again if a saved layout had it closed.
  const openPanel = panels.open
  React.useEffect(() => {
    if (chatPinned && !explore && !chatOpen) openPanel("chat")
  }, [chatPinned, explore, chatOpen, openPanel])

  const { nebulaReady } = useNebulaStage(panels, nebulaPrefs.interaction)
  const { rosterPersonas, reloadRoster, activePersonaName, activePersonaModel, activePersonaVisuals } =
    usePersonaRoster({ activePersona, setActivePersona, modelInUse })
  // A persona's requests for the user's yes, drawn as cards under the reply that made them (docs/decisions/078).
  const confirmations = useConfirmations(activePersona, chat.sessionId, chat.turns, (accepted) => {
    reloadRoster()
    if (accepted.kind === "setting") announceSettingsChanged()
  })

  const { vaultTree, vaultName, hiddenState, isHidden, changeHidden, hideFromView, unhideFromView } =
    useVaultTree({ activePersona, vaultRefreshKey, refreshVault })
  // A persona's own files (docs/decisions/061): listed in the Persona page's FILES chip, and opened in the editor in
  // place of the vault note until a note is opened again.
  const personaFiles = usePersonaFiles(activePersona)
  const fileEditor = usePersonaFileEditor({
    handle: activePersona,
    personaName: activePersonaName,
    refreshFiles: personaFiles.refresh,
  })
  const { close: closePersonaFile } = fileEditor
  // The persona's drafts (docs/decisions/071), and the draft of a new note open in the editor, which has no file yet.
  const drafts = useDrafts(activePersona, vaultRefreshKey)
  const folderInView = React.useRef<string | undefined>(undefined)
  const draftEditor = useDraftEditor({
    handle: activePersona,
    personaName: activePersonaName,
    folder: () => folderInView.current,
    onAccepted: (path) => {
      refreshVault()
      selectNote(path)
      panels.open("editor")
    },
  })
  const { close: closeDraft } = draftEditor
  const { selectedNote, setSelectedNote, openableNote, selectNote: selectVaultNote, noteRenamed, folderRenamed: selectionFollows } =
    useSelectedNote({
      vaultPath: vaultsState.active,
      isHidden,
      recordVisit,
      remapPin,
      remapRecent,
      remapPinFolder,
      remapRecentFolder,
    })
  const selectNote = React.useCallback(
    (path: string) => {
      closePersonaFile()
      closeDraft()
      selectVaultNote(path)
    },
    [closePersonaFile, closeDraft, selectVaultNote]
  )
  const openDraft = (draft: { path: string; is_new: boolean }) => {
    if (!draft.is_new) return selectNote(draft.path)
    closePersonaFile()
    draftEditor.open(draft.path)
    panels.open("editor")
  }
  const openPersonaFile = (name: string) => {
    closeDraft()
    fileEditor.open(name)
    panels.open("editor")
  }
  const currentFileInfo = personaFiles.files.find((f) => f.name === fileEditor.current?.name)
  const personaFileChanged = () => {
    void personaFiles.refresh()
    fileEditor.reload() // the file changed on disk under the editor (a reset, an accepted rewrite)
  }
  // What the editor is told about a persona file: its load and save, and the strip that names the file and says what
  // is particular to it (docs/decisions/061).
  const panelFile = draftEditor.file && draftEditor.current
    ? {
        ...draftEditor.file,
        banner: (
          <DraftBanner
            name={drafts.find((d) => d.path === draftEditor.current?.path)?.name ?? draftEditor.current.path}
            onAccept={() => void draftEditor.accept()}
            onDecline={() => void draftEditor.decline()}
          />
        ),
      }
    : fileEditor.file && fileEditor.current
      ? {
          ...fileEditor.file,
          banner: (
            <PersonaFileBanner
              title={fileEditor.file.title}
              handle={activePersona}
              name={fileEditor.current.name}
              info={currentFileInfo}
              onChanged={personaFileChanged}
            />
          ),
        }
      : undefined
  const {
    pendingCreate,
    createName,
    setCreateName,
    creating,
    setCreating,
    closeCreate,
    toggleCreate,
    noteInputRef,
    folderInputRef,
  } = useCreateField()
  // The vault panel shows the bin instead of the tree when the main-menu
  // Bin row is the active section.
  const trashView = active === MENU_TRASH_ID
  const { handleSwitchVault, handleAddVault } = useVaultSwitching({
    setVaultsState,
    setSelectedNote,
    refreshVault,
  })

  const { menuItems, noteIds } = useMenuItems(vaultTree, editorPrefs.hideExtension === "on")

  const { previewRequest, openWikilink, openGroundedNote, openChatWikilink } =
    useNoteOpening({
      vaultTree,
      selectNote,
      openEditor: () => panels.open("editor"),
    })
  // She opened a note for the user: show it, once for each request.
  const shownNote = chat.shownNote
  React.useEffect(() => {
    if (shownNote) openGroundedNote(shownNote.path)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only a new request opens a note, not a new tree
  }, [shownNote])
  // The notes close in meaning to the vault note open in the editor (docs/decisions/066): a section of the notes
  // panel's footer, never asked for while a persona's own file is open.
  const related = useRelatedNotes(fileEditor.path ? undefined : openableNote, activePersona)
  const showRelated = related.enabled && related.related.some((note) => !note.hidden)
  const { wikiLinkSource, tagSource, embedSource } = useLinkSources(
    vaultTree,
    nebulaGraph,
    activePersona
  )

  const { menuShown, isSentinel, resolvedActive, revealMenu, selectSection } =
    useShellNavigation({
      isPhone,
      panels,
      active,
      setActive,
      setContentDirection,
      menuItems,
      noteIds,
      selectNote,
      closeCreate,
    })

  const { activeNode, panelNodes, activeRootFolder, pinnedNodes, pinnedShowPath, recentNodes } =
    useFolderView({ vaultTree, resolvedActive, pinnedPaths, recentPaths })
  // Where a new note she proposed is made when accepted: the folder the user is in (ADR 071).
  React.useEffect(() => {
    folderInView.current = activeRootFolder?.path
  }, [activeRootFolder])

  // what the toolbar's search field searches on this page (docs/decisions/065)
  const searchScope =
    resolvedActive === MENU_SETTINGS_ID ? "settings" : resolvedActive === MENU_ACCOUNT_ID ? "conversations" : "vault"
  const {
    vaultSearch,
    setVaultSearch,
    searchOpen,
    setSearchOpen,
    closeSearch,
    searchInputRef,
    vaultSearchQuery,
    searchedPanelNodes,
    contentMatches,
    beyondFolderMatches,
  } = useVaultSearch({
    panelNodes,
    resolvedActive,
    isSentinel,
    activePersona,
    vaultRefreshKey,
    scope: searchScope,
  })

  // Only gates the "this folder is empty" message — while searching, an
  // empty *current* folder shouldn't hide vault-wide matches found elsewhere.
  const panelEmpty = !vaultSearchQuery && panelNodes.length === 0

  const activeLabel = SECTION_LABELS[resolvedActive] ?? resolvedActive

  // A folder was renamed (docs/decisions/073): the pins, recents and open note under it follow, and so does the section
  // when the renamed folder is the one in view.
  const folderRenamed = React.useCallback(
    (oldFolder: string, newFolder: string) => {
      selectionFollows(oldFolder, newFolder)
      announceFolderMoved(oldFolder, newFolder)
      const next = sectionAfterFolderMove(active, oldFolder, newFolder)
      if (next !== active) setActive(next)
    },
    [selectionFollows, active, setActive]
  )

  const { moveNote, moveFolder, folderMoveAsk, closeFolderMoveAsk, vaultTreeActions, onEditorRenamed, onEditorDeleted } = useNoteChanges({
    activePersona,
    selectedNote,
    setSelectedNote,
    openableNote,
    selectNote,
    noteRenamed,
    folderRenamed,
    refreshVault,
    openEditor: () => panels.open("editor"),
    hideFromView,
    isPinned,
    togglePin,
    unpinMany,
    removeFromRecents,
    clearRecents,
    hideExtension: editorPrefs.hideExtension === "on",
  })

  const { submitCreate, createAtRoot, openDefinition, folderSetup, closeFolderSetup } = useCreateSubmit({
    field: { pendingCreate, createName, creating, setCreating, closeCreate },
    folder: activeNode?.type === "folder" ? resolvedActive : "",
    activePersona,
    refreshVault,
    selectNote,
    openEditor: () => panels.open("editor"),
  })

  // The main menu's own menu: a note or folder at the vault root (named in a dialog), and a root folder deleted
  // (to the bin, after a confirmation unless it is empty) or defined by hand.
  const [rootCreate, setRootCreate] = React.useState<CreateKind | null>(null)
  const deleteRootFolder = (item: { id: string; label: string }) => {
    const run = async () => {
      const res = await deleteVaultFolder(item.id, activePersona)
      if (res.ok) {
        vaultTreeActions.onDeleted(item.id)
        notify.success(res.detail)
      } else {
        notify.error(res.error)
      }
    }
    const node = vaultTree.find((n) => n.path === item.id)
    if ((node?.children?.length ?? 0) === 0) return void run()
    confirm({
      message: `Delete “${item.label}” and everything inside it?`,
      description: "Any notes inside will move to the vault bin.",
      confirmLabel: "Delete folder",
      onConfirm: run,
    })
  }

  // The brand-mark wordmark: the fixed product name, or the active vault's
  // name when the Workspace setting asks for it (falling back to the name
  // while the vault name hasn't loaded yet, or there's none configured).
  const vaultLabel =
    brandMarkLabel === "vault" ? (vaultName ?? "Sympose") : "Sympose"
  // Phone: the rail only shows alongside the content panel — the two are one
  // view. Desktop / tablet: always shown.
  const menuOpen = isPhone ? menuShown && contentOpen : true
  // Settings / Persona on phone are plain destination pages, styled off the chat
  // panel (same background, same gutter) rather than the vault content surface.
  const plainPage =
    isPhone && (active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID)

  const contentHeader = (
    <ContentToolbar
      onCollapse={isPhone ? undefined : () => panels.close("content")}
      canGoBack={canGoBack}
      canGoForward={canGoForward}
      goBack={goBack}
      goForward={goForward}
      searchOpen={searchOpen}
      setSearchOpen={setSearchOpen}
      vaultSearch={vaultSearch}
      setVaultSearch={setVaultSearch}
      closeSearch={closeSearch}
      searchInputRef={searchInputRef}
      isSentinel={isSentinel}
      pendingCreate={pendingCreate}
      createName={createName}
      setCreateName={setCreateName}
      creating={creating}
      closeCreate={closeCreate}
      toggleCreate={toggleCreate}
      submitCreate={submitCreate}
      noteInputRef={noteInputRef}
      folderInputRef={folderInputRef}
      searchLabel={
        { vault: "Search vault", settings: "Search settings", conversations: "Search conversations" }[searchScope]
      }
    />
  )

  // The model picker, in the chat's footer and on the Persona page (a pick is saved on the persona either way). The
  // cloud notice, with its switches, shows in the panel the picker was used from: `noticeAt` is where it was last asked
  // for, and the other panel's picker offers to bring it there.
  const [noticeAt, setNoticeAt] = React.useState<"chat" | "persona">("chat")
  const editMode = useEditMode(activePersona, activePersonaName)
  const noticeIn = (panel: "chat" | "persona") => cloudNotice.open && noticeAt === panel
  const cloudNoticeBox = (
    <CloudNotice state={sharingState} onChange={setShared} onClose={cloudNotice.close} />
  )
  const modelPicker = (panel: "chat" | "persona") =>
    models.state ? (
      <ModelPicker
        state={models.state}
        onChoose={(model) => {
          setNoticeAt(panel)
          switchModel(model)
        }}
        noticeClosed={!noticeIn(panel)}
        onShowNotice={() => {
          setNoticeAt(panel)
          cloudNotice.reopen()
        }}
        {...(panel === "persona" ? { side: "bottom" as const, align: "start" as const } : {})}
      />
    ) : undefined
  const contentBody =
    active === MENU_ACCOUNT_ID ? (
      <PersonaCard
        personas={rosterPersonas}
        active={activePersona}
        phone={isPhone}
        files={personaFiles.files}
        onOpenFile={openPersonaFile}
        modelSlot={modelPicker("persona")}
        editModeSlot={<PersonaEditMenu info={editMode.info} onChoose={editMode.choose} />}
        notice={noticeIn("persona") ? cloudNoticeBox : undefined}
        conversations={
          <ConversationList
            sessions={sessionList.sessions}
            onOpen={(id) => void sessionList.open(id)}
            onRename={sessionList.rename}
            onPin={(id, pinned) => void sessionList.pin(id, pinned)}
            onDelete={sessionList.remove}
            query={vaultSearchQuery}
          />
        }
      />
    ) : active === MENU_SETTINGS_ID ? (
      <SettingsView
        title={activeLabel}
        brandMarkLabel={brandMarkLabel}
        setBrandMarkLabel={setBrandMarkLabel}
        editorPrefs={editorPrefs}
        setEditorPref={setEditorPref}
        toolbarItems={toolbarItems}
        setToolbarItems={setToolbarItems}
        notifyPrefs={notifyPrefs}
        setNotifyPref={setNotifyPref}
        nebulaPrefs={nebulaPrefs}
        setNebulaPref={setNebulaPref}
        recentsEnabled={recentsEnabled}
        setRecentsEnabled={setRecentsEnabled}
        shownCount={shownCount}
        setShownCount={setShownCount}
        hiddenState={hiddenState}
        unhideFromView={unhideFromView}
        changeHidden={changeHidden}
        chatDisplayPrefs={chatDisplayPrefs}
        setChatDisplayPref={setChatDisplayPref}
        sharingState={sharingState}
        setShared={setShared}
        cloudNotice={cloudNotice}
        query={vaultSearchQuery}
      />
    ) : (
      <VaultFolderView
        trashView={trashView}
        conversationBinKey={sessionList.binVersion}
        onConversationRestored={() => void sessionList.refresh()}
        activeLabel={activeLabel}
        activeRootFolder={activeRootFolder}
        moveNote={moveNote}
        activePersona={activePersona}
        vaultPath={vaultsState.active}
        vaultRefreshKey={vaultRefreshKey}
        refreshVault={refreshVault}
        vaultTreeEmpty={vaultTree.length === 0}
        panelEmpty={panelEmpty}
        vaultSearchQuery={vaultSearchQuery}
        searchedPanelNodes={searchedPanelNodes}
        contentMatches={contentMatches}
        beyondFolderMatches={beyondFolderMatches}
        pinnedNodes={pinnedNodes}
        pinnedShowPath={pinnedShowPath}
        drafts={drafts}
        draftSelectedPath={draftEditor.current?.path ?? openableNote}
        onOpenDraft={openDraft}
        vaultTreeActions={vaultTreeActions}
        unhideFromView={unhideFromView}
        selectNote={selectNote}
        openEditor={() => panels.open("editor")}
      />
    )

  return (
    <div
      ref={rootRef}
      className={cn(
        "flex h-svh w-full overflow-hidden bg-background text-foreground",
        isPhone && "flex-col"
      )}
      // Feeds `.sy-frosted-panel` — the content and editor panels only
      // (blur dropped). `off` (the default: opacity 1) →
      // solid tokens. `tint` → the opacity knob alone.
      data-nebula-frost={nebulaPrefs.panelOpacity < 1 ? "tint" : "off"}
      style={
        {
          "--sy-panel-opacity": String(nebulaPrefs.panelOpacity),
        } as React.CSSProperties
      }
    >
      {/* Module A — the persistent ambient vault graph. Always `fixed inset-0
          z-0`, the literal bottom of the stack in both Focus and Explore —
          the stage below gives up pointer events instead (see its
          `pointer-events-none`), rather than this layer ever climbing above
          the chrome. */}
      {nebulaReady && (
        <React.Suspense fallback={null}>
          <AmbientNebula
            graph={nebulaGraph}
            source={nebulaGraphSource}
            prefs={nebulaPrefs}
            setPref={setNebulaPref}
            activeNoteId={openableNote}
          />
        </React.Suspense>
      )}

      {isPhone && (
        <TopBar
          // `relative` (any positioned value) is enough to paint above the
          // fixed z-0 nebula, via DOM order — no z-index needed.
          className="relative"
          menuOpen={menuShown}
          onToggleMenu={revealMenu}
          settingsActive={contentOpen && active === MENU_SETTINGS_ID}
          onSettings={() => selectSection(MENU_SETTINGS_ID)}
          accountActive={contentOpen && active === MENU_ACCOUNT_ID}
          onAccount={() => selectSection(MENU_ACCOUNT_ID)}
          account={{ name: activePersonaName, icon: activePersonaVisuals.icon, accent: activePersonaVisuals.accent }}
          chatActive={chatOpen}
          onChat={() => panels.toggle("chat")}
          vaults={vaultsState.vaults}
          activeVault={vaultsState.active}
          onSwitchVault={handleSwitchVault}
          onAddVault={handleAddVault}
          vaultLabel={vaultLabel}
        />
      )}

      {/* menu + stage row — overflow-hidden clips the menu (and the panels)
          while they are parked off to the inline-start. `pointer-events-none`
          so this row doesn't sit as a dead hit-target above the nebula in
          Explore once its own children (the menu, the stage) have nothing
          reclaiming a given point — mirrors the same pattern the stage div
          already uses one level down; without it, this row's own box (not
          the panels inside it) is what elementFromPoint hits at a closed
          panel's location, and the click never reaches the nebula. */}
      <div className="pointer-events-none relative flex min-h-0 min-w-0 flex-1 overflow-hidden">
        <MainMenu
          items={menuItems}
          // above the stage so the content panel tucks *behind* it on hide
          className="z-20"
          open={menuOpen}
          hideChrome={isPhone}
          activeId={contentOpen ? resolvedActive : undefined}
          onSelectItem={(item) => selectSection(item.id)}
          onOpenSettings={() => selectSection(MENU_SETTINGS_ID)}
          onSelectAccount={() => selectSection(MENU_ACCOUNT_ID)}
          onSelectTrash={() => selectSection(MENU_TRASH_ID)}
          onDropNote={moveNote}
          onDropFolder={moveFolder}
          onHideItem={(item) => hideFromView(item.id)}
          onCreateRoot={setRootCreate}
          onDeleteItem={deleteRootFolder}
          onDefineItem={(item) => void openDefinition(item.id)}
          persona={activePersona}
          onRenameFolder={vaultTreeActions.onFolderRenamed}
          onBeforeRenameFolder={vaultTreeActions.onBeforeFolderRename}
          vaults={vaultsState.vaults}
          activeVault={vaultsState.active}
          onSwitchVault={handleSwitchVault}
          onAddVault={handleAddVault}
          vaultLabel={vaultLabel}
          account={{
            name: activePersonaName,
            icon: activePersonaVisuals.icon,
            accent: activePersonaVisuals.accent,
          }}
          collapsed={menu.collapsed}
          onCollapsedChange={menu.onCollapsedChange}
          storageKey="sympose:shell.menu"
        />

        {/* the stage — content | editor, in fixed order; overflow-hidden
            clips a panel while it is parked off to the left. `relative` anchors
            the nebula mode toggle at the top-right corner. `pointer-events-none`
            so an empty stretch of stage (nothing open) doesn't sit as a dead
            hit-target above the always-bottom ambient nebula — each child
            claims `pointer-events-auto` back explicitly, both open and closed,
            so ordinary interaction is unaffected. */}
        <div className="pointer-events-none relative flex min-w-0 flex-1 overflow-hidden">
          {!isPhone && (
            // `top-[10.5px]` centers this 32px-tall row on the editor toolbar's
            // own vertical center: the panel's `py-2` outer margin (8px) plus
            // half its 37px toolbar row (4px padding + a 28px button + a 1px
            // border) — 8 + 37/2 - 32/2 = 10.5. A flat `top-4` (16px) sat
            // 5.5px low against it.
            <div className="pointer-events-auto absolute top-[10.5px] right-3 z-30 flex items-center gap-2">
              {!chatPinned && (
                <ChatActionGroup
                  chatOpen={chatOpen}
                  onToggleChat={() => panels.toggle("chat")}
                />
              )}
              <NebulaModeToggle
                explore={explore}
                onToggle={() =>
                  setNebulaPref("interaction", explore ? "focus" : "explore")
                }
              />
            </div>
          )}

          <ContentPanel
            storageKey="sympose:shell.panel"
            scrollKey="sympose:shell.panel.scroll"
            contentClassName={
              // Settings, Persona and the Vault view all share one gutter: `p-8`
              // on desktop/tablet, `px-4 py-6` on the phone plain page, `p-6`
              // for the phone vault surface. The persona card cancels this same
              // pad with its own negative-margin accent band (see PersonaCard).
              !isPhone ? "p-8" : plainPage ? "px-4 py-6" : "p-6"
            }
            open={contentOpen}
            phone={isPhone}
            plain={plainPage}
            fill={active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID}
            flushBottomLeft={
              !isPhone && contentOpen && active === MENU_ACCOUNT_ID
            }
            header={contentHeader}
            footer={
              // Pinned below the scroll surface (not inside it) so a tall
              // Settings list can't scroll it out of reach, the same way the
              // editor panel's own "Links" row stays put under the note body.
              active === MENU_SETTINGS_ID ? (
                <div className="flex items-center justify-between">
                  <SettingsChecks onChanged={refreshVault} />
                  <ThemeToggle />
                </div>
              ) : active === MENU_ACCOUNT_ID ? (
                <PersonaSwitcher personas={rosterPersonas} active={activePersona} onSwitch={setActivePersona} />
              ) : !trashView && (showRelated || recentNodes.length > 0) ? (
                <div className="flex min-h-0 flex-col gap-3">
                  {showRelated && (
                    <RelatedNotesFooter
                      related={related.related}
                      actions={vaultTreeActions}
                      selectedPath={vaultTreeActions.selectedPath}
                      onSelect={vaultTreeActions.onSelect}
                      hideExtension={vaultTreeActions.hideExtension}
                    />
                  )}
                  {recentNodes.length > 0 && (
                    <RecentNotesFooter
                      nodes={recentNodes}
                      actions={vaultTreeActions}
                      selectedPath={vaultTreeActions.selectedPath}
                      onSelect={vaultTreeActions.onSelect}
                      hideExtension={vaultTreeActions.hideExtension}
                      onRemoveFromRecents={vaultTreeActions.onRemoveFromRecents}
                      onClearRecents={vaultTreeActions.onClearRecents}
                    />
                  )}
                </div>
              ) : undefined
            }
          >
            <ContentSlot swapKey={resolvedActive} direction={contentDirection}>
              {contentBody}
            </ContentSlot>
          </ContentPanel>

          <MarkdownPanel
            onCollapse={isPhone ? undefined : () => panels.close("editor")}
            storageKey="sympose:shell.md"
            path={draftEditor.path ?? fileEditor.path ?? openableNote}
            file={panelFile}
            reloadToken={fileEditor.reloadToken}
            persona={activePersona}
            personaName={activePersonaName}
            vaultPath={vaultsState.active}
            onWikiLinkClick={openWikilink}
            wikiLinkSource={wikiLinkSource}
            tagSource={tagSource}
            embedSource={embedSource}
            previewRequest={previewRequest}
            onRenamed={onEditorRenamed}
            onDeleted={onEditorDeleted}
            isPinned={isPinned}
            onTogglePin={togglePin}
            onNavigateToRootFolder={selectSection}
            vaultName={vaultName}
            preferences={editorPrefs}
            toolbarItems={toolbarItems}
            open={editorOpen}
            fill={editorFill}
            phone={isPhone}
          />

          <FolderMoveDialog ask={folderMoveAsk} onClose={closeFolderMoveAsk} />

          <RootCreateDialog kind={rootCreate} onCreate={createAtRoot} onClose={() => setRootCreate(null)} />

          <FolderSetupDialog
            setup={folderSetup}
            persona={activePersona}
            onClose={closeFolderSetup}
            onCreated={() => refreshVault()}
          />

          <React.Suspense fallback={null}>
            <ChatPanel
              turns={chat.turns}
              sending={chat.sending}
              phase={chat.phase}
              indexing={chat.indexing}
              hasMore={chat.hasMore}
              loadingOlder={chat.loadingOlder}
              onLoadOlder={chat.loadOlder}
              renderAfter={(turn) =>
                (turn.sent?.lookups ?? []).flatMap((l) => {
                  const request = l.request && (l.tool === "propose_persona" || l.tool === "propose_setting") ? confirmations.byId[l.request] : undefined
                  if (request?.kind === "persona") {
                    return [<PersonaRequestCard key={request.id} request={request} onAnswer={(accept, folders, editMode) => confirmations.answer(request.id, accept, folders, editMode)} />]
                  }
                  return request?.kind === "setting" ? [<SettingRequestCard key={request.id} request={request} onAnswer={(accept) => confirmations.answer(request.id, accept, null)} />] : []
                })
              }
              onOpenNote={openGroundedNote}
              onWikiLinkClick={openChatWikilink}
              onNewConversation={chat.newConversation}
              pinned={currentSession?.pinned_at != null}
              onTogglePin={currentSession ? () => void sessionList.pin(currentSession.id, currentSession.pinned_at == null) : undefined}
              onCompact={chat.compact}
              compacting={chat.compacting}
              condensed={chat.condensed}
              showGrounding={chatDisplayPrefs.showGrounding}
              showCloudSent={chatDisplayPrefs.showCloudSent}
              statusPhrases={statusPhrases}
              contextFigure={chatDisplayPrefs.showMeter ? contextFigure : null}
              typeStatus={chatDisplayPrefs.typeStatus}
              notice={noticeIn("chat") ? cloudNoticeBox : undefined}
              chips={<AttachedChips />}
              draft={chat.draft}
              onDraftChange={chat.setDraft}
              onSubmit={chat.send}
              onStop={chat.stop}
              model={activePersonaModel}
              modelSlot={modelPicker("chat")}
              personaName={activePersonaName}
              personaHandle={activePersona}
              personaTitle={rosterPersonas.find((p) => p.handle === activePersona)?.title}
              open={chatOpen}
              phone={isPhone}
            />
          </React.Suspense>
        </div>
      </div>
    </div>
  )
}
