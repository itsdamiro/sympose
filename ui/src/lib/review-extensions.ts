import { Decoration, EditorView, GutterMarker, WidgetType, gutter, type DecorationSet } from "@codemirror/view"
import { Facet, StateEffect, StateField, type EditorState, type Extension, type Range } from "@codemirror/state"
import { Cancel01Icon, Tick02Icon } from "@hugeicons/core-free-icons"

import { locate } from "@/lib/passage-finder"
import type { Annotation, Proposal } from "@/lib/persona-changes-api"

/**
 * What the editor draws for a persona's work on the open note (docs/decisions/042, 069, 070): each edit she proposed as
 * a tracked change in place (the passage she quoted struck through, her replacement beside it with its own Accept and
 * Decline), and the user's comments as highlights with a dot in the margin. They are CodeMirror extensions handed to
 * stylo's `extensions` prop. Everything is found again in the text in front of the user, by the passage and the text
 * around it (`passage-finder`), because that text can be ahead of the file on disk; a change whose passage was
 * rewritten is not drawn in the text at all (`classify` lists it as outdated, for the panel to show).
 */
export interface ReviewData {
  proposals: Proposal[]
  annotations: Annotation[]
}

export const NO_REVIEW: ReviewData = { proposals: [], annotations: [] }

/** A proposal placed in the text now, or one whose passage can no longer be told. */
export interface Placed {
  proposal: Proposal
  from: number
  to: number
}

export function classify(text: string, proposals: Proposal[]): { placed: Placed[]; outdated: Proposal[] } {
  const placed: Placed[] = []
  const outdated: Proposal[] = []
  for (const proposal of proposals) {
    if (proposal.kind !== "edit" || proposal.find === undefined) continue
    const found = locate(text, proposal.find, proposal.before, proposal.after)
    if (found.status === "one") placed.push({ proposal, from: found.start, to: found.end })
    else outdated.push(proposal)
  }
  return { placed, outdated }
}

/** The open comments whose passage is still in the text, with where it is. */
export function attachedComments(text: string, annotations: Annotation[]): { annotation: Annotation; from: number; to: number }[] {
  const found: { annotation: Annotation; from: number; to: number }[] = []
  for (const annotation of annotations) {
    if (annotation.state !== "open") continue
    const at = locate(text, annotation.quote, annotation.before, annotation.after)
    if (at.status === "one") found.push({ annotation, from: at.start, to: at.end })
  }
  return found
}

export const setReviewData = StateEffect.define<ReviewData>()

export interface ReviewOptions {
  /** The data to start from: read when a view is made, so a remount of the editor shows it at once. */
  initial: () => ReviewData
  /** Told which proposals were just accepted or declined from the text, to forget them on the server. */
  onResolve: (ids: string[]) => void
  /** A dot in the margin beside a line with a comment; leave out where no note has comments, so no margin is spent. */
  gutter: boolean
}

const reviewField = StateField.define<ReviewData>({
  create: () => NO_REVIEW,
  update(value, tr) {
    for (const effect of tr.effects) if (effect.is(setReviewData)) return effect.value
    return value
  },
})

function icon(data: typeof Tick02Icon): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg")
  svg.setAttribute("viewBox", "0 0 24 24")
  svg.setAttribute("fill", "none")
  svg.setAttribute("aria-hidden", "true")
  for (const [tag, attrs] of data) {
    const child = document.createElementNS("http://www.w3.org/2000/svg", tag)
    for (const [name, value] of Object.entries(attrs)) if (name !== "key") child.setAttribute(name, String(value))
    svg.append(child)
  }
  return svg
}

class ChangeWidget extends WidgetType {
  readonly proposal: Proposal

  constructor(proposal: Proposal) {
    super()
    this.proposal = proposal
  }

  eq(other: ChangeWidget): boolean {
    return other.proposal.id === this.proposal.id && other.proposal.replace === this.proposal.replace && other.proposal.say === this.proposal.say
  }

  toDOM(view: EditorView): HTMLElement {
    const wrap = document.createElement("span")
    wrap.className = "sy-change"
    wrap.dataset.changeId = this.proposal.id
    if (this.proposal.say) wrap.title = this.proposal.say
    const added = document.createElement("span")
    added.className = "sy-change-add"
    added.textContent = this.proposal.replace ?? ""
    wrap.append(added)
    const button = (kind: "accept" | "decline", label: string, glyph: typeof Tick02Icon) => {
      const b = document.createElement("button")
      b.type = "button"
      b.className = `sy-change-btn sy-change-${kind}`
      b.setAttribute("aria-label", label)
      b.title = label
      b.append(icon(glyph))
      b.addEventListener("mousedown", (e) => e.preventDefault()) // keep the caret where it is
      b.addEventListener("click", () => (kind === "accept" ? acceptChanges(view, [this.proposal.id]) : declineChanges(view, [this.proposal.id])))
      wrap.append(b)
    }
    button("accept", "Accept this change", Tick02Icon)
    button("decline", "Decline this change", Cancel01Icon)
    return wrap
  }

  ignoreEvent(): boolean {
    return true // the buttons are ours; the editor does not treat a click on them as a click in the text
  }
}

// Who is told when proposals are accepted or declined from the text; one per editor, set by `reviewExtensions`.
const resolveFacet = Facet.define<(ids: string[]) => void, ((ids: string[]) => void) | undefined>({
  combine: (values) => values[0],
})

/** Applies these proposals to the text, in one change the user can undo, and tells the panel to forget them. */
export function acceptChanges(view: EditorView, ids: string[]): string[] {
  const { placed } = classify(view.state.doc.toString(), view.state.field(reviewField).proposals)
  const chosen = placed.filter((p) => ids.includes(p.proposal.id))
  if (chosen.length === 0) return []
  view.dispatch({
    changes: chosen.map((p) => ({ from: p.from, to: p.to, insert: p.proposal.replace ?? "" })),
    userEvent: "input.accept",
  })
  const done = chosen.map((p) => p.proposal.id)
  view.state.facet(resolveFacet)?.(done)
  return done
}

export function declineChanges(view: EditorView, ids: string[]): void {
  view.state.facet(resolveFacet)?.(ids)
}

/** The proposals in the text now that can still be accepted. */
export function pendingIds(state: EditorState): string[] {
  return classify(state.doc.toString(), state.field(reviewField).proposals).placed.map((p) => p.proposal.id)
}

/** How many proposals the editor holds for the open note, placed in the text or not. */
export function proposalCount(state: EditorState): number {
  return state.field(reviewField, false)?.proposals.length ?? 0
}

export function hasPending(state: EditorState): boolean {
  return state.field(reviewField, false) !== undefined && pendingIds(state).length > 0
}

class Dot extends GutterMarker {
  toDOM(): HTMLElement {
    const dot = document.createElement("span")
    dot.className = "sy-comment-dot"
    return dot
  }
}
const DOT = new Dot()

function decorate(state: EditorState): DecorationSet {
  const data = state.field(reviewField)
  const text = state.doc.toString()
  const ranges: Range<Decoration>[] = []
  for (const { proposal, from, to } of classify(text, data.proposals).placed) {
    ranges.push(Decoration.mark({ class: "sy-change-del" }).range(from, to))
    ranges.push(Decoration.widget({ widget: new ChangeWidget(proposal), side: 1 }).range(to))
  }
  for (const { from, to } of attachedComments(text, data.annotations)) {
    ranges.push(Decoration.mark({ class: "sy-comment-hl" }).range(from, to))
  }
  return Decoration.set(ranges, true)
}

const theme = EditorView.baseTheme({
  ".sy-change-del": {
    textDecoration: "line-through",
    backgroundColor: "color-mix(in srgb, var(--danger) 16%, transparent)",
  },
  ".sy-change": { whiteSpace: "pre-wrap" },
  ".sy-change-add": {
    backgroundColor: "color-mix(in srgb, var(--ok) 20%, transparent)",
    borderRadius: "var(--radius-sm, 3px)",
  },
  ".sy-change-btn": {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: "1.25rem",
    height: "1.25rem",
    marginInlineStart: "0.25rem",
    padding: "0",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm, 3px)",
    background: "var(--background)",
    color: "var(--muted-foreground)",
    cursor: "pointer",
    verticalAlign: "middle",
  },
  ".sy-change-btn svg": { width: "0.8rem", height: "0.8rem", stroke: "currentColor", strokeWidth: "2" },
  ".sy-change-accept:hover": { color: "var(--ok)", borderColor: "var(--ok)" },
  ".sy-change-decline:hover": { color: "var(--danger)", borderColor: "var(--danger)" },
  ".sy-comment-hl": { backgroundColor: "color-mix(in srgb, var(--chip-foreground) 26%, transparent)" },
  ".sy-comment-dot": {
    display: "inline-block",
    width: "0.4rem",
    height: "0.4rem",
    borderRadius: "50%",
    backgroundColor: "var(--chip-foreground)",
  },
  ".sy-comment-gutter": { minWidth: "0.9rem", textAlign: "center" },
})

/** The extensions for stylo's `extensions` prop. Memoize the array; it reconfigures the live editor when it changes. */
export function reviewExtensions({ initial, onResolve, gutter: withGutter }: ReviewOptions): Extension[] {
  const decorations = EditorView.decorations.compute(["doc", reviewField], decorate)
  const margin = gutter({
    class: "sy-comment-gutter",
    lineMarker(view, line) {
      const hit = attachedComments(view.state.doc.toString(), view.state.field(reviewField).annotations).some(
        ({ from, to }) => from <= line.to && to >= line.from
      )
      return hit ? DOT : null
    },
    lineMarkerChange: (update) => update.docChanged || update.transactions.some((tr) => tr.effects.some((e) => e.is(setReviewData))),
  })
  return [
    reviewField.init(() => initial()),
    decorations,
    theme,
    resolveFacet.of(onResolve),
    ...(withGutter ? [margin] : []),
  ]
}
