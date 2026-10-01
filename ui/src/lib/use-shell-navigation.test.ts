// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { MENU_ACCOUNT_ID, MENU_SETTINGS_ID, MENU_TRASH_ID, type MainMenuItem } from "@/components/sympose"
import { getCookieBool } from "./cookies"
import type { Panels, StagePanel } from "./use-panels"
import { useShellNavigation } from "./use-shell-navigation"

function fakePanels(open: StagePanel[] = []) {
  const set = new Set<StagePanel>(open)
  return {
    set,
    isOpen: (p: StagePanel) => set.has(p),
    open: vi.fn((p: StagePanel) => void set.add(p)),
    close: vi.fn((p: StagePanel) => void set.delete(p)),
    toggle: vi.fn(),
    visible: [] as StagePanel[],
  }
}
const items = (...ids: string[]) => ids.map((id) => ({ id, label: id, type: "folder" }) as unknown as MainMenuItem)

function setup(
  init: { isPhone?: boolean; active?: string; open?: StagePanel[]; menu?: string[]; notes?: string[] } = {}
) {
  const panels = fakePanels(init.open)
  const setActive = vi.fn()
  const setContentDirection = vi.fn()
  const selectNote = vi.fn()
  const closeCreate = vi.fn()
  const hook = renderHook(
    (p: { active: string }) =>
      useShellNavigation({
        isPhone: init.isPhone ?? false,
        panels: panels as unknown as Panels,
        active: p.active,
        setActive,
        setContentDirection,
        menuItems: items(...(init.menu ?? ["Notes", "Daily"])),
        noteIds: new Set(init.notes ?? []),
        selectNote,
        closeCreate,
      }),
    { initialProps: { active: init.active ?? "Notes" } }
  )
  return { panels, setActive, setContentDirection, selectNote, closeCreate, ...hook }
}

beforeEach(() => {
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0]?.trim()
    if (name) document.cookie = `${name}=; path=/; max-age=0`
  })
})

describe("useShellNavigation: which section shows", () => {
  it("shows the section picked when the menu has it", () => {
    expect(setup({ active: "Daily" }).result.current.resolvedActive).toBe("Daily")
  })

  it("falls back to the first menu entry for a remembered folder that is gone", () => {
    expect(setup({ active: "Gone" }).result.current.resolvedActive).toBe("Notes")
  })

  it("keeps the remembered section while the menu is still empty", () => {
    expect(setup({ active: "Gone", menu: [] }).result.current.resolvedActive).toBe("Gone")
  })

  it("keeps Settings, Persona and the Bin as they are, though they are not in the menu", () => {
    for (const id of [MENU_SETTINGS_ID, MENU_ACCOUNT_ID, MENU_TRASH_ID]) {
      const { result } = setup({ active: id })
      expect(result.current.resolvedActive).toBe(id)
      expect(result.current.isSentinel).toBe(true)
    }
    expect(setup({ active: "Notes" }).result.current.isSentinel).toBe(false)
  })
})

describe("useShellNavigation: picking a section", () => {
  it("opens a different section forward and brings the content panel up", () => {
    const { result, panels, setActive, setContentDirection } = setup()
    act(() => result.current.selectSection("Daily"))
    expect(setContentDirection).toHaveBeenCalledWith("forward")
    expect(setActive).toHaveBeenCalledWith("Daily")
    expect(panels.open).toHaveBeenCalledWith("content")
  })

  it("switches to a different section while the content panel is open, without closing it", () => {
    const { result, panels, setActive } = setup({ open: ["content"] })
    act(() => result.current.selectSection("Daily"))
    expect(setActive).toHaveBeenCalledWith("Daily")
    expect(panels.close).not.toHaveBeenCalled()
  })

  it("closes the content panel when the section already showing is picked again", () => {
    const { result, panels, setActive } = setup({ open: ["content"] })
    act(() => result.current.selectSection("Notes"))
    expect(panels.close).toHaveBeenCalledWith("content")
    expect(setActive).not.toHaveBeenCalled()
  })

  it("opens the section already showing when its panel is closed", () => {
    const { result, panels, setActive } = setup({ open: [] })
    act(() => result.current.selectSection("Notes"))
    expect(setActive).toHaveBeenCalledWith("Notes")
    expect(panels.open).toHaveBeenCalledWith("content")
  })

  it("compares with the section that is shown, not the one remembered, when the remembered one is gone", () => {
    const { result, panels } = setup({ active: "Gone", open: ["content"] })
    act(() => result.current.selectSection("Notes"))
    expect(panels.close).toHaveBeenCalledWith("content")
  })

  it("selects a root note as well as showing it", () => {
    const { result, selectNote } = setup({ menu: ["Notes", "README.md"], notes: ["README.md"] })
    act(() => result.current.selectSection("README.md"))
    expect(selectNote).toHaveBeenCalledWith("README.md")
    act(() => result.current.selectSection("Daily"))
    expect(selectNote).toHaveBeenCalledTimes(1)
  })

  it("drops a half-typed create-input only on the way to the Bin", () => {
    const { result, closeCreate } = setup()
    act(() => result.current.selectSection("Daily"))
    expect(closeCreate).not.toHaveBeenCalled()
    act(() => result.current.selectSection(MENU_TRASH_ID))
    expect(closeCreate).toHaveBeenCalledTimes(1)
  })
})

describe("useShellNavigation: the phone's vault view", () => {
  it("is closed to begin with, opens on reveal and is remembered in a cookie", () => {
    const { result } = setup({ isPhone: true })
    expect(result.current.menuShown).toBe(false)
    act(() => result.current.revealMenu())
    expect(result.current.menuShown).toBe(true)
    expect(getCookieBool("sympose:shell.rail", false)).toBe(true)
  })

  it("starts open when it was left open", () => {
    document.cookie = "sympose:shell.rail=1; path=/"
    expect(setup({ isPhone: true }).result.current.menuShown).toBe(true)
  })

  it("brings the content panel up on reveal, and lands on a folder when it was on Settings", () => {
    const { result, panels, setActive } = setup({ isPhone: true, active: MENU_SETTINGS_ID })
    act(() => result.current.revealMenu())
    expect(setActive).toHaveBeenCalledWith("Notes")
    expect(panels.open).toHaveBeenCalledWith("content")
  })

  it("stays on the folder it was on when revealed from a folder", () => {
    const { result, setActive } = setup({ isPhone: true, active: "Daily" })
    act(() => result.current.revealMenu())
    expect(setActive).not.toHaveBeenCalled()
  })

  it("does not change section when revealed from Settings with an empty menu", () => {
    const { result, setActive } = setup({ isPhone: true, active: MENU_SETTINGS_ID, menu: [] })
    act(() => result.current.revealMenu())
    expect(setActive).not.toHaveBeenCalled()
  })

  it("returns to the chat that was open before, when closed", () => {
    const { result, panels } = setup({ isPhone: true, open: ["chat"] })
    act(() => result.current.revealMenu())
    act(() => result.current.revealMenu())
    expect(result.current.menuShown).toBe(false)
    expect(panels.close).toHaveBeenCalledWith("content")
    expect(panels.open).toHaveBeenLastCalledWith("chat")
  })

  it("returns to the editor if that was what was open, and prefers the chat if both were", () => {
    const a = setup({ isPhone: true, open: ["editor"] })
    act(() => a.result.current.revealMenu())
    act(() => a.result.current.revealMenu())
    expect(a.panels.open).toHaveBeenLastCalledWith("editor")
    const b = setup({ isPhone: true, open: ["editor", "chat"] })
    act(() => b.result.current.revealMenu())
    act(() => b.result.current.revealMenu())
    expect(b.panels.open).toHaveBeenLastCalledWith("chat")
  })

  it("reopens nothing when nothing was open before", () => {
    const { result, panels } = setup({ isPhone: true })
    act(() => result.current.revealMenu())
    panels.open.mockClear()
    act(() => result.current.revealMenu())
    expect(panels.open).not.toHaveBeenCalled()
  })

  it("slides the menu away when Settings or Persona is picked on a phone", () => {
    for (const id of [MENU_SETTINGS_ID, MENU_ACCOUNT_ID]) {
      document.cookie = "sympose:shell.rail=1; path=/"
      const { result } = setup({ isPhone: true })
      expect(result.current.menuShown).toBe(true)
      act(() => result.current.selectSection(id))
      expect(result.current.menuShown).toBe(false)
    }
  })

  it("keeps the menu when the Bin is picked on a phone, as it does for a folder", () => {
    document.cookie = "sympose:shell.rail=1; path=/"
    const { result } = setup({ isPhone: true })
    act(() => result.current.selectSection(MENU_TRASH_ID))
    expect(result.current.menuShown).toBe(true)
  })

  it("does not slide the menu away for Settings on a larger screen", () => {
    document.cookie = "sympose:shell.rail=1; path=/"
    const { result } = setup({ isPhone: false })
    act(() => result.current.selectSection(MENU_SETTINGS_ID))
    expect(result.current.menuShown).toBe(true)
  })

  it("keeps the menu when a folder is picked on a phone", () => {
    document.cookie = "sympose:shell.rail=1; path=/"
    const { result } = setup({ isPhone: true })
    act(() => result.current.selectSection("Daily"))
    expect(result.current.menuShown).toBe(true)
  })

  it("drops the menu too when the open section is picked again on a phone, so the next toggle reopens it (#84)", () => {
    document.cookie = "sympose:shell.rail=1; path=/"
    const { result, panels } = setup({ isPhone: true, open: ["content"] })
    act(() => result.current.selectSection("Notes"))
    expect(panels.close).toHaveBeenCalledWith("content")
    expect(result.current.menuShown).toBe(false)
  })

  it("leaves the menu state alone when the open section is picked again on a larger screen", () => {
    document.cookie = "sympose:shell.rail=1; path=/"
    const { result } = setup({ isPhone: false, open: ["content"] })
    act(() => result.current.selectSection("Notes"))
    expect(result.current.menuShown).toBe(true)
  })
})
