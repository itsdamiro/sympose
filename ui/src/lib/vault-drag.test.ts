import { afterEach, describe, expect, it } from "vitest"

import { canDropDraggedFolder, canDropFolder, draggedFolder, endFolderDrag, isFolderDrag, readFolderDrag, startFolderDrag } from "./vault-drag"

function event(types: string[] = [], data: Record<string, string> = {}) {
  return { dataTransfer: { types, setData: (k: string, v: string) => { data[k] = v; types.push(k) }, getData: (k: string) => data[k] ?? "", effectAllowed: "" } } as unknown as React.DragEvent
}

afterEach(() => endFolderDrag())

describe("canDropFolder", () => {
  it.each([
    ["People", "People", false],
    ["People", "People/Sub", false],
    ["People", "", false],
    ["Projects/Garden", "Projects", false],
    ["People", "Archive", true],
    ["People", "People and Pets", true],
    ["Projects/Garden", "", true],
    ["Projects/Garden", "Archive/Deep", true],
  ])("%s into %s: %s", (folder, destination, allowed) => {
    expect(canDropFolder(folder, destination)).toBe(allowed)
  })
})

describe("a folder drag", () => {
  it("carries the path under its own type and is told apart from a note drag", () => {
    const e = event()
    startFolderDrag(e, "People")

    expect(isFolderDrag(e)).toBe(true)
    expect(readFolderDrag(e)).toBe("People")
    expect(isFolderDrag(event(["application/x-sympose-vault-note-path"]))).toBe(false)
    expect(readFolderDrag(event())).toBeUndefined()
  })

  it("is remembered until it ends, because a dragover cannot read the payload", () => {
    const e = event()
    startFolderDrag(e, "People")

    expect(draggedFolder()).toBe("People")
    expect(canDropDraggedFolder(e, "Archive")).toBe(true)
    expect(canDropDraggedFolder(e, "People/Sub")).toBe(false)
    endFolderDrag()
    expect(draggedFolder()).toBeUndefined()
    expect(canDropDraggedFolder(e, "Archive")).toBe(false)
  })

  it("is never offered for a note drag", () => {
    startFolderDrag(event(), "People")
    expect(canDropDraggedFolder(event(["application/x-sympose-vault-note-path"]), "Archive")).toBe(false)
  })
})
