import * as React from "react"
import { toast } from "sonner"
import { HugeiconsIcon } from "@hugeicons/react"
import { FolderCheckIcon, Loading03Icon, StethoscopeIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { notify } from "@/lib/notify"
import { fetchDoctor, fetchHealth, fixable, fixDoctor, leftOver } from "@/lib/checks-api"
import { ChecksDialog, type CheckDialogState } from "./checks-dialog"

const PILL =
  "inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-60"

type Running = "doctor" | "health" | "fix" | null

// A result the person asked for with a click is shown whatever the Notifications preference says: with it
// dropped, a click would look like nothing happened.
const say = (message: string) => toast.success(message)

/**
 * The Settings footer's two check pills, "Doctor" and "Vault health" (docs/decisions/063). Nothing runs until a
 * pill is clicked. A clean result is a notification; a finding opens a dialog, where the doctor offers Fix or
 * Decline and the vault health Close; an offer to add a folder's icon has its own Add button (ADR 064), and
 * `onChanged` says a note was changed.
 */
export function SettingsChecks({ className, onChanged }: { className?: string; onChanged?: () => void }) {
  const [running, setRunning] = React.useState<Running>(null)
  const [dialog, setDialog] = React.useState<CheckDialogState | null>(null)

  const checkDoctor = async () => {
    setRunning("doctor")
    const result = await fetchDoctor()
    setRunning(null)
    if (!result.ok) return notify.error(`Setup check: ${result.error}`)
    if (result.report.findings.length === 0) return say("Setup check: everything looks fine.")
    setDialog({ kind: "doctor", report: result.report })
  }

  const checkHealth = async () => {
    setRunning("health")
    const result = await fetchHealth()
    setRunning(null)
    if (!result.ok) return notify.error(`Notes check: ${result.error}`)
    const offered = result.report.checks.some((c) => c.findings.some((f) => f.adds.length > 0))
    if (result.report.problems === 0 && !offered) return say(`Notes check: no problems in ${result.report.notes} notes.`)
    setDialog({ kind: "health", report: result.report })
  }

  const fix = async () => {
    setRunning("fix")
    const result = await fixDoctor()
    setRunning(null)
    if (!result.ok) return notify.error(`Setup check: ${result.error}`)
    if (leftOver(result.report).length === 0) {
      setDialog(null)
      return say(`Fixed ${result.report.findings.length} ${result.report.findings.length === 1 ? "problem" : "problems"}.`)
    }
    setDialog({ kind: "doctor", report: result.report })
  }

  const busy = running !== null
  const pill = (kind: "doctor" | "health", label: string, icon: typeof StethoscopeIcon, onClick: () => void) => (
    <button
      type="button"
      data-slot={`${kind}-pill`}
      disabled={busy}
      onClick={onClick}
      title={kind === "doctor" ? "Check that Sympose is set up correctly" : "Check the notes"}
      className={PILL}
    >
      <HugeiconsIcon icon={running === kind ? Loading03Icon : icon} className={cn("size-3.5", running === kind && "animate-spin")} />
      {label}
    </button>
  )

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {pill("doctor", "Setup check", StethoscopeIcon, () => void checkDoctor())}
      {pill("health", "Notes check", FolderCheckIcon, () => void checkHealth())}
      <ChecksDialog
        state={dialog}
        fixing={running === "fix"}
        fixableCount={dialog?.kind === "doctor" ? fixable(dialog.report).length : 0}
        onFix={() => void fix()}
        onClose={() => setDialog(null)}
        onChanged={() => onChanged?.()}
      />
    </div>
  )
}
