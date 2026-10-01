// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { setCookieBool } from "./cookies"
import type { Breakpoint } from "./use-breakpoint"
import { useMenuCollapse } from "./use-menu-collapse"

function setup(start: Breakpoint) {
  return renderHook(({ bp }) => useMenuCollapse(bp), { initialProps: { bp: start } })
}

describe("useMenuCollapse", () => {
  beforeEach(() => {
    document.cookie.split(";").forEach((c) => {
      const name = c.split("=")[0]?.trim()
      if (name) document.cookie = `${name}=; path=/; max-age=0`
    })
  })

  it("leaves the menu to its own saved width until the breakpoint changes", () => {
    expect(setup("phone").result.current.collapsed).toBeUndefined()
    expect(setup("desktop").result.current.collapsed).toBeUndefined()
  })

  it("snaps to the rail when the window gets smaller, and back to the full menu on desktop", () => {
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBe(true)
    rerender({ bp: "phone" })
    expect(result.current.collapsed).toBe(true)
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(false)
  })

  it("opens the menu again on a return to desktop even if the user had collapsed it there before (as the code stands)", () => {
    const { result, rerender } = setup("desktop")
    act(() => result.current.onCollapsedChange(true))
    expect(result.current.collapsed).toBe(true)
    rerender({ bp: "tablet" }) // the breakpoint's rail takes over: from here it counts as forced
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(false)
  })

  it("keeps the user's open menu on a small window if they opened it by hand after the snap", () => {
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    act(() => result.current.onCollapsedChange(false))
    expect(result.current.collapsed).toBe(false)
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(false)
  })

  it("does not snap to the rail when the auto-collapse preference is off", () => {
    setCookieBool("sympose:pref.autoCollapseMenu", false)
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBeUndefined()
  })

  it("remembers that the rail was forced, across a user drag that did not collapse it", () => {
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" }) // forced rail
    act(() => result.current.onCollapsedChange(true)) // the user "collapses" an already-forced rail
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(false) // still the breakpoint's doing, so it expands again
  })
})
