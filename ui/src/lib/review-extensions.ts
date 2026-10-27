import { ArrowTurnBackwardIcon, Attachment01Icon } from "@hugeicons/core-free-icons"
import { Decoration, EditorView, ViewPlugin, WidgetType, type DecorationSet } from "@codemirror/view"
import { Facet, StateEffect, StateField, type EditorState, type Extension, type Range, type Transaction } from "@codemirror/state"
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
    // The same small square as the paperclip, in the same place (right edge on the end of the words, just above them).
    const anchor = document.createElement("span")
    anchor.className = "sy-anchor"
    const b = document.createElement("button")
    b.type = "button"
    b.className = "sy-clip sy-applied-undo"
    b.setAttribute("aria-label", "Undo this change")
    b.title = this.item.say ? `Undo: ${this.item.say}` : "Undo this change"
    b.append(icon(ArrowTurnBackwardIcon)) // an icon, not a word: the label is its title and its accessible name
    anchor.append(b)
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

// A change that is applied is shown, not swapped (docs/decisions/072, amendment 2026-10-24): the words it replaced are drawn for a
// moment and shrink away, then the new words are typed in. The text is final from the first frame; only what is drawn is staged,
// so undo, the applied marks and the save see one change, and a frame that changes no text is not reported as an edit.

/** One applied change being shown: where its new words are now, and the words they replaced. */
interface Reveal {
  from: number
  to: number
  old: string
  /** For one of several stretches typed in one after another (the new cells of a table): when this one starts, and how long all of
   *  them take together, in unscaled milliseconds, so that the whole run is sped up as one. */
  after?: number
  total?: number
  /** Not yet placed: a table that was replaced, as it was (`find`) and where it was in the text before the change. The cells that
   *  are new are looked for in the text as the change left it, since the editor may have re-padded the table's columns. */
  table?: { find: string; from: number; to: number }
}

interface RevealState {
  items: Reveal[]
  /** The time of the first frame, `null` until it comes. */
  startedAt: number | null
  now: number
}

const REMOVE_MS = 4 // per character taken away
const TYPE_MS = 10 // per character typed in
const REVEAL_MAX_MS = 900 // a long change is sped up to fit

const startReveal = StateEffect.define<Reveal[]>()
/** One frame of the reveal, at this time in milliseconds (`performance.now()`). */
export const tickReveal = StateEffect.define<number>()

/** How much of the old words is left and how much of the new is typed at `elapsed` ms, or `null` when the change is shown. */
function revealProgress(item: Reveal, elapsed: number): { oldLeft: number; typed: number } | null {
  const removing = item.old.length * REMOVE_MS
  const full = removing + (item.to - item.from) * TYPE_MS
  const t = elapsed * Math.max(1, (item.total ?? full) / REVEAL_MAX_MS) - (item.after ?? 0)
  if (t >= full) return null
  if (t < 0) return { oldLeft: item.old.length, typed: 0 }
  if (t < removing) return { oldLeft: item.old.length - Math.floor(t / REMOVE_MS), typed: 0 }
  return { oldLeft: 0, typed: Math.floor((t - removing) / TYPE_MS) }
}

/** The new cells of a table this transaction replaced, typed in one after another (`Reveal.after`, `Reveal.total`). */
function typedCells(tr: Transaction, table: { find: string; from: number; to: number }): Reveal[] {
  const from = tr.changes.mapPos(table.from, -1)
  const to = tr.changes.mapPos(table.to, 1)
  const cells = newTableCells(table.find, tr.newDoc.sliceString(from, to))
  const total = cells.reduce((sum, cell) => sum + (cell.to - cell.from) * TYPE_MS, 0)
  let after = 0
  return cells.map((cell) => {
    const item = { from: from + cell.from, to: from + cell.to, old: "", after, total }
    after += (cell.to - cell.from) * TYPE_MS
    return item
  })
}

const NO_REVEAL: RevealState = { items: [], startedAt: null, now: 0 }

const revealField = StateField.define<RevealState>({
  create: () => NO_REVEAL,
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(startReveal)) return { items: effect.value.flatMap((item) => (item.table ? typedCells(tr, item.table) : [item])), startedAt: null, now: 0 }
    }
    if (tr.docChanged) return NO_REVEAL // the text was changed some other way (typing, undo): never draw over it
    for (const effect of tr.effects) {
      if (!effect.is(tickReveal)) continue
      const startedAt = value.startedAt ?? effect.value
      const items = value.items.filter((item) => revealProgress(item, effect.value - startedAt) !== null)
      return { items, startedAt, now: effect.value }
    }
    return value
  },
})

class RemovedWidget extends WidgetType {
  readonly text: string

  constructor(text: string) {
    super()
    this.text = text
  }

  eq(other: RemovedWidget): boolean {
    return other.text === this.text
  }

  toDOM(): HTMLElement {
    const gone = document.createElement("span")
    gone.className = "sy-change-del sy-reveal-old" // struck through like the words of a tracked change
    gone.textContent = this.text
    return gone
  }

  ignoreEvent(): boolean {
    return true
  }
}

/** What each change being shown has drawn right now: how much of the old words is left and how much of the new is typed. */
function revealFrame(state: EditorState): { item: Reveal; oldLeft: number; typed: number }[] {
  const { items, startedAt, now } = state.field(revealField, false) ?? NO_REVEAL
  return items.flatMap((item) => {
    const progress = revealProgress(item, startedAt === null ? 0 : now - startedAt)
    return progress ? [{ item, ...progress }] : []
  })
}

function revealDecorations(state: EditorState): DecorationSet {
  const ranges: Range<Decoration>[] = []
  for (const { item, oldLeft, typed } of revealFrame(state)) {
    if (oldLeft > 0) ranges.push(Decoration.widget({ widget: new RemovedWidget(item.old.slice(0, oldLeft)), side: -1 }).range(item.from))
    if (typed > 0) ranges.push(Decoration.mark({ class: "sy-reveal-new" }).range(item.from, item.from + typed))
    if (item.from + typed < item.to) ranges.push(Decoration.replace({}).range(item.from + typed, item.to))
  }
  return Decoration.set(ranges, true)
}

/** The same frame for the words inside table cells (stylo's `cellMarks`, which a decoration cannot reach): the typed words are
 *  marked and the others hidden. Stylo ignores a mark that is not inside a cell, where `revealDecorations` has drawn it. */
export function revealCellMarks(state: EditorState): CellMark[] {
  const frame = revealFrame(state)
  if (frame.length === 0) return []
  const text = state.doc.toString()
  // Stylo marks the whole cell for a mark that covers no visible character (only `**`, a bracket or a space), which would hide
  // or tint all of it for a frame or two: such a stretch is left unmarked until a visible character joins it. A range can run
  // over many cells (a draft's whole text), so each cell's part of it is asked on its own.
  const pieces = (from: number, to: number, cls: string): CellMark[] => {
    const marks: CellMark[] = []
    const add = (start: number, end: number) => {
      if (start < end && !/^[\s*_~`[\]|\\]*$/.test(text.slice(start, end))) marks.push({ from: start, to: end, class: cls })
    }
    let start = from
    for (const cut of text.slice(from, to).matchAll(/(?<!\\)\||\n/g)) {
      add(start, from + cut.index)
      start = from + cut.index + 1
    }
    add(start, to)
    return marks
  }
  return frame.flatMap(({ item, typed }) => [
    ...pieces(item.from, item.from + typed, "sy-reveal-new"),
    ...pieces(item.from + typed, item.to, "sy-reveal-hidden"),
  ])
}

/** The old words still drawn, for a cell (stylo's `cellWidgets`); the key holds what is drawn, so a cell is repainted as they shrink. */
function revealCellWidgets(state: EditorState): CellWidget[] {
  return revealFrame(state).flatMap(({ item, oldLeft }) => {
    if (oldLeft === 0) return []
    const text = item.old.slice(0, oldLeft)
    return [{ pos: item.from, key: `reveal:${item.from}:${text}`, toDOM: () => new RemovedWidget(text).toDOM() }]
  })
}

// Sends a frame while a reveal is on; the frames change no text. One frame is asked for at a time: the update that a frame
// causes asks for the next.
const revealFrames = ViewPlugin.define((view) => {
  let frame = 0
  const step = (time: number) => {
    frame = 0
    view.dispatch({ effects: tickReveal.of(time) })
  }
  return {
    update(update) {
      if (frame === 0 && update.state.field(revealField).items.length > 0) frame = requestAnimationFrame(step)
    },
    destroy() {
      cancelAnimationFrame(frame)
    },
  }
})

/** The reveal's field, its drawing and its frame loop: what any editor needs to show a change being typed in. */
const revealExtensions: Extension[] = [revealField, EditorView.decorations.compute([revealField], revealDecorations), revealFrames]

/**
 * For an editor that holds a new-note draft (docs/decisions/072, amendment 2026-10-26): the first time it opens, its whole text
 * is typed in, with nothing to take away. `take` is asked once, as the editor is made, and says whether this opening is the
 * first one. Not shown for an empty text or when the user asked for less motion. A table in the text is hidden until the typing
 * reaches it, then typed in cell by cell through `revealCellMarks`, which the editor must pass to stylo as `inPlace.cellMarks`.
 */
export function revealOnOpen(take: () => boolean): Extension[] {
  return [
    revealExtensions,
    // A table is drawn whole when the typing reaches it and gets its cell marks a frame later: until then it stays invisible.
    EditorView.contentAttributes.compute([revealField], (state) => ({ class: state.field(revealField).items.length > 0 ? "sy-reveal-draft" : "" })),
    ViewPlugin.define((view) => {
      let gone = false
      queueMicrotask(() => {
        // Before the first paint, so the whole text is never drawn first; the editor may be gone by now.
        const length = view.state.doc.length
        if (gone || length === 0 || !take()) return
        if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return
        view.dispatch({ effects: startReveal.of([{ from: 0, to: length, old: "" }]) })
      })
      return {
        destroy() {
          gone = true
        },
      }
    }),
  ]
}

/** Where each of these changes (sorted, none overlapping) lands in the new text once all are applied. */
function landing(chosen: Placed[]): Landed[] {
  let shift = 0
  return chosen.map(({ proposal, from, to }) => {
    const replace = proposal.replace ?? ""
    const start = from + shift
    shift += replace.length - (to - from)
    return { proposal, from: start, to: start + replace.length, was: { from, to } }
  })
}

/** A change as it lands in the new text, with where its old words were before the change. */
interface Landed {
  proposal: Proposal
  from: number
  to: number
  was: { from: number; to: number }
}

/** The effect that shows these applied changes as they go in; it shows none when the user asked for less motion. A change of a
 *  whole table cannot take its old table away (a rendered table cannot hide half a row): the old rows go at once and only the
 *  cells that are new are typed in. */
function revealing(landed: Landed[]): StateEffect<Reveal[]> {
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return startReveal.of([])
  return startReveal.of(
    landed.flatMap(({ proposal, from, to, was }): Reveal[] => {
      const old = proposal.find ?? ""
      if (old === (proposal.replace ?? "")) return []
      if (isTableChange(proposal)) return [{ from, to, old, table: { find: old, ...was } }]
      return [{ from, to, old }]
    })
  )
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
  const landed = landing(chosen)
  const items = landed.map(({ proposal, from, to }) => ({ id: proposal.id, from, to, find: proposal.find ?? "", say: proposal.say }))
  view.dispatch({
    changes: chosen.map((p) => ({ from: p.from, to: p.to, insert: p.proposal.replace ?? "" })),
    effects: [addApplied.of(items), revealing(landed)],
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

/** A change that replaces a whole table by a whole new table (a row or a column added or removed, docs/decisions/069): both its
 *  words and their replacement run over several lines of pipes. Drawn in the table's source, where the new rows are shown. */
export function isTableChange(proposal: { find?: string; replace?: string | null }): boolean {
  const rows = (text: string | null | undefined) => (text ?? "").split("\n")
  return rows(proposal.find).length > 1 && rows(proposal.replace).length > 1 && rows(proposal.find).every((line) => line.includes("|"))
}

interface TableCell {
  text: string
  from: number
  to: number
}

/** The cells of each row of a table's source (its separator row left out): the words of a cell, trimmed, and where they are. */
function tableRows(table: string): TableCell[][] {
  const rows: TableCell[][] = []
  let offset = 0
  for (const line of table.split("\n")) {
    const lineStart = offset
    offset += line.length + 1
    if (!line.includes("|")) continue
    const cells: TableCell[] = []
    let start = 0
    const cut = (end: number) => {
      const raw = line.slice(start, end)
      const text = raw.trim()
      if (text) cells.push({ text, from: lineStart + start + raw.indexOf(text), to: lineStart + start + raw.indexOf(text) + text.length })
    }
    for (const bar of line.matchAll(/(?<!\\)\|/g)) {
      cut(bar.index)
      start = bar.index + 1
    }
    cut(line.length)
    if (cells.length > 0 && !cells.every((cell) => /^:?-+:?$/.test(cell.text))) rows.push(cells)
  }
  return rows
}

/** The longest run of cells two rows share, in order: which cells of `next` are kept (`true`) and how many. */
function sharedCells(old: TableCell[], next: TableCell[]): { kept: boolean[]; count: number } {
  const best = Array.from({ length: old.length + 1 }, () => new Array<number>(next.length + 1).fill(0))
  for (let i = old.length - 1; i >= 0; i--) {
    for (let j = next.length - 1; j >= 0; j--) {
      best[i][j] = old[i].text === next[j].text ? best[i + 1][j + 1] + 1 : Math.max(best[i + 1][j], best[i][j + 1])
    }
  }
  const kept = next.map(() => false)
  for (let i = 0, j = 0; i < old.length && j < next.length; ) {
    if (old[i].text === next[j].text) {
      kept[j] = true
      i++
      j++
    } else if (best[i + 1][j] >= best[i][j + 1]) i++
    else j++
  }
  return { kept, count: best[0][0] }
}

/**
 * Where the words that are new are in `next`, when it replaces the table `old` (a row or a column added or removed, a cell
 * changed): rows are paired by the cells they share, then cells within a pair; a row with nothing in common is all new. What
 * was taken away has no place in the answer, and the separator row is syntax and never new.
 */
export function newTableCells(old: string, next: string): { from: number; to: number }[] {
  const before = tableRows(old)
  const after = tableRows(next)
  // Pair the rows in order so that the most cells are shared (a plain alignment over rows; tables are small).
  const shared = before.map((o) => after.map((n) => sharedCells(o, n).count))
  const total = Array.from({ length: before.length + 1 }, () => new Array<number>(after.length + 1).fill(0))
  for (let i = before.length - 1; i >= 0; i--) {
    for (let j = after.length - 1; j >= 0; j--) {
      const pair = shared[i][j] > 0 ? total[i + 1][j + 1] + shared[i][j] : 0
      total[i][j] = Math.max(pair, total[i + 1][j], total[i][j + 1])
    }
  }
  const paired = new Map<number, number>() // row of `after` -> row of `before`
  for (let i = 0, j = 0; i < before.length && j < after.length; ) {
    if (shared[i][j] > 0 && total[i][j] === total[i + 1][j + 1] + shared[i][j]) paired.set(j++, i++)
    else if (total[i + 1][j] >= total[i][j + 1]) i++
    else j++
  }
  return after.flatMap((row, j) => {
    const mate = paired.get(j)
    const kept = mate === undefined ? [] : sharedCells(before[mate], row).kept
    return row.filter((_, k) => !kept[k]).map(({ from, to }) => ({ from, to }))
  })
}

/** A position inside the last cell of the table a change covers, for what the editor draws in a rendered table: the end of the
 *  last row's last cell, before its closing pipe and padding (the pipe itself is hidden, and a position there is not in a cell). */
export function lastCellEnd(text: string, to: number): number {
  let i = to
  while (i > 0 && /[ \t]/.test(text[i - 1])) i--
  if (i > 0 && text[i - 1] === "|") i--
  while (i > 0 && /[ \t]/.test(text[i - 1])) i--
  return i
}

class ChangeWidget extends WidgetType {
  readonly proposal: Proposal
  readonly compact: boolean

  /** `compact`: only the buttons, no copy of the replacement, in a rendered table (its new rows show in the source). */
  constructor(proposal: Proposal, compact = false) {
    super()
    this.proposal = proposal
    this.compact = compact
  }

  eq(other: ChangeWidget): boolean {
    return other.proposal.id === this.proposal.id && other.proposal.replace === this.proposal.replace && other.proposal.say === this.proposal.say && other.compact === this.compact
  }

  toDOM(view: EditorView): HTMLElement {
    const wrap = document.createElement("span")
    wrap.className = "sy-change"
    wrap.dataset.changeId = this.proposal.id
    if (this.proposal.say) wrap.title = this.proposal.say
    const added = document.createElement("span")
    added.className = "sy-change-add"
    added.textContent = this.compact ? "" : (this.proposal.replace ?? "")
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
  chosen.sort((a, b) => a.from - b.from)
  view.dispatch({
    changes: chosen.map((p) => ({ from: p.from, to: p.to, insert: p.proposal.replace ?? "" })),
    effects: revealing(landing(chosen)),
    userEvent: "input.accept",
  })
  const done = chosen.map((p) => p.proposal.id)
  view.state.facet(resolveFacet)?.(done, true)
  return done
}

export function declineChanges(view: EditorView, ids: string[]): void {
  view.state.facet(resolveFacet)?.(ids)
}

/**
 * Whether this editor holds the review extensions. A draft's editor is made without them (its file has none), and for a moment
 * after the draft is accepted the panel can still be holding that editor, so every helper below needs one that does.
 */
export function holdsReview(state: EditorState): boolean {
  return state.field(reviewField, false) !== undefined
}

/** The proposals in the text now that can still be accepted. */
export function pendingIds(state: EditorState): string[] {
  return classify(state.doc.toString(), state.field(reviewField).proposals).placed.map((p) => p.proposal.id)
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
  return [...struck, ...marks, ...revealCellMarks(state)]
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
  const text = state.doc.toString()
  const widgets: CellWidget[] = classify(text, data.proposals).placed.map(({ proposal, to }) => {
    const whole = isTableChange(proposal)
    return {
      pos: whole ? lastCellEnd(text, to) : to,
      key: `change:${proposal.id}:${proposal.say}:${proposal.replace ?? ""}`,
      toDOM: (view) => new ChangeWidget(proposal, whole).toDOM(view),
    }
  })
  for (const item of state.field(appliedField).items) {
    const whole = isTableChange({ find: item.find, replace: text.slice(item.from, item.to) })
    widgets.push({ pos: whole ? lastCellEnd(text, item.to) : item.to, key: `applied:${item.id}:${item.say}`, toDOM: (view) => new UndoWidget(item).toDOM(view) })
  }
  if (state.facet(attachFacet)) {
    const placed = classify(state.doc.toString(), data.proposals).placed
    for (const { annotations, from, to } of commentHighlights(state.doc.toString(), data.annotations)) {
      if (underChange(placed, from, to)) continue
      const widget = new ClipWidget(annotations[0].id, passageOf(annotations[0]))
      widgets.push({ pos: to, key: `clip:${annotations[0].id}:${annotations[0].quote}`, toDOM: (view) => widget.toDOM(view) })
    }
  }
  return [...widgets, ...revealCellWidgets(state)]
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
  ".sy-change-add, .sy-reveal-new": {
    backgroundColor: "color-mix(in srgb, var(--ok) 20%, transparent)",
  },
  ".sy-reveal-old": { whiteSpace: "pre-wrap" },
  ".sy-reveal-hidden": { display: "none" },
  ".sy-reveal-draft .cm-inplace-table:not(:has([data-stylo-cell-mark]))": { visibility: "hidden" },
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
  // The paperclip above a commented passage, and the Undo above an applied edit: small and quiet until the words are pointed at.
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
  ".sy-comment-hl:hover ~ .sy-anchor .sy-clip, .sy-applied:hover ~ .sy-anchor .sy-clip, .sy-anchor:hover .sy-clip, .sy-clip:focus-visible": { opacity: "1", visibility: "visible", transition: "opacity 0.12s, visibility 0s" },
  ".sy-clip:hover": { opacity: "1", background: "var(--accent)", color: "var(--foreground)" },
  ".sy-clip svg": { width: "0.75rem", height: "0.75rem", stroke: "currentColor", strokeWidth: "2" },
  ".sy-tab button + button": { borderInlineStart: "1px solid var(--border)" },
  ".sy-tab button:hover": { background: "var(--accent)" },


  ".sy-applied": {
    backgroundColor: "color-mix(in srgb, var(--ok) 20%, transparent)",
  },


  ".sy-applied-undo:hover": { color: "var(--danger)" },
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
    revealExtensions,
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
