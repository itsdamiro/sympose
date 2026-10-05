// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ addComment: vi.fn(), replyToComment: vi.fn(), changeComment: vi.fn(), deleteComment: vi.fn() }))
const confirmStore = vi.hoisted(() => ({ confirm: vi.fn() }))
const toast = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock("@/lib/persona-changes-api", () => api)
vi.mock("@/lib/confirm-store", () => confirmStore)
vi.mock("@/lib/notify", () => ({ notify: toast }))

import type { Annotation } from "@/lib/persona-changes-api"
import type { CommentTarget } from "@/lib/review-extensions"

import { CommentPopover, type CommentBox } from "./comment-popover"

const rect = new DOMRect(10, 20, 30, 12)
const target: CommentTarget = { quote: "raised", before: "The beds are ", after: " and the soil", rect }
const note = (id: string, over: Partial<Annotation> = {}): Annotation => ({
  id, time: "2026-10-04T10:00:00+00:00", author: "user", quote: "raised", before: "", after: "", text: `text ${id}`, state: "open", reply_to: null, status: "attached", ...over,
})

function show(box: CommentBox | null, annotations: Annotation[] = [], handlers = { onClose: vi.fn(), onChanged: vi.fn() }) {
  render(<CommentPopover box={box} annotations={annotations} personaName="Samantha" path="n.md" persona="samantha" {...handlers} />)
  return handlers
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} })
  for (const fn of Object.values(api)) fn.mockResolvedValue({ ok: true })
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe("CommentPopover: a new comment", () => {
  it("draws nothing while there is nothing to comment on", () => {
    show(null)
    expect(screen.queryByTestId("comment-compose")).toBeNull()
    expect(screen.queryByTestId("comment-thread")).toBeNull()
  })

  it("shows the selected words and keeps the button off until something is written", async () => {
    show({ kind: "compose", target })

    expect((await screen.findByTestId("comment-compose")).textContent).toContain("raised")
    expect((screen.getByRole("button", { name: "Comment" }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText("Comment"), { target: { value: "   " } })
    expect((screen.getByRole("button", { name: "Comment" }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText("Comment"), { target: { value: "why raised?" } })
    expect((screen.getByRole("button", { name: "Comment" }) as HTMLButtonElement).disabled).toBe(false)
  })

  it("saves it with the editor's own context, then reads the note's changes again and closes", async () => {
    const { onClose, onChanged } = show({ kind: "compose", target })
    fireEvent.change(await screen.findByLabelText("Comment"), { target: { value: "  why raised?  " } })

    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Comment" })))

    expect(api.addComment).toHaveBeenCalledWith({ path: "n.md", persona: "samantha", quote: "raised", before: "The beds are ", after: " and the soil", text: "why raised?" })
    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("sends on Cmd-Enter and on Ctrl-Enter, and not on a plain Enter", async () => {
    show({ kind: "compose", target })
    const box = await screen.findByLabelText("Comment")
    fireEvent.change(box, { target: { value: "hello" } })

    fireEvent.keyDown(box, { key: "Enter" })
    expect(api.addComment).not.toHaveBeenCalled()
    await act(async () => fireEvent.keyDown(box, { key: "Enter", metaKey: true }))
    expect(api.addComment).toHaveBeenCalledTimes(1)
    fireEvent.change(box, { target: { value: "again" } })
    await act(async () => fireEvent.keyDown(box, { key: "Enter", ctrlKey: true }))
    expect(api.addComment).toHaveBeenCalledTimes(2)
  })

  it("does not send an empty or blank comment from the keyboard either", async () => {
    show({ kind: "compose", target })
    const box = await screen.findByLabelText("Comment")

    await act(async () => fireEvent.keyDown(box, { key: "Enter", metaKey: true }))
    fireEvent.change(box, { target: { value: "  \n " } })
    await act(async () => fireEvent.keyDown(box, { key: "Enter", metaKey: true }))

    expect(api.addComment).not.toHaveBeenCalled()
  })

  it("sends once however many times it is asked while the first is still on its way", async () => {
    api.addComment.mockReturnValue(new Promise(() => {}))
    show({ kind: "compose", target })
    const box = await screen.findByLabelText("Comment")
    fireEvent.change(box, { target: { value: "hello" } })

    await act(async () => fireEvent.keyDown(box, { key: "Enter", metaKey: true }))
    await act(async () => fireEvent.keyDown(box, { key: "Enter", metaKey: true }))
    await act(async () => fireEvent.keyDown(box, { key: "Enter", ctrlKey: true }))

    expect(api.addComment).toHaveBeenCalledTimes(1)
  })

  it("says why and stays open with the text kept when it could not be saved", async () => {
    api.addComment.mockResolvedValue({ ok: false, error: "Note `n.md` not found." })
    const { onClose, onChanged } = show({ kind: "compose", target })
    const box = (await screen.findByLabelText("Comment")) as HTMLTextAreaElement
    fireEvent.change(box, { target: { value: "keep me" } })

    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Comment" })))

    expect(toast.error).toHaveBeenCalledWith("Note `n.md` not found.")
    expect(onClose).not.toHaveBeenCalled()
    expect(onChanged).not.toHaveBeenCalled()
    expect(box.value).toBe("keep me")
  })
})

describe("CommentPopover: where it opens", () => {
  const style = () => document.querySelector("[data-slot='popover-content']")?.parentElement?.getAttribute("style") ?? ""

  it("opens on the selected words for a new comment", async () => {
    show({ kind: "compose", target: { ...target, rect: new DOMRect(100, 200, 30, 12) } })
    await screen.findByTestId("comment-compose")

    await waitFor(() => expect(style()).toContain("--anchor-width: 30px"))
    expect(style()).toContain("translate(100px")
  })

  it("opens on the highlighted passage for a thread", async () => {
    show({ kind: "thread", id: "c1", rect: new DOMRect(60, 90, 44, 12) }, [note("c1")])
    await screen.findByTestId("comment-thread")

    await waitFor(() => expect(style()).toContain("--anchor-width: 44px"))
    expect(style()).toContain("translate(60px")
  })
})

describe("CommentPopover: a thread", () => {
  const thread = [note("c1", { text: "why raised?" }), note("r1", { author: "persona", reply_to: "c1", text: "Drainage.", time: "2026-10-04T10:05:00+00:00" })]

  it("shows the comment and its answers by who wrote them, oldest first", async () => {
    const late = note("r0", { author: "user", reply_to: "c1", text: "thanks", time: "2026-10-04T10:09:00+00:00" })
    show({ kind: "thread", id: "c1", rect }, [late, ...thread])

    const text = (await screen.findByTestId("comment-thread")).textContent ?? ""
    expect(text.indexOf("why raised?")).toBeLessThan(text.indexOf("Drainage."))
    expect(text.indexOf("Drainage.")).toBeLessThan(text.indexOf("thanks"))
    expect(text).toContain("Samantha")
    expect(text).toContain("You")
  })

  it("shows only the answers under this comment, not those under another on the same note", async () => {
    const other = [note("c2", { text: "other comment" }), note("r2", { author: "persona", reply_to: "c2", text: "answer to the other one" })]
    show({ kind: "thread", id: "c1", rect }, [...thread, ...other])

    const text = (await screen.findByTestId("comment-thread")).textContent ?? ""

    expect(text).toContain("Drainage.")
    expect(text).not.toContain("answer to the other one")
  })

  it("answers under the comment and reads the changes again, staying open with an empty box", async () => {
    const { onClose, onChanged } = show({ kind: "thread", id: "c1", rect }, thread)
    const box = (await screen.findByLabelText("Reply")) as HTMLTextAreaElement
    fireEvent.change(box, { target: { value: "ok" } })

    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Reply" })))

    expect(api.replyToComment).toHaveBeenCalledWith({ path: "n.md", persona: "samantha", replyTo: "c1", text: "ok" })
    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()
    expect(box.value).toBe("")
  })

  it("resolves the comment and closes", async () => {
    const { onClose, onChanged } = show({ kind: "thread", id: "c1", rect }, thread)

    await act(async () => fireEvent.click(await screen.findByRole("button", { name: "Resolve" })))

    expect(api.changeComment).toHaveBeenCalledWith({ path: "n.md", persona: "samantha", id: "c1", state: "resolved" })
    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("stays open and says why when resolving fails", async () => {
    api.changeComment.mockResolvedValue({ ok: false, error: "No such comment." })
    const { onClose } = show({ kind: "thread", id: "c1", rect }, thread)

    await act(async () => fireEvent.click(await screen.findByRole("button", { name: "Resolve" })))

    expect(toast.error).toHaveBeenCalledWith("No such comment.")
    expect(onClose).not.toHaveBeenCalled()
  })

  it("asks before deleting, warns that the replies go too, and only deletes once confirmed", async () => {
    const { onClose } = show({ kind: "thread", id: "c1", rect }, thread)

    fireEvent.click(await screen.findByRole("button", { name: "Delete" }))

    expect(api.deleteComment).not.toHaveBeenCalled()
    const request = confirmStore.confirm.mock.calls[0][0]
    expect(request).toMatchObject({ permanent: true, confirmLabel: "Delete", description: "Its replies are deleted with it." })
    await act(async () => request.onConfirm())
    expect(api.deleteComment).toHaveBeenCalledWith("n.md", "samantha", "c1")
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("has no warning about replies when there are none", async () => {
    show({ kind: "thread", id: "c1", rect }, [thread[0]])
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }))
    expect(confirmStore.confirm.mock.calls[0][0].description).toBeUndefined()
  })

  it("draws nothing when the comment is gone, resolved elsewhere, or is itself an answer", () => {
    show({ kind: "thread", id: "gone", rect }, thread)
    expect(screen.queryByTestId("comment-thread")).toBeNull()
    cleanup()
    show({ kind: "thread", id: "r1", rect }, thread)
    expect(screen.queryByTestId("comment-thread")).toBeNull()
  })

  it("closes on Escape", async () => {
    const { onClose } = show({ kind: "thread", id: "c1", rect }, thread)
    await screen.findByTestId("comment-thread")

    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" })

    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})

describe("CommentPopover: accepting or declining one of her comments (docs/decisions/069)", () => {
  const hers = (over: Partial<Annotation> = {}) => note("h1", { author: "persona", text: "Are you sure about the count?", ...over })
  const reply = (author: "user" | "persona") => note("r1", { author, reply_to: "h1", text: "an answer", time: "2026-10-04T10:05:00+00:00" })
  const open = (annotations: Annotation[]) => show({ kind: "thread", id: "h1", rect }, annotations)
  const button = (name: string) => screen.findByRole("button", { name }) as Promise<HTMLButtonElement>

  it("offers Accept and Decline on her comment, and no plain Resolve", async () => {
    open([hers()])

    expect(await button("Accept")).toBeTruthy()
    expect(await button("Decline")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Resolve" })).toBeNull()
  })

  it("offers neither on the user's own comment, which is resolved as before", async () => {
    show({ kind: "thread", id: "c1", rect }, [note("c1")])

    expect(await button("Resolve")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Decline" })).toBeNull()
  })

  it("accepts it, tells the note's changes to be read again, and closes", async () => {
    const { onClose, onChanged } = open([hers()])

    await act(async () => fireEvent.click(await button("Accept")))

    expect(api.changeComment).toHaveBeenCalledWith({ path: "n.md", persona: "samantha", id: "h1", verdict: "accepted" })
    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("keeps Decline off until the user has replied in the thread, and says why", async () => {
    open([hers(), reply("persona")]) // an answer of hers is not the user's reply

    const decline = await button("Decline")

    expect(decline.disabled).toBe(true)
    expect(screen.getByText(/reply first/i)).toBeTruthy()
  })

  it("declines once the user has replied, and closes", async () => {
    const { onClose, onChanged } = open([hers(), reply("user")])
    const decline = await button("Decline")
    expect(decline.disabled).toBe(false)
    expect(screen.queryByText(/reply first/i)).toBeNull()

    await act(async () => fireEvent.click(decline))

    expect(api.changeComment).toHaveBeenCalledWith({ path: "n.md", persona: "samantha", id: "h1", verdict: "declined" })
    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("stays open and says why when the decision could not be saved", async () => {
    api.changeComment.mockResolvedValue({ ok: false, error: "Reply first, saying why you disagree." })
    const { onClose } = open([hers(), reply("user")])

    await act(async () => fireEvent.click(await button("Decline")))

    expect(toast.error).toHaveBeenCalledWith("Reply first, saying why you disagree.")
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe("CommentPopover: the thread's buttons are one row (Resolve on the left, Reply and Delete on the right)", () => {
  const row = async (id: string, annotations: Annotation[]) => {
    show({ kind: "thread", id, rect }, annotations)
    await screen.findByTestId("comment-thread")
    return screen.getByTestId("comment-thread-actions")
  }
  const labels = (el: HTMLElement) => [...el.querySelectorAll("button")].map((b) => b.textContent)

  it("puts Resolve, Reply and Delete in one row, in that order", async () => {
    const actions = await row("c1", [note("c1")])

    expect(labels(actions)).toEqual(["Resolve", "Reply", "Delete"])
  })

  it("for one of her comments the left side is Accept and Decline", async () => {
    const actions = await row("h1", [note("h1", { author: "persona" })])

    expect(labels(actions)).toEqual(["Accept", "Decline", "Reply", "Delete"])
  })

  it("keeps Reply and Delete together as the right side, apart from the left", async () => {
    const actions = await row("c1", [note("c1")])
    const [left, right] = [...actions.children] as HTMLElement[]

    expect(labels(left)).toEqual(["Resolve"])
    expect(labels(right)).toEqual(["Reply", "Delete"])
    expect(actions.className).toContain("justify-between")
  })

  it("Reply is off until something is written and sends from that row", async () => {
    const actions = await row("c1", [note("c1")])
    const send = [...actions.querySelectorAll("button")].find((b) => b.textContent === "Reply") as HTMLButtonElement
    expect(send.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText("Reply"), { target: { value: "an answer" } })
    expect(send.disabled).toBe(false)
    await act(async () => fireEvent.click(send))

    expect(api.replyToComment).toHaveBeenCalledWith({ path: "n.md", persona: "samantha", replyTo: "c1", text: "an answer" })
  })

  it("keeps the hint about declining above the row, not inside it", async () => {
    const actions = await row("h1", [note("h1", { author: "persona" })])

    expect(actions.textContent).not.toMatch(/to decline/i)
    expect(screen.getByText(/to decline, reply first/i)).toBeTruthy()
  })
})

