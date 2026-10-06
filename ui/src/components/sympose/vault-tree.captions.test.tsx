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
