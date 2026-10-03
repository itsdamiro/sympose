// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { toast, notify, api } = vi.hoisted(() => ({
  toast: { success: vi.fn() },
  notify: { error: vi.fn() },
  api: { fetchDoctor: vi.fn(), fetchHealth: vi.fn(), fixDoctor: vi.fn() },
}))
vi.mock("sonner", () => ({ toast }))
vi.mock("@/lib/notify", () => ({ notify }))
vi.mock("@/lib/checks-api", async (original) => ({ ...(await original<object>()), ...api }))

import { SettingsChecks } from "./settings-checks"

const finding = (state: string, problem = "a problem") => ({ problem, state, fix: "do it", error: "" })
const doctor = (...findings: ReturnType<typeof finding>[]) => ({ ok: true, report: { models: ["- chat model: local"], findings } })

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe("SettingsChecks", () => {
  it("runs nothing until a pill is clicked", () => {
    render(<SettingsChecks />)
    expect(api.fetchDoctor).not.toHaveBeenCalled()
    expect(api.fetchHealth).not.toHaveBeenCalled()
  })

  it("says so in a notification, with no dialog, when the doctor finds nothing", async () => {
    api.fetchDoctor.mockResolvedValue(doctor())
    render(<SettingsChecks />)
    fireEvent.click(screen.getByRole("button", { name: /Doctor/ }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Doctor: everything looks healthy."))
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("opens a dialog with Fix and Decline for a fixable finding, and a fix that clears it closes with a notification", async () => {
    api.fetchDoctor.mockResolvedValue(doctor(finding("fixable")))
    api.fixDoctor.mockResolvedValue(doctor(finding("fixed")))
    render(<SettingsChecks />)
    fireEvent.click(screen.getByRole("button", { name: /Doctor/ }))
    await screen.findByRole("dialog")
    expect(screen.getByRole("button", { name: "Decline" })).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Fix" }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Doctor: fixed 1 problem(s)."))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("offers only Close when nothing is fixable", async () => {
    api.fetchDoctor.mockResolvedValue(doctor(finding("needs_you")))
    render(<SettingsChecks />)
    fireEvent.click(screen.getByRole("button", { name: /Doctor/ }))
    await screen.findByRole("dialog")
    expect(screen.queryByRole("button", { name: "Fix" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Decline" })).toBeNull()
    expect(screen.getAllByRole("button", { name: "Close" }).length).toBeGreaterThan(0) // the footer's and the corner's
  })

  it("keeps the dialog open with what is left when a fix does not clear everything", async () => {
    api.fetchDoctor.mockResolvedValue(doctor(finding("fixable", "one"), finding("fixable", "two")))
    api.fixDoctor.mockResolvedValue(doctor(finding("fixed", "one"), finding("failed", "two")))
    render(<SettingsChecks />)
    fireEvent.click(screen.getByRole("button", { name: /Doctor/ }))
    await screen.findByRole("dialog")
    fireEvent.click(screen.getByRole("button", { name: "Fix" }))
    await waitFor(() => expect(screen.getByText(/Could not fix/)).toBeTruthy())
    expect(toast.success).not.toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: "Fix" })).toBeNull()
  })

  it("notifies for a clean vault, and opens a Close-only dialog for a problem", async () => {
    api.fetchHealth.mockResolvedValueOnce({ ok: true, report: { persona: "samantha", notes: 7, problems: 0, limits: "", checks: [] } })
    render(<SettingsChecks />)
    fireEvent.click(screen.getByRole("button", { name: /Vault health/ }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Vault health: nothing wrong in 7 notes."))
    expect(screen.queryByRole("dialog")).toBeNull()

    api.fetchHealth.mockResolvedValueOnce({
      ok: true,
      report: {
        persona: "samantha",
        notes: 2,
        problems: 1,
        limits: "Links are not all checked.",
        checks: [{ heading: "Empty notes", problem: true, findings: [{ note: "A.md", message: "has no text" }] }],
      },
    })
    fireEvent.click(screen.getByRole("button", { name: /Vault health/ }))
    await screen.findByRole("dialog")
    expect(screen.getByText("Empty notes (1)")).toBeTruthy()
    expect(screen.getByText("Links are not all checked.")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Fix" })).toBeNull()
  })

  it("shows a failure as an error notification and never as a dialog", async () => {
    api.fetchHealth.mockResolvedValue({ ok: false, error: "No vault is set up." })
    render(<SettingsChecks />)
    fireEvent.click(screen.getByRole("button", { name: /Vault health/ }))
    await waitFor(() => expect(notify.error).toHaveBeenCalledWith("Vault health: No vault is set up."))
    expect(screen.queryByRole("dialog")).toBeNull()
  })
})
