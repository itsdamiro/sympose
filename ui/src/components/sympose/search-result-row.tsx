import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowRight01Icon, Note01Icon, ViewOffIcon } from "@hugeicons/core-free-icons"

import type { VaultSearchResult } from "@/lib/vault-search-api"

/**
 * One row in the search results supplement (in-folder content matches, or
 * beyond-folder matches of any type) — shared so the two sections render
 * identically instead of drifting apart as separate copies. `label` is the
 * bare filename for an in-folder row, the full vault-relative path for a
 * beyond-folder one (folder context matters there, since the row isn't
 * nested under anything that already shows it).
 */
export function SearchResultRow({
  label,
  detail,
  onSelect,
  hidden = false,
  onUnhide,
  unhides,
}: {
  label: string
  detail?: React.ReactNode
  onSelect: () => void
  /** The match sits in something the user hid from view (docs/decisions/037):
   *  listed, but greyed and never opened — the way back is Unhide. */
  hidden?: boolean
  onUnhide?: () => void
  /** What Unhide takes off the list — the note's own path and/or the folders
   *  above it — shown as the button's tooltip. */
  unhides?: string[]
}) {
  if (hidden) {
    return (
      <div className="flex w-full flex-col items-start gap-0.5 py-1 opacity-70">
        <span className="flex w-full items-start gap-1.5 text-sm text-fg-muted">
          <HugeiconsIcon
            icon={ViewOffIcon}
            className="mt-0.5 size-3.5 shrink-0"
          />
          <span className="line-clamp-2 min-w-0 flex-1">{label}</span>
          <span className="shrink-0 rounded border border-border px-1 text-[10px] uppercase tracking-wide">
            Hidden
          </span>
          {onUnhide && (
            <button
              type="button"
              onClick={onUnhide}
              aria-label={`Unhide ${label}`}
              title={unhides ? `Unhides ${unhides.join(", ")}` : undefined}
              className="shrink-0 rounded px-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              Unhide
            </button>
          )}
        </span>
        {detail && (
          <span className="flex w-full min-w-0 items-center gap-1 pl-5 text-xs text-fg-muted">
            {detail}
          </span>
        )}
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={onSelect}
      className="group/result flex w-full flex-col items-start gap-0.5 py-1 text-left focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <span className="flex w-full items-start gap-1.5 text-sm text-entity/85 transition-colors group-hover/result:text-entity">
        <HugeiconsIcon
          icon={Note01Icon}
          className="mt-0.5 size-3.5 shrink-0 text-fg-muted"
        />
        <span className="line-clamp-2 min-w-0 flex-1">{label}</span>
      </span>
      {detail && (
        <span className="flex w-full min-w-0 items-center gap-1 pl-5 text-xs text-fg-muted">
          {detail}
        </span>
      )}
    </button>
  )
}

/**
 * `SearchResultRow`'s `detail` line for one match — a content match's line
 * number and snippet, separated by a chevron; any other match type's
 * snippet alone (it's already self-descriptive: `#tag` for a tag match,
 * a title-line preview for a title match — no line number applies).
 * Shared by both search-result sections so they can't drift apart into
 * two slightly different renderings of the same data.
 */
export function searchMatchDetail(r: VaultSearchResult): React.ReactNode {
  if (!r.snippet) return undefined
  if (r.match_type !== "content") {
    return <span className="truncate">{r.snippet}</span>
  }
  return (
    <>
      <span className="shrink-0">line {r.line_no}</span>
      <HugeiconsIcon icon={ArrowRight01Icon} className="size-3 shrink-0" />
      <span className="truncate">{r.snippet}</span>
    </>
  )
}
