// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { Panels, StagePanel } from "./use-panels"
import { useNebulaStage } from "./use-nebula-stage"

function fakePanels(visible: StagePanel[]) {
  const panels = { visible, isOpen: () => true, open: vi.fn(), close: vi.fn(), toggle: vi.fn() }
  return panels as Panels & { open: ReturnType<typeof vi.fn>; close: ReturnType<typeof vi.fn> }
}

describe("useNebulaStage", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    delete (window as { requestIdleCallback?: unknown }).requestIdleCallback
    delete (window as { cancelIdleCallback?: unknown }).cancelIdleCallback
  })

  describe("explore and focus", () => {
    it("touches no panel on mount, whichever mode it starts in", () => {
      const panels = fakePanels(["content", "editor"])
      renderHook(() => useNebulaStage(panels, "explore"))
      expect(panels.close).not.toHaveBeenCalled()
      expect(panels.open).not.toHaveBeenCalled()
    })

    it("closes every visible panel on entering explore and reopens them, in order, on leaving it", () => {
      const panels = fakePanels(["content", "editor"])
      const { rerender } = renderHook(({ mode }) => useNebulaStage(panels, mode), {
        initialProps: { mode: "focus" as "focus" | "explore" },
      })
      rerender({ mode: "explore" })
      expect(panels.close.mock.calls).toEqual([["content"], ["editor"]])
      expect(panels.open).not.toHaveBeenCalled()
      rerender({ mode: "focus" })
      expect(panels.open.mock.calls).toEqual([["content"], ["editor"]])
    })

    it("acts on the live panel handle, not the one it was first given", () => {
      const first = fakePanels(["content"])
      const { rerender } = renderHook(({ p, mode }) => useNebulaStage(p, mode), {
        initialProps: { p: first, mode: "focus" as "focus" | "explore" },
      })
      const second = fakePanels(["chat"])
      rerender({ p: second, mode: "focus" })
      rerender({ p: second, mode: "explore" })
      expect(second.close).toHaveBeenCalledWith("chat")
      expect(first.close).not.toHaveBeenCalled()
    })
  })

  describe("nebulaReady", () => {
    it("stops the fallback timer on unmount, so nothing is set on a gone shell", () => {
      const clear = vi.spyOn(window, "clearTimeout")
      const { unmount } = renderHook(() => useNebulaStage(fakePanels([]), "focus"))
      unmount()
      expect(clear).toHaveBeenCalled()
      clear.mockRestore()
    })

    it("turns true after the fallback delay where the browser has no idle callback", () => {
      const { result } = renderHook(() => useNebulaStage(fakePanels([]), "focus"))
      expect(result.current.nebulaReady).toBe(false)
      act(() => void vi.advanceTimersByTime(399))
      expect(result.current.nebulaReady).toBe(false)
      act(() => void vi.advanceTimersByTime(1))
      expect(result.current.nebulaReady).toBe(true)
    })

    it("waits for the browser to be idle where it can, and stops waiting on unmount", () => {
      let run: (() => void) | undefined
      const cancel = vi.fn()
      Object.assign(window, {
        requestIdleCallback: (cb: () => void) => ((run = cb), 7),
        cancelIdleCallback: cancel,
      })
      const { result, unmount } = renderHook(() => useNebulaStage(fakePanels([]), "focus"))
      act(() => void vi.advanceTimersByTime(5000))
      expect(result.current.nebulaReady).toBe(false)
      act(() => run?.())
      expect(result.current.nebulaReady).toBe(true)
      unmount()
      expect(cancel).toHaveBeenCalledWith(7)
    })
  })
})
