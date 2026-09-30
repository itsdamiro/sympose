import { cn } from "@/lib/utils"
import type { SentRecord } from "@/lib/chat-types"

/**
 * What a cloud model's reply was and was not given from the user's vault (docs/decisions/031): "Sent: notes,
 * recaps · Held back: properties". Read from the reply's own record, so a resumed conversation shows it too.
 * Nothing for a local reply, or a cloud one that involved nothing of the vault.
 */
function CloudSent({ sent, className }: { sent: SentRecord | null | undefined; className?: string }) {
  const parts = (
    [
      ["Sent", sent?.cloud],
      ["Held back", sent?.withheld],
    ] as const
  ).filter(([, names]) => names && names.length > 0)
  if (parts.length === 0) return null
  return (
    <p data-slot="cloud-sent" className={cn("pt-0.5 text-xs text-fg-muted", className)}>
      {parts.map(([label, names]) => `${label}: ${names?.join(", ")}`).join(" · ")}
    </p>
  )
}

export { CloudSent }
