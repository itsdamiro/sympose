import { cn } from "@/lib/utils"
import type { SharingState } from "@/lib/sharing-api"

/**
 * The standing notice while the persona's model is a cloud one (docs/decisions/031, 044): what always goes to
 * it (the messages and the conversation) and, one switch per category, what may go from the user's vault.
 * Everything starts off; it is on screen before the first message is written, which is what lets the web chat
 * talk to a cloud model at all. A local model shows nothing: nothing leaves the machine.
 */
function CloudNotice({
  state,
  onChange,
  className,
}: {
  state: SharingState | null
  onChange: (category: string, shared: boolean) => void
  className?: string
}) {
  if (!state?.cloud) return null
  const allowed = state.categories.filter((c) => c.shared)
  return (
    <div
      role="region"
      aria-label="Cloud model"
      data-slot="cloud-notice"
      className={cn("mb-3 rounded-lg border border-border bg-muted/40 px-3 py-2.5 text-xs text-fg-muted", className)}
    >
      <p>
        <span className="font-medium text-foreground">{state.model}</span> is a cloud model: it receives your messages and
        this conversation.{" "}
        {allowed.length > 0
          ? "From your vault it may also receive what is switched on below."
          : "Nothing from your vault is sent until you switch a kind on below."}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {state.categories.map((c) => (
          <button
            key={c.name}
            type="button"
            aria-pressed={c.shared}
            title={c.description}
            onClick={() => onChange(c.name, !c.shared)}
            className={cn(
              "rounded-full border px-2.5 py-0.5 transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
              c.shared
                ? "border-brand bg-brand/10 text-foreground"
                : "border-border text-fg-muted hover:bg-accent hover:text-foreground"
            )}
          >
            {c.name}
          </button>
        ))}
      </div>
    </div>
  )
}

export { CloudNotice }
