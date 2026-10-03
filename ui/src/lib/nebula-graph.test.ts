import { describe, expect, it } from "vitest"

import { FOLDER_COLORS, FOLDER_COLORS_LIGHT, folderLegend, nodeColor } from "./nebula-graph"
import type { NebulaNode } from "./nebula-graph"

const node = (folder: string, extra: Partial<NebulaNode> = {}): NebulaNode => ({
  id: `${folder}/${Math.random()}`,
  label: "x",
  folder,
  tags: [],
  val: 1,
  ...extra,
})

describe("nodeColor", () => {
  it("uses the folder's own colour from its definition, over the built-in table", () => {
    const n = node("Movies", { accent: "#111111", accent_dark: "#eeeeee" })
    expect(nodeColor(n, true)).toBe("#111111")
    expect(nodeColor(n, false)).toBe("#eeeeee")
  })

  it("uses the light colour for dark when the definition gives no dark one", () => {
    expect(nodeColor(node("Garden", { accent: "#123456" }), false)).toBe("#123456")
  })

  it("falls back to the built-in table, then the neutral colour", () => {
    expect(nodeColor(node("Movies"), false)).toBe(FOLDER_COLORS.Movies)
    expect(nodeColor(node("Movies"), true)).toBe(FOLDER_COLORS_LIGHT.Movies)
    expect(nodeColor(node("Garden"), false)).not.toBe(FOLDER_COLORS.Movies)
  })

  it("keeps a ghost note faint whatever its folder says", () => {
    expect(nodeColor(node("Movies", { exists: false, accent: "#111111" }), false)).not.toBe("#111111")
  })
})

describe("folderLegend", () => {
  it("lists a folder with a colour of its own, built-in ones first in the table's order, then the rest by name", () => {
    const graph = { nodes: [node("Zeta", { accent: "#222222" }), node("Movies"), node("Alpha", { accent: "#111111" }), node("Code")], links: [] }
    expect(folderLegend(graph).map((e) => e.folder)).toEqual(["Code", "Movies", "Alpha", "Zeta"])
  })

  it("leaves out a folder with no colour of its own, and one only a ghost note is in", () => {
    const graph = { nodes: [node("Garden"), node("Movies", { exists: false })], links: [] }
    expect(folderLegend(graph)).toEqual([])
  })

  it("shows the colour the notes are drawn in, for the theme", () => {
    const graph = { nodes: [node("Movies"), node("Movies", { accent: "#111111", accent_dark: "#eeeeee" })], links: [] }
    expect(folderLegend(graph, true)).toEqual([{ folder: "Movies", color: "#111111" }])
    expect(folderLegend(graph, false)).toEqual([{ folder: "Movies", color: "#eeeeee" }])
  })

  it("lists, and colours in the dark, a folder that sets only its dark colour", () => {
    const graph = { nodes: [node("Garden", { accent_dark: "#88cc88" })], links: [] }
    expect(folderLegend(graph, false)).toEqual([{ folder: "Garden", color: "#88cc88" }])
  })

  it("never takes a name of the object prototype for a folder in a table", () => {
    const graph = { nodes: [node("constructor"), node("toString", { accent: "#123456" })], links: [] }
    expect(folderLegend(graph).map((e) => e.folder)).toEqual(["toString"])
    expect(nodeColor(node("constructor"), false)).toBe("#8b93a7")
    expect(nodeColor(node("constructor"), true)).toBe("#334155")
  })
})
