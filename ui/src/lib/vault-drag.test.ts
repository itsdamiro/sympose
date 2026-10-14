import { afterEach, describe, expect, it, vi } from "vitest"

import {
  canDropDraggedFolder,
  canDropFolder,
  draggedFolder,
  endFolderDrag,
  folderDropHandlers,
  isFolderDrag,
  readFolderDrag,
  startFolderDrag,
  startNoteDrag,
} from "./vault-drag"

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

/** A drag event on a surface: `inside` says whether the pointer is still over it (a `dragleave` onto a child). */
function onSurface(source: React.DragEvent, inside = false) {
  const stops: string[] = []
  const prevented: string[] = []
  const e = Object.assign(source, {
    stopPropagation: () => stops.push("stop"),
    preventDefault: () => prevented.push("prevent"),
    currentTarget: { contains: () => inside },
    relatedTarget: null,
  }) as unknown as React.DragEvent<HTMLElement>
  return { e, stops, prevented }
}

function noteDrag(path: string) {
  const e = event()
  startNoteDrag(e, path)
  return e
}

function folderDrag(path: string) {
  const e = event()
  startFolderDrag(e, path)
  return e
}

describe("folderDropHandlers", () => {
  const setup = (extra: Partial<Parameters<typeof folderDropHandlers>[0]> = {}, claims = false) => {
    const calls = { note: vi.fn(), folder: vi.fn(), over: vi.fn(), claim: vi.fn() }
    const handlers = folderDropHandlers<HTMLElement>({
      destination: "Archive",
      onMoveNote: calls.note,
      onMoveFolder: calls.folder,
      setOver: calls.over,
      onClaim: claims ? calls.claim : undefined,
      ...extra,
    })
    return { calls, handlers }
  }

  it("takes a note dropped on it, and lights up while the drag is over", () => {
    const { calls, handlers } = setup()
    const over = onSurface(noteDrag("People/Ada.md"))
    handlers.onDragEnter!(over.e)
    handlers.onDragOver!(over.e)
    expect(calls.over).toHaveBeenLastCalledWith(true)
    expect(over.prevented).toEqual(["prevent"])
    expect(over.e.dataTransfer.dropEffect).toBe("move")

    const drop = onSurface(noteDrag("People/Ada.md"))
    handlers.onDrop!(drop.e)
    expect(calls.note).toHaveBeenCalledWith("People/Ada.md", "Archive")
    expect(calls.over).toHaveBeenLastCalledWith(false)
    expect(drop.prevented).toEqual(["prevent"])
  })

  it("takes a folder that may go there, and moves it once", () => {
    const { calls, handlers } = setup()
    const e = folderDrag("People")
    handlers.onDragEnter!(onSurface(e).e)
    expect(calls.over).toHaveBeenLastCalledWith(true)

    handlers.onDrop!(onSurface(e).e)
    expect(calls.folder).toHaveBeenCalledWith("People", "Archive")
    expect(draggedFolder()).toBeUndefined() // the drag is over
  })

  it("shows nothing and moves nothing for a folder that may not go there", () => {
    const { calls, handlers } = setup({ destination: "People/Sub" })
    const e = folderDrag("People")
    const over = onSurface(e)
    handlers.onDragEnter!(over.e)
    handlers.onDragOver!(over.e)
    expect(calls.over).not.toHaveBeenCalledWith(true)
    expect(over.prevented).toEqual([])

    handlers.onDrop!(onSurface(e).e)
    expect(calls.folder).not.toHaveBeenCalled()
  })

  it("ignores what it does not take: a note when it takes only folders, a folder when it takes only notes", () => {
    const folders = setup({ onMoveNote: undefined })
    const note = onSurface(noteDrag("a.md"))
    folders.handlers.onDragOver!(note.e)
    folders.handlers.onDrop!(note.e)
    expect(note.prevented).toEqual([])
    expect(folders.calls.note).not.toHaveBeenCalled()

    const notes = setup({ onMoveFolder: undefined })
    const folder = onSurface(folderDrag("People"))
    notes.handlers.onDragOver!(folder.e)
    notes.handlers.onDrop!(folder.e)
    expect(folder.prevented).toEqual([])
    expect(notes.calls.folder).not.toHaveBeenCalled()
  })

  it("puts the highlight out only when the drag really leaves", () => {
    const { calls, handlers } = setup()
    handlers.onDragLeave!(onSurface(noteDrag("a.md"), true).e)
    expect(calls.over).not.toHaveBeenCalled()
    handlers.onDragLeave!(onSurface(noteDrag("a.md"), false).e)
    expect(calls.over).toHaveBeenCalledWith(false)
  })

  it("lets a drag reach the surface behind it unless it owns folder drags", () => {
    const plain = setup()
    const reach = onSurface(folderDrag("People"))
    plain.handlers.onDragOver!(reach.e)
    plain.handlers.onDragEnter!(reach.e)
    plain.handlers.onDragLeave!(reach.e)
    expect(reach.stops).toEqual([])
    expect(plain.calls.claim).not.toHaveBeenCalled() // nothing is claimed from a surface behind it
  })

  it("answers for every folder drag when it owns them, takes it or not, and tells the surface behind", () => {
    const { calls, handlers } = setup({ onMoveFolder: undefined }, true)
    const e = folderDrag("People")
    const over = onSurface(e)
    handlers.onDragOver!(over.e)
    handlers.onDragEnter!(over.e)
    handlers.onDragLeave!(over.e)
    handlers.onDrop!(over.e)
    expect(over.stops).toEqual(["stop", "stop", "stop", "stop"])
    expect(calls.claim).toHaveBeenCalledTimes(2) // on entering and on the drop
    expect(calls.folder).not.toHaveBeenCalled()

    const note = onSurface(noteDrag("a.md")) // a note drag is not a folder drag: it is not claimed
    handlers.onDragOver!(note.e)
    expect(note.stops).toEqual([])
  })
})
