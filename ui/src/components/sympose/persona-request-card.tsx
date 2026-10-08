import * as React from "react"
import { ArrowDown01Icon, Cancel01Icon, Folder01Icon, Tick02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { iconByName } from "@/lib/persona-icons"
import { resolvePersonaVisuals } from "@/lib/personas"
import type { EditModeId } from "@/lib/edit-mode-api"
import type { ConfirmationRequest, RequestState } from "@/lib/confirmations-api"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ControlRow } from "@/components/sympose/control-section"
import { EDIT_MODE_LABELS } from "@/components/sympose/persona-edit-menu"
import { PersonaHeader } from "@/components/sympose/persona-header"
import { TogglePill } from "@/components/sympose/toggle-pill"

interface PersonaRequestCardProps extends Omit<React.ComponentProps<"div">, "onAnswer"> {
  request: ConfirmationRequest
  /** Accept (with the folders and the edit mode as the card was left) or decline; resolves to an error text, or `null` when it went through. */
  onAnswer: (accept: boolean, folders: string[], editMode: string) => Promise<string | null>
}

const OUTCOMES: Record<Exclude<RequestState, "waiting">, string> = {
  accepted: "Created",
  declined: "Declined",
  replaced: "Replaced by a newer proposal",
  outdated: "No longer possible",
}

/** The soul as text: four lines, with a More button beneath when it is longer (the reply footer's expander, ArrowDown that turns). */
function SoulText({ text }: { text: string }) {
  const ref = React.useRef<HTMLParagraphElement>(null)
  const [open, setOpen] = React.useState(false)
  const [long, setLong] = React.useState(false)
  React.useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => {
      if (!open) setLong(el.scrollHeight > el.clientHeight + 1)
    }
    measure()
    if (typeof ResizeObserver === "undefined") return
    const watch = new ResizeObserver(measure)
    watch.observe(el)
    return () => watch.disconnect()
  }, [text, open])
  return (
    <div className="flex flex-col items-start gap-1">
      <p ref={ref} className={cn("leading-relaxed whitespace-pre-wrap text-muted-foreground", !open && "line-clamp-4")}>
        {text}
      </p>
      {(long || open) && (
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {open ? "Less" : "More"}
          <HugeiconsIcon icon={ArrowDown01Icon} aria-hidden className={cn("size-3 shrink-0 transition-transform", open && "rotate-180")} />
        </button>
      )}
    </div>
  )
}

/**
 * A persona's request to make a new persona (docs/decisions/078): a card in the chat, made of what the app already has.
 * Its top is the Persona panel's own header (`PersonaHeader`) in the proposed icon and colour; under it the edit mode as the
 * chip the panel shows, the folders as the same pills the cloud notice uses, and Decline and Accept as the Doctor's dialog
 * has them. Everything on it is
 * the persona's suggestion; the pills are the user's last word on access, and a change to anything else is asked of her in
 * the chat. Answered, the card keeps its header and one line.
 */
function PersonaRequestCard({ className, request, onAnswer, ...props }: PersonaRequestCardProps) {
  const { draft } = request
  const choices = request.folder_choices
  const [on, setOn] = React.useState<string[]>(() => draft.folders.filter((f) => choices.includes(f)))
  const [mode, setMode] = React.useState(draft.edit_mode)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const waiting = request.state === "waiting"

  const send = async (accept: boolean) => {
    setBusy(true)
    setError(await onAnswer(accept, on, mode))
    setBusy(false)
  }
  const toggle = (folder: string) => setOn((prev) => (prev.includes(folder) ? prev.filter((f) => f !== folder) : [...prev, folder]))

  return (
    <div
      data-slot="persona-request-card"
      data-state={request.state}
      className={cn("overflow-hidden rounded-lg border border-border bg-panel pb-3 text-xs text-fg-muted", !waiting && "opacity-80", className)}
      {...props}
    >
      <PersonaHeader
        name={draft.name}
        title={draft.title}
        icon={iconByName(draft.icon) ?? resolvePersonaVisuals("").icon}
        accent={draft.accent}
        accentDark={draft.accent_dark}
        bandClass="h-12 rounded-none"
        className="px-4"
      />
      <div className="flex flex-col gap-3 px-4 pt-3">
        {!waiting ? (
          <p className="flex items-center gap-1.5">
            <HugeiconsIcon icon={request.state === "accepted" ? Tick02Icon : Cancel01Icon} className="size-3.5" aria-hidden />
            {request.state === "outdated" && request.reason ? request.reason : OUTCOMES[request.state as Exclude<RequestState, "waiting">]}
          </p>
        ) : (
          <>
            <ControlRow
              label="Edits"
              hint={<p>{request.edit_modes.find((m) => m.id === mode)?.summary}</p>}
            >
              <Select value={mode} onValueChange={(v) => v && setMode(v)}>
                <SelectTrigger size="sm" className="w-40" aria-label="What it may do to your notes">
                  <SelectValue>{(v: string) => EDIT_MODE_LABELS[v as EditModeId] ?? v}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {request.edit_modes.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {EDIT_MODE_LABELS[m.id as EditModeId] ?? m.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </ControlRow>
            <ControlRow
              label="Folders"
              hint={<p>The folders it may read.</p>}
            >
              <span className="flex items-center gap-1 font-mono tabular-nums" title="Folders it may read">
                <HugeiconsIcon icon={Folder01Icon} className="size-3.5" aria-hidden />
                {on.length}/{choices.length}
              </span>
            </ControlRow>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Folders it may read">
              {choices.map((folder) => (
                <TogglePill key={folder} pressed={on.includes(folder)} onClick={() => toggle(folder)}>
                  {folder}
                </TogglePill>
              ))}
            </div>
            <ControlRow label="Soul" hint={<p>How it talks and what it is like to talk to.</p>} />
            <SoulText text={draft.soul} />
            {error && (
              <p role="alert" className="text-destructive">
                {error}
              </p>
            )}
            <div className="flex items-center justify-end gap-2">
              <Button type="button" variant="outline" disabled={busy} onClick={() => void send(false)}>
                Decline
              </Button>
              <Button
                type="button"
                disabled={busy || on.length === 0}
                title={on.length === 0 ? "Turn on at least one folder" : undefined}
                onClick={() => void send(true)}
              >
                Accept
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export { PersonaRequestCard }
