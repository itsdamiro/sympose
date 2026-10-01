import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  ArrowLeft01Icon,
  ArrowRight01Icon,
  Cancel01Icon,
  FolderAddIcon,
  Search01Icon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { CreateKind } from "@/lib/use-create-flow"

/**
 * The content panel's toolbar, pinned to its top edge through `<ContentPanel
 * header>` and mirroring the editor toolbar's chrome rather than sitting inline
 * with the section title. Shown on every section (vault folders, Bin, Settings,
 * Persona) so back and forward always work; new note and new folder only make
 * sense on an actual vault folder, so that group is dropped on the sentinel
 * sections (`isSentinel`) instead of rendering disabled, inert buttons.
 *
 * Search, new note and new folder are icon-toggled fields that slide open and
 * auto-hide on blur; what they hold, and what they do, lives in `useVaultSearch`
 * and `useCreateField` / `useCreateSubmit`.
 */
export function ContentToolbar({
  canGoBack,
  canGoForward,
  goBack,
  goForward,
  searchOpen,
  setSearchOpen,
  vaultSearch,
  setVaultSearch,
  closeSearch,
  searchInputRef,
  isSentinel,
  pendingCreate,
  createName,
  setCreateName,
  creating,
  closeCreate,
  toggleCreate,
  submitCreate,
  noteInputRef,
  folderInputRef,
}: {
  canGoBack: boolean
  canGoForward: boolean
  goBack: () => void
  goForward: () => void
  searchOpen: boolean
  setSearchOpen: (open: boolean) => void
  vaultSearch: string
  setVaultSearch: (value: string) => void
  closeSearch: () => void
  searchInputRef: React.RefObject<HTMLInputElement | null>
  isSentinel: boolean
  pendingCreate: CreateKind | null
  createName: string
  setCreateName: (value: string) => void
  creating: boolean
  closeCreate: () => void
  toggleCreate: (kind: CreateKind) => void
  submitCreate: () => Promise<void>
  noteInputRef: React.RefObject<HTMLInputElement | null>
  folderInputRef: React.RefObject<HTMLInputElement | null>
}) {
  return (
    <div className="flex items-center justify-between gap-1">
      <div className="flex items-center gap-0.5">
        <button
          type="button"
          onClick={goBack}
          disabled={!canGoBack}
          aria-label="Back"
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
        >
          <HugeiconsIcon icon={ArrowLeft01Icon} className="size-4" />
        </button>
        <button
          type="button"
          onClick={goForward}
          disabled={!canGoForward}
          aria-label="Forward"
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
        >
          <HugeiconsIcon icon={ArrowRight01Icon} className="size-4" />
        </button>
      </div>
      <div className="flex items-center gap-0.5">
        <div
          className={cn(
            // `h-7` on the wrapper (not just the input) is load-bearing: `w-0`
            // only clips width, so an unconstrained-height input still pushes
            // the whole toolbar row taller by its own natural line-height even
            // while invisibly zero-width. Fixing the wrapper's height to match
            // the buttons keeps the row at their 28px regardless.
            "h-7 overflow-hidden rounded-[calc(var(--radius-md)-3px)] transition-[width] duration-snappy ease-snappy",
            searchOpen ? "w-40" : "w-0"
          )}
        >
          <div className="relative h-7 w-full">
            <input
              ref={searchInputRef}
              type="text"
              value={vaultSearch}
              onChange={(e) => setVaultSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") closeSearch()
              }}
              // A blur while the field still holds a query keeps it open —
              // otherwise focusing the results below (or anything else) would
              // wipe the query out from under the list it's filtering.
              // Empty-field blur still auto-hides, same as new note/folder.
              onBlur={() => {
                if (!vaultSearch) closeSearch()
              }}
              placeholder="Search vault"
              aria-label="Search vault"
              tabIndex={searchOpen ? 0 : -1}
              // Sized off stylo's own `.stylo-search-field` (the find/replace
              // input this was modeled on): `radius-md - 3px`, not the toolbar's
              // plain `rounded-md`, and its 11px `font-size` (sympose's own
              // override of stylo's field, see index.css) — matching `text-sm`
              // here read visibly larger and rounder than that reference field.
              // New note/folder share this exact styling for visual parity.
              className="h-7 w-full rounded-[calc(var(--radius-md)-3px)] border border-border bg-background py-1 pr-6 pl-2 text-[0.6875rem] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            />
            {vaultSearch && (
              <button
                type="button"
                // Runs before the input's blur, so the clear can't be read as
                // "field went empty because it lost focus" and re-hide it.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setVaultSearch("")
                  searchInputRef.current?.focus()
                }}
                aria-label="Clear search"
                className="absolute top-1/2 right-1.5 grid size-3.5 -translate-y-1/2 place-items-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
              >
                <HugeiconsIcon icon={Cancel01Icon} className="size-3" />
              </button>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            if (searchOpen) closeSearch()
            else setSearchOpen(true)
          }}
          aria-label="Search vault"
          aria-pressed={searchOpen}
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground aria-pressed:text-foreground"
        >
          <HugeiconsIcon icon={Search01Icon} className="size-4" />
        </button>
        {!isSentinel && (
          <>
            <div
              className={cn(
                "h-7 overflow-hidden rounded-[calc(var(--radius-md)-3px)] transition-[width] duration-snappy ease-snappy",
                pendingCreate === "note" ? "w-40" : "w-0"
              )}
            >
              <input
                ref={noteInputRef}
                value={pendingCreate === "note" ? createName : ""}
                disabled={creating}
                onChange={(e) => setCreateName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submitCreate()
                  else if (e.key === "Escape") closeCreate()
                }}
                onBlur={closeCreate}
                placeholder="Filename"
                aria-label="New note filename"
                tabIndex={pendingCreate === "note" ? 0 : -1}
                className="h-7 w-full rounded-[calc(var(--radius-md)-3px)] border border-border bg-background px-2 text-[0.6875rem] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
              />
            </div>
            <button
              type="button"
              onClick={() => toggleCreate("note")}
              aria-label="New note"
              aria-pressed={pendingCreate === "note"}
              className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground aria-pressed:text-foreground"
            >
              <HugeiconsIcon icon={Add01Icon} className="size-4" />
            </button>
            <div
              className={cn(
                "h-7 overflow-hidden rounded-[calc(var(--radius-md)-3px)] transition-[width] duration-snappy ease-snappy",
                pendingCreate === "folder" ? "w-40" : "w-0"
              )}
            >
              <input
                ref={folderInputRef}
                value={pendingCreate === "folder" ? createName : ""}
                disabled={creating}
                onChange={(e) => setCreateName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submitCreate()
                  else if (e.key === "Escape") closeCreate()
                }}
                onBlur={closeCreate}
                placeholder="Folder name"
                aria-label="New folder name"
                tabIndex={pendingCreate === "folder" ? 0 : -1}
                className="h-7 w-full rounded-[calc(var(--radius-md)-3px)] border border-border bg-background px-2 text-[0.6875rem] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
              />
            </div>
            <button
              type="button"
              onClick={() => toggleCreate("folder")}
              aria-label="New folder"
              aria-pressed={pendingCreate === "folder"}
              className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground aria-pressed:text-foreground"
            >
              <HugeiconsIcon icon={FolderAddIcon} className="size-4" />
            </button>
          </>
        )}
      </div>
    </div>
  )
}
