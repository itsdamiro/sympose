import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  AlertCircleIcon,
  CheckmarkCircle01Icon,
  CloudIcon,
  ComputerIcon,
  Delete02Icon,
  Edit01Icon,
  File02Icon,
  MoreHorizontalIcon,
  PauseIcon,
  PencilEdit01Icon,
} from "@hugeicons/core-free-icons"

import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { ControlRow } from "@/components/sympose/control-section"
import { ModelPicker } from "@/components/sympose/model-picker"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import { agoIso } from "@/lib/ago"
import { confirm } from "@/lib/confirm-store"
import type { Job } from "@/lib/jobs-api"
import type { ModelsState } from "@/lib/models-api"
import { getUnsavedGuard } from "@/lib/unsaved-guard"
import { useJobs } from "@/lib/use-jobs"
import { useModels } from "@/lib/use-models"
import { useSchedule } from "@/lib/use-schedule"

/** The drafts of a job that wait for the user: the number, in the alert colour once the job has stopped filing more. */
function DraftsWaiting({ job }: { job: Job }) {
  const full = job.drafts >= job.draft_cap
  const label = full
    ? `${job.drafts} drafts from this job are waiting; it files no more until you decide some`
    : `${job.drafts} draft${job.drafts === 1 ? "" : "s"} from this job waiting`
  return (
    <span className={`flex items-center gap-1 ${full ? "text-destructive" : ""}`} title={label}>
      <HugeiconsIcon icon={File02Icon} className="size-3 shrink-0" aria-hidden />
      <span aria-label={label}>{job.drafts}</span>
    </span>
  )
}

/** One line under a job's name: its schedule, and how it last went (or what stops it), in the muted style of a hint. */
function JobStatus({ job }: { job: Job }) {
  const when = agoIso(job.last_run)
  const schedule = job.schedule || "no schedule"
  if (job.problem) {
    return (
      <p className="flex items-center gap-1 text-xs text-destructive">
        <HugeiconsIcon icon={AlertCircleIcon} className="size-3 shrink-0" aria-hidden />
        {job.problem}
      </p>
    )
  }
  return (
    <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-fg-muted">
      <span>{schedule}</span>
      {job.paused ? (
        <span className="flex items-center gap-1 text-destructive" title={job.detail || undefined}>
          <HugeiconsIcon icon={PauseIcon} className="size-3 shrink-0" aria-hidden />
          Paused after {job.failures} failures in a row
        </span>
      ) : job.last_run ? (
        <span className="flex items-center gap-1" title={job.detail || undefined}>
          <HugeiconsIcon
            icon={job.outcome === "failed" ? AlertCircleIcon : CheckmarkCircle01Icon}
            className={`size-3 shrink-0 ${job.outcome === "failed" ? "text-destructive" : "text-ok"}`}
            aria-label={job.outcome === "failed" ? "Failed" : "Ran"}
          />
          {when}
          {job.outcome === "failed" && job.detail ? `: ${job.detail}` : ""}
        </span>
      ) : (
        <span>not run yet</span>
      )}
      {job.drafts > 0 && <DraftsWaiting job={job} />}
    </p>
  )
}

/**
 * One job's row: the name (an inline field while it is being renamed: Enter commits, Esc or a click away cancels), the
 * model's picker (its mark and name; a pick is written in the job's file), a `⋯` menu (open the file, rename, delete) and the On/Off switch.
 */
function JobRow({
  job,
  models,
  onOpen,
  onSwitch,
  onModel,
  onRename,
  onDelete,
}: {
  job: Job
  /** The persona's models, which a job's picker offers and falls back to; `null` until known. */
  models: ModelsState | null
  onOpen: () => void
  onSwitch: (on: boolean) => void
  onModel: (model: string | null) => void
  /** Rename it; the job under its new name, or `null` if refused. */
  onRename: (name: string) => Promise<Job | null>
  onDelete: () => Promise<boolean>
}) {
  const [renaming, setRenaming] = React.useState<string | null>(null)
  const [pendingRename, setPendingRename] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (renaming === null) return
    const id = requestAnimationFrame(() => {
      inputRef.current?.focus()
      inputRef.current?.select()
    })
    return () => cancelAnimationFrame(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when the field opens, not on each keystroke
  }, [renaming === null])

  const commit = async () => {
    const typed = (renaming ?? "").trim()
    if (!typed || typed === job.name || busy) return setRenaming(null)
    setBusy(true)
    const renamed = await onRename(typed)
    setBusy(false)
    if (renamed) setRenaming(null)
  }

  const askToDelete = () =>
    confirm({
      message: `Delete “${job.name}”?`,
      description: "A copy of its file stays in the jobs folder as a backup.",
      confirmLabel: "Delete",
      onConfirm: async () => {
        await onDelete()
      },
    })

  const label =
    renaming === null ? (
      job.name
    ) : (
      <input
        ref={inputRef}
        value={renaming}
        disabled={busy}
        aria-label={`New name for ${job.name}`}
        onChange={(e) => setRenaming(e.target.value)}
        onBlur={() => !busy && setRenaming(null)}
        onKeyDown={(e) => {
          if (e.key === "Enter") void commit()
          else if (e.key === "Escape") setRenaming(null)
        }}
        className="h-7 w-44 rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
      />
    )

  return (
    <ControlRow label={label} keywords={`${job.name} ${job.schedule} ${job.kind} ${job.model ?? ""}`} hint={<JobStatus job={job} />}>
      <div className="flex items-center gap-2">
        {job.model && models ? (
          <ModelPicker
            side="bottom"
            state={{ ...models, current: job.model, currentCloud: job.cloud, own: job.own_model, fallback: models.current, fallbackCloud: models.currentCloud }}
            onChoose={onModel}
          />
        ) : job.model ? (
          <HugeiconsIcon
            icon={job.cloud ? CloudIcon : ComputerIcon}
            className={`size-3.5 shrink-0 ${job.cloud ? "text-fg-muted" : "text-ok"}`}
            aria-label={job.cloud ? `Cloud model: ${job.model}` : `On your computer: ${job.model}`}
          />
        ) : null}
        <DropdownMenu
          modal={false}
          // Entering the field waits for the menu to finish closing: it hands focus back to the trigger, which would
          // blur the new field at once and cancel the rename (as in the note's own menu).
          onOpenChangeComplete={(open) => {
            if (!open && pendingRename) {
              setPendingRename(false)
              setRenaming(job.name)
            }
          }}
        >
          <DropdownMenuTrigger
            aria-label={`Actions for ${job.name}`}
            className="grid size-6 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-popup-open:bg-accent data-popup-open:text-foreground"
          >
            <HugeiconsIcon icon={MoreHorizontalIcon} className="size-3.5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
            <DropdownMenuItem onClick={onOpen}>
              <HugeiconsIcon icon={Edit01Icon} />
              Open in the editor
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setPendingRename(true)}>
              <HugeiconsIcon icon={PencilEdit01Icon} />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={askToDelete}>
              <HugeiconsIcon icon={Delete02Icon} />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <SegmentedControl
          size="sm"
          aria-label={`Run ${job.name}`}
          value={job.enabled && !job.paused ? "on" : "off"}
          onValueChange={(v) => onSwitch(v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </div>
    </ControlRow>
  )
}

/**
 * Settings → Jobs (docs/decisions/091): one row for each of the persona's scheduled jobs, with its schedule, how the last
 * run went, the model's picker, a menu (open the job's file in the editor, rename, delete) and a switch, and a button that makes a new
 * job from the template (off, and opened in the editor at once), and, on a Mac, the switch that has the operating system
 * run due jobs while the app is closed. A job that stopped itself after failing shows as off: the
 * switch turns it back on. The backend holds every rule: this only asks, and shows the reason when it refuses.
 */
function JobsRows({
  persona,
  personaName,
  version = 0,
  onOpen,
  onRenamed,
  onRemoved,
}: {
  persona: string | null
  personaName: string
  /** Changes when the editor saved a job's file, so the rows are read again. */
  version?: number
  /** Open a job's file (`jobs/<name>.md`) in the editor. */
  onOpen: (file: string) => void
  /** A job's file was renamed: the editor holding the old one is pointed at the new. */
  onRenamed?: (file: string, newFile: string) => void
  /** A job's file was deleted: the editor holding it lets go. */
  onRemoved?: (file: string) => void
}) {
  const { state, setEnabled, setModel, add, rename, remove } = useJobs(persona, version)
  const { state: models } = useModels(persona)
  const { schedule, busy: scheduleBusy, set: setSchedule } = useSchedule()
  const [adding, setAdding] = React.useState(false)

  if (!persona) return null

  const make = async () => {
    if (adding) return
    setAdding(true)
    const job = await add()
    setAdding(false)
    if (job) onOpen(job.file)
  }

  const jobs = state.status === "ready" ? state.jobs : []

  return (
    <>
      <ControlRow
        label="Add a job"
        keywords="job schedule scheduled run automatic"
        hint={
          <p className="text-xs text-fg-muted">
            A job is something {personaName} does by itself on a schedule, such as a weekly review. What it writes
            waits in Drafts for you to accept. A new job starts off. In its file, the properties say when it runs and the
            text says what to do.
          </p>
        }
      >
        <Button variant="outline" size="icon-xs" aria-label="Add a job" title="Add a job" disabled={adding} onClick={() => void make()}>
          <HugeiconsIcon icon={Add01Icon} />
        </Button>
      </ControlRow>
      {schedule?.supported && (
        <ControlRow
          label="Run while Sympose is closed"
          keywords="job schedule scheduled background launchd login"
          hint={
            <p className="text-xs text-fg-muted">
              On: your Mac checks for jobs that are due every 5 minutes, even when this app is closed. Off: they run only
              while it is open.
            </p>
          }
        >
          <SegmentedControl
            size="sm"
            aria-label="Run jobs while Sympose is closed"
            value={schedule.installed ? "on" : "off"}
            onValueChange={(v) => void setSchedule(v === "on")}
            disabledValues={scheduleBusy ? ["on", "off"] : undefined}
            options={[
              { value: "on", label: "On" },
              { value: "off", label: "Off" },
            ]}
          />
        </ControlRow>
      )}
      {state.status === "error" && <p className="text-sm text-fg-muted">Couldn&apos;t load the jobs: {state.error}</p>}
      {jobs.map((job) => (
        <JobRow
          key={job.name}
          job={job}
          models={models}
          onOpen={() => onOpen(job.file)}
          onSwitch={(on) => void setEnabled(job.name, on)}
          onModel={(model) => void setModel(job.name, model)}
          onRename={async (name) => {
            // Unsaved edits in the editor are saved to the file under its old name first, so a rename never loses them.
            if (getUnsavedGuard() && !(await getUnsavedGuard()!.save())) return null
            const renamed = await rename(job.name, name)
            if (renamed) onRenamed?.(job.file, renamed.file)
            return renamed
          }}
          onDelete={async () => {
            const done = await remove(job.name)
            if (done) onRemoved?.(job.file)
            return done
          }}
        />
      ))}
    </>
  )
}

export { JobsRows }
