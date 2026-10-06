import { ArrowTurnBackwardIcon, Attachment01Icon } from "@hugeicons/core-free-icons"
import { Decoration, EditorView, ViewPlugin, WidgetType, type DecorationSet } from "@codemirror/view"
import { Facet, StateEffect, StateField, type EditorState, type Extension, type Range } from "@codemirror/state"
import type { CellMark, CellWidget } from "@damiro/stylo"

import { captureContext, locate } from "@/lib/passage-finder"
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

/** The open comments whose passage is still in the text, with where it is. Answers are not listed: they share their comment's passage. */
export function attachedComments(text: string, annotations: Annotation[]): { annotation: Annotation; from: number; to: number }[] {
  const found: { annotation: Annotation; from: number; to: number }[] = []
  for (const annotation of annotations) {
    if (annotation.state !== "open" || annotation.reply_to) continue
    const at = locate(text, annotation.quote, annotation.before, annotation.after)
    if (at.status === "one") found.push({ annotation, from: at.start, to: at.end })
  }
  return found
}

function passageOf(a: Annotation): { quote: string; before: string; after: string } {
  return { quote: a.quote, before: a.before, after: a.after }
}

/** Whether a change of hers, still waiting, covers any of `from`-`to`: the words are then drawn as that change, not also as a
 *  comment's highlight (two highlights on top of each other say nothing more than one). The comment stays: it opens on a
 *  click and keeps its dot in the margin. */
function underChange(placed: { from: number; to: number }[], from: number, to: number): boolean {
  return placed.some((p) => p.from < to && from < p.to)
}

/**
 * `attachedComments` with the comments on exactly the same words put together: they are one highlight, which carries
 * every thread's id (a click opens them all). Two highlights on one range would be drawn on top of each other, and
 * a click would reach only one of the threads.
 */
export function commentHighlights(text: string, annotations: Annotation[]): { annotations: Annotation[]; from: number; to: number }[] {
  const groups = new Map<string, { annotations: Annotation[]; from: number; to: number }>()
  for (const { annotation, from, to } of attachedComments(text, annotations)) {
    const group = groups.get(`${from}:${to}`)
    if (group) group.annotations.push(annotation)
    else groups.set(`${from}:${to}`, { annotations: [annotation], from, to })
  }
  return [...groups.values()]
}

/** The attributes of a highlight: the first thread's id (what a click on it opens first), and every id when there are several. */
function highlightAttributes(annotations: Annotation[]): Record<string, string> {
  const first = { "data-comment-id": annotations[0].id }
  return annotations.length > 1 ? { ...first, "data-comment-ids": annotations.map((a) => a.id).join(" ") } : first
}

export const setReviewData = StateEffect.define<ReviewData>()

export interface ReviewOptions {
  /** The data to start from: read when a view is made, so a remount of the editor shows it at once. */
  initial: () => ReviewData
  /** Told which proposals were just accepted or declined from the text, to forget them on the server. */
  onResolve: (ids: string[], accepted?: boolean) => void
  /** Told when the user clicks a highlighted passage: the comment's id and where the passage is on screen. */
  onOpenComment?: (id: string, rect: DOMRect, ids: string[]) => void
  /** The paperclip on a change: the user attached its words to the next chat message (docs/decisions/076). */
  onAttach?: (passage: { quote: string; before: string; after: string }) => void
  /** Told when the set of her applied edits (`accept` mode) changes, and whether the user has touched the note since. */
  onApplied?: (ids: string[], untouched: boolean) => void
  /** Told once when a view has been made with these extensions (after the current update, so it may dispatch): stylo
   *  makes its editor after a lazy chunk loads, long after the note and her edits may have arrived. */
  onReady?: (view: EditorView) => void
}

const reviewField = StateField.define<ReviewData>({
  create: () => NO_REVIEW,
  update(value, tr) {
    for (const effect of tr.effects) if (effect.is(setReviewData)) return effect.value
    return value
  },
})

/** One of her edits applied to the text in `accept` mode: where the new words are now, and what they replaced. */
interface Applied {
  id: string
  from: number
  to: number
  find: string
  say: string
}

interface AppliedState {
  items: Applied[]
  /** No change by the user (typing, undo, anything not her application) since the first edit was applied. */
  untouched: boolean
}

const addApplied = StateEffect.define<Applied[]>()
const endApplied = StateEffect.define<null>()
const restoreApplied = StateEffect.define<{ items: Applied[]; untouched: boolean }>()

/** Whether a change (in the old text's positions) reaches into the applied words; touching an edge does not. */
function reaches(item: Applied, from: number, to: number): boolean {
  if (item.from === item.to) return from <= item.from && to >= item.from // a deletion: anything at its point
  return from < item.to && to > item.from ? true : from === to && from > item.from && from < item.to
}

const appliedField = StateField.define<AppliedState>({
  create: () => ({ items: [], untouched: true }),
  update(value, tr) {
    const effects = tr.effects.filter((e) => e.is(addApplied) || e.is(endApplied) || e.is(restoreApplied))
    if (!tr.docChanged && effects.length === 0) return value
    let items = value.items
    if (tr.docChanged && items.length > 0) {
      const kept: Applied[] = []
      for (const item of items) {
        let hit = false
        tr.changes.iterChangedRanges((fromA, toA) => {
          if (reaches(item, fromA, toA)) hit = true
        })
        if (!hit) kept.push({ ...item, from: tr.changes.mapPos(item.from, 1), to: tr.changes.mapPos(item.to, -1) })
      }
      items = kept
    }
    let adding = false
    let restored: boolean | null = null
    for (const effect of effects) {
      if (effect.is(endApplied)) items = []
      else if (effect.is(restoreApplied)) {
        items = [...items, ...effect.value.items]
        restored = effect.value.untouched
      }
      else if (effect.is(addApplied)) {
        adding = true
        items = [...items, ...effect.value]
      }
    }
    if (items.length === 0) return value.items.length === 0 && value.untouched ? value : { items, untouched: true }
    return { items, untouched: restored ?? (value.untouched && !(tr.docChanged && !adding)) }
  },
})

function icon(data: typeof Attachment01Icon): SVGSVGElement {
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

class UndoWidget extends WidgetType {
  readonly item: Applied

  constructor(item: Applied) {
    super()
    this.item = item
  }

  eq(other: UndoWidget): boolean {
    return other.item.id === this.item.id && other.item.say === this.item.say
  }

  toDOM(view: EditorView): HTMLElement {
    const anchor = document.createElement("span")
    anchor.className = "sy-anchor"
    const tab = document.createElement("span")
    tab.className = "sy-tab"
    anchor.append(tab)
    const b = document.createElement("button")
    b.type = "button"
    b.className = "sy-applied-undo"
    b.setAttribute("aria-label", "Undo this change")
    b.title = this.item.say ? `Undo: ${this.item.say}` : "Undo this change"
    b.append(icon(ArrowTurnBackwardIcon)) // an icon, not a word: the label is its title and its accessible name
    tab.append(b)
    b.addEventListener("mousedown", (e) => e.preventDefault()) // keep the caret where it is
    b.addEventListener("click", () => {
      const now = view.state.field(appliedField).items.find((i) => i.id === this.item.id)
      if (!now) return
      view.dispatch({ changes: { from: now.from, to: now.to, insert: now.find }, userEvent: "input.undo-applied" })
    })
    return anchor
  }

  ignoreEvent(): boolean {
    return true
  }
}

// Told when her applied edits change; one per editor, set by `reviewExtensions`.
const appliedFacet = Facet.define<(ids: string[], untouched: boolean) => void, ((ids: string[], untouched: boolean) => void) | undefined>({
  combine: (values) => values[0],
})

const appliedListener = EditorView.updateListener.of((update) => {
  const before = update.startState.field(appliedField)
  const after = update.state.field(appliedField)
  if (before === after) return
  const ended = update.transactions.some((tr) => tr.effects.some((e) => e.is(endApplied)))
  const gone = before.items.filter((b) => !after.items.some((a) => a.id === b.id)).map((i) => i.id)
  if (!ended && gone.length > 0) update.view.state.facet(resolveFacet)?.(gone) // undone or edited over: the proposal is forgotten
  const ids = after.items.map((i) => i.id)
  if (ended || gone.length > 0 || ids.length !== before.items.length || after.untouched !== before.untouched) {
    update.view.state.facet(appliedFacet)?.(ids, after.untouched)
  }
})

/** The ids of her edits applied to the text now, and whether the user has left the note alone since. */
export function appliedState(state: EditorState): { ids: string[]; untouched: boolean } {
  const { items, untouched } = state.field(appliedField)
  return { ids: items.map((i) => i.id), untouched }
}

/**
 * Applies these proposals to the text (`accept` mode, docs/decisions/072) as one undoable change, marks the new words,
 * and keeps the proposals pending on the server: they are forgotten when the note is saved (`clearApplied`) or when the
 * words are undone or edited over. Two proposals on one passage: the earlier is applied, the other waits.
 */
export function applyProposals(view: EditorView, ids: string[]): string[] {
  const { placed } = classify(view.state.doc.toString(), view.state.field(reviewField).proposals)
  const chosen: Placed[] = []
  for (const p of placed) {
    if (!ids.includes(p.proposal.id)) continue
    if (!chosen.some((c) => p.from < c.to && c.from < p.to)) chosen.push(p)
  }
  if (chosen.length === 0) return []
  chosen.sort((a, b) => a.from - b.from)
  let shift = 0
  const items = chosen.map((p) => {
    const replace = p.proposal.replace ?? ""
    const from = p.from + shift
    shift += replace.length - (p.to - p.from)
    return { id: p.proposal.id, from, to: from + replace.length, find: p.proposal.find ?? "", say: p.proposal.say }
  })
  view.dispatch({
    changes: chosen.map((p) => ({ from: p.from, to: p.to, insert: p.proposal.replace ?? "" })),
    effects: addApplied.of(items),
    userEvent: "input.apply",
  })
  return items.map((i) => i.id)
}

/**
 * A new editor was made over the text that already holds her applied edits (another editing surface, or back from read
 * mode): draws the marks again for the edits in `ids`, finding each one's new words in the text by their surroundings
 * (the finder the tracked changes use), and keeps whether the user had touched the note. An edit whose new words are
 * gone or cannot be told apart is not marked; one that is marked already is not marked twice.
 */
export function restoreAppliedMarks(view: EditorView, proposals: Proposal[], ids: string[], untouched: boolean): void {
  const text = view.state.doc.toString()
  const have = view.state.field(appliedField).items
  const items: Applied[] = []
  for (const p of proposals) {
    if (!ids.includes(p.id) || p.kind !== "edit" || !p.replace || have.some((h) => h.id === p.id)) continue
    const at = locate(text, p.replace, p.before, p.after)
    if (at.status === "one") items.push({ id: p.id, from: at.start, to: at.end, find: p.find ?? "", say: p.say })
  }
  if (items.length > 0) view.dispatch({ effects: restoreApplied.of({ items, untouched }) })
}

/** The note was saved: the marks end and the text stays. Returns the ids that were applied, for the panel to forget. */
export function clearApplied(view: EditorView): string[] {
  const ids = view.state.field(appliedField).items.map((i) => i.id)
  if (ids.length > 0) view.dispatch({ effects: endApplied.of(null) })
  return ids
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
    // The buttons sit in a small tab above the words, joined to them by a short line, not in the line of text: after a
    // sentence a bare ✕ reads as part of it and says nothing of what it would close. Their words are drawn by the style
    // (`data-label`), so they are not part of the note's text when it is read or copied.
    const tab = document.createElement("span")
    tab.className = "sy-tab"
    wrap.append(added, tab)
    const button = (kind: "accept" | "decline", label: string, word: string) => {
      const b = document.createElement("button")
      b.type = "button"
      b.className = `sy-change-btn sy-change-${kind}`
      b.setAttribute("aria-label", label)
      b.title = label
      b.dataset.label = word
      b.addEventListener("mousedown", (e) => e.preventDefault()) // keep the caret where it is
      b.addEventListener("click", () => (kind === "accept" ? acceptChanges(view, [this.proposal.id]) : declineChanges(view, [this.proposal.id])))
      tab.append(b)
    }
    // The paperclip: attach these words to the next chat message, so Sam knows which part is meant.
    const clip = document.createElement("button")
    clip.type = "button"
    clip.className = "sy-change-btn sy-change-attach"
    clip.setAttribute("aria-label", "Attach to your message")
    clip.title = "Attach to your message"
    clip.append(icon(Attachment01Icon))
    clip.addEventListener("mousedown", (e) => e.preventDefault())
    clip.addEventListener("click", () => view.state.facet(attachFacet)?.({ quote: this.proposal.find ?? "", before: this.proposal.before ?? "", after: this.proposal.after ?? "" }))
    if (view.state.facet(attachFacet) && this.proposal.find) tab.append(clip)
    button("accept", "Accept this change", "Accept")
    button("decline", "Decline this change", "Decline")
    return wrap
  }

  ignoreEvent(): boolean {
    return true // the buttons are ours; the editor does not treat a click on them as a click in the text
  }
}

/** A small paperclip above the end of a commented passage, shown when the words are pointed at: one click attaches them to the
 *  next chat message, without opening the comment first (docs/decisions/076). */
class ClipWidget extends WidgetType {
  readonly id: string
  readonly passage: { quote: string; before: string; after: string }

  constructor(id: string, passage: { quote: string; before: string; after: string }) {
    super()
    this.id = id
    this.passage = passage
  }

  eq(other: ClipWidget): boolean {
    return other.id === this.id && other.passage.quote === this.passage.quote
  }

  toDOM(view: EditorView): HTMLElement {
    const anchor = document.createElement("span")
    anchor.className = "sy-anchor"
    const b = document.createElement("button")
    b.type = "button"
    b.className = "sy-clip"
    b.setAttribute("aria-label", "Attach to your message")
    b.title = "Attach to your message"
    b.append(icon(Attachment01Icon))
    b.addEventListener("mousedown", (e) => e.preventDefault()) // keep the caret where it is
    b.addEventListener("click", (e) => {
      e.stopPropagation() // not a click on the commented words, which would open the comment
      view.state.facet(attachFacet)?.(this.passage)
    })
    anchor.append(b)
    return anchor
  }

  ignoreEvent(): boolean {
    return true
  }
}

const attachFacet = Facet.define<(passage: { quote: string; before: string; after: string }) => void, ((passage: { quote: string; before: string; after: string }) => void) | undefined>({
  combine: (values) => values[0],
})

const openCommentFacet = Facet.define<(id: string, rect: DOMRect, ids: string[]) => void, ((id: string, rect: DOMRect, ids: string[]) => void) | undefined>({
  combine: (values) => values[0],
})

// Who is told when proposals are accepted or declined from the text; one per editor, set by `reviewExtensions`.
// `accepted`: the user accepted them (so the comments they answered are settled), not declined or undone.
const resolveFacet = Facet.define<(ids: string[], accepted?: boolean) => void, ((ids: string[], accepted?: boolean) => void) | undefined>({
  combine: (values) => values[0],
})

/** Applies these proposals to the text, in one change the user can undo, and tells the panel to forget them. */
export function acceptChanges(view: EditorView, ids: string[]): string[] {
  const { placed } = classify(view.state.doc.toString(), view.state.field(reviewField).proposals)
  // Two proposals on one passage cannot both be applied: the earlier one is, the other stays waiting (ADR 070).
  const chosen: Placed[] = []
  for (const p of placed) {
    if (ids.includes(p.proposal.id) && !chosen.some((c) => p.from < c.to && c.from < p.to)) chosen.push(p)
  }
  if (chosen.length === 0) return []
  view.dispatch({
    changes: chosen.map((p) => ({ from: p.from, to: p.to, insert: p.proposal.replace ?? "" })),
    userEvent: "input.accept",
  })
  const done = chosen.map((p) => p.proposal.id)
  view.state.facet(resolveFacet)?.(done, true)
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

/** What the user has selected, for a new comment: the words, the text around them and where they are on screen. */
export interface CommentTarget {
  quote: string
  before: string
  after: string
  rect: DOMRect
}

/**
 * The selection as a comment target, or `null` when nothing is selected. `anchor` is the screen rectangle to open the
 * box beside when the caller knows it better than the editor does: stylo gives one for words in a table cell, where
 * `coordsAtPos` can only answer with the table's edge.
 */
export function selectionTarget(view: EditorView, anchor?: DOMRect): CommentTarget | null {
  const { from, to } = view.state.selection.main
  if (from === to) return null
  const text = view.state.doc.toString()
  const [before, after] = captureContext(text, from, to)
  const start = view.coordsAtPos(from)
  const end = view.coordsAtPos(to)
  const box = view.dom.getBoundingClientRect()
  const rect = anchor ?? (start && end ? new DOMRect(Math.min(start.left, end.left), start.top, Math.abs(end.right - start.left) || 1, end.bottom - start.top) : box)
  return { quote: text.slice(from, to), before, after, rect }
}

export function hasPending(state: EditorState): boolean {
  return state.field(reviewField, false) !== undefined && pendingIds(state).length > 0
}

/**
 * What stylo draws inside table cells (its `inPlace.cellMarks`, 0.20): the same highlights `decorate` gives words
 * outside a table (a decoration cannot reach a cell), as marks in document positions. The words of a change she
 * proposed are struck (the replacement and its buttons are `cellWidgets`); each open comment is marked with its
 * author's colour and its id (a click on it opens the thread) and its cell gets the author's dot; an edit she has
 * applied is marked as applied. Stylo ignores a mark that is not inside a cell, where `decorate` has already drawn it.
 */
export function cellMarks(state: EditorState): CellMark[] {
  const data = state.field(reviewField, false)
  if (!data) return []
  const text = state.doc.toString()
  const placed = classify(text, data.proposals).placed
  const struck: CellMark[] = placed.map(({ from, to }) => ({ from, to, class: "sy-change-del" }))
  const marks: CellMark[] = commentHighlights(text, data.annotations).map(({ annotations, from, to }) => {
    const by = annotations.every((a) => a.author === "persona") ? "persona" : "user"
    // Not `sy-by-*`: that class also draws the margin dot of a line, which a cell must not get on every highlighted word.
    const base = by === "persona" ? "sy-comment-hl sy-hl-persona" : "sy-comment-hl"
    return { from, to, class: underChange(placed, from, to) ? `${base} sy-under-change` : base, attributes: highlightAttributes(annotations), cellClass: `sy-cell-by-${by}` }
  })
  for (const item of state.field(appliedField).items) {
    if (item.from < item.to) marks.push({ from: item.from, to: item.to, class: "sy-applied", ...(item.say ? { attributes: { title: item.say } } : {}) })
  }
  return [...struck, ...marks]
}

/**
 * The elements stylo draws inside table cells (its `inPlace.cellWidgets`, 0.21): what `decorate` gives a change outside
 * a table as a widget, which a decoration cannot do in a cell. A pending change's replacement with its Accept and
 * Decline, a change applied in `accept` mode with its Undo, each right after the words it belongs to. Positions are
 * worked out from the state given, every time: typing in a table re-pads its columns and moves every position. The key
 * is everything the element draws, since stylo repaints a cell only when it changes. Stylo ignores a position that is not
 * inside a cell, where `decorate` has already put the widget; its buttons are hidden while the cell is being edited.
 */
export function cellWidgets(state: EditorState): CellWidget[] {
  const data = state.field(reviewField, false)
  if (!data) return []
  const widgets: CellWidget[] = classify(state.doc.toString(), data.proposals).placed.map(({ proposal, to }) => ({
    pos: to,
    key: `change:${proposal.id}:${proposal.say}:${proposal.replace ?? ""}`,
    toDOM: (view) => new ChangeWidget(proposal).toDOM(view),
  }))
  for (const item of state.field(appliedField).items) {
    widgets.push({ pos: item.to, key: `applied:${item.id}:${item.say}`, toDOM: (view) => new UndoWidget(item).toDOM(view) })
  }
  if (state.facet(attachFacet)) {
    const placed = classify(state.doc.toString(), data.proposals).placed
    for (const { annotations, from, to } of commentHighlights(state.doc.toString(), data.annotations)) {
      if (underChange(placed, from, to)) continue
      const widget = new ClipWidget(annotations[0].id, passageOf(annotations[0]))
      widgets.push({ pos: to, key: `clip:${annotations[0].id}:${annotations[0].quote}`, toDOM: (view) => widget.toDOM(view) })
    }
  }
  return widgets
}

function decorate(state: EditorState): DecorationSet {
  const data = state.field(reviewField)
  const text = state.doc.toString()
  const ranges: Range<Decoration>[] = []
  const placed = classify(text, data.proposals).placed
  for (const { proposal, from, to } of placed) {
    ranges.push(Decoration.mark({ class: "sy-change-del" }).range(from, to))
    ranges.push(Decoration.widget({ widget: new ChangeWidget(proposal), side: 1 }).range(to))
  }
  for (const item of state.field(appliedField).items) {
    if (item.from < item.to) ranges.push(Decoration.mark({ class: "sy-applied", attributes: item.say ? { title: item.say } : undefined }).range(item.from, item.to))
    ranges.push(Decoration.widget({ widget: new UndoWidget(item), side: 1 }).range(item.to))
  }
  for (const { annotations, from, to } of commentHighlights(text, data.annotations)) {
    const by = annotations.every((a) => a.author === "persona") ? "sy-by-persona" : "sy-by-user"
    const under = underChange(placed, from, to) ? " sy-under-change" : ""
    ranges.push(Decoration.mark({ class: `sy-comment-hl ${by}${under}`, attributes: highlightAttributes(annotations) }).range(from, to))
    if (!under && state.facet(attachFacet)) ranges.push(Decoration.widget({ widget: new ClipWidget(annotations[0].id, passageOf(annotations[0])), side: 1 }).range(to))
    // A dot beside each line the comment touches, drawn in the line's own left space so the editor never changes width.
    for (let line = state.doc.lineAt(from); ; line = state.doc.line(line.number + 1)) {
      ranges.push(Decoration.line({ class: `sy-comment-line ${by}` }).range(line.from))
      if (line.to >= to) break
    }
  }
  return Decoration.set(ranges, true)
}

const theme = EditorView.baseTheme({
  ".sy-change-del": {
    textDecoration: "line-through",
    backgroundColor: "color-mix(in srgb, var(--danger) 16%, transparent)",
  },
  ".sy-change-add": {
    backgroundColor: "color-mix(in srgb, var(--ok) 20%, transparent)",
  },
  ".sy-change": { whiteSpace: "pre-wrap", position: "relative" },
  ".sy-anchor": { position: "relative" },
  // The tab with the buttons, above the words it is about: a short line joins it to them.
  ".sy-tab": {
    position: "absolute",
    insetInlineStart: "0",
    bottom: "calc(100% + 0.4rem)",
    zIndex: "5",
    display: "inline-flex",
    alignItems: "stretch",
    whiteSpace: "nowrap",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm, 3px)",
    background: "var(--background)",
    boxShadow: "0 1px 3px color-mix(in srgb, var(--foreground) 14%, transparent)",
    userSelect: "none",
  },
  ".sy-tab::after": {
    content: '""',
    position: "absolute",
    insetInlineStart: "0.7rem",
    top: "100%",
    width: "1px",
    height: "0.4rem",
    background: "var(--border)",
  },
  ".sy-tab button": {
    padding: "0 0.5rem",
    border: "0",
    background: "transparent",
    color: "var(--muted-foreground)",
    font: "500 0.6875rem/1.3rem var(--font-sans, system-ui, sans-serif)",
    cursor: "pointer",
  },
  ".sy-tab button::before": { content: "attr(data-label)" },
  ".sy-tab button svg": { width: "0.85rem", height: "0.85rem", stroke: "currentColor", strokeWidth: "2", verticalAlign: "middle" },
  // The paperclip above a commented passage: small and quiet until it is pointed at.
  ".sy-clip": {
    position: "absolute",
    insetInlineEnd: "0",
    bottom: "calc(100% - 0.15rem)",
    zIndex: "4",
    display: "grid",
    placeItems: "center",
    width: "1.1rem",
    height: "1.1rem",
    padding: "0",
    border: "0",
    borderRadius: "var(--radius-sm, 3px)",
    background: "var(--background)",
    color: "var(--muted-foreground)",
    opacity: "0",
    visibility: "hidden",
    transition: "opacity 0.12s, visibility 0s 0.3s",
    cursor: "pointer",
    userSelect: "none",
  },
  // Out of sight until the commented words (or the paperclip itself) are pointed at or reached by keyboard, so it does not sit on
  // the line above all the time.
  ".sy-comment-hl:hover ~ .sy-anchor .sy-clip, .sy-anchor:hover .sy-clip, .sy-clip:focus-visible": { opacity: "1", visibility: "visible", transition: "opacity 0.12s, visibility 0s" },
  ".sy-clip:hover": { opacity: "1", background: "var(--accent)", color: "var(--foreground)" },
  ".sy-clip svg": { width: "0.75rem", height: "0.75rem", stroke: "currentColor", strokeWidth: "2" },
  // The Undo tab of an applied edit is quiet like the paperclip: out of sight until its words (or the tab) are pointed at or reached
  // by keyboard, so it is not always on top of the line above.
  // `visibility`, not just opacity: while hidden it takes no clicks, so the line above can be clicked; it hides after a short delay, so the
  // pointer can travel from the words up to it.
  ".sy-anchor .sy-tab": { opacity: "0", visibility: "hidden", transition: "opacity 0.12s, visibility 0s 0.3s" },
  ".sy-applied:hover ~ .sy-anchor .sy-tab, .sy-anchor .sy-tab:hover, .sy-anchor .sy-tab:focus-within": { opacity: "1", visibility: "visible", transition: "opacity 0.12s, visibility 0s" },
  ".sy-tab button + button": { borderInlineStart: "1px solid var(--border)" },
  ".sy-tab button:hover": { background: "var(--accent)" },


  ".sy-applied": {
    backgroundColor: "color-mix(in srgb, var(--ok) 20%, transparent)",
  },


  ".sy-applied-undo:hover": { color: "var(--danger)", borderColor: "var(--danger)" },
  ".sy-change-accept:hover": { color: "var(--ok)", borderColor: "var(--ok)" },
  ".sy-change-decline:hover": { color: "var(--danger)", borderColor: "var(--danger)" },
  // A light tint, so the text stays readable on it (measured: 14% keeps the note's text above 4.2:1 in light and 5.7:1 in dark);
  // the underline carries what the tint no longer does. The user's comments are amber, hers the brand blue.
  ".sy-comment-hl": {
    backgroundColor: "color-mix(in srgb, var(--chip-foreground) 14%, transparent)",
    boxShadow: "inset 0 -1.5px 0 color-mix(in srgb, var(--chip-foreground) 60%, transparent)",
  },
  ".sy-comment-hl.sy-by-persona, .sy-comment-hl.sy-hl-persona": {
    backgroundColor: "color-mix(in srgb, var(--brand) 14%, transparent)",
    boxShadow: "inset 0 -1.5px 0 color-mix(in srgb, var(--brand) 60%, transparent)",
  },  // After the authors own colours, which would otherwise win: words under a waiting change are drawn as the change.
  ".sy-comment-hl.sy-under-change.sy-under-change": { backgroundColor: "transparent", boxShadow: "none" },

  // The dot beside a commented line is drawn in the line's own left space; a line holding both authors shows two.
  ".cm-line.sy-comment-line": { position: "relative" },
  ".sy-by-user::before, .sy-by-persona::after": {
    content: '""',
    position: "absolute",
    insetInlineStart: "-0.7rem",
    top: "0.7em",
    width: "0.4rem",
    height: "0.4rem",
    borderRadius: "50%",
  },
  ".sy-by-user::before": { backgroundColor: "var(--chip-foreground)" },
  ".sy-by-persona::after": { backgroundColor: "var(--brand)" },
  ".sy-by-user.sy-by-persona::before": { insetInlineStart: "-1.2rem" },
  // A table cell holding a comment shows the author's dot in its corner (the cell is stylo's, so the host's class on it).
  ".sy-cell-by-user, .sy-cell-by-persona": { position: "relative" },
  ".sy-cell-by-user::before, .sy-cell-by-persona::after": {
    content: '""',
    position: "absolute",
    top: "0.3rem",
    insetInlineEnd: "0.3rem",
    width: "0.4rem",
    height: "0.4rem",
    borderRadius: "50%",
  },
  ".sy-cell-by-user::before": { backgroundColor: "var(--chip-foreground)" },
  ".sy-cell-by-persona::after": { backgroundColor: "var(--brand)" },
  ".sy-cell-by-user.sy-cell-by-persona::before": { insetInlineEnd: "0.9rem" },
})

/** The extensions for stylo's `extensions` prop. Memoize the array; it reconfigures the live editor when it changes. */
export function reviewExtensions({ initial, onResolve, onOpenComment, onAttach, onApplied, onReady }: ReviewOptions): Extension[] {
  const decorations = EditorView.decorations.compute(["doc", reviewField, appliedField], decorate)
  return [
    reviewField.init(() => initial()),
    decorations,
    theme,
    resolveFacet.of(onResolve),
    appliedField,
    appliedListener,
    ...(onApplied ? [appliedFacet.of(onApplied)] : []),
    ...(onReady
      ? [
          ViewPlugin.define((view) => {
            queueMicrotask(() => onReady(view))
            return {}
          }),
        ]
      : []),
    ...(onOpenComment ? [openCommentFacet.of(onOpenComment)] : []),
    ...(onAttach ? [attachFacet.of(onAttach)] : []),
    // A listener on the editor's own element rather than `domEventHandlers`: a click inside a table cell (stylo's own
    // contenteditable DOM) is not passed to the editor's handlers, but it still reaches the element around them (stylo
    // 0.20.1 keeps the pressed word in place until after the release, so the click is sent there too).
    ViewPlugin.define((view) => {
      const click = (event: MouseEvent) => {
        const hit = (event.target as HTMLElement | null)?.closest?.<HTMLElement>(".sy-comment-hl")
        const id = hit?.dataset.commentId
        // Every thread on these words, the first one first.
        const ids = hit?.dataset.commentIds?.split(" ").filter(Boolean) ?? (id ? [id] : [])
        if (hit && id) view.state.facet(openCommentFacet)?.(id, hit.getBoundingClientRect(), ids) // the click still places the caret
      }
      view.dom.addEventListener("click", click)
      return { destroy: () => view.dom.removeEventListener("click", click) }
    }),
  ]
}
