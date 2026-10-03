import { HugeiconsIcon } from "@hugeicons/react"
import { ViewIcon, ViewOffIcon } from "@hugeicons/core-free-icons"

import { EmptyState } from "@/components/sympose/empty-state"
import { ControlRow, ControlSection } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"

/**
 * Settings → Hidden from view (docs/decisions/037). What the user hid with
 * "Hide from view" on a folder or note, each with an Unhide action, and the
 * switch that lists folder definition notes in the tree. Says plainly that
 * hiding is for the view only, so nobody takes it for privacy: the persona
 * can still read what is hidden here. The list is kept in the settings file,
 * per vault.
 */
function HiddenSection({
  hidden,
  showDefinitionNotes,
  onUnhide,
  onShowDefinitionNotes,
}: {
  /** Vault-relative paths the user hid, in the order to list them. */
  hidden: string[]
  showDefinitionNotes: boolean
  onUnhide: (path: string) => void
  onShowDefinitionNotes: (show: boolean) => void
}) {
  return (
    <ControlSection title="Hidden from view">
      <p className="text-xs text-fg-muted">
        Hidden from view only; the persona can still read them. A hidden note
        is not listed or opened here, but search still finds it.
      </p>
      {hidden.length === 0 ? (
        <EmptyState
          compact
          icon={ViewOffIcon}
          title="Nothing is hidden"
          description="Right-click a folder or note and choose “Hide from view”."
        />
      ) : (
        <ul className="flex flex-col gap-0.5" aria-label="Hidden folders and notes">
          {hidden.map((path) => (
            <li
              key={path}
              className="flex items-center justify-between gap-2 py-0.5 text-sm"
            >
              <span className="min-w-0 truncate font-mono text-xs" title={path}>
                {path}
              </span>
              <button
                type="button"
                onClick={() => onUnhide(path)}
                aria-label={`Unhide ${path}`}
                className="flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <HugeiconsIcon icon={ViewIcon} className="size-3.5" />
                Unhide
              </button>
            </li>
          ))}
        </ul>
      )}
      <ControlRow label="Folder definition notes">
        <SegmentedControl
          size="sm"
          aria-label="Show folder definition notes"
          value={showDefinitionNotes ? "shown" : "hidden"}
          onValueChange={(v) => onShowDefinitionNotes(v === "shown")}
          options={[
            { value: "hidden", label: "Hidden" },
            { value: "shown", label: "Shown" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        A definition note (<code>Folder/Folder.md</code>) says what a folder is
        for. Hidden, it is left out of the tree; the persona still reads it.
      </p>
    </ControlSection>
  )
}

export { HiddenSection }
