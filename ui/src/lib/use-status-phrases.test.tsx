// @vitest-environment jsdom
import { cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchStatusPhrases: vi.fn() }))
vi.mock("@/lib/status-phrases-api", async (original) => ({ ...(await original<object>()), ...api }))

import { GENERIC_PHRASES } from "./status-phrases-api"
import { useStatusPhrases } from "./use-status-phrases"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("useStatusPhrases", () => {
  it("gives the generic phrases until the persona's are read, then its own", async () => {
    api.fetchStatusPhrases.mockResolvedValue({ phrases: ["Own one…"], own: true })
    const { result } = renderHook(() => useStatusPhrases("samantha", false))
    expect(result.current).toEqual(GENERIC_PHRASES)
    await waitFor(() => expect(result.current).toEqual(["Own one…"]))
  })

  it("keeps the generic phrases when the backend cannot say", async () => {
    api.fetchStatusPhrases.mockResolvedValue(null)
    const { result } = renderHook(() => useStatusPhrases("samantha", false))
    await waitFor(() => expect(api.fetchStatusPhrases).toHaveBeenCalled())
    expect(result.current).toEqual(GENERIC_PHRASES)
  })

  it("does not show one persona's phrases for another while the new one is read", async () => {
    let resolveSecond: (v: unknown) => void = () => {}
    api.fetchStatusPhrases
      .mockResolvedValueOnce({ phrases: ["Sam's…"], own: true })
      .mockReturnValueOnce(new Promise((r) => (resolveSecond = r)))
    const { result, rerender } = renderHook(({ p }) => useStatusPhrases(p, false), { initialProps: { p: "samantha" } })
    await waitFor(() => expect(result.current).toEqual(["Sam's…"]))
    rerender({ p: "aria" })
    expect(result.current).toEqual(GENERIC_PHRASES)
    resolveSecond({ phrases: ["Aria's…"], own: true })
    await waitFor(() => expect(result.current).toEqual(["Aria's…"]))
  })

  it("ignores an answer that arrives after the persona has changed", async () => {
    let resolveFirst: (v: unknown) => void = () => {}
    api.fetchStatusPhrases
      .mockReturnValueOnce(new Promise((r) => (resolveFirst = r)))
      .mockResolvedValueOnce({ phrases: ["Aria's…"], own: true })
    const { result, rerender } = renderHook(({ p }) => useStatusPhrases(p, false), { initialProps: { p: "samantha" } })
    rerender({ p: "aria" })
    await waitFor(() => expect(result.current).toEqual(["Aria's…"]))
    resolveFirst({ phrases: ["Sam's, too late…"], own: true }) // the first persona's answer, arriving late
    await new Promise((r) => setTimeout(r, 20))
    expect(result.current).toEqual(["Aria's…"])
  })

  it("reads again when a reply ends while the persona has only the generic phrases, and stops once it has its own", async () => {
    api.fetchStatusPhrases
      .mockResolvedValueOnce({ phrases: ["Generic…"], own: false })
      .mockResolvedValueOnce({ phrases: ["Own now…"], own: true })
    const { result, rerender } = renderHook(({ sending }) => useStatusPhrases("samantha", sending), { initialProps: { sending: false } })
    await waitFor(() => expect(result.current).toEqual(["Generic…"]))
    rerender({ sending: true }) // a reply in flight: no read
    expect(api.fetchStatusPhrases).toHaveBeenCalledTimes(1)
    rerender({ sending: false }) // the reply ended: read again
    await waitFor(() => expect(result.current).toEqual(["Own now…"]))
    rerender({ sending: true })
    rerender({ sending: false })
    expect(api.fetchStatusPhrases).toHaveBeenCalledTimes(2) // its own are there: nothing more to read
  })

  it("reads nothing without a persona", () => {
    renderHook(() => useStatusPhrases(null, false))
    expect(api.fetchStatusPhrases).not.toHaveBeenCalled()
  })
})
