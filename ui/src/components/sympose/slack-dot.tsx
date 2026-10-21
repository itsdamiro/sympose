import { cn } from "@/lib/utils"
import { chipClass } from "@/components/sympose/model-chip"

/**
 * The persona is connected to Slack (docs/decisions/093): a green dot and the word, in the size and look of the Files chip
 * beside it. Drawn only while `sympose slack` has the persona connected, so a persona with no Slack App, or a stopped
 * command, shows nothing. It says a fact and offers nothing to press.
 */
export function SlackDot({ className }: { className?: string }) {
  return (
    <span
      data-slot="slack-dot"
      title="Connected to Slack"
      className={cn(chipClass, "gap-1.5 text-fg-muted uppercase tracking-wide", className)}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-ok" />
      Slack
    </span>
  )
}
