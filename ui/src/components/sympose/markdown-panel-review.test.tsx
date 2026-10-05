// @vitest-environment jsdom
import { getOpenNote } from "@/lib/open-note-source"
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { EditorView } from "@codemirror/view"

const api = vi.hoisted(() => ({ fetchVaultNote: vi.fn(), saveVaultNote: vi.fn() }))
const changesApi = vi.hoisted(() => ({ fetchChanges: vi.fn(), resolveChanges: vi.fn(), addComment: vi.fn(), replyToComment: vi.fn(), changeComment: vi.fn(), deleteComment: vi.fn() }))

// A stand-in for stylo that mounts a real CodeMirror view with the `extensions` it is given, draws the custom toolbar
// buttons and the canvas header, and reports edits through `onChange`: enough to run the panel's review wiring for real.
vi.mock("@damiro/stylo", async () => {
  const React = await import("react")
  const { EditorView } = await import("@codemirror/view")
  const { EditorState, Compartment } = await import("@codemirror/state")
  type Item = { id: string; title: string; run: (v: unknown) => void; disabled?: (s: unknown) => boolean }
  type Props = {
    value: string
    onChange: (next: string) => void
    mode?: string
    extensions?: import("@codemirror/state").Extension[]
    toolbar?: { items?: (string | Item)[] }
    inPlace?: { contextMenu?: boolean | { items?: (Item & { when?: string; readOnlySafe?: boolean })[] } }
    canvasHeader?: (ctx: { view: unknown }) => React.ReactNode
  }
  const Stylo = React.forwardRef<unknown, Props>(function Stylo(props, ref) {
    const host = React.useRef<HTMLDivElement>(null)
    const viewRef = React.useRef<InstanceType<typeof EditorView> | null>(null)
    const latest = React.useRef(props)
    latest.current = props
    const [, force] = React.useReducer((n: number) => n + 1, 0)
    React.useImperativeHandle(ref, () => ({ getView: () => viewRef.current, focus() {} }))
    const compartment = React.useRef(new Compartment())
    React.useEffect(() => {
      const view = new EditorView({
        state: EditorState.create({
          doc: props.value,
          extensions: [
            compartment.current.of(props.extensions ?? []),
            EditorView.updateListener.of((u) => {
              if (u.docChanged) latest.current.onChange(u.state.doc.toString())
              force()
            }),
          ],
        }),
        parent: host.current!,
      })
      viewRef.current = view
      force()
      return () => view.destroy()
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
    // Like stylo 0.17: a changed `extensions` array reconfigures the live editor, no remount.
    React.useEffect(() => {
      viewRef.current?.dispatch({ effects: compartment.current.reconfigure(props.extensions ?? []) })
    }, [props.extensions])
    const view = viewRef.current
    const items = props.toolbar?.items ?? []
    return (
      <div data-mode={props.mode} data-extensions={props.extensions ? "yes" : "no"}>
        {props.canvasHeader?.({ view })}
        <div role="toolbar">
          {items.map((item) =>
            typeof item === "string" ? null : (
              <button key={item.id} aria-label={item.title} disabled={view ? item.disabled?.(view.state) : true} onClick={() => item.run(view)} />
            )
          )}
        </div>
        <div role="menu" aria-label="right-click menu">
          {(typeof props.inPlace?.contextMenu === "object" ? props.inPlace.contextMenu.items ?? [] : []).map((item) => (
            <button key={item.id} role="menuitem" onClick={() => item.run(view)}>{item.title}</button>
          ))}
        </div>
        <div ref={host} data-testid="cm" />
      </div>
    )
  })
  return { splitFrontmatter: (text: string) => ({ frontmatter: "", body: text, prefix: "" }), Stylo }
})
vi.mock("@damiro/stylo/styles.css", () => ({}))
vi.mock("@damiro/stylo/katex.css", () => ({}))
vi.mock("@/lib/vault-note-api", () => api)
vi.mock("@/lib/persona-changes-api", () => changesApi)
const notify = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))
vi.mock("@/components/sympose/note-actions-menu", () => ({ NoteActionsMenu: () => null }))

import { captureContext } from "@/lib/passage-finder"
import type { Proposal } from "@/lib/persona-changes-api"
import type { EditorPreferences } from "@/lib/use-editor-preferences"
import { MarkdownPanel } from "./markdown-panel"

// jsdom does no layout, so a range has no rectangles; CodeMirror asks for them to find where a position is on screen.
beforeAll(() => {
  const none = Object.assign([] as unknown as DOMRectList, { item: () => null })
  Range.prototype.getClientRects = () => none
  Range.prototype.getBoundingClientRect = () => new DOMRect(0, 0, 0, 0)
})

const PREFERENCES = { surface: "in-place", reveal: "never", selectionUI: "bar", tableEditing: "source", focusOutline: "on", autosave: "off", hideExtension: "on" } as EditorPreferences
const NOTE = "I run three times a week. The beds are raised.\n"
const edit = (id: string, find: string, replace: string): Proposal => {
  const at = NOTE.indexOf(find)
  const [before, after] = captureContext(NOTE, at, at + find.length)
  return { id, time: "t", kind: "edit", say: `say ${id}`, find, replace, before, after, status: "pending" }
}
const changes = (proposals: Proposal[], annotations: unknown[] = []) => ({ path: "Garden plan.md", exists: true, mtime: 100, proposals, annotations })

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} })
  api.fetchVaultNote.mockResolvedValue({ path: "Garden plan.md", content: NOTE.trimEnd(), mtime: 100 })
  api.saveVaultNote.mockResolvedValue({ ok: true, mtime: 200 })
  changesApi.fetchChanges.mockResolvedValue(changes([]))
  changesApi.resolveChanges.mockResolvedValue({ ok: true, resolved: [] })
  for (const fn of [changesApi.addComment, changesApi.replyToComment, changesApi.changeComment, changesApi.deleteComment]) fn.mockResolvedValue({ ok: true })
})
afterEach(() => {
  document.cookie = "sympose:pref.noteReadOnly=; max-age=0"
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const open = (props: Partial<React.ComponentProps<typeof MarkdownPanel>> = {}) =>
  render(<MarkdownPanel path="Garden plan.md" persona="samantha" preferences={PREFERENCES} toolbarItems={["undo"]} {...props} />)
const editorView = () => EditorView.findFromDOM(screen.getByTestId("cm").querySelector(".cm-editor") as HTMLElement) as EditorView
const commentButton = () => document.querySelector('button[aria-label="Comment on the selected text"]') as HTMLButtonElement | null
const doc = () => (screen.getByTestId("cm").querySelector(".cm-content") as HTMLElement).textContent

describe("MarkdownPanel with the persona's suggested changes", () => {
  it("asks for the open note's changes for the persona, and draws a suggestion in the text", async () => {
    changesApi.fetchChanges.mockResolvedValue(changes([edit("p1", "three times", "four times")]))

    open()

    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".sy-change-add")?.textContent).toBe("four times"))
    expect(changesApi.fetchChanges).toHaveBeenCalledWith("Garden plan.md", "samantha")
    expect(screen.getByTestId("cm").querySelector(".sy-change-del")?.textContent).toBe("three times")
  })

  it("accepts one change from its own button: the text changes, the server forgets it, and nothing is saved yet", async () => {
    changesApi.fetchChanges.mockResolvedValue(changes([edit("p1", "three times", "four times")]))
    open()
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".sy-change-accept")).not.toBeNull())

    await act(async () => fireEvent.click(screen.getByTestId("cm").querySelector(".sy-change-accept") as HTMLElement))

    expect(doc()).toContain("four times a week")
    await waitFor(() => expect(changesApi.resolveChanges).toHaveBeenCalledWith("Garden plan.md", "samantha", ["p1"]))
    expect(api.saveVaultNote).not.toHaveBeenCalled()
  })

  it("declines one change from its own button without touching the text", async () => {
    changesApi.fetchChanges.mockResolvedValue(changes([edit("p1", "three times", "four times")]))
    open()
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".sy-change-decline")).not.toBeNull())

    await act(async () => fireEvent.click(screen.getByTestId("cm").querySelector(".sy-change-decline") as HTMLElement))

    expect(doc()).toContain("three times a week")
    await waitFor(() => expect(changesApi.resolveChanges).toHaveBeenCalledWith("Garden plan.md", "samantha", ["p1"]))
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".sy-change")).toBeNull())
  })

  it("accepts the whole note from the toolbar: every change applied, forgotten, and the note saved with them", async () => {
    changesApi.fetchChanges.mockResolvedValue(changes([edit("p1", "three times", "four times"), edit("p2", "raised", "sunken")]))
    open()
    const accept = await screen.findByRole("button", { name: /accept all suggested changes/i })
    await waitFor(() => expect((accept as HTMLButtonElement).disabled).toBe(false))

    await act(async () => fireEvent.click(accept))

    await waitFor(() => expect(api.saveVaultNote).toHaveBeenCalledTimes(1))
    expect(api.saveVaultNote.mock.calls[0][1]).toContain("four times a week. The beds are sunken.")
    expect(changesApi.resolveChanges).toHaveBeenCalledWith("Garden plan.md", "samantha", expect.arrayContaining(["p1", "p2"]))
  })

  it("declines the whole note from the toolbar, forgetting every suggestion and leaving the text", async () => {
    changesApi.fetchChanges.mockResolvedValue(changes([edit("p1", "three times", "four times")]))
    open()

    const decline = await screen.findByRole("button", { name: /decline all suggested changes/i })
    await waitFor(() => expect((decline as HTMLButtonElement).disabled).toBe(false))

    await act(async () => fireEvent.click(decline))

    expect(changesApi.resolveChanges).toHaveBeenCalledWith("Garden plan.md", "samantha", "all")
    expect(doc()).toContain("three times a week")
    expect(api.saveVaultNote).not.toHaveBeenCalled()
  })

  it("adds the two toolbar buttons only while the note has suggestions", async () => {
    open()
    await waitFor(() => expect(changesApi.fetchChanges).toHaveBeenCalled())
    expect(screen.queryByRole("button", { name: /suggested changes/i })).toBeNull()

    cleanup()
    changesApi.fetchChanges.mockResolvedValue(changes([edit("p1", "three times", "four times")]))
    open()
    expect(await screen.findByRole("button", { name: /accept all suggested changes/i })).toBeTruthy()
    expect(screen.getByRole("button", { name: /decline all suggested changes/i })).toBeTruthy()
  })

  it("shows a suggestion whose passage was rewritten in a strip, not in the text, and declines it from there", async () => {
    const stale = edit("p1", "three times", "four times")
    api.fetchVaultNote.mockResolvedValue({ path: "Garden plan.md", content: NOTE.replace("three times", "five times").trimEnd(), mtime: 100 })
    changesApi.fetchChanges.mockResolvedValue(changes([stale]))

    open()

    const strip = await screen.findByRole("status")
    expect(strip.textContent).toContain("no longer fits")
    expect(screen.getByTestId("cm").querySelector(".sy-change-del")).toBeNull()
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Decline" })))
    expect(changesApi.resolveChanges).toHaveBeenCalledWith("Garden plan.md", "samantha", ["p1"])
  })

  it("highlights an open comment's passage and puts a dot in the margin, and no margin without one", async () => {
    const at = NOTE.indexOf("raised")
    const [before, after] = captureContext(NOTE, at, at + 6)
    const comment = { id: "c1", time: "t", author: "user", quote: "raised", before, after, text: "why?", state: "open", reply_to: null, status: "attached" }
    changesApi.fetchChanges.mockResolvedValue(changes([], [comment]))

    open()

    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".sy-comment-hl")?.textContent).toBe("raised"))
    await waitFor(() => expect(screen.getByTestId("cm").querySelectorAll(".sy-comment-line")).toHaveLength(1))

    cleanup()
    changesApi.fetchChanges.mockResolvedValue(changes([], [{ ...comment, state: "resolved" }]))
    open()
    await waitFor(() => expect(changesApi.fetchChanges).toHaveBeenCalledTimes(2))
    // Only once the editor is on screen and the fetched comment has been handed to it does an absence mean anything.
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".cm-content")).not.toBeNull())
    await act(async () => {})
    expect(screen.getByTestId("cm").querySelector(".cm-content")).not.toBeNull()
    expect(screen.getByTestId("cm").querySelector(".sy-comment-line")).toBeNull()
    expect(screen.getByTestId("cm").querySelector(".sy-comment-hl")).toBeNull()
  })

  it("comments on selected words: the button wakes up with a selection, opens a box on them, and saves with the editor's own context", async () => {
    open()
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".cm-content")).not.toBeNull())
    await waitFor(() => expect(commentButton()).not.toBeNull())
    expect(commentButton()?.disabled).toBe(true)

    const at = NOTE.indexOf("raised")
    await act(async () => editorView().dispatch({ selection: { anchor: at, head: at + 6 } }))
    await waitFor(() => expect(commentButton()?.disabled).toBe(false))
    await act(async () => fireEvent.click(commentButton() as HTMLButtonElement))

    const box = await screen.findByTestId("comment-compose")
    expect(box.textContent).toContain("raised")
    fireEvent.change(screen.getByLabelText("Comment"), { target: { value: "why raised?" } })
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Comment" })))

    expect(changesApi.addComment).toHaveBeenCalledWith({ path: "Garden plan.md", persona: "samantha", quote: "raised", before: NOTE.slice(0, at), after: NOTE.trimEnd().slice(at + 6, at + 46), text: "why raised?" })
    await waitFor(() => expect(changesApi.fetchChanges).toHaveBeenCalledTimes(2)) // the changes are read again to show it
    await waitFor(() => expect(screen.queryByTestId("comment-compose")).toBeNull())
  })

  it("closes the box when another note is opened, so a comment is never saved onto the wrong note", async () => {
    const view = open()
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".cm-content")).not.toBeNull())
    const at = NOTE.indexOf("raised")
    await act(async () => editorView().dispatch({ selection: { anchor: at, head: at + 6 } }))
    await waitFor(() => expect(commentButton()?.disabled).toBe(false))
    await act(async () => fireEvent.click(commentButton() as HTMLButtonElement))
    await screen.findByTestId("comment-compose")

    api.fetchVaultNote.mockResolvedValue({ path: "Other.md", content: "other note", mtime: 1 })
    view.rerender(<MarkdownPanel path="Other.md" persona="samantha" preferences={PREFERENCES} toolbarItems={["undo"]} />)

    await waitFor(() => expect(screen.queryByTestId("comment-compose")).toBeNull())
    expect(changesApi.addComment).not.toHaveBeenCalled()
  })

  it("opens a comment's thread when its highlighted passage is clicked, and an answer is saved under it", async () => {
    const at = NOTE.indexOf("raised")
    const comment = { id: "c1", time: "2026-10-04T10:00:00+00:00", author: "user", quote: "raised", before: NOTE.slice(0, at), after: NOTE.slice(at + 6, at + 46), text: "why raised?", state: "open", reply_to: null, status: "attached" }
    const answer = { ...comment, id: "r1", author: "persona", reply_to: "c1", text: "Drainage.", time: "2026-10-04T10:05:00+00:00" }
    changesApi.fetchChanges.mockResolvedValue(changes([], [comment, answer]))
    open({ personaName: "Samantha" })
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".sy-comment-hl")).not.toBeNull())

    await act(async () => fireEvent.click(screen.getByTestId("cm").querySelector(".sy-comment-hl") as HTMLElement))

    const thread = await screen.findByTestId("comment-thread")
    expect(thread.textContent).toContain("why raised?")
    expect(thread.textContent).toContain("Samantha")
    expect(thread.textContent).toContain("Drainage.")
    fireEvent.change(screen.getByLabelText("Reply"), { target: { value: "thanks" } })
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Reply" })))
    expect(changesApi.replyToComment).toHaveBeenCalledWith({ path: "Garden plan.md", persona: "samantha", replyTo: "c1", text: "thanks" })
    await waitFor(() => expect(changesApi.fetchChanges).toHaveBeenCalledTimes(2))
  })

  it("names the persona by her handle when it is not told her name", async () => {
    const comment = { id: "c1", time: "t", author: "persona", quote: "raised", before: "", after: "", text: "hi", state: "open", reply_to: null, status: "attached" }
    changesApi.fetchChanges.mockResolvedValue(changes([], [comment]))
    open()
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".sy-comment-hl")).not.toBeNull())

    await act(async () => fireEvent.click(screen.getByTestId("cm").querySelector(".sy-comment-hl") as HTMLElement))

    expect((await screen.findByTestId("comment-thread")).textContent).toContain("Samantha")
  })

  it("offers Comment in the right-click menu and it opens the box on the selected words", async () => {
    open()
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".cm-content")).not.toBeNull())
    const at = NOTE.indexOf("raised")
    await act(async () => editorView().dispatch({ selection: { anchor: at, head: at + 6 } }))

    await act(async () => fireEvent.click(screen.getByRole("menuitem", { name: "Comment" })))

    expect((await screen.findByTestId("comment-compose")).textContent).toContain("raised")
  })

  it("tells the chat which note is open and its text as the editor holds it, and forgets it when the note closes", async () => {
    const { unmount } = open()
    await waitFor(() => expect(screen.getByTestId("cm").querySelector(".cm-content")).not.toBeNull())
    await waitFor(() => expect(getOpenNote()?.path).toBe("Garden plan.md"))
    expect(getOpenNote()?.text.trimEnd()).toBe(NOTE.trimEnd())

    await act(async () => editorView().dispatch({ changes: { from: 0, insert: "Hi. " } }))
    await waitFor(() => expect(getOpenNote()?.text.startsWith("Hi. ")).toBe(true))

    unmount()
    expect(getOpenNote()).toBeNull()
  })

  it("does not offer a persona's own file to the chat as a note", async () => {
    const file = { load: vi.fn().mockResolvedValue({ content: NOTE, mtime: 1 }), save: vi.fn(), title: "soul.md" }
    open({ path: "soul.md", file })
    await screen.findByTestId("cm")
    expect(getOpenNote()).toBeNull()
  })

  it("has no comment in the right-click menu for a persona's own file", async () => {
    const file = { load: vi.fn().mockResolvedValue({ content: NOTE, mtime: 1 }), save: vi.fn(), title: "soul.md" }
    open({ path: "soul.md", file })
    await screen.findByTestId("cm")
    expect(screen.queryByRole("menuitem", { name: "Comment" })).toBeNull()
  })

  it("has no comment button for a persona's own file", async () => {
    const file = { load: vi.fn().mockResolvedValue({ content: NOTE, mtime: 1 }), save: vi.fn(), title: "soul.md" }
    open({ path: "soul.md", file })
    await screen.findByTestId("cm")
    expect(commentButton()).toBeNull()
  })

  it("draws nothing for a persona's own file, and does not ask for its changes", async () => {
    const file = { load: vi.fn().mockResolvedValue({ content: NOTE, mtime: 1 }), save: vi.fn(), title: "soul.md" }

    open({ path: "soul.md", file })

    await screen.findByTestId("cm")
    expect(changesApi.fetchChanges).not.toHaveBeenCalled()
    expect(screen.getByTestId("cm").parentElement?.getAttribute("data-extensions")).toBe("no")
  })

  it("does not draw suggestions in read mode", async () => {
    document.cookie = "sympose:pref.noteReadOnly=1"
    changesApi.fetchChanges.mockResolvedValue(changes([edit("p1", "three times", "four times")]))

    open()

    await waitFor(() => expect(changesApi.fetchChanges).toHaveBeenCalled())
    expect(screen.getByTestId("cm").parentElement?.getAttribute("data-extensions")).toBe("no")
    expect(screen.getByTestId("cm").querySelector(".sy-change")).toBeNull()
  })
})
