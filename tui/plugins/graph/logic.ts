/**
 * The graph plugin's logic that needs no TUI (DEC-015, DEC-016, DEC-017): the shapes the Hobbes server
 * sends, the logo as terminal spans, which logo fits, the Hobbes item's and the mode item's text, and the
 * panel's selection and row text. tui.tsx draws with these; logic.test.ts checks them. Nothing here
 * imports the TUI, so colours are whatever the caller's `fromHex` makes.
 */

export const MAX_LINKS = 8
export const FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

export type Box = {
  id: string
  label: string
  detail: string
  opens: string | null
  root: boolean
  links: string[]
  tests: string[]
}
export type View = {
  id: string
  kind: "folder" | "module" | "entries" | "flow"
  title: string
  level: number
  parent: string | null
  parentTitle: string | null
  sha: string
  dirty: boolean
  notes: string[]
  boxes: Box[]
  outside: string[]
  cycles: string[]
}
export type Reply = View | { error: string }
export type Status = { state: "unavailable" | "off" | "starting" | "on" | "failed"; detail: string; since: number | null }
export type Mode = { sessionID: string | null; mode: "default" | "mapped" | "mapping"; mapped: boolean; detail: string; error?: string }
export type Picture = { rows: string[]; palette: Record<string, string> }
export type LogoData = { letters: Picture; art: Picture | null; error?: string }
export type Span<C> = { text: string; fg?: C; bg?: C }

/** A picture as terminal lines: two pixels a cell (upper and lower half block), runs of one colour pair
 * merged into a span. "." is empty, "T" the text colour, "t" the muted one, any other letter its palette
 * hex; each hex is made once. */
export function lines<C>(picture: Picture, text: C, muted: C, fromHex: (hex: string) => C): Span<C>[][] {
  const cache: Record<string, C> = {}
  const colour = (ch: string | undefined): C | undefined => {
    if (ch === "." || ch === undefined) return undefined
    if (ch === "T") return text
    if (ch === "t") return muted
    return (cache[ch] ??= fromHex(picture.palette[ch]))
  }
  const out: Span<C>[][] = []
  for (let y = 0; y < picture.rows.length; y += 2) {
    const top = picture.rows[y]
    const bottom = picture.rows[y + 1] ?? ""
    const spans: Span<C>[] = []
    for (let x = 0; x < top.length; x++) {
      const a = colour(top[x])
      const b = colour(bottom[x])
      const cell: Span<C> = !a && !b ? { text: " " } : !b ? { text: "▀", fg: a } : !a ? { text: "▄", fg: b } : { text: "▀", fg: a, bg: b }
      const last = spans[spans.length - 1]
      if (last && last.fg === cell.fg && last.bg === cell.bg && last.text[0] === cell.text) last.text += cell.text
      else spans.push(cell)
    }
    out.push(spans)
  }
  return out
}

/** The logo to draw: the art when it fits with room for the prompt, else the plain letters, else none. A
 * picture fits when the terminal is four columns wider and, at two pixels a row, twelve rows taller. */
export function pickPicture(logo: LogoData | undefined, width: number, height: number): Picture | undefined {
  const fits = (p: Picture | null | undefined): p is Picture =>
    Boolean(p && width >= p.rows[0].length + 4 && height >= p.rows.length / 2 + 12)
  if (fits(logo?.art)) return logo!.art!
  if (fits(logo?.letters)) return logo!.letters
  return undefined
}

export type Tone = "success" | "warning" | "error" | "muted"

/** The Hobbes item's text and tone; with details, the action a click takes (or, starting, the seconds so far). */
export function statusLine(status: Status | undefined, details: boolean, now: number): { text: string; tone: Tone } {
  if (!status) return { text: "", tone: "muted" }
  switch (status.state) {
    case "on":
      return { text: "● hobbes on", tone: "success" }
    case "starting": {
      const seconds = status.since ? Math.max(0, Math.floor((now - status.since) / 1000)) : 0
      const frame = FRAMES[Math.floor(now / 120) % FRAMES.length]
      return { text: `${frame} hobbes starting${details ? ` · ${seconds}s` : ""}`, tone: "warning" }
    }
    case "failed":
      return { text: `✕ hobbes failed${details ? " · retry" : ""}`, tone: "error" }
    case "unavailable":
      return { text: "◌ hobbes unavailable", tone: "muted" }
    default:
      return { text: `◌ hobbes off${details ? " · start" : ""}`, tone: "muted" }
  }
}

/** The mode item's text. */
export function modeLabel(mode: Mode["mode"]): string {
  return mode === "mapped" ? "◆ agent mapped" : mode === "mapping" ? "✎ edit mapping" : "◇ default"
}

/** The row selected after a step up or down a list of `count` rows, held to the list; none to move in, none moved. */
export function moveSelection(index: number, step: number, count: number): number {
  return count > 0 ? Math.min(count - 1, Math.max(0, index + step)) : index
}

/** The panel's line under a view's title. */
export function viewHeading(view: Pick<View, "kind" | "level" | "sha" | "dirty">): string {
  return `  ${view.kind} · level ${view.level} · ${view.sha}${view.dirty ? " (dirty)" : ""}`
}

/** A row's marker (it opens a view) and its label (the repo's own box says so). */
export function rowText(box: Pick<Box, "opens" | "label" | "root">): { marker: string; label: string } {
  return { marker: box.opens !== null ? "▸ " : "  ", label: box.label + (box.root ? " (root)" : "") }
}

/** The links to list for a box, at most MAX_LINKS, and how many more there are. */
export function shownLinks(links: string[]): { shown: string[]; more: number } {
  return { shown: links.slice(0, MAX_LINKS), more: Math.max(0, links.length - MAX_LINKS) }
}
