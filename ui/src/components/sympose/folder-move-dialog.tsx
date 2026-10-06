import * as React from "react"

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
import { clashList, reachLine, suggestedName } from "@/lib/folder-move-wording"
import type { FolderMoveReach } from "@/lib/vault-folder-move-api"

const FIELD =
  "block w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-brand disabled:opacity-60"

/** What the user is asked while a folder move waits on them (docs/decisions/074). `resolve` answers it; closing the
 *  dialog any other way is a cancel (`null` / `false`). */
export type FolderMoveAsk =
  | { kind: "clash"; name: string; destination: string; resolve: (answer: { merge: true } | { newName: string } | null) => void }
  | { kind: "notes"; files: string[]; resolve: (ok: boolean) => void }
  | { kind: "reach"; reach: FolderMoveReach[]; resolve: (ok: boolean) => void }

function ClashForm({ ask, close }: { ask: Extract<FolderMoveAsk, { kind: "clash" }>; close: () => void }) {
  const [name, setName] = React.useState(suggestedName(ask.name))
  const trimmed = name.trim()
  const where = ask.destination || "the vault root"
  const answer = (value: { merge: true } | { newName: string }) => {
    ask.resolve(value)
    close()
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (trimmed && trimmed !== ask.name) answer({ newName: trimmed })
      }}
    >
      <DialogHeader>
        <DialogTitle>{`“${ask.name}” is already in ${where}`}</DialogTitle>
        <DialogDescription>Merge this folder into the one there, or move it under another name.</DialogDescription>
      </DialogHeader>
      <input
        autoFocus
        value={name}
        aria-label="New name for the folder"
        onChange={(e) => setName(e.target.value)}
        className={`${FIELD} my-4`}
      />
      <DialogFooter>
        <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
        <Button type="button" variant="outline" onClick={() => answer({ merge: true })}>
          Merge
        </Button>
        <Button type="submit" disabled={!trimmed || trimmed === ask.name}>
          Move as this name
        </Button>
      </DialogFooter>
    </form>
  )
}

function Confirm({
  title,
  children,
  confirmLabel,
  onAnswer,
}: {
  title: string
  children: React.ReactNode
  confirmLabel: string
  onAnswer: (ok: boolean) => void
}) {
  return (
    <>
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription render={<div />}>{children}</DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
        <Button onClick={() => onAnswer(true)}>{confirmLabel}</Button>
      </DialogFooter>
    </>
  )
}

/** The prompts of a folder move: a folder of that name is already there (rename it or merge), the files that are in both
 *  (rename the incoming ones or cancel the merge), and a persona whose reach would change. Open while `ask` is set;
 *  closing it, or Cancel, answers "no". */
function FolderMoveDialog({ ask, onClose }: { ask: FolderMoveAsk | null; onClose: () => void }) {
  const close = onClose
  return (
    <Dialog
      open={ask !== null}
      onOpenChange={(open) => {
        // Only the user's own closing (Escape, the backdrop, Cancel) comes through here, not the buttons' answers.
        if (open || !ask) return
        ;(ask.resolve as (v: null | false) => void)(ask.kind === "clash" ? null : false)
        onClose()
      }}
    >
      <DialogContent>
        {ask?.kind === "clash" && <ClashForm key={ask.name} ask={ask} close={close} />}
        {ask?.kind === "notes" && (
          <Confirm
            title={`${ask.files.length} ${ask.files.length === 1 ? "file has" : "files have"} the same name in both folders`}
            confirmLabel="Rename them and merge"
            onAnswer={(ok) => {
              ask.resolve(ok)
              close()
            }}
          >
            <p>The incoming ones are renamed to “Name (2)”, the first free number. Nothing is overwritten.</p>
            <ul className="mt-2 list-disc pl-5 font-mono text-xs">
              {clashList(ask.files).shown.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            {clashList(ask.files).more > 0 && <p className="mt-1 text-xs">and {clashList(ask.files).more} more</p>}
          </Confirm>
        )}
        {ask?.kind === "reach" && (
          <Confirm
            title="Moving this folder changes which notes some personas can read"
            confirmLabel="Move anyway"
            onAnswer={(ok) => {
              ask.resolve(ok)
              close()
            }}
          >
            {ask.reach.map((r) => (
              <p key={r.handle}>{reachLine(r)}</p>
            ))}
            <p className="mt-2">Move anyway?</p>
          </Confirm>
        )}
      </DialogContent>
    </Dialog>
  )
}

export { FolderMoveDialog }
