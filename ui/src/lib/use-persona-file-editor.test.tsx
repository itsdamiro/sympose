// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchPersonaFile: vi.fn(), savePersonaFile: vi.fn() }))
vi.mock("@/lib/persona-files-api", () => api)

import { usePersonaFileEditor } from "./use-persona-file-editor"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const setup = (handle = "samantha") => {
  const refreshFiles = vi.fn()
  const hook = renderHook(({ h }) => usePersonaFileEditor({ handle: h, personaName: "Samantha", refreshFiles }), { initialProps: { h: handle } })
  return { ...hook, refreshFiles }
}

describe("usePersonaFileEditor", () => {
  it("shows no persona file until one is opened, and then names it for the editor", () => {
    const { result } = setup()
    expect(result.current.current).toBeNull()
    expect(result.current.path).toBeUndefined()
    act(() => result.current.open("soul.md"))
    expect(result.current.current).toEqual({ handle: "samantha", name: "soul.md" })
    expect(result.current.path).toBe("persona:samantha/soul.md") // a key that is never a vault path
    expect(result.current.file?.title).toBe("Samantha · soul.md")
  })

  it("loads the file through the persona's files, a file not written yet as empty", async () => {
    api.fetchPersonaFile.mockResolvedValueOnce({ name: "soul.md", content: "voice", mtime: 7, local: false })
    api.fetchPersonaFile.mockResolvedValueOnce({ name: "context.md", content: "", mtime: null, local: false })
    api.fetchPersonaFile.mockResolvedValueOnce(null)
    const { result } = setup()
    act(() => result.current.open("soul.md"))
    expect(await result.current.file!.load("persona:samantha/soul.md")).toEqual({ content: "voice", mtime: 7 })
    act(() => result.current.open("context.md"))
    expect(await result.current.file!.load("persona:samantha/context.md")).toEqual({ content: "", mtime: undefined })
    act(() => result.current.open("profile.md"))
    expect(await result.current.file!.load("persona:samantha/profile.md")).toBeNull()
    expect(api.fetchPersonaFile.mock.calls.map((c) => c.join(":"))).toEqual(["samantha:soul.md", "samantha:context.md", "samantha:profile.md"])
  })

  it("saves through the persona's files and asks for the list again, since a soul save makes a copy", async () => {
    api.savePersonaFile.mockResolvedValue({ ok: true, mtime: 9, local: true })
    const { result, refreshFiles } = setup()
    act(() => result.current.open("soul.md"))
    const saved = await result.current.file!.save("persona:samantha/soul.md", "my voice", 7)
    expect(saved).toEqual({ ok: true, mtime: 9, local: true })
    expect(api.savePersonaFile).toHaveBeenCalledWith("samantha", "soul.md", "my voice", 7)
    expect(refreshFiles).toHaveBeenCalledTimes(1)
  })

  it("does not ask for the list again when a save failed", async () => {
    api.savePersonaFile.mockResolvedValue({ ok: false, error: "changed on disk", conflict: true })
    const { result, refreshFiles } = setup()
    act(() => result.current.open("profile.md"))
    expect((await result.current.file!.save("persona:samantha/profile.md", "x", 1)).ok).toBe(false)
    expect(refreshFiles).not.toHaveBeenCalled()
  })

  it("closes, and forgets a file of the persona before when the persona changes", () => {
    const { result, rerender } = setup()
    act(() => result.current.open("soul.md"))
    rerender({ h: "aria" })
    expect(result.current.current).toBeNull()
    act(() => result.current.open("profile.md"))
    expect(result.current.current).toEqual({ handle: "aria", name: "profile.md" })
    act(() => result.current.close())
    expect(result.current.current).toBeNull()
  })

  it("has a reload token that moves when the file is changed on disk from outside", () => {
    const { result } = setup()
    const before = result.current.reloadToken
    act(() => result.current.reload())
    expect(result.current.reloadToken).toBe(before + 1)
  })
})
