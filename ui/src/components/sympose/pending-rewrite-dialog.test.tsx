// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchPendingRewrite: vi.fn(), resolvePendingRewrite: vi.fn() }))
vi.mock("@/lib/persona-files-api", () => api)
const notify = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))

import { PendingRewriteDialog } from "./pending-rewrite-dialog"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const DIFF = "--- profile.md (current)\n+++ profile.md (proposed)\n@@ -1 +1,2 @@\n-likes small steps\n+likes small steps\n+prefers mornings"

function setup(over: Partial<React.ComponentProps<typeof PendingRewriteDialog>> = {}) {
  const props = { handle: "samantha", name: "profile.md", open: true, onClose: vi.fn(), onResolved: vi.fn(), ...over }
  render(<PendingRewriteDialog {...props} />)
  return props
}

describe("PendingRewriteDialog", () => {
  it("shows what she proposed as a diff against the file, additions and removals told apart", async () => {
    api.fetchPendingRewrite.mockResolvedValue({ text: "x", diff: DIFF })
    setup()
    expect(await screen.findByText("Proposed changes to profile.md")).toBeTruthy()
    expect(api.fetchPendingRewrite).toHaveBeenCalledWith("samantha", "profile.md")
    expect((await screen.findByText("+prefers mornings")).className).toContain("text-ok")
    expect(screen.getByText("-likes small steps").className).toContain("text-destructive")
    expect(screen.getByText("@@ -1 +1,2 @@").className).toContain("text-fg-muted")
  })

  it("applies it on Accept, tells the page and closes", async () => {
    api.fetchPendingRewrite.mockResolvedValue({ text: "x", diff: DIFF })
    api.resolvePendingRewrite.mockResolvedValue({ ok: true })
    const props = setup()
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }))
    await waitFor(() => expect(api.resolvePendingRewrite).toHaveBeenCalledWith("samantha", "profile.md", "accept"))
    await waitFor(() => expect(props.onResolved).toHaveBeenCalledTimes(1))
    expect(props.onClose).toHaveBeenCalled()
    expect(notify.success).toHaveBeenCalled()
  })

  it("removes it on Discard and leaves the file as it is", async () => {
    api.fetchPendingRewrite.mockResolvedValue({ text: "x", diff: DIFF })
    api.resolvePendingRewrite.mockResolvedValue({ ok: true })
    const props = setup()
    fireEvent.click(await screen.findByRole("button", { name: "Discard" }))
    await waitFor(() => expect(api.resolvePendingRewrite).toHaveBeenCalledWith("samantha", "profile.md", "discard"))
    await waitFor(() => expect(props.onResolved).toHaveBeenCalledTimes(1))
  })

  it("says why when it cannot be applied, and stays open", async () => {
    api.fetchPendingRewrite.mockResolvedValue({ text: "x", diff: DIFF })
    api.resolvePendingRewrite.mockResolvedValue({ ok: false, error: "Couldn't apply the rewrite of `profile.md`." })
    const props = setup()
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }))
    await waitFor(() => expect(notify.error).toHaveBeenCalledWith("Couldn't apply the rewrite of `profile.md`."))
    expect(props.onClose).not.toHaveBeenCalled()
    expect(props.onResolved).not.toHaveBeenCalled()
  })

  it("says so when nothing is waiting any more, offering no way to accept it", async () => {
    api.fetchPendingRewrite.mockResolvedValue(null)
    setup()
    expect(await screen.findByText("Nothing is waiting for this file.")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull()
  })

  it("reads nothing while it is closed", () => {
    setup({ open: false })
    expect(api.fetchPendingRewrite).not.toHaveBeenCalled()
  })
})
