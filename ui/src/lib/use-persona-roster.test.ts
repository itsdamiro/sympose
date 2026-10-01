// @vitest-environment jsdom
import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { LivePersona } from "./personas"
import { usePersonaRoster } from "./use-persona-roster"

const fetchPersonas = vi.fn()
vi.mock("./personas", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./personas")>()),
  fetchPersonas: () => fetchPersonas(),
}))

const persona = (handle: string, extra: Partial<LivePersona> = {}): LivePersona => ({
  handle,
  name: handle.toUpperCase(),
  title: "t",
  model: `${handle}-model`,
  skills: [],
  isDefault: false,
  ...extra,
})

function setup(activePersona: string, modelInUse?: string) {
  const setActivePersona = vi.fn()
  const hook = renderHook(
    (p: { activePersona: string; modelInUse?: string }) =>
      usePersonaRoster({ activePersona: p.activePersona, setActivePersona, modelInUse: p.modelInUse }),
    { initialProps: { activePersona, modelInUse } }
  )
  return { setActivePersona, ...hook }
}

beforeEach(() => {
  vi.resetAllMocks()
  fetchPersonas.mockResolvedValue([persona("samantha", { isDefault: true }), persona("grace")])
})

describe("usePersonaRoster", () => {
  it("lists the roster once it is fetched, and names the active persona", async () => {
    const { result } = setup("grace")
    expect(result.current.rosterPersonas).toEqual([])
    expect(result.current.activePersonaName).toBe("grace") // the raw handle until the roster is known
    await waitFor(() => expect(result.current.rosterPersonas.length).toBe(2))
    expect(result.current.activePersonaName).toBe("GRACE")
    expect(result.current.activePersonaModel).toBe("grace-model")
  })

  it("replaces only the active persona's model with the one in use", async () => {
    const { result } = setup("grace", "gemini-x")
    await waitFor(() => expect(result.current.rosterPersonas.length).toBe(2))
    expect(result.current.rosterPersonas.map((p) => p.model)).toEqual(["samantha-model", "gemini-x"])
    expect(result.current.activePersonaModel).toBe("grace-model") // the persona's own setting, not the pick
  })

  it("keeps every model as the roster has it while none is known to be in use", async () => {
    const { result } = setup("grace", undefined)
    await waitFor(() => expect(result.current.rosterPersonas.length).toBe(2))
    expect(result.current.rosterPersonas.map((p) => p.model)).toEqual(["samantha-model", "grace-model"])
  })

  it("follows the model in use when it changes", async () => {
    const { result, rerender } = setup("grace", "a")
    await waitFor(() => expect(result.current.rosterPersonas.length).toBe(2))
    rerender({ activePersona: "grace", modelInUse: "b" })
    expect(result.current.rosterPersonas[1].model).toBe("b")
  })

  it("heals a persona cookie that names nobody on the roster, to the default persona", async () => {
    const { setActivePersona } = setup("removed")
    await waitFor(() => expect(setActivePersona).toHaveBeenCalledWith("samantha"))
  })

  it("heals to the persona marked default even when it is not first on the roster", async () => {
    fetchPersonas.mockResolvedValue([persona("grace"), persona("samantha", { isDefault: true })])
    const { setActivePersona } = setup("removed")
    await waitFor(() => expect(setActivePersona).toHaveBeenCalledWith("samantha"))
  })

  it("heals to the first persona when none is marked default", async () => {
    fetchPersonas.mockResolvedValue([persona("grace"), persona("anais")])
    const { setActivePersona } = setup("removed")
    await waitFor(() => expect(setActivePersona).toHaveBeenCalledWith("grace"))
  })

  it("leaves a persona that is on the roster alone, and waits while the roster is empty", async () => {
    const { setActivePersona, result } = setup("grace")
    await waitFor(() => expect(result.current.rosterPersonas.length).toBe(2))
    expect(setActivePersona).not.toHaveBeenCalled()
    fetchPersonas.mockResolvedValue([])
    const empty = setup("removed")
    await new Promise((r) => setTimeout(r, 20))
    expect(empty.setActivePersona).not.toHaveBeenCalled()
  })

  it("does not apply a roster that arrives after it was unmounted", async () => {
    let release: (v: LivePersona[]) => void = () => {}
    fetchPersonas.mockImplementation(() => new Promise((r) => (release = r)))
    const { result, unmount } = setup("grace")
    unmount()
    release([persona("grace")])
    await new Promise((r) => setTimeout(r, 20))
    expect(result.current.rosterPersonas).toEqual([])
  })

  it("gives the active persona's own accent and icon, and a neutral look for one it does not know", async () => {
    const { result } = setup("samantha")
    const known = result.current.activePersonaVisuals
    const unknown = setup("nobody").result.current.activePersonaVisuals
    expect(known.accent).not.toBe(unknown.accent)
    expect(unknown.icon).toBeTruthy()
  })
})
