import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Add01Icon, ViewIcon } from "@hugeicons/core-free-icons"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ControlRow } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import { notify } from "@/lib/notify"
import { readSkill, type Skill, type SkillText } from "@/lib/skills-api"
import { useSkills } from "@/lib/use-skills"

/** What a skill's `tools:` names mean for the persona, in the user's words. */
const NEEDS: Record<string, string> = {
  propose_note: "propose new notes",
  propose_edit: "propose changes to a note",
  comment_on: "comment on a note",
  show_note: "show a note",
  search_notes: "look in your notes",
  open_note: "look in your notes",
  find_notes: "look in your notes",
  list_notes: "look in your notes",
  tool_calls: "use a model that can call tools",
}

const needs = (tools: string[]) => [...new Set(tools.map((t) => NEEDS[t] ?? t))].join(", ")

function Review({
  persona,
  skill,
  onClose,
  onSwitch,
}: {
  persona: string
  skill: Skill
  onClose: () => void
  onSwitch: (enabled: boolean) => Promise<boolean>
}) {
  const [read, setRead] = React.useState<SkillText | { error: string } | null>(null)
  const [busy, setBusy] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    void readSkill(persona, skill.name).then((r) => {
      if (!cancelled) setRead(r.ok ? r.skill : { error: r.error })
    })
    return () => {
      cancelled = true
    }
  }, [persona, skill.name])

  const flip = async () => {
    setBusy(true)
    await onSwitch(!skill.enabled)
    setBusy(false)
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{skill.name}</DialogTitle>
          <DialogDescription>{skill.description}</DialogDescription>
        </DialogHeader>
        <ul className="space-y-0.5 text-xs text-fg-muted">
          <li>
            {skill.length} characters
            {skill.length > skill.cap ? `; only the first ${skill.cap} are sent with a message` : ""}
          </li>
          {skill.tools.length > 0 && <li>Needs the persona to {needs(skill.tools)}</li>}
          <li>
            {skill.own
              ? "Yours: it is sent only to a model on your computer, never to a cloud model"
              : "Ships with Sympose"}
          </li>
        </ul>
        {read === null ? (
          <p className="text-sm text-fg-muted">Loading</p>
        ) : "error" in read ? (
          <p className="text-sm text-destructive">{read.error}</p>
        ) : (
          <pre className="max-h-72 overflow-auto rounded-lg border border-border px-3 py-2 text-xs whitespace-pre-wrap">
            {read.text}
          </pre>
        )}
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>Close</DialogClose>
          <Button disabled={busy || read === null || "error" in read} onClick={() => void flip()}>
            {skill.enabled ? "Turn off" : "Turn on"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Settings → Skills, under the two settings of that group (docs/decisions/077, the amendment of 2026-10-14): one field
 * to add a skill by the path of its folder, then a row for each skill the persona could carry, with a switch and a
 * button that opens what it says. A skill that is added arrives off and opens for reading at once. The backend holds
 * every rule: this only asks, and shows the reason when it refuses.
 */
function SkillsRows({ persona, personaName }: { persona: string | null; personaName: string }) {
  const { state, add, setEnabled } = useSkills(persona)
  const [folder, setFolder] = React.useState("")
  const [adding, setAdding] = React.useState(false)
  const [reviewing, setReviewing] = React.useState<string | null>(null)

  if (!persona) return null

  const submit = async () => {
    if (adding || folder.trim() === "") return
    setAdding(true)
    const added = await add(folder.trim())
    setAdding(false)
    if (!added) return
    setFolder("")
    setReviewing(added.skill.name)
    if (added.leftOut > 0) notify.info("Only SKILL.md was copied. Nothing else in that folder is used.")
  }

  const skills = state.status === "ready" ? state.skills : []
  const open = skills.find((s) => s.name === reviewing)

  return (
    <>
      <ControlRow
        label="Add a skill"
        keywords="skill folder path copy"
        className="flex-col items-stretch"
        hint={
          <p className="text-xs text-fg-muted">
            These are {personaName}&apos;s skills. Paste the full path of a skill&apos;s folder: Sympose copies its
            SKILL.md and nothing else. It starts off: read it, then turn it on.
          </p>
        }
      >
        <div className="flex w-full items-center gap-2">
          <input
            type="text"
            aria-label="Folder of the skill to add"
            value={folder}
            placeholder="/Users/you/skills/my-skill"
            onChange={(e) => setFolder(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void submit()}
            className="h-7 min-w-0 flex-1 rounded-md border border-input bg-transparent px-2 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
          <Button
            variant="outline"
            size="icon-xs"
            aria-label="Add the skill"
            title="Add the skill"
            disabled={adding || folder.trim() === ""}
            onClick={() => void submit()}
          >
            <HugeiconsIcon icon={Add01Icon} />
          </Button>
        </div>
      </ControlRow>
      {state.status === "error" && <p className="text-sm text-fg-muted">Couldn&apos;t load the skills: {state.error}</p>}
      {skills.map((s) => (
        <ControlRow key={s.name} label={s.name} keywords={s.description}>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={`Read ${s.name}`}
              title="Read it"
              onClick={() => setReviewing(s.name)}
            >
              <HugeiconsIcon icon={ViewIcon} />
            </Button>
            <SegmentedControl
              size="sm"
              aria-label={`Use ${s.name}`}
              value={s.enabled ? "on" : "off"}
              onValueChange={(v) => void setEnabled(s.name, v === "on")}
              options={[
                { value: "on", label: "On" },
                { value: "off", label: "Off" },
              ]}
            />
          </div>
        </ControlRow>
      ))}
      {open && (
        <Review
          persona={persona}
          skill={open}
          onClose={() => setReviewing(null)}
          onSwitch={(enabled) => setEnabled(open.name, enabled)}
        />
      )}
    </>
  )
}

export { SkillsRows }
