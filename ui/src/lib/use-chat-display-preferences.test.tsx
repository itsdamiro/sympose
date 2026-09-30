// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { useChatDisplayPreferences } from "./use-chat-display-preferences"

afterEach(() => {
  cleanup()
  document.cookie = "sympose:chat.showGrounding=; max-age=0"
})

describe("useChatDisplayPreferences", () => {
  it("shows the grounded-notes line unless the user turned it off", () => {
    const { result } = renderHook(() => useChatDisplayPreferences())
    expect(result.current[0].showGrounding).toBe(true)
  })

  it("keeps a change in a cookie, so the next visit remembers it", () => {
    const first = renderHook(() => useChatDisplayPreferences())
    act(() => first.result.current[1]("showGrounding", false))
    expect(first.result.current[0].showGrounding).toBe(false)
    first.unmount()
    const second = renderHook(() => useChatDisplayPreferences())
    expect(second.result.current[0].showGrounding).toBe(false)
  })
})
