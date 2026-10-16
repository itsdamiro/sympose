import { Cancel01Icon, Tick02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { COLOR_PRESETS, counterpart, presetFor } from "@/lib/folder-colors"
import { cn } from "@/lib/utils"

const SWATCH =
  "inline-flex size-6 items-center justify-center rounded-md ring-offset-2 ring-offset-popover transition-shadow focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-60"

/**
 * A folder's colour in the Knowledge Nebula (docs/decisions/087): a row of preset pairs, a cross for none, and a
 * colour input for each theme, labelled Light and Dark, alike. Picking either sets that theme's colour and works out
 * the matching one for the other theme (`counterpart`), so one pick is enough, from whichever side. `null` is a colour that is not
 * set. A preset sets both.
 */
export function FolderColorField({
  accent,
  accentDark,
  onChange,
  disabled = false,
}: {
  accent: string | null
  accentDark: string | null
  onChange: (next: { accent: string | null; accentDark: string | null }) => void
  disabled?: boolean
}) {
  const chosen = presetFor(accent, accentDark)
  const none = accent === null && accentDark === null
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Colour">
      <button
        type="button"
        aria-label="No colour"
        aria-pressed={none}
        title="No colour"
        disabled={disabled}
        onClick={() => onChange({ accent: null, accentDark: null })}
        className={cn(SWATCH, "border border-border text-muted-foreground", none && "ring-2 ring-foreground")}
      >
        <HugeiconsIcon icon={Cancel01Icon} className="size-3.5" />
      </button>
      {COLOR_PRESETS.map((preset) => (
        <button
          key={preset.name}
          type="button"
          aria-label={preset.name}
          aria-pressed={chosen === preset}
          title={preset.name}
          disabled={disabled}
          onClick={() => onChange({ accent: preset.light, accentDark: preset.dark })}
          style={{ background: `linear-gradient(135deg, ${preset.light} 50%, ${preset.dark} 50%)` }}
          className={cn(SWATCH, chosen === preset && "ring-2 ring-foreground")}
        >
          {chosen === preset && <HugeiconsIcon icon={Tick02Icon} className="size-3.5 text-white mix-blend-difference" />}
        </button>
      ))}
      <span className="mx-1 h-5 w-px bg-border" aria-hidden />
      {(["light", "dark"] as const).map((side) => {
        const mine = side === "light" ? accent : accentDark
        const theirs = side === "light" ? accentDark : accent
        return (
          <label key={side} className="inline-flex items-center gap-1 text-muted-foreground" title={`Pick a colour for the ${side} theme`}>
            <span className="text-xs">{side === "light" ? "Light" : "Dark"}</span>
            <input
              type="color"
              aria-label={`${side === "light" ? "Light" : "Dark"} theme colour`}
              disabled={disabled}
              value={mine ?? theirs ?? "#888888"}
              onChange={(e) => {
                const picked = e.target.value
                const matched = counterpart(picked, side)
                onChange(side === "light" ? { accent: picked, accentDark: matched } : { accent: matched, accentDark: picked })
              }}
              className={cn("size-6 cursor-pointer rounded-md border border-border bg-transparent p-0", none && "opacity-40")}
            />
          </label>
        )
      })}
    </div>
  )
}
