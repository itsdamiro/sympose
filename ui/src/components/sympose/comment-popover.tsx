import * as React from "react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent } from "@/components/ui/popover"
import { agoIso } from "@/lib/ago"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import { addComment, changeComment, deleteComment, replyToComment, type Annotation } from "@/lib/persona-changes-api"
import type { CommentTarget } from "@/lib/review-extensions"

/** What the box is open for: a new comment on the selected words, or the thread of a comment already there. */
export type CommentBox = { kind: "compose"; target: CommentTarget } | { kind: "thread"; id: string; rect: DOMRect }

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

/**
 * The box that opens on a highlight (docs/decisions/069): a new comment on what the user selected, or the thread under
 * a comment, where they answer, resolve it (its answers go with it) or delete it. It opens on the passage itself. A
 * comment travels to the persona with the user's next message; what she answers appears here the next time the note's
 * changes are read.
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
  const root = box?.kind === "thread" ? annotations.find((a) => a.id === box.id && !a.reply_to) : undefined
  const answers = root ? annotations.filter((a) => a.reply_to === root.id).sort((a, b) => a.time.localeCompare(b.time)) : []

  const saved = (result: { ok: boolean } & { error?: string }) => {
    if (!result.ok) notify.error(result.error ?? "Could not save the comment")
    else onChanged()
    return result.ok
  }
  // Declining one of her comments needs the user's own reply first, saying why (docs/decisions/069).
  const replied = answers.some((a) => a.author === "user")
  const decide = async (verdict: "accepted" | "declined") => {
    if (root && saved(await changeComment({ path, persona, id: root.id, verdict }))) onClose()
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
  } else if (box?.kind === "thread" && root) {
    body = (
      <div className="flex flex-col gap-2" data-testid="comment-thread">
        <Quote text={root.quote} />
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

  return (
    <Popover open={body !== null} onOpenChange={(open) => !open && onClose()}>
      <PopoverContent anchor={anchor} side="bottom" align="start" className="w-80 max-w-[calc(100vw-1rem)] space-y-0 text-sm text-foreground">
        {body}
      </PopoverContent>
    </Popover>
  )
}
