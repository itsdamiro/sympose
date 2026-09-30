import { beforeEach, describe, expect, it, vi } from "vitest"

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }))
vi.mock("sonner", () => ({ toast }))
vi.mock("@/lib/use-notification-preferences", () => ({ getNotificationPreferences: () => ({ enabled: "off" }) }))

import { notify } from "./notify"

beforeEach(() => vi.clearAllMocks())

describe("notify with notifications turned off", () => {
  it("still shows an error", () => {
    notify.error("Save failed")
    expect(toast.error).toHaveBeenCalledWith("Save failed", undefined)
  })

  it("drops a success", () => {
    notify.success("Saved")
    expect(toast.success).not.toHaveBeenCalled()
  })
})
