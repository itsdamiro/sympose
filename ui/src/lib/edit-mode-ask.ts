import { confirm } from "@/lib/confirm-store"
import type { EditModeId } from "@/lib/edit-mode-api"
import { notify } from "@/lib/notify"
import { getNotificationPreferences } from "@/lib/use-notification-preferences"

const ASKS: Partial<Record<EditModeId, { persona: (name: string) => string; global: string; confirmLabel: string }>> = {
  accept: {
    persona: (name) => `Let ${name} apply her edits in the editor?`,
    global: "Let the personas that follow this setting apply their edits in the editor?",
    confirmLabel: "Use Accept edits",
  },
  auto: {
    persona: (name) => `Let ${name} act on her own initiative?`,
    global: "Let the personas that follow this setting act on their own initiative?",
    confirmLabel: "Use Auto",
  },
}

/**
 * Choosing `accept` or `auto` (docs/decisions/072) first shows the note about the model, in the way the user's
 * Notifications settings say a question is asked (the dialog, or the one-line form); with confirmations set to none the
 * choice is applied at once and the same note is shown as a notice, so the figures are never silently skipped. `who` is
 * the persona's name, or `null` for the global setting. Any other mode, or no note to show, is applied at once.
 * `apply` saves and says whether it did.
 */
export function askBeforeEditMode({
  mode,
  who,
  note,
  apply,
}: {
  mode: EditModeId | null
  who: string | null
  note: string | null | undefined
  apply: () => Promise<boolean>
}): void {
  const ask = mode ? ASKS[mode] : undefined
  if (!ask || !note) return void apply()
  if (getNotificationPreferences().confirm === "none") {
    void apply().then((ok) => ok && notify.warning(note, { duration: 12000 }))
    return
  }
  confirm({
    message: who === null ? ask.global : ask.persona(who),
    description: note,
    confirmLabel: ask.confirmLabel,
    tone: "default",
    onConfirm: () => void apply(),
  })
}
