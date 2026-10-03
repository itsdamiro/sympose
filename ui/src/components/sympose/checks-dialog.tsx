import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { addFolderIcon, type DoctorReport, type HealthReport } from "@/lib/checks-api"

export type CheckDialogState =
  | { kind: "doctor"; report: DoctorReport }
  | { kind: "health"; report: HealthReport }

const STATE_NOTE: Record<string, string> = {
  fixable: "Fix would",
  fixed: "Fixed",
  failed: "Could not fix",
  needs_you: "Needs you: nothing here can be fixed automatically",
}

function DoctorBody({ report }: { report: DoctorReport }) {
  return (
    <div className="space-y-3 text-sm">
      <ul className="space-y-0.5 text-xs text-muted-foreground">
        {report.models.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <ul className="space-y-2">
        {report.findings.map((f) => (
          <li key={f.problem} className="rounded-lg border border-border px-3 py-2">
            <p>{f.problem}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {f.state === "needs_you" ? STATE_NOTE.needs_you : `${STATE_NOTE[f.state]}: ${f.error || f.fix}`}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}

function HealthBody({ report, onChanged }: { report: HealthReport; onChanged: () => void }) {
  const [added, setAdded] = React.useState<Set<string>>(new Set())
  const [failed, setFailed] = React.useState<Record<string, string>>({})
  const [busy, setBusy] = React.useState<string | null>(null)

  // The one fix the health has (docs/decisions/064): a click on one folder's offer writes that folder's note.
  const add = async (folder: string) => {
    setBusy(folder)
    const result = await addFolderIcon(folder)
    setBusy(null)
    if (!result.ok) return setFailed((prev) => ({ ...prev, [folder]: result.error }))
    setFailed((prev) => Object.fromEntries(Object.entries(prev).filter(([name]) => name !== folder)))
    setAdded((prev) => new Set(prev).add(folder))
    onChanged()
  }

  return (
    <div className="space-y-3 text-sm">
      {report.checks.map((check) => (
        <section key={check.heading}>
          <h3 className="font-medium">
            {check.heading} ({check.findings.length})
          </h3>
          <ul className="mt-1 space-y-1">
            {check.findings.map((f) => (
              <li key={`${f.note}:${f.message}`} className="flex items-start justify-between gap-3 text-xs text-muted-foreground">
                <span>
                  <span className="text-foreground">{f.note}</span>: {f.message}
                  {failed[f.folder] && <span className="block text-destructive">{failed[f.folder]}</span>}
                </span>
                {f.adds.length > 0 &&
                  (added.has(f.folder) ? (
                    <span className="shrink-0">Added</span>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="shrink-0"
                      disabled={busy !== null}
                      onClick={() => void add(f.folder)}
                    >
                      Add
                    </Button>
                  ))}
              </li>
            ))}
          </ul>
        </section>
      ))}
      <p className="text-xs text-muted-foreground">{report.limits}</p>
    </div>
  )
}

/**
 * The findings of a Settings footer check (docs/decisions/063). It opens only when something needs a look: the
 * doctor offers Fix (only while something is fixable) and Decline, the vault health has Close and, on an offer to
 * add a folder's icon, an Add button for that folder alone (docs/decisions/064).
 */
export function ChecksDialog({
  state,
  fixing,
  fixableCount,
  onFix,
  onClose,
  onChanged,
}: {
  state: CheckDialogState | null
  fixing: boolean
  fixableCount: number
  onFix: () => void
  onClose: () => void
  /** A note was changed by an offer: the vault is read again. */
  onChanged: () => void
}) {
  const doctor = state?.kind === "doctor"
  return (
    <Dialog open={state !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {state && (
          <>
            <DialogHeader>
              <DialogTitle>{doctor ? "Doctor" : "Vault health"}</DialogTitle>
              <DialogDescription>
                {state.kind === "doctor"
                  ? "Fix corrects Sympose's own persona folders and settings file, never your notes."
                  : `${state.report.notes} notes read as ${state.report.persona}. Nothing is changed unless you press Add on an offer.`}
              </DialogDescription>
            </DialogHeader>
            <div className="max-h-[60vh] overflow-y-auto">
              {state.kind === "doctor" ? <DoctorBody report={state.report} /> : <HealthBody report={state.report} onChanged={onChanged} />}
            </div>
            <DialogFooter>
              {doctor && fixableCount > 0 ? (
                <>
                  <DialogClose render={<Button type="button" variant="outline" disabled={fixing} />}>Decline</DialogClose>
                  <Button type="button" disabled={fixing} onClick={onFix}>
                    Fix
                  </Button>
                </>
              ) : (
                <DialogClose render={<Button type="button" variant="outline" />}>Close</DialogClose>
              )}
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
