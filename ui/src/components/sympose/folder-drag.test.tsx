// @vitest-environment jsdom
import { act, cleanup, createEvent, fireEvent, render, screen } from "@testing-library/react"
import { Folder01Icon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it, vi } from "vitest"

import { announceFolderMoved } from "@/lib/folder-moved"
import { endFolderDrag } from "@/lib/vault-drag"
import { MainMenu, type MainMenuItem } from "./main-menu"
import { VaultTree, type VaultNode } from "./vault-tree"

afterEach(() => {
  cleanup()
  endFolderDrag()
})

const FOLDER_MIME = "application/x-sympose-vault-folder-path"
const NOTE_MIME = "application/x-sympose-vault-note-path"

/** One drag's data, shared by every event of it, as a browser does. */
function drag() {
  const data: Record<string, string> = {}
  return { types: [] as string[], dropEffect: "none", effectAllowed: "", setData(k: string, v: string) { data[k] = v; this.types.push(k) }, getData: (k: string) => data[k] ?? "" }
}
type Drag = ReturnType<typeof drag>
const ev = (dataTransfer: Drag) => ({ dataTransfer })

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const folder = (path: string, children: VaultNode[] = []): VaultNode =>
  ({ type: "folder", name: path.split("/").pop()!, path, children }) as VaultNode

/** A `dragleave` on `el` heading for `to` (jsdom has no DragEvent, so the relatedTarget is put on the event by hand). */
function leave(el: Element, dt: Drag, to: Element | null) {
  const e = createEvent.dragLeave(el, ev(dt))
  Object.defineProperty(e, "relatedTarget", { value: to })
  fireEvent(el, e)
}

/** Start dragging the row labelled `name`, the way a browser does, and hand back the drag. */
function pickUp(name: string) {
  const dt = drag()
  fireEvent.dragStart(screen.getByRole("button", { name }), ev(dt))
  return dt
}

describe("VaultTree: dragging a folder row (docs/decisions/074)", () => {
  const tree = [folder("People", [folder("People/Sub", [note("People/Sub/b.md")]), note("People/a.md")]), folder("Archive"), folder("Projects", [folder("Projects/Garden")])]
  const props = { nodes: tree, defaultExpanded: ["People", "Projects"] }
  const row = (name: string) => screen.getByRole("button", { name })

  it("makes folder rows draggable only when moving folders is wired, and never note rows", () => {
    render(<VaultTree {...props} onMoveNote={vi.fn()} />)
    expect(row("People").getAttribute("draggable")).toBeNull()
    cleanup()
    render(<VaultTree {...props} onMoveFolder={vi.fn()} onMoveNote={vi.fn()} />)
    expect(row("People").getAttribute("draggable")).toBe("true")
    expect(row("a.md").getAttribute("draggable")).toBe("true") // a note is draggable as a note, already
  })

  it("moves the folder onto the folder it is dropped on, once, and takes over the drop", () => {
    const onMoveFolder = vi.fn()
    render(<VaultTree {...props} onMoveFolder={onMoveFolder} />)

    const dt = pickUp("People")
    fireEvent.dragOver(row("Archive"), ev(dt))
    expect(fireEvent.drop(row("Archive"), ev(dt))).toBe(false)

    expect(onMoveFolder).toHaveBeenCalledExactlyOnceWith("People", "Archive")
  })

  it("forgets the drag once it is dropped, because the row that was dragged may be gone and never say it ended", () => {
    render(<VaultTree {...props} onMoveFolder={vi.fn()} />)
    const dt = pickUp("People")
    fireEvent.drop(row("Archive"), ev(dt))

    expect(fireEvent.dragOver(row("Archive"), ev(dt))).toBe(true)
  })

  it("lights the folder it is over and puts it out on leave or drop, marking the drag as a move", () => {
    render(<VaultTree {...props} onMoveFolder={vi.fn()} />)
    const dt = pickUp("People")

    fireEvent.dragOver(row("Archive"), ev(dt))
    expect(dt.dropEffect).toBe("move")
    fireEvent.dragEnter(row("Archive"), ev(dt))
    expect(row("Archive").className).toContain("ring-brand")
    fireEvent.dragLeave(row("Archive"), ev(dt))
    expect(row("Archive").className).not.toContain("ring-brand")
    fireEvent.dragEnter(row("Archive"), ev(dt))
    fireEvent.drop(row("Archive"), ev(dt))
    expect(row("Archive").className).not.toContain("ring-brand")
  })

  it("stays lit while the drag moves onto the row's own icon or label, and goes out when it leaves the row", () => {
    render(<VaultTree {...props} onMoveFolder={vi.fn()} />)
    const dt = pickUp("People")
    fireEvent.dragEnter(row("Archive"), ev(dt))

    leave(row("Archive"), dt, row("Archive").querySelector("span"))
    expect(row("Archive").className).toContain("ring-brand")
    leave(row("Archive"), dt, document.body)
    expect(row("Archive").className).not.toContain("ring-brand")
  })

  it.each([
    ["itself", "People", "People"],
    ["one of its own folders", "People", "Sub"],
    ["the folder it is already in", "Garden", "Projects"],
  ])("does not offer a drop on %s: no highlight, no cursor, no move", (_what, dragged, target) => {
    const onMoveFolder = vi.fn()
    render(<VaultTree {...props} onMoveFolder={onMoveFolder} />)
    const dt = pickUp(dragged)

    expect(fireEvent.dragOver(row(target), ev(dt))).toBe(true) // not prevented: the browser shows no-drop
    expect(dt.dropEffect).toBe("none")
    fireEvent.dragEnter(row(target), ev(dt))
    expect(row(target).className).not.toContain("ring-brand")
    fireEvent.drop(row(target), ev(dt))
    expect(onMoveFolder).not.toHaveBeenCalled()
  })

  it("keeps moving notes as before, and a note dropped on a folder never moves a folder", () => {
    const onMoveFolder = vi.fn()
    const onMoveNote = vi.fn()
    render(<VaultTree {...props} onMoveFolder={onMoveFolder} onMoveNote={onMoveNote} />)
    const dt = drag()
    fireEvent.dragStart(row("a.md"), ev(dt))
    expect(dt.types).toEqual([NOTE_MIME])

    fireEvent.drop(row("Archive"), ev(dt))

    expect(onMoveNote).toHaveBeenCalledExactlyOnceWith("People/a.md", "Archive")
    expect(onMoveFolder).not.toHaveBeenCalled()
  })

  it("does not take a folder when only notes are wired, nor a note when only folders are", () => {
    const onMoveNote = vi.fn()
    render(<VaultTree {...props} onMoveNote={onMoveNote} />)
    const dt = drag()
    dt.setData(FOLDER_MIME, "People")
    fireEvent.drop(row("Archive"), ev(dt))
    expect(onMoveNote).not.toHaveBeenCalled()
    cleanup()

    const onMoveFolder = vi.fn()
    render(<VaultTree {...props} onMoveFolder={onMoveFolder} />)
    const noteDrag = drag()
    noteDrag.setData(NOTE_MIME, "People/a.md")
    fireEvent.drop(row("Archive"), ev(noteDrag))
    expect(onMoveFolder).not.toHaveBeenCalled()
  })

  it("forgets the drag when it ends without a drop, so nothing stays lit later", () => {
    render(<VaultTree {...props} onMoveFolder={vi.fn()} />)
    const dt = pickUp("People")
    fireEvent.dragEnd(row("People"), ev(dt))

    expect(fireEvent.dragOver(row("Archive"), ev(dt))).toBe(true)
  })
})

describe("VaultTree: a renamed or moved folder keeps its open state", () => {
  it("follows the folder to its new path, so it does not come back collapsed", () => {
    const before = [folder("People", [note("People/a.md")])]
    const after = [folder("Archive/People", [note("Archive/People/a.md")])]
    const { rerender } = render(<VaultTree nodes={before} defaultExpanded={["People"]} />)
    expect(screen.queryByRole("button", { name: "a.md" })).not.toBeNull()

    act(() => announceFolderMoved("People", "Archive/People"))
    rerender(<VaultTree nodes={after} />)

    expect(screen.queryByRole("button", { name: "a.md" })).not.toBeNull()
  })

  it("leaves other folders as they were", () => {
    const nodes = [folder("People", [note("People/a.md")]), folder("Other", [note("Other/b.md")])]
    render(<VaultTree nodes={nodes} defaultExpanded={["People"]} />)

    act(() => announceFolderMoved("Other", "Elsewhere"))

    expect(screen.queryByRole("button", { name: "a.md" })).not.toBeNull()
    expect(screen.queryByRole("button", { name: "b.md" })).toBeNull()
  })

  it("stops listening when the tree goes away", () => {
    const { unmount } = render(<VaultTree nodes={[folder("People")]} />)
    unmount()
    expect(() => announceFolderMoved("People", "X")).not.toThrow()
  })
})

describe("MainMenu: dropping a folder (docs/decisions/074)", () => {
  const items: MainMenuItem[] = [
    { id: "People", label: "People", icon: Folder01Icon, type: "folder" },
    { id: "Archive", label: "Archive", icon: Folder01Icon, type: "folder" },
    { id: "README.md", label: "README", icon: Folder01Icon, type: "note" },
  ]
  const setup = () => {
    const onDropFolder = vi.fn()
    render(<MainMenu items={items} onDropFolder={onDropFolder} vaultLabel="My vault" />)
    return onDropFolder
  }
  const held = (path: string) => {
    const dt = drag()
    dt.setData(FOLDER_MIME, path)
    // the tree remembers what is being dragged (a dragover cannot read it)
    const e = { dataTransfer: dt } as unknown as React.DragEvent
    return import("@/lib/vault-drag").then((m) => (m.startFolderDrag(e, path), dt))
  }
  const row = (name: string) => screen.getByRole("button", { name })
  const vaultName = () => document.querySelector<HTMLElement>('[data-slot="vault-root-drop"]')!

  it("moves a folder into the root folder it is dropped on, lighting the row meanwhile", async () => {
    const onDropFolder = setup()
    const dt = await held("Projects/Garden")

    fireEvent.dragEnter(row("Archive"), ev(dt))
    expect(row("Archive").className).toContain("ring-brand")
    expect(fireEvent.drop(row("Archive"), ev(dt))).toBe(false)

    expect(onDropFolder).toHaveBeenCalledExactlyOnceWith("Projects/Garden", "Archive")
    expect(row("Archive").className).not.toContain("ring-brand")
  })

  it("does not offer a root folder dropped on itself, and a root note takes no folder", async () => {
    const onDropFolder = setup()
    const dt = await held("People")

    expect(fireEvent.dragOver(row("People"), ev(dt))).toBe(true)
    fireEvent.drop(row("People"), ev(dt))
    fireEvent.drop(row("README"), ev(dt))

    expect(onDropFolder).not.toHaveBeenCalled()
  })

  it("keeps a root folder's row lit while the drag moves onto its icon or label", async () => {
    setup()
    const dt = await held("Projects/Garden")
    fireEvent.dragEnter(row("Archive"), ev(dt))

    leave(row("Archive"), dt, row("Archive").querySelector("span"))
    expect(row("Archive").className).toContain("ring-brand")
    leave(row("Archive"), dt, document.body)
    expect(row("Archive").className).not.toContain("ring-brand")
  })

  it("moves a nested folder to the vault root when dropped on the vault name, and lights it", async () => {
    const onDropFolder = setup()
    const dt = await held("Projects/Garden")

    fireEvent.dragEnter(vaultName(), ev(dt))
    expect(vaultName().className).toContain("ring-brand")
    fireEvent.drop(vaultName(), ev(dt))

    expect(onDropFolder).toHaveBeenCalledExactlyOnceWith("Projects/Garden", "")
    expect(vaultName().className).not.toContain("ring-brand")
  })

  it("moves a nested folder to the vault root when dropped on the space below the folders", async () => {
    const onDropFolder = setup()
    const dt = await held("Projects/Garden")

    fireEvent.drop(screen.getByRole("list"), ev(dt))

    expect(onDropFolder).toHaveBeenCalledExactlyOnceWith("Projects/Garden", "")
  })

  it("does not offer the root to a folder that is already at the root", async () => {
    const onDropFolder = setup()
    const dt = await held("People")

    expect(fireEvent.dragOver(vaultName(), ev(dt))).toBe(true)
    fireEvent.dragEnter(vaultName(), ev(dt))
    expect(vaultName().className).not.toContain("ring-brand")
    fireEvent.drop(vaultName(), ev(dt))
    fireEvent.drop(screen.getByRole("list"), ev(dt))

    expect(onDropFolder).not.toHaveBeenCalled()
  })

  it("keeps the vault root lit while the drag moves between its parts, and puts it out when it leaves", async () => {
    setup()
    const dt = await held("Projects/Garden")
    fireEvent.dragEnter(vaultName(), ev(dt))

    leave(vaultName(), dt, vaultName().firstElementChild)
    expect(vaultName().className).toContain("ring-brand")
    leave(vaultName(), dt, document.body)
    expect(vaultName().className).not.toContain("ring-brand")
  })

  it("never lets a drop on a row fall through to the vault root behind it", async () => {
    const onDropFolder = setup()
    const dt = await held("Projects/Garden")

    fireEvent.drop(row("Archive"), ev(dt))
    // a row that does not take it (a note) answers for the drag too, without moving it to the root
    fireEvent.drop(row("README"), ev(dt))

    expect(onDropFolder).toHaveBeenCalledExactlyOnceWith("Projects/Garden", "Archive")
  })

  it("takes no folder at all when moving folders is not wired", async () => {
    render(<MainMenu items={items} vaultLabel="My vault" />)
    const dt = await held("Projects/Garden")
    expect(fireEvent.dragOver(row("Archive"), ev(dt))).toBe(true)
  })
})
