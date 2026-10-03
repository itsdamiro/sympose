// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ listPersonaFiles: vi.fn() }))
vi.mock("@/lib/persona-files-api", () => api)

import { usePersonaFiles } from "./use-persona-files"

const info = (name: string, over: Record<string, unknown> = {}) => ({ name, label: name, description: "", exists: true, local: false, pending: false, ...over })

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("usePersonaFiles", () => {
  it("lists the persona's files, and none until they have arrived", async () => {
    api.listPersonaFiles.mockResolvedValue([info("soul.md"), info("profile.md")])
    const { result } = renderHook(() => usePersonaFiles("samantha"))
    expect(result.current.files).toEqual([])
    await waitFor(() => expect(result.current.files.map((f) => f.name)).toEqual(["soul.md", "profile.md"]))
    expect(api.listPersonaFiles).toHaveBeenCalledWith("samantha")
  })

  it("reads them again when asked, as after a save made a copy of the soul or a rewrite was resolved", async () => {
    api.listPersonaFiles.mockResolvedValueOnce([info("soul.md")]).mockResolvedValueOnce([info("soul.md", { local: true })])
    const { result } = renderHook(() => usePersonaFiles("samantha"))
    await waitFor(() => expect(result.current.files[0]?.local).toBe(false))
    await act(async () => result.current.refresh())
    expect(result.current.files[0].local).toBe(true)
  })

  it("never shows one persona's files for another, while the other's load or when a late answer arrives", async () => {
    let lateForSamantha!: (v: unknown) => void
    api.listPersonaFiles.mockImplementation((handle: string) =>
      handle === "samantha" ? new Promise((resolve) => (lateForSamantha = resolve)) : Promise.resolve([info("profile.md")])
    )
    const { result, rerender } = renderHook(({ handle }) => usePersonaFiles(handle), { initialProps: { handle: "samantha" } })
    rerender({ handle: "aria" })
    await waitFor(() => expect(result.current.files.map((f) => f.name)).toEqual(["profile.md"]))
    await act(async () => lateForSamantha([info("soul.md")]))
    expect(result.current.files.map((f) => f.name)).toEqual(["profile.md"])
  })
})
