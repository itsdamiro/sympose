import { BrainIcon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it } from "vitest"

import { ICON_SET, iconByName } from "./persona-icons"
import { resolvePersonaVisuals, setLiveLooks, type LivePersona } from "./personas"

const row = (handle: string, look: Partial<LivePersona> = {}): LivePersona => ({
  handle, name: handle, title: "", model: "m", skills: [], isDefault: false, ...look,
})

afterEach(() => setLiveLooks([]))

describe("a persona's look from her persona.yaml", () => {
  it("uses the icon and colours her file names, over the defaults", () => {
    setLiveLooks([row("ada", { icon: "leaf", accent: "rgb(1, 2, 3)", accentDark: "rgb(4, 5, 6)" })])
    expect(resolvePersonaVisuals("ada")).toEqual({ icon: ICON_SET.leaf, accent: "rgb(1, 2, 3)", accentDark: "rgb(4, 5, 6)" })
  })

  it("uses a light colour for dark too when her file gives only one", () => {
    setLiveLooks([row("ada", { accent: "rgb(1, 2, 3)" })])
    expect(resolvePersonaVisuals("ada").accentDark).toBe("rgb(1, 2, 3)")
  })

  it("falls back to the defaults for what her file does not say, or an icon the set does not have", () => {
    setLiveLooks([row("ada", { icon: "not-in-this-set" })])
    const v = resolvePersonaVisuals("ada")
    expect(v.icon).toBe(BrainIcon)
    expect(v.accent).toBe("oklch(0.58 0.02 260)") // neutral, for a persona that does not ship
    expect(resolvePersonaVisuals("samantha").accent).toBe("oklch(0.55 0.13 233)") // the shipped default
  })

  it("matches a handle however it is written", () => {
    setLiveLooks([row("ada", { icon: "star" })])
    expect(resolvePersonaVisuals("@Ada").icon).toBe(ICON_SET.star)
  })

  it("finds an icon by its name, in any case, and none for an unknown or empty name", () => {
    expect(iconByName("Brain")).toBe(BrainIcon)
    expect(iconByName("nope")).toBeUndefined()
    expect(iconByName(null)).toBeUndefined()
  })
})
