import * as React from "react"
import { Cancel01Icon, Tick02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"

import { searchIcons } from "@/lib/icon-search"
import { ICON_SET, iconByName } from "@/lib/persona-icons"
import { cn } from "@/lib/utils"

/**
 * An icon chosen by typing (docs/decisions/087): the field shows the icon it holds and its name; a click or typing lists the
 * icons whose name or a word people use for them matches, best first; arrow keys and Enter, or a click, choose;
 * the cross clears the choice (`null`, the folder is then drawn with its default). Escape closes the list and
 * keeps the dialog around it open. A name the icon set lacks is shown as typed with the default's drawing, so a
 * save does not drop what a note names.
 */
export function IconPicker({
  value,
  fallback,
  onChange,
  disabled = false,
  label,
}: {
  value: string | null
  /** What is drawn when nothing is chosen, so the field shows the icon the folder has now. */
  fallback: IconSvgElement
  onChange: (name: string | null) => void
  disabled?: boolean
  label: string
}) {
  const listId = React.useId()
  const [query, setQuery] = React.useState<string | null>(null) // `null` while the field shows the chosen name
  const [open, setOpen] = React.useState(false)
  const [active, setActive] = React.useState(0)
  const matches = React.useMemo(() => searchIcons(query ?? ""), [query])
  const shown = open ? matches : []
  const activeId = shown.length > 0 ? `${listId}-${shown[Math.min(active, shown.length - 1)]}` : undefined

  React.useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" })
  }, [activeId])

  const choose = (name: string) => {
    onChange(name)
    setQuery(null)
    setOpen(false)
  }
  const close = () => {
    setQuery(null)
    setOpen(false)
  }
  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      if (!open) return setOpen(true)
      const step = e.key === "ArrowDown" ? 1 : -1
      setActive((i) => (Math.min(i, matches.length - 1) + step + matches.length) % Math.max(matches.length, 1))
    } else if (e.key === "Enter" && open && shown.length > 0) {
      e.preventDefault()
      choose(shown[Math.min(active, shown.length - 1)])
    } else if (e.key === "Escape" && open) {
      e.preventDefault()
      e.stopPropagation()
      close()
    }
  }

  return (
    <div className="relative">
      <div className="flex h-9 items-center gap-2 rounded-lg border border-border bg-background px-3 transition-colors focus-within:border-brand has-disabled:opacity-60">
        <HugeiconsIcon
          icon={iconByName(value) ?? fallback}
          className={cn("size-4 shrink-0", value === null && "text-muted-foreground")}
        />
        <input
          role="combobox"
          aria-label={label}
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={activeId}
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          value={query ?? value ?? ""}
          placeholder="Search icons, like film or travel"
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
            setOpen(true)
          }}
          // Not on focus: a dialog focuses its first field when it opens, and a list over the rest would greet the person.
          onClick={() => {
            setOpen(true)
            setActive(Math.max(0, matches.indexOf(value ?? "")))
          }}
          onBlur={close}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        {value !== null && (
          <button
            type="button"
            aria-label="Clear the icon"
            title="Clear the icon"
            disabled={disabled}
            // Keep focus in the field, so clearing does not also fire the blur that closes the list.
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              onChange(null)
              close()
            }}
            className="inline-flex size-5 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <HugeiconsIcon icon={Cancel01Icon} className="size-3.5" />
          </button>
        )}
      </div>
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label={`${label} matches`}
          data-slot="popover-content"
          // Anything pressed in the list, its scrollbar and gaps included, keeps the field focused.
          onMouseDown={(e) => e.preventDefault()}
          className="absolute inset-x-0 top-full z-20 mt-1 max-h-52 overflow-y-auto rounded-lg p-1 shadow-2xl ring-1 ring-foreground/5 dark:ring-foreground/10"
        >
          {shown.length === 0 && <li className="px-3 py-2 text-xs text-muted-foreground">No icon matches</li>}
          {shown.map((name, i) => (
            <li
              key={name}
              id={`${listId}-${name}`}
              role="option"
              aria-selected={i === Math.min(active, shown.length - 1)}
              // Pressing an option must not blur the field, or the list would close before the click lands.
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(name)}
              className="flex cursor-default items-center gap-2.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground aria-selected:bg-accent aria-selected:text-accent-foreground"
            >
              <HugeiconsIcon icon={ICON_SET[name]} className="size-4 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{name}</span>
              {name === value && <HugeiconsIcon icon={Tick02Icon} className="size-3.5 shrink-0" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
