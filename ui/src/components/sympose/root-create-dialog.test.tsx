// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RootCreateDialog } from "./root-create-dialog"

afterEach(cleanup)

describe("RootCreateDialog", () => {
  it("is closed with no kind, and names what it makes at the vault root", () => {
    const { rerender } = render(<RootCreateDialog kind={null} onCreate={vi.fn()} onClose={vi.fn()} />)
    expect(screen.queryByRole("dialog")).toBeNull()
    rerender(<RootCreateDialog kind="folder" onCreate={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText("New folder in the vault root")).toBeTruthy()
  })

  it("creates with the typed name on Enter, and closes only when it was created", async () => {
    const onCreate = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true)
    const onClose = vi.fn()
    render(<RootCreateDialog kind="note" onCreate={onCreate} onClose={onClose} />)
    const field = screen.getByLabelText("Name of the new note")
    fireEvent.change(field, { target: { value: "Ideas" } })
    fireEvent.submit(field.closest("form") as HTMLFormElement)
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith("note", "Ideas"))
    expect(onClose).not.toHaveBeenCalled() // refused: it stays open for another try
    fireEvent.submit(field.closest("form") as HTMLFormElement)
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it("will not create a blank name", () => {
    const onCreate = vi.fn()
    render(<RootCreateDialog kind="note" onCreate={onCreate} onClose={vi.fn()} />)
    expect((screen.getByRole("button", { name: "Create" }) as HTMLButtonElement).disabled).toBe(true)
  })
})
