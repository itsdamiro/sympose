// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { Folder01Icon, File01Icon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it, vi } from "vitest"

import { MainMenu, type MainMenuItem } from "./main-menu"

afterEach(cleanup)

const items: MainMenuItem[] = [
  { id: "People", label: "People", icon: Folder01Icon, type: "folder" },
  { id: "README.md", label: "README", icon: File01Icon, type: "note" },
]

function setup(extra: Partial<React.ComponentProps<typeof MainMenu>> = {}) {
  const handlers = { onCreateRoot: vi.fn(), onDeleteItem: vi.fn(), onDefineItem: vi.fn(), onHideItem: vi.fn() }
  render(<MainMenu items={items} {...handlers} {...extra} />)
  return handlers
}

describe("MainMenu: its own menu", () => {
  it("offers a new note and a new folder at the root from a right click on a row's empty surroundings", async () => {
    const h = setup()
    fireEvent.contextMenu(screen.getByRole("list"))
    fireEvent.click(await screen.findByRole("menuitem", { name: "New folder" }))
    expect(h.onCreateRoot).toHaveBeenCalledWith("folder")
    fireEvent.contextMenu(screen.getByRole("list"))
    fireEvent.click(await screen.findByRole("menuitem", { name: "New note" }))
    expect(h.onCreateRoot).toHaveBeenCalledWith("note")
  })

  it("gives a folder row Define folder, Hide from view and Delete folder, each acting on that row", async () => {
    const h = setup()
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).toEqual([
      "Define folder",
      "Hide from view",
      "Delete folder",
    ])
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete folder" }))
    expect(h.onDeleteItem).toHaveBeenCalledWith(items[0])
  })

  it("gives a root note only Hide from view: no folder actions", async () => {
    setup()
    fireEvent.contextMenu(screen.getByRole("button", { name: "README" }))
    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).toEqual(["Hide from view"])
  })
})
