import { confirm } from "@/lib/confirm-store"
import { getUnsavedGuard } from "@/lib/unsaved-guard"

/**
 * Changing the vault closes the note in the editor, and a save after the change would land on the same path in
 * the other vault. So when the note has unsaved edits, ask first (ADR 004, amendment of 2026-10-01): "Save and
 * switch" saves to the vault still active, then runs `proceed`; "Stay" does nothing. Returns `true` when it asked
 * (the caller stops, and `proceed` runs later), `false` when there was nothing to ask.
 */
export function askToSaveFirst(proceed: () => void): boolean {
  const guard = getUnsavedGuard()
  if (!guard?.isDirty()) return false
  confirm({
    message: `Save your changes to "${guard.name()}" first?`,
    description: "Switching vaults closes this note. Its unsaved changes are saved to the current vault before you switch.",
    confirmLabel: "Save and switch",
    cancelLabel: "Stay",
    tone: "default",
    onConfirm: async () => {
      if (!(await guard.save())) return // the editor says why; the vault stays as it is
      proceed()
    },
  })
  return true
}
