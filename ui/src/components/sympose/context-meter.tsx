import { cn } from "@/lib/utils"
import { explanation, level, percent, type ContextFigure, type MeterLevel } from "@/lib/context-meter"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

const SIZE = 16
const STROKE = 2.5
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const COLOUR: Record<MeterLevel, string> = {
  ok: "text-fg-muted",
  warn: "text-amber-600 dark:text-amber-400",
  error: "text-destructive",
}

/**
 * The context meter (docs/decisions/044, 018): a small ring that fills as the conversation uses its prompt
 * budget, with the percentage beside it, in the composer's footer. Normal below 70%, warning from 70%, error
 * from 90%; the number is always shown so colour is never the only signal. An estimate (after a refresh or a
 * model switch) has a dashed track and a `~` in front. Hovering or focusing it shows the figures in full and
 * what they mean, the terminal's `/context`. Nothing without a figure, and it takes no room then.
 */
function ContextMeter({ figure, className }: { figure: ContextFigure | null; className?: string }) {
  if (!figure) return null
  const pct = percent(figure.used, figure.limit)
  const shown = `${figure.estimated ? "~" : ""}${pct}%`
  const lines = explanation(figure)
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <div
            role="meter"
            tabIndex={0}
            aria-label="Context used"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-valuetext={`${shown} of the context used`}
            data-slot="context-meter"
            data-level={level(pct)}
            data-estimated={figure.estimated || undefined}
            className={cn(
              "inline-flex h-5 items-center gap-1 rounded px-1 text-xs tabular-nums outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
              COLOUR[level(pct)],
              className
            )}
          />
        }
      >
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden className="-rotate-90">
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.25}
            strokeWidth={STROKE}
            strokeDasharray={figure.estimated ? "2 2" : undefined}
            data-part="track"
          />
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="currentColor"
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={`${(CIRCUMFERENCE * pct) / 100} ${CIRCUMFERENCE}`}
            data-part="fill"
          />
        </svg>
        <span>{shown}</span>
      </TooltipTrigger>
      <TooltipContent className="flex-col items-start gap-1">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </TooltipContent>
    </Tooltip>
  )
}

export { ContextMeter }
