// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"

const api = vi.hoisted(() => ({ fetchEditMode: vi.fn(), saveEditMode: vi.fn() }))
const confirmFn = vi.hoisted(() => vi.fn())
const notify = vi.hoisted(() => ({ notify: { error: vi.fn(), warning: vi.fn() } }))
vi.mock("@/lib/edit-mode-api", () => api)
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmFn }))
vi.mock("@/lib/notify", () => notify)

import { setNotificationPreference } from "./use-notification-preferences"
import { useEditMode } from "./use-edit-mode"

const info = (over = {}) => ({ mode: "manual", source: "global", modes: [], notes: { accept: "ACCEPT NOTE", auto: "AUTO NOTE" }, model: "m", ...over })

beforeEach(() => {
  api.fetchEditMode.mockResolvedValue(info())
  api.saveEditMode.mockImplementation(async (_h: string, mode: string | null) => ({ ok: true, info: info({ mode: mode ?? "manual", source: mode ? "persona" : "global" }) }))
  setNotificationPreference("confirm", "dialog")
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function ready(handle = "samantha") {
  const hook = renderHook(({ h }) => useEditMode(h, "Samantha"), { initialProps: { h: handle } })
  await waitFor(() => expect(hook.result.current.info).not.toBeNull())
  return hook
}

describe("useEditMode", () => {
  it("reads the persona's mode, and never shows another persona's while hers is on its way", async () => {
    const { result, rerender } = await ready("samantha")
    expect(result.current.info?.mode).toBe("manual")
    api.fetchEditMode.mockReturnValue(new Promise(() => {}))
    rerender({ h: "grace" })
    expect(result.current.info).toBeNull()
  })

  it("saves plan, manual and clearing at once, with no question", async () => {
    const { result } = await ready()
    await act(async () => result.current.choose("plan"))
    expect(api.saveEditMode).toHaveBeenCalledWith("samantha", "plan")
    await act(async () => result.current.choose(null))
    expect(api.saveEditMode).toHaveBeenLastCalledWith("samantha", null)
    expect(confirmFn).not.toHaveBeenCalled()
  })

  it.each([["accept", "ACCEPT NOTE"], ["auto", "AUTO NOTE"]])("asks before %s, showing the note about her model, and saves only when confirmed", async (mode, note) => {
    const { result } = await ready()
    act(() => result.current.choose(mode as "accept" | "auto"))
    expect(api.saveEditMode).not.toHaveBeenCalled()
    expect(confirmFn).toHaveBeenCalledWith(expect.objectContaining({ description: note, tone: "default", message: expect.stringContaining("Samantha") }))
    await act(async () => confirmFn.mock.calls[0][0].onConfirm())
    expect(api.saveEditMode).toHaveBeenCalledWith("samantha", mode)
    expect(result.current.info?.mode).toBe(mode)
  })

  it("applies accept or auto at once when there is no note to show for it, rather than asking an empty question", async () => {
    api.fetchEditMode.mockResolvedValue(info({ notes: { accept: null, auto: null } }))
    const { result } = await ready()
    await act(async () => result.current.choose("auto"))
    expect(confirmFn).not.toHaveBeenCalled()
    expect(api.saveEditMode).toHaveBeenCalledWith("samantha", "auto")
  })

  it("with confirmations set to none applies the choice at once and shows the note as a notice, never skipping it", async () => {
    setNotificationPreference("confirm", "none")
    const { result } = await ready()
    await act(async () => result.current.choose("auto"))
    expect(confirmFn).not.toHaveBeenCalled()
    expect(api.saveEditMode).toHaveBeenCalledWith("samantha", "auto")
    expect(notify.notify.warning).toHaveBeenCalledWith("AUTO NOTE", expect.anything())
  })

  it("shows no notice when the save failed, and says why", async () => {
    setNotificationPreference("confirm", "none")
    api.saveEditMode.mockResolvedValue({ ok: false, error: "disk" })
    const { result } = await ready()
    await act(async () => result.current.choose("auto"))
    expect(notify.notify.error).toHaveBeenCalledWith(expect.stringContaining("disk"))
    expect(notify.notify.warning).not.toHaveBeenCalled()
    expect(result.current.info?.mode).toBe("manual")
  })
})
