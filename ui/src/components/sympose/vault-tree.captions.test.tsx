// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { FilmRoll01Icon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it } from "vitest"

import { VaultTree, type VaultNode } from "./vault-tree"

afterEach(cleanup)

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const captions = () => [...document.querySelectorAll('[data-slot="group-caption"]')].map((el) => el.textContent)

describe("VaultTree: captions", () => {
  it("sets the plain tree apart as All notes once Pinned sits above it, and not for Recent, which is the footer's", () => {
    render(<VaultTree nodes={[note("a.md")]} pinnedNodes={[note("p.md")]} />)
    expect(captions()).toEqual(["Pinned", "All notes"])
  })

  it("names the folder and takes its icon when given them", () => {
    render(<VaultTree nodes={[note("a.md")]} pinnedNodes={[note("p.md")]} listLabel="Notes in Movies" listIcon={FilmRoll01Icon} />)
    expect(captions()).toEqual(["Pinned", "Notes in Movies"])
  })

  it("has no caption at all when there is neither, and none when the tree itself is empty", () => {
    render(<VaultTree nodes={[note("a.md")]} />)
    expect(captions()).toEqual([])
    cleanup()
    render(<VaultTree nodes={[]} pinnedNodes={[note("p.md")]} />)
    expect(captions()).toEqual(["Pinned"])
    expect(screen.queryByText("All notes")).toBeNull()
  })

  it("captions the plain tree when something else sits above it, even with no Pinned, so the notes do not run on from it", () => {
    render(<VaultTree nodes={[note("a.md")]} captionList listLabel="Notes in Movies" />)
    expect(captions()).toEqual(["Notes in Movies"])
  })

  it("has one caption, not two, when Pinned and the Drafts section are both above the tree", () => {
    render(<VaultTree nodes={[note("a.md")]} pinnedNodes={[note("p.md")]} captionList />)
    expect(captions()).toEqual(["Pinned", "All notes"])
  })

  it("captions nothing when the tree itself is empty, whatever sits above it", () => {
    render(<VaultTree nodes={[]} captionList />)
    expect(captions()).toEqual([])
  })
})

describe("VaultTree: a subfolder's icon (docs/decisions/090)", () => {
  const folder = (path: string, extra: Partial<VaultNode> = {}, children: VaultNode[] = []): VaultNode =>
    ({ type: "folder", name: path.split("/").pop()!, path, children, ...extra }) as VaultNode
  // The folder glyph of the row named `name`: the third svg in its row after the arrow, as markup to compare.
  const glyph = (name: string) => {
    const label = screen.getByText(name)
    return label.parentElement!.querySelectorAll("svg")[1].innerHTML
  }

  it("draws a folder below a top-level one with the icon its entry names, and leaves one without alone", () => {
    const nodes = [
      folder("Projects", {}, [folder("Projects/plain"), folder("Projects/sympose", { icon: "rocket" })]),
    ]
    render(<VaultTree nodes={nodes} defaultExpanded={["Projects"]} />)
    expect(glyph("sympose")).not.toBe(glyph("plain"))
  })

  it("keeps a name the icon set lacks as the usual glyph", () => {
    const nodes = [folder("Projects", {}, [folder("Projects/plain"), folder("Projects/odd", { icon: "no-such-icon-here" })])]
    render(<VaultTree nodes={nodes} defaultExpanded={["Projects"]} />)
    expect(glyph("odd")).toBe(glyph("plain"))
  })

  it("does not change how a top-level folder is drawn in the tree", () => {
    render(<VaultTree nodes={[folder("Movies", { icon: "rocket" }), folder("Plain")]} />)
    expect(glyph("Movies")).toBe(glyph("Plain"))
  })
})
