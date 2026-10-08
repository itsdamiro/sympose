// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { PersonaRequest } from "@/lib/confirmations-api"
import { PersonaRequestCard } from "./persona-request-card"

afterEach(cleanup)

const request = (over: Partial<PersonaRequest> = {}): PersonaRequest => ({
  id: "r1", kind: "persona", state: "waiting", handle: "ada", reason: null, created_at: "t",
  folder_choices: ["Journal", "Recipes", "Work"],
  edit_modes: [
    { id: "plan", summary: "Talks about a change and proposes nothing." },
    { id: "manual", summary: "Proposes changes when you ask; you accept or decline each one." },
    { id: "accept", summary: "Edits appear in the editor as they are made; saving is what keeps them." },
    { id: "auto", summary: "Proposes changes on its own; nothing is kept until you accept it." },
  ],
  draft: {
    name: "Ada", title: "A warm tutor", soul: "You are Ada.\n\nHow you talk:\n- Gently.", icon: "graduation",
    accent: "rgb(1, 2, 3)", accent_dark: "rgb(4, 5, 6)", edit_mode: "manual", folders: ["Recipes", "Work"],
  },
  ...over,
})

describe("PersonaRequestCard, waiting", () => {
  it("shows who it is about, what she proposed, and the folders as pills with the count on", () => {
    render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
    expect(screen.getByText("Ada")).toBeTruthy()
    expect(screen.getByText("A warm tutor")).toBeTruthy()
    // each part says what it is: a header, a line, and the control
    expect(screen.getByText("Edits")).toBeTruthy()
    expect(screen.getByText("Proposes changes when you ask; you accept or decline each one.")).toBeTruthy()
    expect(screen.getByRole("combobox", { name: "What it may do to your notes" }).textContent).toContain("Manual")
    expect(screen.getByText("Folders")).toBeTruthy()
    expect(screen.getByText("The folders it may read.")).toBeTruthy()
    expect(screen.getByText("2/3")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Recipes" }).getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "Journal" }).getAttribute("aria-pressed")).toBe("false")
    expect(screen.getByText(/How you talk/)).toBeTruthy()
  })

  it("puts the soul last, shown and not hidden, under a header that says what it is", () => {
    const { container } = render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
    expect(screen.getByText("Soul")).toBeTruthy()
    expect(screen.getByText("How it talks and what it is like to talk to.")).toBeTruthy()
    expect(container.querySelector("details")).toBeNull()
    const order = (text: string) => (container.textContent ?? "").indexOf(text)
    expect(order("Edits")).toBeLessThan(order("Folders"))
    expect(order("Folders")).toBeLessThan(order("Soul"))
    expect(order("Soul")).toBeLessThan(order("You are Ada."))
    expect(screen.getByText(/Gently\./).textContent).toContain("How you talk:")
  })

  describe("the soul's More button", () => {
    const measured = (scroll: number, client: number) => {
      vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockReturnValue(scroll)
      vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(client)
    }
    afterEach(() => vi.restoreAllMocks())

    it("shows four lines and a More button when the soul is longer than that", () => {
      measured(200, 80)
      render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
      expect(screen.getByText(/Gently\./).className).toContain("line-clamp-4")
      expect(screen.getByRole("button", { name: "More" }).getAttribute("aria-expanded")).toBe("false")
    })

    it("shows the whole soul on More, and four lines again on Less", () => {
      measured(200, 80)
      render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
      fireEvent.click(screen.getByRole("button", { name: "More" }))
      expect(screen.getByText(/Gently\./).className).not.toContain("line-clamp-4")
      expect(screen.getByRole("button", { name: "Less" }).getAttribute("aria-expanded")).toBe("true")
      fireEvent.click(screen.getByRole("button", { name: "Less" }))
      expect(screen.getByText(/Gently\./).className).toContain("line-clamp-4")
    })

    it("has no button when the soul fits in four lines", () => {
      measured(80, 80)
      render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
      expect(screen.queryByRole("button", { name: "More" })).toBeNull()
      expect(screen.queryByRole("button", { name: "Less" })).toBeNull()
    })
  })

  it("draws the avatar in the colour she chose", () => {
    const { container } = render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
    const avatar = container.querySelector("[data-slot='avatar-fallback']") as HTMLElement
    expect(avatar.style.background).toContain("rgb(1, 2, 3)")
  })

  it("turns a pill on and off and keeps the count", () => {
    render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
    fireEvent.click(screen.getByRole("button", { name: "Journal" }))
    expect(screen.getByText("3/3")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Work" }))
    expect(screen.getByText("2/3")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Work" }).getAttribute("aria-pressed")).toBe("false")
  })

  it("accepts with the folders as the user left them", async () => {
    const onAnswer = vi.fn().mockResolvedValue(null)
    render(<PersonaRequestCard request={request()} onAnswer={onAnswer} />)
    fireEvent.click(screen.getByRole("button", { name: "Journal" }))
    fireEvent.click(screen.getByRole("button", { name: "Work" }))
    fireEvent.click(screen.getByRole("button", { name: "Accept" }))
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(true, ["Recipes", "Journal"], "manual"))
  })

  it("offers the four edit modes in the dropdown", async () => {
    render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
    const trigger = screen.getByRole("combobox", { name: "What it may do to your notes" })
    fireEvent.mouseDown(trigger)
    fireEvent.mouseUp(trigger)
    const options = await screen.findAllByRole("option")
    expect(options.map((o) => o.textContent)).toEqual(["Plan", "Manual", "Accept edits", "Auto"])
  })

  it("declines", async () => {
    const onAnswer = vi.fn().mockResolvedValue(null)
    render(<PersonaRequestCard request={request()} onAnswer={onAnswer} />)
    fireEvent.click(screen.getByRole("button", { name: "Decline" }))
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(false, ["Recipes", "Work"], "manual"))
  })

  it("cannot accept with no folder on", () => {
    render(<PersonaRequestCard request={request()} onAnswer={vi.fn()} />)
    fireEvent.click(screen.getByRole("button", { name: "Recipes" }))
    fireEvent.click(screen.getByRole("button", { name: "Work" }))
    const accept = screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement
    expect(accept.disabled).toBe(true)
    expect(accept.title).toBe("Turn on at least one folder")
    expect(screen.getByText("0/3")).toBeTruthy()
  })

  it("shows the reason when the answer is refused, and can be answered again", async () => {
    const onAnswer = vi.fn().mockResolvedValueOnce("Choose at least one folder.").mockResolvedValueOnce(null)
    render(<PersonaRequestCard request={request()} onAnswer={onAnswer} />)
    fireEvent.click(screen.getByRole("button", { name: "Accept" }))
    expect((await screen.findByRole("alert")).textContent).toBe("Choose at least one folder.")
    fireEvent.click(screen.getByRole("button", { name: "Accept" }))
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull())
  })

  it("shows every pill off, and cannot be accepted, when she left the folders to the user", async () => {
    const draft = { ...request().draft, folders: [] }
    const onAnswer = vi.fn().mockResolvedValue(null)
    render(<PersonaRequestCard request={request({ draft })} onAnswer={onAnswer} />)
    expect(screen.getByText("0/3")).toBeTruthy()
    expect((screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole("button", { name: "Journal" }))
    fireEvent.click(screen.getByRole("button", { name: "Accept" }))
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(true, ["Journal"], "manual"))
  })

  it("ignores a proposed folder the persona cannot read", () => {
    const draft = { ...request().draft, folders: ["Recipes", "Gone"] }
    render(<PersonaRequestCard request={request({ draft })} onAnswer={vi.fn()} />)
    expect(screen.getByText("1/3")).toBeTruthy()
  })
})

describe("PersonaRequestCard, answered", () => {
  it.each([
    ["accepted", "Created"],
    ["declined", "Declined"],
    ["replaced", "Replaced by a newer proposal"],
  ] as const)("keeps the header and one line for %s, with no buttons", (state, line) => {
    render(<PersonaRequestCard request={request({ state })} onAnswer={vi.fn()} />)
    expect(screen.getByText("Ada")).toBeTruthy()
    expect(screen.getByText(line)).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("says why an outdated request cannot be made", () => {
    render(<PersonaRequestCard request={request({ state: "outdated", reason: "A persona called ada already exists." })} onAnswer={vi.fn()} />)
    expect(screen.getByText("A persona called ada already exists.")).toBeTruthy()
  })
})
