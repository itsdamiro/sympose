// @vitest-environment jsdom
import { cleanup, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useOnWindowFocus } from "./use-on-window-focus"

afterEach(cleanup)

describe("useOnWindowFocus", () => {
  it("calls the callback each time the window is focused", () => {
    const callback = vi.fn()
    renderHook(() => useOnWindowFocus(callback))
    window.dispatchEvent(new Event("focus"))
    window.dispatchEvent(new Event("focus"))
    expect(callback).toHaveBeenCalledTimes(2)
  })

  it("calls the latest callback, not the one from the first render", () => {
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook(({ cb }) => useOnWindowFocus(cb), { initialProps: { cb: first } })
    rerender({ cb: second })
    window.dispatchEvent(new Event("focus"))
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })

  it("stops listening when the component goes away", () => {
    const callback = vi.fn()
    const { unmount } = renderHook(() => useOnWindowFocus(callback))
    unmount()
    window.dispatchEvent(new Event("focus"))
    expect(callback).not.toHaveBeenCalled()
  })
})
