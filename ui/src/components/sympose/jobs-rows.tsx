import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Add01Icon,
  AlertCircleIcon,
  CheckmarkCircle01Icon,
  CloudIcon,
  ComputerIcon,
  Edit01Icon,
  PauseIcon,
} from "@hugeicons/core-free-icons"

import { Button } from "@/components/ui/button"
import { ControlRow } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import { agoIso } from "@/lib/ago"
import type { Job } from "@/lib/jobs-api"
import { useJobs } from "@/lib/use-jobs"

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
    </p>
  )
}

/**
 * Settings → Jobs (docs/decisions/091): one row for each of the persona's scheduled jobs, with its schedule, how the last
 * run went, the model's mark, a button that opens the job's file in the editor and a switch, and a button that makes a new
 * job from the template (off, and opened in the editor at once). A job that stopped itself after failing shows as off: the
 * switch turns it back on. The backend holds every rule: this only asks, and shows the reason when it refuses.
 */
function JobsRows({
  persona,
  personaName,
  version = 0,
  onOpen,
}: {
  persona: string | null
  personaName: string
  /** Changes when the editor saved a job's file, so the rows are read again. */
  version?: number
  /** Open a job's file (`jobs/<name>.md`) in the editor. */
  onOpen: (file: string) => void
}) {
  const { state, setEnabled, add } = useJobs(persona, version)
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
            waits in Drafts for you to accept. A new job starts off.
          </p>
        }
      >
        <Button variant="outline" size="icon-xs" aria-label="Add a job" title="Add a job" disabled={adding} onClick={() => void make()}>
          <HugeiconsIcon icon={Add01Icon} />
        </Button>
      </ControlRow>
      {state.status === "error" && <p className="text-sm text-fg-muted">Couldn&apos;t load the jobs: {state.error}</p>}
      {jobs.map((job) => (
        <ControlRow
          key={job.name}
          label={job.name}
          keywords={`${job.schedule} ${job.kind} ${job.model ?? ""}`}
          hint={<JobStatus job={job} />}
        >
          <div className="flex items-center gap-2">
            {job.model && (
              <HugeiconsIcon
                icon={job.cloud ? CloudIcon : ComputerIcon}
                className={`size-3.5 shrink-0 ${job.cloud ? "text-fg-muted" : "text-ok"}`}
                aria-label={job.cloud ? `Cloud model: ${job.model}` : `On your computer: ${job.model}`}
              />
            )}
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={`Open ${job.name} in the editor`}
              title="Open it in the editor"
              onClick={() => onOpen(job.file)}
            >
              <HugeiconsIcon icon={Edit01Icon} />
            </Button>
            <SegmentedControl
              size="sm"
              aria-label={`Run ${job.name}`}
              value={job.enabled && !job.paused ? "on" : "off"}
              onValueChange={(v) => void setEnabled(job.name, v === "on")}
              options={[
                { value: "on", label: "On" },
                { value: "off", label: "Off" },
              ]}
            />
          </div>
        </ControlRow>
      ))}
    </>
  )
}

export { JobsRows }
