// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FolderColorField } from "./folder-color-field"
import { COLOR_PRESETS, counterpart, presetFor } from "@/lib/folder-colors"

afterEach(cleanup)

function setup(accent: string | null = null, accentDark: string | null = null) {
  const onChange = vi.fn()
  render(<FolderColorField accent={accent} accentDark={accentDark} onChange={onChange} />)
  return onChange
}

describe("FolderColorField", () => {
  it("sets both colours from a preset", () => {
    const onChange = setup()
    fireEvent.click(screen.getByRole("button", { name: "Rose" }))
    expect(onChange).toHaveBeenCalledWith({ accent: "#be123c", accentDark: "#f2889b" })
  })

  it("marks the preset whose pair is the current one, and no preset for another pair", () => {
    setup("#be123c", "#f2889b")
    expect(screen.getByRole("button", { name: "Rose" }).getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "Cyan" }).getAttribute("aria-pressed")).toBe("false")
    expect(screen.getByRole("button", { name: "No colour" }).getAttribute("aria-pressed")).toBe("false")
    cleanup()
    setup("#be123c", "#000000")
    expect(screen.queryAllByRole("button", { pressed: true })).toEqual([])
  })

  it("marks no colour while neither is set, and clears both", () => {
    const onChange = setup()
    expect(screen.getByRole("button", { name: "No colour" }).getAttribute("aria-pressed")).toBe("true")
    cleanup()
    const again = setup("#be123c", "#f2889b")
    fireEvent.click(screen.getByRole("button", { name: "No colour" }))
    expect(again).toHaveBeenCalledWith({ accent: null, accentDark: null })
    expect(onChange).not.toHaveBeenCalled()
  })

  it("sets the light colour from its one input and works out the dark one from it", () => {
    const onChange = setup("#be123c", "#f2889b")
    fireEvent.change(screen.getByLabelText("Light theme colour"), { target: { value: "#112233" } })
    expect(onChange).toHaveBeenLastCalledWith({ accent: "#112233", accentDark: counterpart("#112233", "light") })
    expect(screen.queryByLabelText("Dark theme colour")).toBeNull()
  })

  it("in the dark theme the one input is the dark colour and the light one is worked out", () => {
    document.documentElement.classList.add("dark")
    try {
      const onChange = setup("#be123c", "#f2889b")
      expect((screen.getByLabelText("Dark theme colour") as HTMLInputElement).value).toBe("#f2889b")
      fireEvent.change(screen.getByLabelText("Dark theme colour"), { target: { value: "#aabbcc" } })
      expect(onChange).toHaveBeenLastCalledWith({ accent: counterpart("#aabbcc", "dark"), accentDark: "#aabbcc" })
    } finally {
      document.documentElement.classList.remove("dark")
    }
  })

  it("shows the colour in effect, not an unset one, when only the other theme's is set", () => {
    document.documentElement.classList.add("dark")
    try {
      setup("#be123c", null)
      const input = screen.getByLabelText("Dark theme colour") as HTMLInputElement
      expect(input.value).toBe("#be123c")
      expect(input.className).not.toContain("opacity-40")
    } finally {
      document.documentElement.classList.remove("dark")
    }
  })

  it("shows the matching colour of the other theme, read only, in its own swatch", () => {
    setup("#be123c", "#f2889b")
    const swatch = screen.getByRole("img", { name: "Dark theme colour, matched" })
    expect(swatch.style.background).toBe("rgb(242, 136, 155)")
  })
})

describe("counterpart", () => {
  const lightness = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    return (Math.max(r, g, b) + Math.min(r, g, b)) / 2
  }
  const hue = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
    const d = Math.max(r, g, b) - Math.min(r, g, b)
    return d === 0 ? 0 : Math.round(((Math.max(r, g, b) === r ? ((g - b) / d) % 6 : Math.max(r, g, b) === g ? (b - r) / d + 2 : (r - g) / d + 4) * 60 + 360) % 360)
  }

  it("gives a six-digit hex of the same hue, brighter for the dark theme than the colour it came from", () => {
    const dark = counterpart("#be123c", "light")
    expect(dark).toMatch(/^#[0-9a-f]{6}$/)
    expect(Math.abs(hue(dark) - hue("#be123c"))).toBeLessThanOrEqual(2)
    expect(lightness(dark)).toBeGreaterThan(lightness("#be123c"))
  })

  it("gives a deeper colour for the light theme than the bright one it came from", () => {
    const light = counterpart("#f2889b", "dark")
    expect(lightness(light)).toBeLessThan(lightness("#f2889b"))
    expect(Math.abs(hue(light) - hue("#f2889b"))).toBeLessThanOrEqual(2)
  })

  it("lands close to the presets' own pairs", () => {
    for (const p of COLOR_PRESETS) {
      expect(Math.abs(lightness(counterpart(p.light, "light")) - lightness(p.dark))).toBeLessThan(0.17)
      expect(Math.abs(lightness(counterpart(p.dark, "dark")) - lightness(p.light))).toBeLessThan(0.17)
    }
  })

  it("keeps a grey a grey, and does not blow up on black or white", () => {
    const grey = counterpart("#808080", "light")
    expect([grey.slice(1, 3), grey.slice(3, 5), grey.slice(5, 7)]).toEqual(Array(3).fill(grey.slice(1, 3)))
    expect(counterpart("#000000", "light")).toMatch(/^#[0-9a-f]{6}$/)
    expect(counterpart("#ffffff", "dark")).toMatch(/^#[0-9a-f]{6}$/)
  })
})

describe("presets", () => {
  it("are six-digit hex pairs the server accepts, with distinct names", () => {
    for (const p of COLOR_PRESETS) expect(`${p.light}${p.dark}`).toMatch(/^#[0-9a-f]{6}#[0-9a-f]{6}$/)
    expect(new Set(COLOR_PRESETS.map((p) => p.name)).size).toBe(COLOR_PRESETS.length)
  })

  it("find a pair in any case, and need both colours", () => {
    expect(presetFor("#BE123C", "#F2889B")?.name).toBe("Rose")
    expect(presetFor("#be123c", null)).toBeUndefined()
    expect(presetFor(null, null)).toBeUndefined()
  })
})
