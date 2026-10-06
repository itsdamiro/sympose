// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { PersonaFileInfo } from "@/lib/persona-files-api"

const api = vi.hoisted(() => ({ resetPersonaSoul: vi.fn(), fetchPendingRewrite: vi.fn(), resolvePendingRewrite: vi.fn() }))
vi.mock("@/lib/persona-files-api", () => api)
const notify = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))
const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }))
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmMock }))

import { PersonaFileBanner } from "./persona-file-banner"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const info = (name: string, over: Partial<PersonaFileInfo> = {}): PersonaFileInfo => ({
  name, label: name, description: `What ${name} is.`, exists: true, local: false, pending: false, ...over,
})
const TITLE = "Samantha · file.md"

describe("PersonaFileBanner", () => {
  it("says the soul being edited is the shipped one, and that saving makes the user's own copy", () => {
    render(<PersonaFileBanner title={TITLE} handle="samantha" name="soul.md" info={info("soul.md")} onChanged={() => {}} />)
    expect(screen.getByText(/default persona description/i)).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Reset to default" })).toBeNull()
  })

  it("says the user's own soul is in use and offers to put the shipped one back, after asking", async () => {
    api.resetPersonaSoul.mockResolvedValue(true)
    const onChanged = vi.fn()
    render(<PersonaFileBanner title={TITLE} handle="samantha" name="soul.md" info={info("soul.md", { local: true })} onChanged={onChanged} />)
    expect(screen.getByText(/your own version/i)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }))
    const ask = confirmMock.mock.calls[0][0]
    expect(ask.message).toMatch(/restore the default/i)
    expect(String(ask.description)).toMatch(/kept/i) // the user's text is set aside, not thrown away
    expect(api.resetPersonaSoul).not.toHaveBeenCalled() // nothing happens before it is confirmed
    await ask.onConfirm()
    expect(api.resetPersonaSoul).toHaveBeenCalledWith("samantha")
    expect(notify.success).toHaveBeenCalled()
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it("says why when the reset did not happen", async () => {
    api.resetPersonaSoul.mockResolvedValue(null)
    const onChanged = vi.fn()
    render(<PersonaFileBanner title={TITLE} handle="samantha" name="soul.md" info={info("soul.md", { local: true })} onChanged={onChanged} />)
    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }))
    await confirmMock.mock.calls[0][0].onConfirm()
    expect(notify.error).toHaveBeenCalled()
    expect(onChanged).not.toHaveBeenCalled()
  })

  it("says a rewrite is waiting, and Review shows it", async () => {
    api.fetchPendingRewrite.mockResolvedValue({ text: "x", diff: "-a\n+b" })
    render(<PersonaFileBanner title={TITLE} handle="samantha" name="profile.md" info={info("profile.md", { pending: true })} onChanged={() => {}} />)
    expect(screen.getByText(/proposed changes/i)).toBeTruthy()
    expect(api.fetchPendingRewrite).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Review" }))
    await waitFor(() => expect(api.fetchPendingRewrite).toHaveBeenCalledWith("samantha", "profile.md"))
    expect(await screen.findByText("Proposed changes to profile.md")).toBeTruthy()
  })

  it("tells the page to read the file again once a rewrite has been accepted", async () => {
    api.fetchPendingRewrite.mockResolvedValue({ text: "x", diff: "-a\n+b" })
    api.resolvePendingRewrite.mockResolvedValue({ ok: true })
    const onChanged = vi.fn()
    render(<PersonaFileBanner title={TITLE} handle="samantha" name="context.md" info={info("context.md", { pending: true })} onChanged={onChanged} />)
    fireEvent.click(screen.getByRole("button", { name: "Review" }))
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
  })

  it("always says which file this is, leading with its name", () => {
    render(<PersonaFileBanner title={TITLE} handle="samantha" name="soul.md" info={info("soul.md")} onChanged={() => {}} />)
    expect(screen.getByText(TITLE)).toBeTruthy()
  })

  it("says what a file with nothing particular to it is, in its own words", () => {
    for (const name of ["decisions.md", "profile.md", "context.md"]) {
      render(<PersonaFileBanner title={TITLE} handle="samantha" name={name} info={info(name)} onChanged={() => {}} />)
      expect(screen.getByText(TITLE)).toBeTruthy()
      expect(screen.getByText(`What ${name} is.`)).toBeTruthy()
      expect(screen.queryByRole("button")).toBeNull() // nothing to do here
      cleanup()
    }
  })

  it("still names the file before the files have been listed", () => {
    render(<PersonaFileBanner title={TITLE} handle="samantha" name="profile.md" info={undefined} onChanged={() => {}} />)
    expect(screen.getByText(TITLE)).toBeTruthy()
  })
})
