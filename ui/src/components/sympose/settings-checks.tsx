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
 * Decline and the vault health only Close.
 */
export function SettingsChecks({ className }: { className?: string }) {
  const [running, setRunning] = React.useState<Running>(null)
  const [dialog, setDialog] = React.useState<CheckDialogState | null>(null)

  const checkDoctor = async () => {
    setRunning("doctor")
    const result = await fetchDoctor()
    setRunning(null)
    if (!result.ok) return notify.error(`Doctor: ${result.error}`)
    if (result.report.findings.length === 0) return say("Doctor: everything looks healthy.")
    setDialog({ kind: "doctor", report: result.report })
  }

  const checkHealth = async () => {
    setRunning("health")
    const result = await fetchHealth()
    setRunning(null)
    if (!result.ok) return notify.error(`Vault health: ${result.error}`)
    if (result.report.problems === 0) return say(`Vault health: nothing wrong in ${result.report.notes} notes.`)
    setDialog({ kind: "health", report: result.report })
  }

  const fix = async () => {
    setRunning("fix")
    const result = await fixDoctor()
    setRunning(null)
    if (!result.ok) return notify.error(`Doctor: ${result.error}`)
    if (leftOver(result.report).length === 0) {
      setDialog(null)
      return say(`Doctor: fixed ${result.report.findings.length} problem(s).`)
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
      title={kind === "doctor" ? "Check the installation" : "Check the notes"}
      className={PILL}
    >
      <HugeiconsIcon icon={running === kind ? Loading03Icon : icon} className={cn("size-3.5", running === kind && "animate-spin")} />
      {label}
    </button>
  )

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {pill("doctor", "Doctor", StethoscopeIcon, () => void checkDoctor())}
      {pill("health", "Vault health", FolderCheckIcon, () => void checkHealth())}
      <ChecksDialog
        state={dialog}
        fixing={running === "fix"}
        fixableCount={dialog?.kind === "doctor" ? fixable(dialog.report).length : 0}
        onFix={() => void fix()}
        onClose={() => setDialog(null)}
      />
    </div>
  )
}
