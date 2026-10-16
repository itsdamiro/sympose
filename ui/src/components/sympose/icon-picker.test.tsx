// @vitest-environment jsdom
import { Folder01Icon } from "@hugeicons/core-free-icons"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { IconPicker } from "./icon-picker"

afterEach(cleanup)

function setup(value: string | null = null) {
  const onChange = vi.fn()
  const view = render(<IconPicker label="Icon" value={value} fallback={Folder01Icon} onChange={onChange} />)
  const input = screen.getByRole("combobox", { name: "Icon" }) as HTMLInputElement
  return { onChange, input, ...view }
}
const options = () => screen.queryAllByRole("option").map((o) => o.textContent)

describe("IconPicker", () => {
  it("shows the chosen name, and the list stays closed until the field is used", () => {
    const { input } = setup("film-roll")
    expect(input.value).toBe("film-roll")
    expect(input.getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("listbox")).toBeNull()
  })

  it("lists every icon on a click, with the chosen one marked, but not when it is only focused", () => {
    const { input } = setup("book")
    fireEvent.focus(input)
    expect(screen.queryByRole("listbox")).toBeNull()
    fireEvent.click(input)
    expect(input.getAttribute("aria-expanded")).toBe("true")
    expect(options().length).toBeGreaterThan(50)
    expect(screen.getByRole("option", { name: "book" }).getAttribute("aria-selected")).toBe("true")
  })

  it("narrows as the person types, by name or by a word for it, best match first", () => {
    const { input } = setup()
    fireEvent.change(input, { target: { value: "food" } })
    expect(options()).toEqual(expect.arrayContaining(["chef", "chef-hat"]))
    expect(options().indexOf("street-food")).toBeLessThan(options().indexOf("chef")) // its name has the word, the chef's is a keyword
    fireEvent.change(input, { target: { value: "zzzz" } })
    expect(screen.getByText("No icon matches")).toBeTruthy()
  })

  it("chooses the highlighted icon on Enter and closes, without anything else reacting to the key", () => {
    const { input, onChange } = setup()
    fireEvent.change(input, { target: { value: "film" } })
    const enter = fireEvent.keyDown(input, { key: "Enter" })
    expect(onChange).toHaveBeenCalledExactlyOnceWith("film-roll")
    expect(enter).toBe(false) // default prevented: a form around the field would not submit
    expect(screen.queryByRole("listbox")).toBeNull()
  })

  it("moves the highlight with the arrow keys, wrapping at both ends", () => {
    const { input, onChange } = setup()
    fireEvent.change(input, { target: { value: "book" } }) // book, book-open, bookmark, notebook, ...
    const ids = screen.getAllByRole("option").map((o) => o.id)
    expect(input.getAttribute("aria-activedescendant")).toBe(ids[0])
    fireEvent.keyDown(input, { key: "ArrowDown" })
    fireEvent.keyDown(input, { key: "ArrowDown" })
    expect(input.getAttribute("aria-activedescendant")).toBe(ids[2])
    fireEvent.keyDown(input, { key: "ArrowUp" })
    fireEvent.keyDown(input, { key: "ArrowUp" })
    fireEvent.keyDown(input, { key: "ArrowUp" })
    expect(input.getAttribute("aria-activedescendant")).toBe(ids[ids.length - 1])
    fireEvent.keyDown(input, { key: "ArrowDown" })
    expect(input.getAttribute("aria-activedescendant")).toBe(ids[0])
    fireEvent.keyDown(input, { key: "ArrowDown" })
    fireEvent.keyDown(input, { key: "ArrowDown" })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(onChange).toHaveBeenCalledWith("bookmark")
  })

  it("chooses on a click", () => {
    const { input, onChange } = setup()
    fireEvent.click(input)
    fireEvent.click(screen.getByRole("option", { name: "airplane" }))
    expect(onChange).toHaveBeenCalledWith("airplane")
  })

  it("closes on Escape and keeps the key from reaching the dialog around it", () => {
    const { input, onChange } = setup()
    fireEvent.click(input)
    const escape = fireEvent.keyDown(input, { key: "Escape" })
    expect(escape).toBe(false)
    expect(screen.queryByRole("listbox")).toBeNull()
    expect(onChange).not.toHaveBeenCalled()
  })

  it("does not let the Escape that closes the list reach the dialog around it", () => {
    const outer = vi.fn()
    render(
      <div onKeyDown={outer}>
        <IconPicker label="Icon" value={null} fallback={Folder01Icon} onChange={vi.fn()} />
      </div>
    )
    const input = screen.getByRole("combobox", { name: "Icon" })
    fireEvent.click(input)
    fireEvent.keyDown(input, { key: "Escape" })
    expect(outer).not.toHaveBeenCalled()
    fireEvent.keyDown(input, { key: "Escape" }) // list closed now: this one goes on to the dialog
    expect(outer).toHaveBeenCalledTimes(1)
  })

  it("keeps focus in the field when the list itself, its scrollbar or gaps, is pressed", () => {
    const { input } = setup()
    fireEvent.click(input)
    expect(fireEvent.mouseDown(screen.getByRole("listbox"))).toBe(false)
  })

  it("keeps focus in the field when the cross is pressed, so the list does not close under the click", () => {
    setup("book")
    expect(fireEvent.mouseDown(screen.getByRole("button", { name: "Clear the icon" }))).toBe(false)
  })

  it("lets Escape through when the list is already closed, so the dialog can close", () => {
    const { input } = setup()
    expect(fireEvent.keyDown(input, { key: "Escape" })).toBe(true)
  })

  it("gives back the chosen name when the person leaves the field with something half typed", () => {
    const { input, onChange } = setup("book")
    fireEvent.change(input, { target: { value: "fil" } })
    fireEvent.blur(input)
    expect(input.value).toBe("book")
    expect(onChange).not.toHaveBeenCalled()
  })

  it("clears the choice with the cross", () => {
    const { onChange } = setup("book")
    fireEvent.click(screen.getByRole("button", { name: "Clear the icon" }))
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it("has no cross while nothing is chosen", () => {
    setup()
    expect(screen.queryByRole("button", { name: "Clear the icon" })).toBeNull()
  })

  it("shows an icon name the set lacks as it is", () => {
    const { input } = setup("old-name")
    expect(input.value).toBe("old-name")
  })
})
