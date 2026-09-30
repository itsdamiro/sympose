// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { useChatDisplayPreferences } from "./use-chat-display-preferences"

afterEach(() => {
  cleanup()
  document.cookie = "sympose:chat.showGrounding=; max-age=0"
  document.cookie = "sympose:chat.typeStatus=; max-age=0"
  document.cookie = "sympose:chat.showMeter=; max-age=0"
})

describe("useChatDisplayPreferences", () => {
  it("shows the grounded-notes line unless the user turned it off", () => {
    const { result } = renderHook(() => useChatDisplayPreferences())
    expect(result.current[0].showGrounding).toBe(true)
  })

  it("types the busy line out unless the user turned it off, and keeps that in a cookie too", () => {
    const first = renderHook(() => useChatDisplayPreferences())
    expect(first.result.current[0].typeStatus).toBe(true)
    act(() => first.result.current[1]("typeStatus", false))
    expect(document.cookie).toContain("sympose:chat.typeStatus=0")
    first.unmount()
    expect(renderHook(() => useChatDisplayPreferences()).result.current[0].typeStatus).toBe(false)
    expect(renderHook(() => useChatDisplayPreferences()).result.current[0].showGrounding).toBe(true) // independent
  })

  it("shows the context meter unless the user turned it off, and keeps that in a cookie too", () => {
    const first = renderHook(() => useChatDisplayPreferences())
    expect(first.result.current[0].showMeter).toBe(true)
    act(() => first.result.current[1]("showMeter", false))
    expect(document.cookie).toContain("sympose:chat.showMeter=0")
    first.unmount()
    const again = renderHook(() => useChatDisplayPreferences()).result.current[0]
    expect(again.showMeter).toBe(false)
    expect(again.typeStatus).toBe(true) // independent of the other switches
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
