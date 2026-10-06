import * as React from "react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent } from "@/components/ui/popover"
import { agoIso } from "@/lib/ago"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import { Attachment01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { attach } from "@/lib/attachments"
import { addComment, changeComment, deleteComment, replyToComment, type Annotation } from "@/lib/persona-changes-api"
import type { CommentTarget } from "@/lib/review-extensions"

/** What the box is open for: a new comment on the selected words, or the thread of a comment already there. `ids` are
 *  every thread on those words when there is more than one, `id` first. */
export type CommentBox = { kind: "compose"; target: CommentTarget } | { kind: "thread"; id: string; ids?: string[]; rect: DOMRect }

const FIELD =
  "w-full resize-none rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground outline-none placeholder:text-fg-muted focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"

function Quote({ text }: { text: string }) {
  return (
    <p className="truncate border-s-2 border-border ps-2 text-fg-muted" title={text}>
      {text}
    </p>
  )
}

/** A text box that sends on ⌘/Ctrl-Enter as well as on its button. */
function Entry({
  label,
  submit,
  placeholder,
  onDone,
  actions,
}: {
  label: string
  submit: (text: string) => Promise<boolean>
  placeholder: string
  onDone?: () => void
  /** Replaces the box's own button row, to put other buttons beside the send button (the thread's one row). */
  actions?: (send: { send: () => void; canSend: boolean }) => React.ReactNode
}) {
  const [text, setText] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const send = async () => {
    const body = text.trim()
    if (!body || busy) return
    setBusy(true)
    const ok = await submit(body)
    setBusy(false)
    if (ok) {
      setText("")
      onDone?.()
    }
  }
  return (
    <div className="flex flex-col gap-2">
      <textarea
        autoFocus
        rows={3}
        value={text}
        placeholder={placeholder}
        aria-label={label}
        className={FIELD}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            void send()
          }
        }}
      />
      {actions ? (
        actions({ send: () => void send(), canSend: !!text.trim() && !busy })
      ) : (
        <div className="flex justify-end">
          <Button type="button" size="xs" disabled={!text.trim() || busy} onClick={() => void send()}>
            {label}
          </Button>
        </div>
      )}
    </div>
  )
}

/** One comment with its answers, where the user answers, resolves it (its answers go with it) or deletes it. */
function Thread({
  root,
  answers,
  personaName,
  path,
  persona,
  onClose,
  saved,
}: {
  root: Annotation
  answers: Annotation[]
  personaName: string
  path: string
  persona: string
  onClose: () => void
  saved: (result: { ok: boolean } & { error?: string }) => boolean
}) {
  // Declining one of her comments needs the user's own reply first, saying why (docs/decisions/069).
  const replied = answers.some((a) => a.author === "user")
  const decide = async (verdict: "accepted" | "declined") => {
    if (saved(await changeComment({ path, persona, id: root.id, verdict }))) onClose()
  }
  return (
    <div className="flex flex-col gap-2" data-testid="comment-thread">
      <div className="flex items-center gap-1">
        <div className="min-w-0 flex-1">
          <Quote text={root.quote} />
        </div>
        <button
          type="button"
          onClick={() => attach({ quote: root.quote, before: root.before, after: root.after })}
          title="Attach to your message"
          aria-label="Attach to your message"
          className="grid size-6 shrink-0 place-items-center rounded text-fg-muted hover:bg-accent hover:text-foreground"
        >
          <HugeiconsIcon icon={Attachment01Icon} className="size-3.5" />
        </button>
      </div>
      <ul className="flex flex-col gap-2">
        {[root, ...answers].map((a) => (
          <li key={a.id}>
            <p className="text-[11px] text-fg-muted">
              {a.author === "user" ? "You" : personaName} · {agoIso(a.time)}
            </p>
            <p className="whitespace-pre-wrap text-sm text-foreground">{a.text}</p>
          </li>
        ))}
      </ul>
      <Entry
        label="Reply"
        placeholder="Reply"
        submit={async (text) => saved(await replyToComment({ path, persona, replyTo: root.id, text }))}
        actions={({ send, canSend }) => (
          <>
            {root.author === "persona" && !replied && <p className="text-[11px] text-fg-muted">To decline, reply first, saying why you disagree.</p>}
            <div className="flex items-center justify-between" data-testid="comment-thread-actions">
              {root.author === "persona" ? (
                <span className="flex gap-1">
                  <Button type="button" variant="ghost" size="xs" onClick={() => decide("accepted")}>
                    Accept
                  </Button>
                  <Button type="button" variant="ghost" size="xs" disabled={!replied} onClick={() => decide("declined")}>
                    Decline
                  </Button>
                </span>
              ) : (
                <span className="flex gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="xs"
                    onClick={async () => {
                      if (saved(await changeComment({ path, persona, id: root.id, state: "resolved" }))) onClose()
                    }}
                  >
                    Resolve
                  </Button>
                </span>
              )}
              <span className="flex gap-1">
                <Button type="button" size="xs" disabled={!canSend} onClick={send}>
                  Reply
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  size="xs"
                  onClick={() =>
                    confirm({
                      message: "Delete this comment?",
                      description: answers.length > 0 ? "Its replies are deleted with it." : undefined,
                      confirmLabel: "Delete",
                      permanent: true,
                      onConfirm: async () => {
                        if (saved(await deleteComment(path, persona, root.id))) onClose()
                      },
                    })
                  }
                >
                  Delete
                </Button>
              </span>
            </div>
          </>
        )}
      />
    </div>
  )
}

/**
 * The box that opens on a highlight (docs/decisions/069): a new comment on what the user selected, or the thread under
 * a comment. Comments on exactly the same words are one highlight, and the box shows every one of their threads, one
 * under the other, so none is out of reach. It opens on the passage itself. A comment travels to the persona with the
 * user's next message; what she answers appears here the next time the note's changes are read.
 */
export function CommentPopover({
  box,
  annotations,
  personaName,
  path,
  persona,
  onClose,
  onChanged,
}: {
  box: CommentBox | null
  annotations: Annotation[]
  personaName: string
  path: string
  persona: string
  onClose: () => void
  /** Something was saved: read the note's changes again. */
  onChanged: () => void
}) {
  const rect = box ? (box.kind === "compose" ? box.target.rect : box.rect) : null
  const anchor = React.useMemo(() => (rect ? { getBoundingClientRect: () => rect } : undefined), [rect])
  const roots =
    box?.kind === "thread"
      ? (box.ids ?? [box.id]).map((id) => annotations.find((a) => a.id === id && !a.reply_to)).filter((a): a is Annotation => !!a)
      : []

  const saved = (result: { ok: boolean } & { error?: string }) => {
    if (!result.ok) notify.error(result.error ?? "Could not save the comment")
    else onChanged()
    return result.ok
  }

  let body: React.ReactNode = null
  if (box?.kind === "compose") {
    const { target } = box
    body = (
      <div className="flex flex-col gap-2" data-testid="comment-compose">
        <Quote text={target.quote} />
        <Entry
          label="Comment"
          placeholder="Say what you want to discuss here"
          submit={async (text) => saved(await addComment({ path, persona, quote: target.quote, before: target.before, after: target.after, text }))}
          onDone={onClose}
        />
      </div>
    )
  } else if (box?.kind === "thread" && roots.length > 0) {
    body = (
      <div className="flex flex-col gap-4">
        {roots.map((root) => (
          <Thread
            key={root.id}
            root={root}
            answers={annotations.filter((a) => a.reply_to === root.id).sort((a, b) => a.time.localeCompare(b.time))}
            personaName={personaName}
            path={path}
            persona={persona}
            onClose={onClose}
            saved={saved}
          />
        ))}
      </div>
    )
  }

  return (
    <Popover open={body !== null} onOpenChange={(open) => !open && onClose()}>
      <PopoverContent anchor={anchor} side="bottom" align="start" className="max-h-[70vh] w-80 max-w-[calc(100vw-1rem)] space-y-0 overflow-y-auto text-sm text-foreground">
        {body}
      </PopoverContent>
    </Popover>
  )
}
