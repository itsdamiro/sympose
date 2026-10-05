// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"

const settingsApi = vi.hoisted(() => ({ fetchSettings: vi.fn(), changeSetting: vi.fn() }))
const editModeApi = vi.hoisted(() => ({ fetchGlobalEditMode: vi.fn() }))
const confirmFn = vi.hoisted(() => vi.fn())
const notify = vi.hoisted(() => ({ notify: { error: vi.fn(), warning: vi.fn() } }))
vi.mock("@/lib/settings-api", () => settingsApi)
vi.mock("@/lib/edit-mode-api", () => editModeApi)
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmFn }))
vi.mock("@/lib/notify", () => notify)

import { setNotificationPreference } from "./use-notification-preferences"
import { useEngineSettings } from "./use-engine-settings"

const row = (key: string, value: string) => ({ key, kind: "choice", summary: "s", value, default: "manual", isDefault: false, text: value, choices: [], hint: "", whole: false })

beforeEach(() => {
  settingsApi.fetchSettings.mockResolvedValue({ ok: true, groups: [{ name: "Editing", settings: [row("edit_mode", "manual")] }] })
  settingsApi.changeSetting.mockImplementation(async (key: string, value: string) => ({ ok: true, setting: row(key, value) }))
  editModeApi.fetchGlobalEditMode.mockResolvedValue({ mode: "manual", following: [], notes: { accept: "ACCEPT NOTE", auto: "AUTO NOTE" } })
  setNotificationPreference("confirm", "dialog")
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function ready() {
  const hook = renderHook(() => useEngineSettings())
  await waitFor(() => expect(hook.result.current.state.status).toBe("ready"))
  return hook
}
const shown = (hook: Awaited<ReturnType<typeof ready>>) => {
  const state = hook.result.current.state
  return state.status === "ready" ? state.groups[0].settings[0].value : null
}

describe("useEngineSettings, the global edit mode (docs/decisions/072)", () => {
  it.each([["accept", "ACCEPT NOTE"], ["auto", "AUTO NOTE"]])("asks before %s with the note for the personas that follow it, and saves only when confirmed", async (mode, note) => {
    const hook = await ready()

    let saved = true
    await act(async () => {
      saved = await hook.result.current.change("edit_mode", mode)
    })

    expect(saved).toBe(false) // asked, not saved
    expect(settingsApi.changeSetting).not.toHaveBeenCalled()
    expect(shown(hook)).toBe("manual")
    expect(confirmFn).toHaveBeenCalledWith(expect.objectContaining({ description: note, tone: "default", message: expect.stringContaining("follow this setting") }))

    await act(async () => confirmFn.mock.calls[0][0].onConfirm())
    expect(settingsApi.changeSetting).toHaveBeenCalledWith("edit_mode", mode)
    await waitFor(() => expect(shown(hook)).toBe(mode))
  })

  it.each(["plan", "manual"])("saves %s at once, with no question", async (mode) => {
    const hook = await ready()
    await act(async () => void (await hook.result.current.change("edit_mode", mode)))
    expect(settingsApi.changeSetting).toHaveBeenCalledWith("edit_mode", mode)
    expect(confirmFn).not.toHaveBeenCalled()
    expect(editModeApi.fetchGlobalEditMode).not.toHaveBeenCalled()
  })

  it("asks about no other setting, even one given the same value", async () => {
    const hook = await ready()
    await act(async () => void (await hook.result.current.change("vault_lookup", "auto")))
    expect(settingsApi.changeSetting).toHaveBeenCalledWith("vault_lookup", "auto")
    expect(confirmFn).not.toHaveBeenCalled()
  })

  it("with confirmations set to none saves at once and shows the note as a notice", async () => {
    setNotificationPreference("confirm", "none")
    const hook = await ready()
    await act(async () => void (await hook.result.current.change("edit_mode", "auto")))
    expect(confirmFn).not.toHaveBeenCalled()
    await waitFor(() => expect(settingsApi.changeSetting).toHaveBeenCalledWith("edit_mode", "auto"))
    await waitFor(() => expect(notify.notify.warning).toHaveBeenCalledWith("AUTO NOTE", expect.anything()))
  })

  it("saves without asking when the note cannot be read, rather than blocking the setting", async () => {
    editModeApi.fetchGlobalEditMode.mockResolvedValue(null)
    const hook = await ready()
    let saved = false
    await act(async () => {
      saved = await hook.result.current.change("edit_mode", "accept")
    })
    expect(saved).toBe(true)
    expect(confirmFn).not.toHaveBeenCalled()
    expect(settingsApi.changeSetting).toHaveBeenCalledWith("edit_mode", "accept")
  })
})
