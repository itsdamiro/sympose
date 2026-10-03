// @vitest-environment jsdom
import { renderHook } from "@testing-library/react"
import { Folder01Icon, Note01Icon, File01Icon, StarIcon } from "@hugeicons/core-free-icons"
import { describe, expect, it } from "vitest"

import type { VaultNode } from "@/components/sympose"
import { iconByName } from "./persona-icons"
import { VAULT_FOLDERS } from "./vault-folders"
import { useMenuItems } from "./use-menu-items"

const note = (path: string): VaultNode => ({ type: "note", name: path, path }) as VaultNode
const folder = (name: string): VaultNode => ({ type: "folder", name, path: name, children: [] }) as VaultNode

describe("useMenuItems", () => {
  it("lists the top-level entries in the tree's own order, by path", () => {
    const { result } = renderHook(() => useMenuItems([folder("Zeta"), note("README.md"), folder("Alpha")], false))
    expect(result.current.menuItems.map((i) => [i.id, i.label, i.type])).toEqual([
      ["Zeta", "Zeta", "folder"],
      ["README.md", "README.md", "note"],
      ["Alpha", "Alpha", "folder"],
    ])
  })

  it("drops the .md from a label only when asked to", () => {
    const tree = [note("README.md")]
    expect(renderHook(() => useMenuItems(tree, true)).result.current.menuItems[0].label).toBe("README")
    expect(renderHook(() => useMenuItems(tree, false)).result.current.menuItems[0].label).toBe("README.md")
  })

  it("gives a note, another file and a folder their own icons, and a known folder its curated one", () => {
    const known = VAULT_FOLDERS[0]
    const { result } = renderHook(() => useMenuItems([note("a.md"), note("b.pdf"), folder("Unheard Of"), folder(known.name)], false))
    const icons = result.current.menuItems.map((i) => i.icon)
    expect(icons).toEqual([Note01Icon, File01Icon, Folder01Icon, iconByName(known.icon)])
  })

  it("draws a folder with the icon its definition names, over the curated one, and ignores a name the set lacks", () => {
    const items = renderHook(() =>
      useMenuItems(
        [
          { ...folder("Movies"), icon: "star" },
          { ...folder("Garden"), icon: "star" },
          { ...folder("Orchard"), icon: "not-in-the-set" },
          { ...folder("Movies"), icon: "not-in-the-set" },
        ],
        false,
      ),
    ).result.current.menuItems
    expect(items.map((i) => i.icon)).toEqual([StarIcon, StarIcon, Folder01Icon, iconByName("film-roll")])
  })

  it("collects the root notes, so a menu pick can open them", () => {
    const { result } = renderHook(() => useMenuItems([folder("Notes"), note("README.md")], false))
    expect([...result.current.noteIds]).toEqual(["README.md"])
  })

  it("keeps the same list while neither the tree nor the extension setting changes", () => {
    const tree = [note("a.md")]
    const { result, rerender } = renderHook(() => useMenuItems(tree, false))
    const first = result.current
    rerender()
    expect(result.current.menuItems).toBe(first.menuItems)
    expect(result.current.noteIds).toBe(first.noteIds)
  })

  it("follows the tree and the extension setting when either changes", () => {
    const { result, rerender } = renderHook(({ tree, hide }) => useMenuItems(tree, hide), {
      initialProps: { tree: [note("a.md")], hide: false },
    })
    const next = [note("b.md")]
    rerender({ tree: next, hide: false })
    expect(result.current.menuItems.map((i) => i.id)).toEqual(["b.md"])
    expect([...result.current.noteIds]).toEqual(["b.md"])
    rerender({ tree: next, hide: true })
    expect(result.current.menuItems[0].label).toBe("b")
  })
})
