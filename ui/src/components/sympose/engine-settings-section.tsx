import * as React from "react"
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react"

import { ControlRow, ControlSection } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { notify } from "@/lib/notify"
import type { EngineSetting } from "@/lib/settings-api"
import { useEngineSettings } from "@/lib/use-engine-settings"

type Change = (key: string, value: boolean | string | number | null) => Promise<boolean>

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)
const label = (s: EngineSetting) => capital(s.summary)

/** A number typed in, saved on Enter or when the field is left; empty puts it back to its default. */
function NumberField({ setting, change }: { setting: EngineSetting; change: Change }) {
  const [draft, setDraft] = React.useState<string | null>(null)
  const shown = setting.value === null ? "" : String(setting.value)
  const text = draft ?? shown

  const commit = async () => {
    const wanted = (draft ?? shown).trim()
    setDraft(null)
    if (wanted === shown) return
    const value = wanted === "" ? null : Number(wanted)
    if (value !== null && !Number.isFinite(value)) {
      notify.error(`Enter a number. ${setting.hint}`)
      return
    }
    await change(setting.key, value)
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        inputMode="decimal"
        aria-label={label(setting)}
        value={text}
        placeholder={setting.default === null ? "automatic" : String(setting.default)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void commit()}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur()
          if (e.key === "Escape") setDraft(null)
        }}
        className="h-7 w-24 rounded-md border border-input bg-transparent px-2 text-right text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      />
      {!setting.isDefault && (
        <button
          type="button"
          aria-label={`Reset ${label(setting)}`}
          onClick={() => void change(setting.key, null)}
          className="rounded-md px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          Reset
        </button>
      )}
    </div>
  )
}

function Control({ setting, change }: { setting: EngineSetting; change: Change }) {
  if (setting.kind === "number") return <NumberField setting={setting} change={change} />
  if (setting.kind === "toggle") {
    return (
      <SegmentedControl
        size="sm"
        aria-label={label(setting)}
        value={setting.value ? "on" : "off"}
        onValueChange={(v) => void change(setting.key, v === "on")}
        options={[
          { value: "on", label: "On" },
          { value: "off", label: "Off" },
        ]}
      />
    )
  }
  if (setting.choices.length <= 3) {
    return (
      <SegmentedControl
        size="sm"
        aria-label={label(setting)}
        value={String(setting.value)}
        onValueChange={(v) => void change(setting.key, v)}
        options={setting.choices.map((c) => ({ value: c, label: capital(c) }))}
      />
    )
  }
  return (
    <Select value={String(setting.value)} onValueChange={(v) => void change(setting.key, v as string)}>
      <SelectTrigger size="sm" className="w-40" aria-label={label(setting)}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {setting.choices.map((c) => (
          <SelectItem key={c} value={c}>
            {c}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function SettingRow({ setting, change }: { setting: EngineSetting; change: Change }) {
  return (
    <ControlRow
      label={label(setting)}
      keywords={setting.hint}
      hint={setting.kind === "number" && setting.hint ? <p className="text-xs text-fg-muted">{setting.hint}</p> : undefined}
    >
      <Control setting={setting} change={change} />
    </ControlRow>
  )
}

/** Rows of the page's own drawn first in a group, with some of the group's settings placed inside them
 *  (`keys`, given to `render` by key) instead of in the list below: a setting sits next to the switch it depends on. */
type Lead = { keys: string[]; render: (placed: Record<string, React.ReactNode>) => React.ReactNode }

/**
 * Settings → the engine settings, one section per group (docs/decisions/044, 097). The same list the terminal's
 * `/settings` shows, described by the backend, which also decides what a value may be: this only draws each
 * row as a switch, a set of choices or a number field, and shows the reason when a value is refused. The page adds
 * its own rows to a group by its name: `leads` before the settings (the cloud permissions, with `web_access` placed
 * among them) and `extras` after them (the skills and the jobs, which belong to the persona that is open); they are
 * drawn in a section of their own when the settings cannot be loaded. `icons` and `open` (the sections open on first
 * sight) are by group name too.
 */
function EngineSettingsSections({
  extras = {},
  leads = {},
  icons = {},
  open = [],
}: {
  extras?: Record<string, React.ReactNode>
  leads?: Record<string, Lead>
  icons?: Record<string, IconSvgElement>
  open?: string[]
}) {
  const { state, change } = useEngineSettings()
  const iconFor = (name: string) => (icons[name] ? <HugeiconsIcon icon={icons[name]} /> : undefined)

  if (state.status === "loading") return null
  if (state.status === "error") {
    const names = [...new Set([...Object.keys(leads), ...Object.keys(extras)])]
    return (
      <>
        <ControlSection title="Advanced" defaultOpen>
          <p className="text-sm text-fg-muted">
            Couldn&apos;t load these: {state.error}.
          </p>
        </ControlSection>
        {names.map((name) => (
          <ControlSection key={name} title={name} icon={iconFor(name)}>
            {leads[name]?.render({})}
            {extras[name]}
          </ControlSection>
        ))}
      </>
    )
  }
  return (
    <>
      {state.groups.map((group) => {
        const lead = leads[group.name]
        const placed = Object.fromEntries(
          group.settings.filter((s) => lead?.keys.includes(s.key)).map((s) => [s.key, <SettingRow key={s.key} setting={s} change={change} />])
        )
        return (
          <ControlSection key={group.name} title={group.name} icon={iconFor(group.name)} defaultOpen={open.includes(group.name)}>
            {lead?.render(placed)}
            {group.settings
              .filter((s) => !(s.key in placed))
              .map((s) => (
                <SettingRow key={s.key} setting={s} change={change} />
              ))}
            {extras[group.name]}
          </ControlSection>
        )
      })}
    </>
  )
}

export { EngineSettingsSections }
