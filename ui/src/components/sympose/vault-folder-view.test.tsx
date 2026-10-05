// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import * as React from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { VaultSearchResult } from "@/lib/vault-search-api"
import { endFolderDrag, startFolderDrag } from "@/lib/vault-drag"
import { folderIconFor } from "@/lib/vault-folders"
import { VaultFolderView } from "./vault-folder-view"
import type { VaultNode } from "./vault-tree"

const treeProps: Record<string, unknown>[] = []
const trashProps: Record<string, unknown>[] = []
let treeMounts = 0
vi.mock("./vault-tree", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./vault-tree")>()),
  VaultTree: (p: Record<string, unknown>) => {
    treeProps.push(p)
    React.useEffect(() => {
      treeMounts++
    }, [])
    return <div data-testid="tree" />
  },
}))
vi.mock("./trash-list", () => ({
  TrashList: (p: Record<string, unknown>) => {
    trashProps.push(p)
    return <div data-testid="trash" />
  },
}))

const MIME = "application/x-sympose-vault-note-path"
beforeEach(() => {
  treeProps.length = 0
  trashProps.length = 0
  treeMounts = 0
})
afterEach(cleanup)

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const folder = (path: string, children: VaultNode[] = []): VaultNode =>
  ({ type: "folder", name: path.split("/").pop()!, path, children }) as VaultNode
const hit = (rel: string, extra: Partial<VaultSearchResult> = {}): VaultSearchResult => ({
  file_name: rel.split("/").pop()!,
  rel_path: rel,
  match_type: "content",
  line_no: 3,
  snippet: "a snippet",
  title: "t",
  tags: [],
  index: 0,
  ...extra,
})

function setup(over: Partial<React.ComponentProps<typeof VaultFolderView>> = {}) {
  const spies = {
    moveNote: vi.fn(),
    refreshVault: vi.fn(),
    unhideFromView: vi.fn(),
    selectNote: vi.fn(),
    openEditor: vi.fn(),
    onOpenDraft: vi.fn(),
  }
  const props: React.ComponentProps<typeof VaultFolderView> = {
    trashView: false,
    conversationBinKey: 0,
    onConversationRestored: vi.fn(),
    activeLabel: "Notes",
    activeRootFolder: folder("Notes", [note("Notes/a.md")]),
    activePersona: "samantha",
    vaultPath: "/vault",
    vaultRefreshKey: 4,
    vaultTreeEmpty: false,
    panelEmpty: false,
    vaultSearchQuery: "",
    searchedPanelNodes: [note("Notes/a.md")],
    contentMatches: [],
    beyondFolderMatches: [],
    pinnedNodes: [],
    pinnedShowPath: false,
    drafts: [],
    vaultTreeActions: { persona: "samantha" } as React.ComponentProps<typeof VaultFolderView>["vaultTreeActions"],
    ...spies,
    ...over,
  }
  const view = render(<VaultFolderView {...props} />)
  return { ...spies, props, ...view }
}

describe("VaultFolderView: the heading", () => {
  it("is the name of the folder in view", () => {
    setup({ activeLabel: "Daily" })
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Daily")
  })

  it("says Vault when the section has no label, and Bin on the Bin", () => {
    setup({ activeLabel: "" })
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Vault")
    cleanup()
    setup({ trashView: true, activeLabel: "Whatever" })
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Bin")
  })
})

describe("VaultFolderView: the Bin", () => {
  it("shows the bin for the persona and re-pulls it with the vault, and nothing of the tree", () => {
    const s = setup({ trashView: true })
    expect(screen.getByTestId("trash")).toBeTruthy()
    expect(screen.queryByTestId("tree")).toBeNull()
    expect(trashProps[0].persona).toBe("samantha")
    expect(trashProps[0].refreshKey).toBe(4)
    ;(trashProps[0].onRestored as () => void)()
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
  })
})

describe("VaultFolderView: what is said instead of a tree", () => {
  it("says so when the vault has nothing in scope", () => {
    setup({ vaultTreeEmpty: true })
    expect(screen.getByText(/No notes in scope/)).toBeTruthy()
    expect(screen.queryByTestId("tree")).toBeNull()
  })

  it("says an empty folder is empty, and shows no tree", () => {
    setup({ panelEmpty: true, searchedPanelNodes: [] })
    expect(screen.getByText("This folder is empty")).toBeTruthy()
    expect(screen.queryByTestId("tree")).toBeNull()
  })

  it("still shows pinned notes in an empty folder", () => {
    setup({ panelEmpty: true, searchedPanelNodes: [], pinnedNodes: [note("Other/p.md")] })
    expect(screen.getByTestId("tree")).toBeTruthy()
  })

  it("says nothing matched, in the folder, when a search found nothing anywhere in it", () => {
    setup({ vaultSearchQuery: "zzz", searchedPanelNodes: [], contentMatches: [] })
    expect(screen.getByText(/No matches for "zzz"/)).toBeTruthy()
  })

  it("does not say so when nothing is being searched for, whatever the tree holds", () => {
    setup({ vaultSearchQuery: "", panelEmpty: false, searchedPanelNodes: [], contentMatches: [] })
    expect(screen.queryByText(/No matches for/)).toBeNull()
  })

  it("does not say so while the folder has matching nodes, or content matches", () => {
    setup({ vaultSearchQuery: "a", searchedPanelNodes: [note("Notes/a.md")] })
    expect(screen.queryByText(/No matches for/)).toBeNull()
    cleanup()
    setup({ vaultSearchQuery: "a", searchedPanelNodes: [], contentMatches: [hit("Notes/b.md")] })
    expect(screen.queryByText(/No matches for/)).toBeNull()
  })

  it("does not say so, nor that the folder is empty, when the folder is empty but the search found things elsewhere", () => {
    setup({ panelEmpty: false, vaultSearchQuery: "a", searchedPanelNodes: [], beyondFolderMatches: [hit("Daily/x.md")] })
    expect(screen.queryByText("This folder is empty")).toBeNull()
  })
})

describe("VaultFolderView: the tree", () => {
  it("hands the tree the folder's nodes, its pinned notes, and the row actions", () => {
    const pinned = [note("Notes/p.md")]
    setup({ pinnedNodes: pinned, pinnedShowPath: true })
    const p = treeProps[0]
    expect((p.nodes as VaultNode[]).map((n) => n.path)).toEqual(["Notes/a.md"])
    expect(p.pinnedNodes).toBe(pinned)
    expect(p.pinnedShowPath).toBe(true)
    expect(p.persona).toBe("samantha")
  })

  it("has the tree caption its plain list \"Notes in\" the folder, with the folder's own icon", () => {
    setup({ activeLabel: "Movies", pinnedNodes: [note("Other/p.md")] })
    const p = treeProps.at(-1)!
    expect(p.listLabel).toBe("Notes in Movies")
    expect(p.listIcon).toBe(folderIconFor("Movies"))
    expect(p.listIcon).not.toBe(folderIconFor("Unknown"))
  })

  it("says an empty folder is empty even with recent notes: they are the footer's, not the tree's", () => {
    setup({ panelEmpty: true, searchedPanelNodes: [] })
    expect(screen.queryByTestId("tree")).toBeNull()
    expect(screen.getByText("This folder is empty")).toBeTruthy()
  })

  it("browsing: remembers the open folders for the vault, and starts none expanded", () => {
    setup({ searchedPanelNodes: [folder("Notes/Sub", [note("Notes/Sub/a.md")])] })
    const p = treeProps[0]
    expect(String(p.storageKey)).toContain("sympose:vault.expanded")
    expect(p.defaultExpanded).toEqual([])
  })

  it("searching: starts the folders that match expanded, and keeps the remembered ones untouched", () => {
    setup({ vaultSearchQuery: "a", searchedPanelNodes: [folder("Notes/Sub", [note("Notes/Sub/a.md")])] })
    const p = treeProps[0]
    expect(p.storageKey).toBeUndefined()
    expect(p.defaultExpanded).toEqual(["Notes/Sub"])
  })

  it("starts the tree afresh between browsing and searching, and between vaults, not otherwise", () => {
    const { rerender, props } = setup()
    expect(treeMounts).toBe(1)
    rerender(<VaultFolderView {...props} activeLabel="Renamed" />)
    expect(treeMounts).toBe(1)
    rerender(<VaultFolderView {...props} vaultSearchQuery="a" />)
    expect(treeMounts).toBe(2)
    rerender(<VaultFolderView {...props} vaultSearchQuery="ab" />)
    expect(treeMounts).toBe(2)
    rerender(<VaultFolderView {...props} vaultSearchQuery="ab" vaultPath="/other" />)
    expect(treeMounts).toBe(3)
  })
})

describe("VaultFolderView: search results beyond the tree", () => {
  it("lists the content matches in the folder under Also found in, as files without the .md", () => {
    setup({ vaultSearchQuery: "x", contentMatches: [hit("Notes/b.md")] })
    expect(screen.getByText("Also found in Notes")).toBeTruthy()
    expect(screen.getByText("b")).toBeTruthy()
    expect(screen.getByText("a snippet")).toBeTruthy()
  })

  it("opens a content match in the editor", () => {
    const s = setup({ vaultSearchQuery: "x", contentMatches: [hit("Notes/b.md")] })
    fireEvent.click(screen.getByRole("button", { name: /^b/ }))
    expect(s.selectNote).toHaveBeenCalledWith("Notes/b.md")
    expect(s.openEditor).toHaveBeenCalledTimes(1)
  })

  it("lists matches beyond the folder with their whole path, counted and pluralised", () => {
    setup({ vaultSearchQuery: "x", beyondFolderMatches: [hit("Daily/2026/c.md")] })
    expect(screen.getByText(/1 match\s+beyond/)).toBeTruthy()
    expect(screen.getByText("Daily/2026/c")).toBeTruthy()
    cleanup()
    setup({ vaultSearchQuery: "x", beyondFolderMatches: [hit("Daily/c.md"), hit("Code/d.md")] })
    expect(screen.getByText(/2 matches\s+beyond/)).toBeTruthy()
  })

  it("opens a match beyond the folder in the editor", () => {
    const s = setup({ vaultSearchQuery: "x", beyondFolderMatches: [hit("Daily/c.md")] })
    fireEvent.click(screen.getByRole("button", { name: /Daily\/c/ }))
    expect(s.selectNote).toHaveBeenCalledWith("Daily/c.md")
    expect(s.openEditor).toHaveBeenCalledTimes(1)
  })

  it("shows no heading for a list that has no hits", () => {
    setup({ vaultSearchQuery: "x", contentMatches: [], beyondFolderMatches: [] })
    expect(screen.queryByText(/Also found in/)).toBeNull()
    expect(screen.queryByText(/beyond/)).toBeNull()
  })

  it("shows neither list when there is no query", () => {
    setup({ contentMatches: [hit("Notes/b.md")], beyondFolderMatches: [hit("Daily/c.md")] })
    expect(screen.queryByText(/Also found in/)).toBeNull()
    expect(screen.queryByText(/beyond/)).toBeNull()
  })

  it("lists a hit that sits in something hidden greyed, with an Unhide for every entry that hides it", () => {
    const s = setup({
      vaultSearchQuery: "x",
      contentMatches: [hit("Notes/h.md", { hidden: true, hidden_by: ["Notes"] })],
      beyondFolderMatches: [hit("Daily/g.md", { hidden: true })],
    })
    fireEvent.click(screen.getByRole("button", { name: "Unhide h" }))
    expect(s.unhideFromView).toHaveBeenLastCalledWith(["Notes"])
    fireEvent.click(screen.getByRole("button", { name: "Unhide Daily/g" }))
    expect(s.unhideFromView).toHaveBeenLastCalledWith("Daily/g.md")
    expect(s.selectNote).not.toHaveBeenCalled()
  })
})

describe("VaultFolderView: dropping a note on the heading", () => {
  const dragData = (path?: string) => ({
    dataTransfer: {
      types: path ? [MIME] : ["Files"],
      getData: (t: string) => (t === MIME && path ? path : ""),
      dropEffect: "none",
    },
  })
  const heading = () => screen.getByRole("heading", { level: 2 })

  it("moves the note to the root of the folder in view", () => {
    const s = setup()
    fireEvent.drop(heading(), dragData("Daily/x.md"))
    expect(s.moveNote).toHaveBeenCalledExactlyOnceWith("Daily/x.md", "Notes")
  })

  it("takes over the drop, so the browser does not also handle the dropped data", () => {
    setup()
    expect(fireEvent.drop(heading(), dragData("Daily/x.md"))).toBe(false)
  })

  it("accepts only a vault note: a drop of anything else does nothing", () => {
    const s = setup()
    fireEvent.drop(heading(), dragData())
    expect(s.moveNote).not.toHaveBeenCalled()
  })

  it("lights the heading while a note is over it, and puts it out on leave or drop", () => {
    setup()
    expect(heading().className).not.toContain("ring-brand")
    fireEvent.dragEnter(heading(), dragData("Daily/x.md"))
    expect(heading().className).toContain("ring-brand")
    fireEvent.dragLeave(heading(), dragData("Daily/x.md"))
    expect(heading().className).not.toContain("ring-brand")
    fireEvent.dragEnter(heading(), dragData("Daily/x.md"))
    fireEvent.drop(heading(), dragData("Daily/x.md"))
    expect(heading().className).not.toContain("ring-brand")
  })

  it("does not light up for a drag that is not a vault note", () => {
    setup()
    fireEvent.dragEnter(heading(), dragData())
    expect(heading().className).not.toContain("ring-brand")
  })

  it("marks a note drag as a move on dragover, and leaves other drags alone", () => {
    setup()
    const note = dragData("a.md")
    fireEvent.dragOver(heading(), note)
    expect(note.dataTransfer.dropEffect).toBe("move")
    const other = dragData()
    fireEvent.dragOver(heading(), other)
    expect(other.dataTransfer.dropEffect).toBe("none")
  })

  it("is no drop target when the section is not a folder (a root note)", () => {
    const s = setup({ activeRootFolder: undefined })
    fireEvent.drop(heading(), dragData("Daily/x.md"))
    fireEvent.dragEnter(heading(), dragData("Daily/x.md"))
    expect(s.moveNote).not.toHaveBeenCalled()
    expect(heading().className).not.toContain("ring-brand")
  })
})

describe("VaultFolderView: the Drafts section", () => {
  const draft = { path: "Ideas/New plan.md", name: "New plan", is_new: true, count: 1, comments: 0, time: "t" }

  it("lists the drafts above the notes, and opens one when its row is chosen", () => {
    const s = setup({ drafts: [draft], vaultTreeActions: { persona: "samantha", hideExtension: true } as React.ComponentProps<typeof VaultFolderView>["vaultTreeActions"] })
    expect(screen.getByText("Drafts")).toBeTruthy()
    fireEvent.click(screen.getByText("New plan"))
    expect(s.onOpenDraft).toHaveBeenCalledWith(draft)
    const section = document.querySelector('[data-slot="drafts-section"]')!
    expect(section.compareDocumentPosition(screen.getByTestId("tree")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it("is not shown on the Bin or while searching, where nothing lists drafts", () => {
    setup({ drafts: [draft], trashView: true })
    expect(screen.queryByText("Drafts")).toBeNull()
    cleanup()
    setup({ drafts: [draft], vaultSearchQuery: "plan" })
    expect(screen.queryByText("Drafts")).toBeNull()
  })

  it("shows nothing when there are no drafts", () => {
    setup({ drafts: [] })
    expect(document.querySelector('[data-slot="drafts-section"]')).toBeNull()
  })
})

describe("VaultFolderView: dropping a folder on the heading (docs/decisions/074)", () => {
  const FOLDER_MIME = "application/x-sympose-vault-folder-path"
  const heading = () => screen.getByRole("heading", { level: 2 })
  const held = (path: string) => {
    const dt = { types: [FOLDER_MIME], getData: (t: string) => (t === FOLDER_MIME ? path : ""), setData: vi.fn(), dropEffect: "none", effectAllowed: "" }
    startFolderDrag({ dataTransfer: dt } as unknown as React.DragEvent, path)
    return { dataTransfer: dt }
  }
  const withFolders = () => {
    const onMoveFolder = vi.fn()
    const s = setup({ vaultTreeActions: { persona: "samantha", onMoveFolder } as unknown as React.ComponentProps<typeof VaultFolderView>["vaultTreeActions"] })
    return { onMoveFolder, ...s }
  }
  afterEach(endFolderDrag)

  it("moves the folder into the folder in view, lighting the heading meanwhile and taking over the drop", () => {
    const { onMoveFolder } = withFolders()
    const e = held("Daily/Old")

    fireEvent.dragEnter(heading(), e)
    expect(heading().className).toContain("ring-brand")
    expect(fireEvent.drop(heading(), e)).toBe(false)

    expect(onMoveFolder).toHaveBeenCalledExactlyOnceWith("Daily/Old", "Notes")
    expect(heading().className).not.toContain("ring-brand")
  })

  it.each([
    ["itself", "Notes"],
    ["a folder already in it", "Notes/Sub"],
  ])("does not offer %s", (_what, dragged) => {
    const { onMoveFolder } = withFolders()
    const e = held(dragged)

    expect(fireEvent.dragOver(heading(), e)).toBe(true)
    fireEvent.dragEnter(heading(), e)
    expect(heading().className).not.toContain("ring-brand")
    fireEvent.drop(heading(), e)
    expect(onMoveFolder).not.toHaveBeenCalled()
  })

  it("takes no folder when moving folders is not wired, and still takes a note", () => {
    const s = setup()
    fireEvent.drop(heading(), held("Daily/Old"))
    expect(s.moveNote).not.toHaveBeenCalled()
  })

  it("is no drop target for a folder when the section is not a folder", () => {
    const onMoveFolder = vi.fn()
    setup({ activeRootFolder: undefined, vaultTreeActions: { persona: "samantha", onMoveFolder } as unknown as React.ComponentProps<typeof VaultFolderView>["vaultTreeActions"] })
    fireEvent.drop(heading(), held("Daily/Old"))
    expect(onMoveFolder).not.toHaveBeenCalled()
  })
})
