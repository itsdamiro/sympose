// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { FilmRoll01Icon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it } from "vitest"

import { VaultTree, type VaultNode } from "./vault-tree"

afterEach(cleanup)

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const captions = () => [...document.querySelectorAll('[data-slot="group-caption"]')].map((el) => el.textContent)

describe("VaultTree: captions", () => {
  it("sets the plain tree apart as All notes once Pinned or Recent sits above it", () => {
    render(<VaultTree nodes={[note("a.md")]} pinnedNodes={[note("p.md")]} />)
    expect(captions()).toEqual(["Pinned", "All notes"])
    cleanup()
    render(<VaultTree nodes={[note("a.md")]} recentNodes={[note("r.md")]} />)
    expect(captions()).toEqual(["Recent", "All notes"])
    cleanup()
    render(<VaultTree nodes={[note("a.md")]} pinnedNodes={[note("p.md")]} recentNodes={[note("r.md")]} />)
    expect(captions()).toEqual(["Pinned", "Recent", "All notes"])
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
})
