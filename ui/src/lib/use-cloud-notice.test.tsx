// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { useCloudNotice } from "./use-cloud-notice"

afterEach(() => {
  const reset = renderHook(() => useCloudNotice(undefined)) // the store outlives a test: put it back
  act(() => reset.result.current.reopen())
  cleanup()
  document.cookie = "sympose:chat.cloudNoticeClosed=; max-age=0"
})

describe("useCloudNotice", () => {
  it("is open until the user closes it, and can be opened again", () => {
    const { result } = renderHook(() => useCloudNotice(true))
    expect(result.current.open).toBe(true)
    act(() => result.current.close())
    expect(result.current.open).toBe(false)
    act(() => result.current.reopen())
    expect(result.current.open).toBe(true)
  })

  it("remembers a close in a cookie", () => {
    const { result } = renderHook(() => useCloudNotice(true))
    act(() => result.current.close())
    expect(document.cookie).toContain("sympose:chat.cloudNoticeClosed=1")
  })

  it("writes nothing when nothing changed, e.g. a local model on screen while the notice was never closed", () => {
    renderHook(() => useCloudNotice(false))
    expect(document.cookie).not.toContain("cloudNoticeClosed")
  })

  it("keeps every place that shows it in step", () => {
    const one = renderHook(() => useCloudNotice(true))
    const two = renderHook(() => useCloudNotice(true))
    act(() => one.result.current.close())
    expect(two.result.current.open).toBe(false)
  })

  it("stays closed across a switch between cloud models", () => {
    const { result, rerender } = renderHook(({ cloud }) => useCloudNotice(cloud), { initialProps: { cloud: true as boolean | undefined } })
    act(() => result.current.close())
    rerender({ cloud: true })
    expect(result.current.open).toBe(false)
  })

  it("opens again once the model in use is a local one, so the next cloud switch is announced", () => {
    const { result, rerender } = renderHook(({ cloud }) => useCloudNotice(cloud), { initialProps: { cloud: true as boolean | undefined } })
    act(() => result.current.close())
    rerender({ cloud: false })
    expect(result.current.open).toBe(true)
    rerender({ cloud: true })
    expect(result.current.open).toBe(true)
  })

  it("does not reset while it is not yet known whether the model is cloud", () => {
    const { result, rerender } = renderHook(({ cloud }) => useCloudNotice(cloud), { initialProps: { cloud: true as boolean | undefined } })
    act(() => result.current.close())
    rerender({ cloud: undefined })
    expect(result.current.open).toBe(false)
  })
})
