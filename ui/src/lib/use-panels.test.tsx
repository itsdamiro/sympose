// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { usePanels } from "./use-panels"

beforeEach(() => {
  vi.useFakeTimers()
  document.cookie = "sympose:shell.order=content,editor; path=/"
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  document.cookie = "sympose:shell.order=; path=/; max-age=0"
})

describe("usePanels at the tablet width (two panels on the stage)", () => {
  it("slides the oldest panel out before the newcomer arrives", () => {
    const { result } = renderHook(() => usePanels("tablet"))
    expect(result.current.visible).toEqual(["content", "editor"])
    act(() => result.current.open("chat"))
    expect(result.current.visible).toEqual(["editor"]) // the outgoing one is gone at once
    act(() => void vi.advanceTimersByTime(320))
    expect(result.current.visible).toEqual(["editor", "chat"])
  })

  it("brings the outgoing panel back when the newcomer is closed again within the slide", () => {
    const { result } = renderHook(() => usePanels("tablet"))
    act(() => result.current.open("chat"))
    act(() => result.current.close("chat")) // a quick toggle, before the 320 ms are up
    act(() => void vi.advanceTimersByTime(1000))
    expect(result.current.visible).toEqual(["content", "editor"])
  })

  it("does not leave a panel held back when the newcomer is opened twice within the slide", () => {
    const { result, rerender } = renderHook(({ bp }) => usePanels(bp), { initialProps: { bp: "tablet" as const } })
    act(() => result.current.open("chat"))
    act(() => result.current.open("chat"))
    act(() => void vi.advanceTimersByTime(1000))
    expect(result.current.visible).toEqual(["editor", "chat"])
    // The panel pushed out is hidden by the cap only: a wider screen shows it again.
    rerender({ bp: "desktop" as never })
    expect(result.current.visible).toEqual(["content", "editor", "chat"])
  })
})
