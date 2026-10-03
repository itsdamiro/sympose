// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useBrandMarkLabel } from "@/lib/use-brand-mark-preference"
import { useChatDisplayPreferences } from "@/lib/use-chat-display-preferences"
import { useEditorPreferences } from "@/lib/use-editor-preferences"
import { useNebulaPreferences } from "@/lib/use-nebula-preferences"
import { useNotificationPreferences } from "@/lib/use-notification-preferences"
import { useToolbarItems } from "@/lib/use-toolbar-items"
import { SettingsView } from "./settings-view"

const setShowDefinitionNotes = vi.fn()
vi.mock("@/lib/vault-hidden-api", () => ({ setShowDefinitionNotes: (...a: unknown[]) => setShowDefinitionNotes(...a) }))

const OPEN = ["hidden-from-view", "cloud-models", "recent-notes", "workspace"]
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }))
  for (const k of OPEN) document.cookie = `sympose:pref.section.${k}=1`
})
afterEach(() => {
  cleanup()
  for (const k of OPEN) document.cookie = `sympose:pref.section.${k}=; max-age=0`
})

const state = {
  model: "gemini/x",
  cloud: true,
  categories: [{ name: "notes", description: "passages of your notes", shared: false }],
}

function setup(over: Record<string, unknown> = {}) {
  const spies = {
    unhideFromView: vi.fn(),
    changeHidden: vi.fn(),
    setShared: vi.fn(),
    setRecentsEnabled: vi.fn(),
    setShownCount: vi.fn(),
    reopen: vi.fn(),
    close: vi.fn(),
  }
  function Host() {
    const [editorPrefs, setEditorPref] = useEditorPreferences()
    const [toolbarItems, setToolbarItems] = useToolbarItems()
    const [notifyPrefs, setNotifyPref] = useNotificationPreferences()
    const [nebulaPrefs, setNebulaPref] = useNebulaPreferences()
    const [chatDisplayPrefs, setChatDisplayPref] = useChatDisplayPreferences()
    const [brandMarkLabel, setBrandMarkLabel] = useBrandMarkLabel()
    return (
      <SettingsView
        title="Settings"
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
        recentsEnabled
        setRecentsEnabled={spies.setRecentsEnabled}
        shownCount={5}
        setShownCount={spies.setShownCount}
        hiddenState={{ hidden: ["Drafts"], showDefinitionNotes: false }}
        unhideFromView={spies.unhideFromView}
        changeHidden={spies.changeHidden}
        chatDisplayPrefs={chatDisplayPrefs}
        setChatDisplayPref={setChatDisplayPref}
        sharingState={state}
        setShared={spies.setShared}
        cloudNotice={{ open: true, reopen: spies.reopen, close: spies.close }}
        {...over}
      />
    )
  }
  render(<Host />)
  return spies
}

describe("SettingsView", () => {
  it("is headed with the section's title", () => {
    setup()
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Settings")
  })

  it("lists every group of preferences", () => {
    setup()
    for (const name of ["Workspace", "Markdown editor", "Notifications", "Knowledge Nebula", "Recent notes", "Hidden from view", "Chat", "Cloud models"]) {
      expect(screen.getAllByText(name).length, name).toBeGreaterThan(0)
    }
  })

  it("unhides a path through the shell's unhide", () => {
    const s = setup()
    fireEvent.click(screen.getByRole("button", { name: "Unhide Drafts" }))
    expect(s.unhideFromView).toHaveBeenCalledExactlyOnceWith("Drafts")
  })

  it("turns the definition-notes switch into a change of the hidden list, which the shell applies", () => {
    setShowDefinitionNotes.mockReturnValue("the-request")
    const s = setup()
    fireEvent.click(radio("Show folder definition notes", "Shown"))
    expect(setShowDefinitionNotes).toHaveBeenCalledWith(true)
    expect(s.changeHidden).toHaveBeenCalledExactlyOnceWith("the-request")
  })

  it("changes what a cloud model may receive through the shell's setter", () => {
    const s = setup()
    fireEvent.click(radio("Share notes with cloud models", "On"))
    expect(s.setShared).toHaveBeenCalledWith("notes", true)
  })

  it("shows the notice and the definition-notes switch as they stand", () => {
    setup()
    expect(radio("Notice above the message box", "Shown").getAttribute("aria-checked")).toBe("true")
    expect(radio("Show folder definition notes", "Hidden").getAttribute("aria-checked")).toBe("true")
    cleanup()
    setup({ cloudNotice: { open: false, reopen: vi.fn(), close: vi.fn() }, hiddenState: { hidden: [], showDefinitionNotes: true } })
    expect(radio("Notice above the message box", "Hidden").getAttribute("aria-checked")).toBe("true")
    expect(radio("Show folder definition notes", "Shown").getAttribute("aria-checked")).toBe("true")
  })

  it("closes the cloud notice when it is switched to hidden", () => {
    const s = setup()
    fireEvent.click(radio("Notice above the message box", "Hidden"))
    expect(s.close).toHaveBeenCalledTimes(1)
    expect(s.reopen).not.toHaveBeenCalled()
  })

  it("reopens the cloud notice when it is switched to shown", () => {
    const reopen = vi.fn()
    const close = vi.fn()
    setup({ cloudNotice: { open: false, reopen, close } })
    fireEvent.click(radio("Notice above the message box", "Shown"))
    expect(reopen).toHaveBeenCalledTimes(1)
    expect(close).not.toHaveBeenCalled()
  })

  it("turns the recent notes on and off through the shell's setter", () => {
    const s = setup()
    const group = screen.getAllByRole("radiogroup").find((g) => /recent/i.test(g.getAttribute("aria-label") ?? ""))
    expect(group).toBeTruthy()
    fireEvent.click(group!.querySelector('[aria-checked="false"]') as HTMLElement)
    expect(s.setRecentsEnabled).toHaveBeenCalledTimes(1)
  })
})

function radio(group: string, option: string): HTMLElement {
  const g = screen.getByRole("radiogroup", { name: group })
  const el = [...g.querySelectorAll('[role="radio"]')].find((r) => r.textContent === option)
  if (!el) throw new Error(`no ${option} in ${group}`)
  return el as HTMLElement
}

describe("SettingsView: the toolbar search", () => {
  it("filters its rows and sections by the toolbar's query, and says so when nothing matches", () => {
    setup({ query: "autosave" })
    expect(document.querySelector('[data-slot="control-row"]:not([hidden])')?.textContent).toContain("Autosave")
    cleanup()
    setup({ query: "zzzzqqq" })
    expect(screen.getByText('No settings match "zzzzqqq"').closest('[class*="group-has-"]')).toBeTruthy() // hides itself while a row or section shows
    cleanup()
    setup({ query: "" })
    expect(screen.queryByText(/No settings match/)).toBeNull()
  })
})
