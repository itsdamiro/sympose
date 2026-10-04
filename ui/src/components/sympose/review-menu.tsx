import * as React from "react"
import type { EditorView } from "@codemirror/view"
import type { ToolbarCustomItem } from "@damiro/stylo"

import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu"

/**
 * The review buttons (comment, accept all, decline all) as the first entries of the note's `⋯` menu, which sits among
 * the panel's floating controls. This is a stand-in: the editor toolbar wraps onto a second row when they are added to
 * it, and stylo cannot yet fold the buttons that do not fit into an overflow button (its request:
 * `2026-10-04_toolbar-overflow-menu.md`). They are the same items the toolbar would hold, so when stylo can, the items
 * go back into `toolbar.items` and this goes away. Whether an item is greyed is worked out when the menu opens, from
 * the editor's text and selection as they are then.
 */
export function useReviewMenu(items: ToolbarCustomItem[] | undefined, getView: () => EditorView | null | undefined) {
  const [off, setOff] = React.useState<ReadonlySet<string>>(new Set())
  const onOpenChange = (open: boolean) => {
    const view = getView()
    if (open && view && items) setOff(new Set(items.filter((item) => item.disabled?.(view.state)).map((item) => item.id)))
  }
  const run = (item: ToolbarCustomItem) => {
    const view = getView()
    if (view) item.run(view)
  }
  const entries =
    items && items.length > 0 ? (
      <>
        {items.map((item) => (
          <DropdownMenuItem key={item.id} disabled={off.has(item.id)} onClick={() => run(item)}>
            {item.icon}
            {item.title}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
      </>
    ) : null
  return { onOpenChange, entries }
}
