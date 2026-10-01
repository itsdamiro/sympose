// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { getCookie, setCookie, setCookieBool } from "./cookies"
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

  it("leaves the menu to its own saved width until the window size changes", () => {
    expect(setup("phone").result.current.collapsed).toBeUndefined()
    expect(setup("desktop").result.current.collapsed).toBeUndefined()
  })

  it("defaults to the rail on a smaller window and to the full menu on desktop", () => {
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBe(true)
    rerender({ bp: "phone" })
    expect(result.current.collapsed).toBe(true)
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(false)
  })

  it("keeps a menu the user collapsed on desktop collapsed across a trip through a smaller window (#123)", () => {
    const { result, rerender } = setup("desktop")
    act(() => result.current.onCollapsedChange(true))
    rerender({ bp: "tablet" })
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(true)
  })

  it("keeps a menu the user opened on a small window open when that size comes back", () => {
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    act(() => result.current.onCollapsedChange(false))
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(false)
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBe(false)
  })

  it("remembers each window size on its own", () => {
    const { result, rerender } = setup("desktop")
    act(() => result.current.onCollapsedChange(true)) // desktop: folded
    rerender({ bp: "tablet" })
    act(() => result.current.onCollapsedChange(false)) // tablet: opened
    rerender({ bp: "phone" })
    expect(result.current.collapsed).toBe(true) // phone never chosen: the default
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(true)
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBe(false)
  })

  it("saves the choice for the size it was made on, as 1 or 0", () => {
    const { result, rerender } = setup("desktop")
    act(() => result.current.onCollapsedChange(true))
    rerender({ bp: "tablet" })
    act(() => result.current.onCollapsedChange(false))
    expect([getCookie("sympose:pref.menuCollapsed.desktop"), getCookie("sympose:pref.menuCollapsed.tablet")]).toEqual(["1", "0"])
  })

  it("does not save a default as if it were a choice (the menu reports its own snap too)", () => {
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    act(() => result.current.onCollapsedChange(true)) // the menu following the snap
    rerender({ bp: "desktop" })
    act(() => result.current.onCollapsedChange(false))
    expect(getCookie("sympose:pref.menuCollapsed.tablet")).toBeNull()
    expect(getCookie("sympose:pref.menuCollapsed.desktop")).toBeNull()
  })

  it("uses a choice saved in an earlier visit when the size comes round", () => {
    setCookieBool("sympose:pref.menuCollapsed.tablet", false)
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBe(false)
  })

  it("ignores a saved value that is not a 1 or a 0", () => {
    setCookie("sympose:pref.menuCollapsed.tablet", "maybe")
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBe(true)
  })

  it("forces nothing when the auto-collapse preference is off (a size never chosen for leaves the menu as it is), but still keeps a choice", () => {
    setCookieBool("sympose:pref.autoCollapseMenu", false)
    const { result, rerender } = setup("desktop")
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBeUndefined()
    act(() => result.current.onCollapsedChange(true))
    rerender({ bp: "desktop" })
    expect(result.current.collapsed).toBe(true) // desktop was never chosen for: the menu is left as it is
    rerender({ bp: "tablet" })
    expect(result.current.collapsed).toBe(true)
  })
})
