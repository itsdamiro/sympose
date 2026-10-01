export { ActionBadge } from "./action-badge"
export { ChatActionGroup } from "./chat-action-group"
export { ChatMessage, StreamingCaret } from "./chat-message"
// `ChatPanel` is intentionally NOT re-exported here: the app shell lazy-imports it directly from
// "@/components/sympose/chat-panel" so the chat stays out of the first page load (docs/decisions/044).
export { ChatSystemLine } from "./chat-system-line"
export { ConfirmDialog } from "./confirm-dialog"
export { ContentPanel } from "./content-panel"
export {
  ControlRow,
  ControlSection,
  ControlSectionsProvider,
  useCollapseAll,
  CollapseAllButton,
} from "./control-section"
export { BusyLine } from "./busy-line"
export { CloudNotice } from "./cloud-notice"
export { ContextMeter } from "./context-meter"
export { CloudSharingSection } from "./cloud-sharing-section"
export { ModelPicker } from "./model-picker"
export { ChatDisplaySection } from "./chat-display-section"
export { EditorPreferencesSection } from "./editor-preferences-section"
export { FolderSetupDialog } from "./folder-setup-dialog"
export { FrontmatterCard } from "./frontmatter-card"
export { EngineSettingsSections } from "./engine-settings-section"
export { HiddenSection } from "./hidden-section"
// `AmbientNebula` is intentionally NOT re-exported here — it pulls in
// `react-force-graph`. The app shell lazy-imports it directly from
// "@/components/sympose/ambient-nebula" so it stays off the TTFT hot path.
export {
  MainMenu,
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  MENU_TRASH_ID,
  type MainMenuItem,
} from "./main-menu"
export { MarkdownPanel, TOOLBAR_ICONS } from "./markdown-panel"
export { NebulaAppearanceSection } from "./nebula-appearance-section"
export { NebulaModeToggle } from "./nebula-mode-toggle"
export { NotificationsSection } from "./notifications-section"
export { ModelChip } from "./model-chip"
export { PersonaCard } from "./persona-card"
export {
  RecentNotesPreferencesSection,
} from "./recent-notes-preferences-section"
export {
  SegmentedControl,
  type SegmentedControlOption,
} from "./segmented-control"
export { ThemeToggle } from "./theme-toggle"
export { TopBar } from "./top-bar"
export { TrashList } from "./trash-list"
export { WorkspaceSection } from "./workspace-section"
export { WorkspaceSwitcher } from "./workspace-switcher"
export {
  filterVaultTree,
  filterTreeByQuery,
  flatSearchTree,
  collectFolderPaths,
  VaultTree,
  type VaultNode,
  type FlatVaultMatch,
} from "./vault-tree"
export { SearchResultRow, searchMatchDetail } from "./search-result-row"
