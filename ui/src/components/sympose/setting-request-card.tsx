import * as React from "react"
import { ArrowRight02Icon, Cancel01Icon, Tick02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import type { RequestState, SettingRequest } from "@/lib/confirmations-api"
import { Button } from "@/components/ui/button"
import { ControlRow } from "@/components/sympose/control-section"

interface SettingRequestCardProps extends Omit<React.ComponentProps<"div">, "onAnswer"> {
  request: SettingRequest
  /** Accept or decline; resolves to an error text (the backend's reason, such as a number the setting does not take), or `null` when it went through. */
  onAnswer: (accept: boolean) => Promise<string | null>
}

const OUTCOMES: Record<Exclude<RequestState, "waiting">, string> = {
  accepted: "Changed",
  declined: "Declined",
  replaced: "Replaced by a newer proposal",
  outdated: "No longer possible",
}

/**
 * A persona's request to change one setting (docs/decisions/080), on the same card as a request for a new persona
 * (docs/decisions/078) and made of the same parts: the Settings page's row (what it is, a line on what it does, the change
 * as from and to), a line where the consequence is not in the change itself, and Decline and Accept. Nothing changes until
 * Accept; a value the setting refuses comes back as the reason and the card keeps waiting.
 */
function SettingRequestCard({ className, request, onAnswer, ...props }: SettingRequestCardProps) {
  const { setting } = request
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const waiting = request.state === "waiting"

  const send = async (accept: boolean) => {
    setBusy(true)
    setError(await onAnswer(accept))
    setBusy(false)
  }

  return (
    <div
      data-slot="setting-request-card"
      data-state={request.state}
      className={cn("flex flex-col gap-3 rounded-lg border border-border bg-panel p-4 text-xs text-fg-muted", !waiting && "opacity-80", className)}
      {...props}
    >
      <ControlRow label={setting.label} hint={setting.summary ? <p>{setting.summary}</p> : undefined}>
        <span className="flex items-center gap-1.5 font-mono tabular-nums text-foreground" aria-label={`From ${setting.from} to ${setting.to}`}>
          {setting.from}
          <HugeiconsIcon icon={ArrowRight02Icon} className="size-3.5 text-fg-muted" aria-hidden />
          {setting.to}
        </span>
      </ControlRow>
      {waiting && setting.note && <p>{setting.note}</p>}
      {!waiting ? (
        <p className="flex items-center gap-1.5">
          <HugeiconsIcon icon={request.state === "accepted" ? Tick02Icon : Cancel01Icon} className="size-3.5" aria-hidden />
          {OUTCOMES[request.state as Exclude<RequestState, "waiting">]}
        </p>
      ) : (
        <>
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
          <div className="flex items-center justify-end gap-2">
            <Button type="button" variant="outline" disabled={busy} onClick={() => void send(false)}>
              Decline
            </Button>
            <Button type="button" disabled={busy} onClick={() => void send(true)}>
              Accept
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

export { SettingRequestCard }
