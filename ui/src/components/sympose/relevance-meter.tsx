/**
 * A slim meter and its percentage, the strength of a relation between two notes (docs/decisions/066). It is a reading
 * of strength (the bottom is the chosen level's bar, the top a strong match), never a probability, so the label says
 * "relevance" and not "chance". Drawn in the entity colour over the track of a hairline, from tokens only.
 */
export function RelevanceMeter({ percent }: { percent: number }) {
  const value = Math.max(0, Math.min(100, Math.round(percent)))
  return (
    <span
      role="meter"
      aria-label="Relevance"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      className="ml-auto flex shrink-0 items-center gap-1.5 pl-2 text-[11px] text-fg-muted tabular-nums"
    >
      <span className="h-1 w-10 overflow-hidden rounded-full bg-border">
        <span className="block h-full rounded-full bg-entity" style={{ width: `${value}%` }} />
      </span>
      <span className="w-7 text-right">{value}%</span>
    </span>
  )
}
