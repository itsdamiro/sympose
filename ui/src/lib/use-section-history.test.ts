// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { getCookie, setCookie } from "./cookies"
import { useSectionHistory } from "./use-section-history"

const COOKIE = "sympose:shell.section"

function visit(result: { current: ReturnType<typeof useSectionHistory> }, ...ids: string[]) {
  for (const id of ids) act(() => result.current.setActive(id))
}

describe("useSectionHistory", () => {
  beforeEach(() => {
    document.cookie.split(";").forEach((c) => {
      const name = c.split("=")[0]?.trim()
      if (name) document.cookie = `${name}=; path=/; max-age=0`
    })
  })

  it("starts on the remembered section, or on none, with nowhere to go back or forward", () => {
    setCookie(COOKIE, "Notes")
    const { result } = renderHook(() => useSectionHistory())
    expect(result.current.active).toBe("Notes")
    expect(result.current.canGoBack).toBe(false)
    expect(result.current.canGoForward).toBe(false)
    expect(result.current.contentDirection).toBe("forward")
    document.cookie = `${COOKIE}=; path=/; max-age=0`
    expect(renderHook(() => useSectionHistory()).result.current.active).toBe("")
  })

  it("remembers each pick in the cookie", () => {
    const { result } = renderHook(() => useSectionHistory())
    visit(result, "Daily")
    expect(getCookie(COOKIE)).toBe("Daily")
  })

  it("records each new section as a visit and goes back and forward through them", () => {
    const { result } = renderHook(() => useSectionHistory())
    visit(result, "A", "B", "C")
    expect(result.current.canGoBack).toBe(true)
    expect(result.current.canGoForward).toBe(false)

    act(() => result.current.goBack())
    expect(result.current.active).toBe("B")
    expect(result.current.contentDirection).toBe("back")
    expect(result.current.canGoForward).toBe(true)

    act(() => result.current.goBack())
    expect(result.current.active).toBe("A")
    act(() => result.current.goBack())
    expect(result.current.active).toBe("") // the section the session started on
    expect(result.current.canGoBack).toBe(false)

    act(() => result.current.goForward())
    expect(result.current.active).toBe("A")
    expect(result.current.contentDirection).toBe("forward")
  })

  it("does nothing on back at the start or forward at the end", () => {
    const { result } = renderHook(() => useSectionHistory())
    visit(result, "A")
    act(() => result.current.goForward())
    expect(result.current.active).toBe("A")
    act(() => result.current.goBack())
    act(() => result.current.goBack())
    expect(result.current.active).toBe("")
  })

  it("does not record a back or forward click as a new visit", () => {
    const { result } = renderHook(() => useSectionHistory())
    visit(result, "A", "B")
    act(() => result.current.goBack())
    act(() => result.current.goBack())
    act(() => result.current.goForward())
    act(() => result.current.goForward())
    expect(result.current.active).toBe("B")
    expect(result.current.canGoForward).toBe(false)
    act(() => result.current.goBack())
    act(() => result.current.goBack())
    act(() => result.current.goBack())
    expect(result.current.active).toBe("") // three entries only: "", A, B
  })

  it("drops what was ahead when a new section is picked after going back", () => {
    const { result } = renderHook(() => useSectionHistory())
    visit(result, "A", "B")
    act(() => result.current.goBack())
    visit(result, "C")
    expect(result.current.canGoForward).toBe(false)
    act(() => result.current.goBack())
    expect(result.current.active).toBe("A")
  })

  it("does not record the section it is already on", () => {
    const { result } = renderHook(() => useSectionHistory())
    visit(result, "A", "A")
    act(() => result.current.goBack())
    expect(result.current.active).toBe("")
  })

  it("lets the caller set the slide direction for a pick that is not back or forward", () => {
    const { result } = renderHook(() => useSectionHistory())
    act(() => result.current.setContentDirection("back"))
    expect(result.current.contentDirection).toBe("back")
  })
})
