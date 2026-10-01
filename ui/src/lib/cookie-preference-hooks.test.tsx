// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { getCookie, setCookie } from "./cookies"
import { useBrandMarkLabel } from "./use-brand-mark-preference"
import { useChatDisplayPreferences } from "./use-chat-display-preferences"
import { useEditorPreferences } from "./use-editor-preferences"
import { NEBULA_DEFAULTS, useNebulaPreferences } from "./use-nebula-preferences"
import { getNotificationPreferences, setNotificationPreference } from "./use-notification-preferences"

// What each cookie-backed preference hook reads and writes, name by name and format by format: a user's
// saved choices live in these cookies, so a refactor of the hooks must not move or reshape any of them.
const clear = () => {
  for (const part of document.cookie.split("; ")) {
    const name = part.split("=")[0]
    if (name) document.cookie = `${name}=; max-age=0; path=/`
  }
}
beforeEach(clear)
afterEach(clear)

describe("brand mark label", () => {
  it("defaults to the product name, reads 'vault', and ignores anything else", () => {
    expect(renderHook(() => useBrandMarkLabel()).result.current[0]).toBe("sympose")
    setCookie("sympose:brand_mark_label", "vault")
    expect(renderHook(() => useBrandMarkLabel()).result.current[0]).toBe("vault")
    setCookie("sympose:brand_mark_label", "garbage")
    expect(renderHook(() => useBrandMarkLabel()).result.current[0]).toBe("sympose")
  })

  it("writes the plain value", () => {
    const { result } = renderHook(() => useBrandMarkLabel())
    act(() => result.current[1]("vault"))
    expect(result.current[0]).toBe("vault")
    expect(getCookie("sympose:brand_mark_label")).toBe("vault")
  })
})

describe("chat display", () => {
  it("defaults all on, reads '1' and '0', and writes '1' and '0'", () => {
    expect(renderHook(() => useChatDisplayPreferences()).result.current[0]).toEqual({ showGrounding: true, typeStatus: true, showMeter: true })
    setCookie("sympose:chat.typeStatus", "0")
    setCookie("sympose:chat.showGrounding", "yes")
    const { result } = renderHook(() => useChatDisplayPreferences())
    expect(result.current[0].typeStatus).toBe(false)
    expect(result.current[0].showGrounding).toBe(false) // only "1" is true, as before
    act(() => result.current[1]("showMeter", false))
    expect(getCookie("sympose:chat.showMeter")).toBe("0")
    act(() => result.current[1]("showGrounding", true))
    expect(getCookie("sympose:chat.showGrounding")).toBe("1")
    expect(result.current[0]).toEqual({ showGrounding: true, typeStatus: false, showMeter: false })
  })
})

describe("editor", () => {
  it("has its defaults, reads each cookie, and falls back on an unknown value", () => {
    expect(renderHook(() => useEditorPreferences()).result.current[0]).toEqual({
      surface: "in-place", reveal: "caret", selectionUI: "menu", tableEditing: "source",
      focusOutline: "off", autosave: "off", hideExtension: "on",
    })
    setCookie("sympose:editor.surface", "source")
    setCookie("sympose:editor.selection_ui", "bar")
    setCookie("sympose:editor.table_editing", "cells")
    setCookie("sympose:editor.focus_outline", "on")
    setCookie("sympose:editor.autosave", "on")
    setCookie("sympose:editor.hide_extension", "off")
    setCookie("sympose:editor.reveal", "old-renamed-value")
    expect(renderHook(() => useEditorPreferences()).result.current[0]).toEqual({
      surface: "source", reveal: "caret", selectionUI: "bar", tableEditing: "cells",
      focusOutline: "on", autosave: "on", hideExtension: "off",
    })
  })

  it("writes the plain value under its own cookie", () => {
    const { result } = renderHook(() => useEditorPreferences())
    act(() => result.current[1]("selectionUI", "bar"))
    expect(getCookie("sympose:editor.selection_ui")).toBe("bar")
    expect(result.current[0].selectionUI).toBe("bar")
  })
})

describe("nebula", () => {
  it("starts from the defaults, reads bools, numbers and enums, and ignores bad ones", () => {
    expect(renderHook(() => useNebulaPreferences()).result.current[0]).toEqual(NEBULA_DEFAULTS)
    setCookie("sympose:nebula.interaction", "explore")
    setCookie("sympose:nebula.mode", "4d")
    setCookie("sympose:nebula.orphans", "1")
    setCookie("sympose:nebula.labels", "0")
    setCookie("sympose:nebula.focus_blur", "7.5")
    setCookie("sympose:nebula.link_distance", "NaN-ish")
    const p = renderHook(() => useNebulaPreferences()).result.current[0]
    expect([p.interaction, p.mode, p.orphans, p.labels, p.focusBlur, p.linkDistance]).toEqual(["explore", "2d", true, false, 7.5, 492])
  })

  it("writes bools as 1/0, numbers as text, enums as is", () => {
    const { result } = renderHook(() => useNebulaPreferences())
    act(() => {
      result.current[1]("orphans", true)
      result.current[1]("focusTint", 0.25)
      result.current[1]("mode", "3d")
    })
    expect([getCookie("sympose:nebula.orphans"), getCookie("sympose:nebula.focus_tint"), getCookie("sympose:nebula.mode")]).toEqual(["1", "0.25", "3d"])
    expect(result.current[0].focusTint).toBe(0.25)
  })
})

describe("notifications", () => {
  it("writes the plain value under its own cookie and updates the shared snapshot", () => {
    setNotificationPreference("position", "top-left")
    setNotificationPreference("confirm", "inline")
    setNotificationPreference("enabled", "off")
    expect(getCookie("sympose:notify.position")).toBe("top-left")
    expect(getCookie("sympose:notify.confirm")).toBe("inline")
    expect(getCookie("sympose:notify.enabled")).toBe("off")
    expect(getNotificationPreferences()).toEqual({ enabled: "off", confirm: "inline", position: "top-left" })
  })

  it("starts from the cookies it finds, and from the defaults for a missing or unknown one", async () => {
    setCookie("sympose:notify.confirm", "none")
    setCookie("sympose:notify.position", "top-center")
    setCookie("sympose:notify.enabled", "maybe")
    vi.resetModules()
    const fresh = await import("./use-notification-preferences")
    expect(fresh.getNotificationPreferences()).toEqual({ enabled: "on", confirm: "none", position: "top-center" })
  })
})
