import * as React from "react"
import { Search01Icon } from "@hugeicons/core-free-icons"

import {
  CloudSharingSection,
  ChatDisplaySection,
  CollapseAllButton,
  ControlSearchProvider,
  ControlSectionsProvider,
  EditorPreferencesSection,
  EngineSettingsSections,
  HiddenSection,
  NebulaAppearanceSection,
  NotificationsSection,
  RecentNotesPreferencesSection,
  WorkspaceSection,
} from "@/components/sympose"
import { EmptyState } from "@/components/sympose/empty-state"
import { setShowDefinitionNotes } from "@/lib/vault-hidden-api"

/**
 * The Settings section of the content panel: every preference the web app has,
 * as collapsible sections. The values live in the shell (the cookie-backed hooks
 * beside them are read elsewhere too, by the editor and the nebula, so a second
 * copy here would drift), so each section is handed its value and its setter.
 */
export function SettingsView({
  title,
  brandMarkLabel,
  setBrandMarkLabel,
  editorPrefs,
  setEditorPref,
  toolbarItems,
  setToolbarItems,
  notifyPrefs,
  setNotifyPref,
  nebulaPrefs,
  setNebulaPref,
  recentsEnabled,
  setRecentsEnabled,
  shownCount,
  setShownCount,
  hiddenState,
  unhideFromView,
  changeHidden,
  chatDisplayPrefs,
  setChatDisplayPref,
  sharingState,
  setShared,
  cloudNotice,
  query = "",
}: {
  title: string
  brandMarkLabel: React.ComponentProps<typeof WorkspaceSection>["brandMarkLabel"]
  setBrandMarkLabel: React.ComponentProps<typeof WorkspaceSection>["setBrandMarkLabel"]
  editorPrefs: React.ComponentProps<typeof EditorPreferencesSection>["prefs"]
  setEditorPref: React.ComponentProps<typeof EditorPreferencesSection>["setPref"]
  toolbarItems: React.ComponentProps<typeof EditorPreferencesSection>["toolbarItems"]
  setToolbarItems: React.ComponentProps<typeof EditorPreferencesSection>["onToolbarItemsChange"]
  notifyPrefs: React.ComponentProps<typeof NotificationsSection>["prefs"]
  setNotifyPref: React.ComponentProps<typeof NotificationsSection>["setPref"]
  nebulaPrefs: React.ComponentProps<typeof NebulaAppearanceSection>["prefs"]
  setNebulaPref: React.ComponentProps<typeof NebulaAppearanceSection>["setPref"]
  recentsEnabled: React.ComponentProps<typeof RecentNotesPreferencesSection>["enabled"]
  setRecentsEnabled: React.ComponentProps<typeof RecentNotesPreferencesSection>["setEnabled"]
  shownCount: React.ComponentProps<typeof RecentNotesPreferencesSection>["shownCount"]
  setShownCount: React.ComponentProps<typeof RecentNotesPreferencesSection>["setShownCount"]
  hiddenState: { hidden: string[]; showDefinitionNotes: boolean }
  unhideFromView: React.ComponentProps<typeof HiddenSection>["onUnhide"]
  changeHidden: (change: ReturnType<typeof setShowDefinitionNotes>) => unknown
  chatDisplayPrefs: React.ComponentProps<typeof ChatDisplaySection>["prefs"]
  setChatDisplayPref: React.ComponentProps<typeof ChatDisplaySection>["setPref"]
  sharingState: React.ComponentProps<typeof CloudSharingSection>["state"]
  setShared: React.ComponentProps<typeof CloudSharingSection>["onChange"]
  cloudNotice: { open: boolean; reopen: () => void; close: () => void }
  /** What the toolbar's search field holds (docs/decisions/065): rows and sections without a match are hidden. */
  query?: string
}) {
  return (
    <div className="group/settings contents">
      <ControlSearchProvider query={query}>
      <ControlSectionsProvider>
        <div className="flex items-center justify-between gap-4">
          <h1 className="font-heading text-2xl font-semibold text-fg-strong">
            {title}
          </h1>
          <CollapseAllButton />
        </div>
        <WorkspaceSection
          brandMarkLabel={brandMarkLabel}
          setBrandMarkLabel={setBrandMarkLabel}
        />
        <EditorPreferencesSection
          prefs={editorPrefs}
          setPref={setEditorPref}
          toolbarItems={toolbarItems}
          onToolbarItemsChange={setToolbarItems}
        />
        <NotificationsSection prefs={notifyPrefs} setPref={setNotifyPref} />
        <NebulaAppearanceSection prefs={nebulaPrefs} setPref={setNebulaPref} />
        <RecentNotesPreferencesSection
          enabled={recentsEnabled}
          setEnabled={setRecentsEnabled}
          shownCount={shownCount}
          setShownCount={setShownCount}
        />
        <HiddenSection
          hidden={hiddenState.hidden}
          showDefinitionNotes={hiddenState.showDefinitionNotes}
          onUnhide={unhideFromView}
          onShowDefinitionNotes={(show) =>
            changeHidden(setShowDefinitionNotes(show))
          }
        />
        <ChatDisplaySection prefs={chatDisplayPrefs} setPref={setChatDisplayPref} />
        <CloudSharingSection
          state={sharingState}
          onChange={setShared}
          noticeOpen={cloudNotice.open}
          onNoticeOpenChange={(open) => (open ? cloudNotice.reopen() : cloudNotice.close())}
        />
        <EngineSettingsSections />
        {query.trim() !== "" && (
          // shown only while no row is visible and no section matched by its title (the page has no state of its own
          // about that: the rows and sections hide themselves)
          <EmptyState
            icon={Search01Icon}
            title={`No settings match "${query.trim()}"`}
            className="group-has-[[data-slot=control-row]:not([hidden])]/settings:hidden group-has-[[data-search-match]]/settings:hidden"
          />
        )}
      </ControlSectionsProvider>
      </ControlSearchProvider>
    </div>
  )
}
