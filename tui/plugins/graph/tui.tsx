/**
 * Hobbes's graph panel (DEC-015): the views of `hobbes levels` as a keyboard list;
 * Hobbes's on/off item under the prompt with `/hobbes` to start or stop it (DEC-016);
 * the home screen's logo, drawn where opencode's was (DEC-017); `/review`, which
 * has the server write the review page and open it in the browser (DEC-018); and
 * the session's mode, default, agent mapped (DEC-022) or edit mapping (DEC-023), picked
 * with `/mode` or by clicking it under the prompt; picking edit mapping while Hobbes is
 * off offers to start it first.
 *
 * `hobbes tui` loads this directory through OPENCODE_CLI_CONFIG_CONTENT; the
 * pinned TUI compiles this file itself, so there is no build step. Views come
 * from the Hobbes server over opencode's RPC call (`hobbes.view`), already
 * shaped into rows, and are fetched again on `rpc.hobbes.changed`, on
 * `rpc.hobbes.status` and on reconnect. Hobbes's state comes from
 * `hobbes.status` and is pushed as `rpc.hobbes.status`; `hobbes.start` and
 * `hobbes.stop` change it. The logo comes from `hobbes.logo` and takes over the
 * home screen's `home.logo` slot, which our fork of the TUI adds (DEC-025). The mode comes from
 * `hobbes.mode` for the session on screen (on the home screen: the mode new sessions
 * start in), again on each route change and on `rpc.hobbes.mode`; the same call with
 * a `mode` sets it. This file only draws and handles keys.
 *
 * Written against opencode v2.0.29 (tag 042d083) and our fork of it: the plugin API in
 * packages/plugin/src/tui/context.ts, the session panel docs in
 * services/www/src/docs/content/build/plugins/cli.mdx, and the row style of
 * packages/tui/src/feature-plugins/system/diff-viewer-file-tree.tsx (MIT).
 */
import { Plugin } from "@opencode/plugin/tui"
import type { PanelInput } from "@opencode/plugin/tui/context"
import { RGBA, TextAttributes, type ScrollBoxRenderable } from "@opentui/core"
import { useTerminalDimensions } from "@opentui/solid"
import { createEffect, createMemo, createSignal, For, on, onCleanup, Show } from "solid-js"

const PANEL = "hobbes.graph"
const MAX_LINKS = 8

type Box = {
  id: string
  label: string
  detail: string
  opens: string | null
  root: boolean
  links: string[]
  tests: string[]
}
type View = {
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
type Reply = View | { error: string }
type Status = { state: "unavailable" | "off" | "starting" | "on" | "failed"; detail: string; since: number | null }
type Mode = { sessionID: string | null; mode: "default" | "mapped" | "mapping"; mapped: boolean; detail: string; error?: string }

const FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
type Picture = { rows: string[]; palette: Record<string, string> }
type LogoData = { letters: Picture; art: Picture | null; error?: string }
type Span = { text: string; fg?: RGBA; bg?: RGBA }

export default Plugin.define({
  id: PANEL,
  setup(context) {
    const [status, setStatus] = createSignal<Status | undefined>()

    function show(next: Status) {
      const before = status()?.state
      setStatus(next)
      if (before === "starting" && next.state === "on") context.ui.toast.show({ message: "Hobbes is on.", variant: "success" })
      if (before !== "failed" && next.state === "failed")
        context.ui.toast.show({ title: "Hobbes did not start", message: next.detail, variant: "error", duration: 10000 })
    }

    async function call(method: "status" | "start" | "stop") {
      try {
        const result = await context.client.rpc.call({ rpcID: "hobbes", method, input: {} })
        show(result.output as Status)
      } catch (error) {
        context.ui.toast.show({ message: `The Hobbes server did not answer: ${String(error)}`, variant: "error" })
      }
    }

    async function toggle() {
      const current = status()
      if (!current) return void call("status")
      if (current.state === "off" || current.state === "failed") return void call("start")
      if (current.state === "unavailable") return context.ui.toast.show({ message: current.detail, variant: "warning" })
      const stop = await context.ui.dialog.confirm({
        title: current.state === "on" ? "Stop Hobbes?" : "Stop starting Hobbes?",
        message: "The graph panel and Hobbes's knowledge of this repo turn off until you start it again.",
        label: { confirm: "stop" },
      })
      if (stop) void call("stop")
    }

    // Not awaited: the TUI waits for every plugin's setup before it draws.
    void call("status")

    const [mode, setMode] = createSignal<Mode | undefined>()
    // The session on screen, or null on the home screen; the router's route is a reactive store.
    const sessionID = () => {
      const route = context.ui.router.current() as { type: string; sessionID?: string }
      return route.type === "session" && route.sessionID ? route.sessionID : null
    }

    async function modeCall(input: { sessionID?: string; mode?: string }): Promise<Mode | undefined> {
      try {
        const result = await context.client.rpc.call({ rpcID: "hobbes", method: "mode", input })
        return result.output as Mode
      } catch (error) {
        context.ui.toast.show({ message: `The Hobbes server did not answer: ${String(error)}`, variant: "error" })
        return undefined
      }
    }

    async function loadMode() {
      const id = sessionID()
      const output = await modeCall(id ? { sessionID: id } : {})
      if (output && !output.error && id === sessionID()) setMode(output)
    }

    async function pickMode() {
      const current = mode()
      const chosen = await context.ui.dialog.select({
        title: sessionID() ? "Session mode" : "Mode for new sessions",
        placeholder: "Pick a mode",
        current: current?.mode,
        options: [
          { title: "default", value: "default", description: "the harness as it is, no agent mapping" },
          {
            title: "agent mapped",
            value: "mapped",
            description: current?.mapped !== false
              ? "jobs: plan, approve, dispatch"
              : `not here: ${current.detail}`,
          },
          { title: "edit mapping", value: "mapping", description: "tell the model what roles you want" },
        ],
      })
      if (chosen === undefined || chosen === current?.mode) return
      const state = status()?.state
      if (chosen === "mapping" && (state === "off" || state === "failed")) {
        const start = await context.ui.dialog.confirm({
          title: "Start Hobbes first?",
          message: "The mapper can read the repo's structure from Hobbes's graph once Hobbes is on. " +
            "Decline to continue without it: the mapper then reads the files.",
          label: { confirm: "start Hobbes" },
        })
        if (start) void call("start")
      }
      const id = sessionID()
      const output = await modeCall(id ? { sessionID: id, mode: chosen as string } : { mode: chosen as string })
      if (output?.error) context.ui.toast.show({ message: output.error, variant: "warning", duration: 8000 })
      else if (output) setMode(output)
    }

    context.ui.slot({
      append: "prompt.footer.status",
      render: (input) => <HobbesItem context={context} status={status} toggle={toggle} details={input.showDetails} />,
    })
    context.ui.slot({
      append: "prompt.footer.status",
      render: () => <ModeItem context={context} mode={mode} pick={() => void pickMode()} />,
    })
    context.ui.slot({
      append: "session.panel",
      render: (panel) => (
        <Show when={panel.name === PANEL}>
          <GraphPanel context={context} panel={panel} />
        </Show>
      ),
    })
    context.ui.slot({
      append: "app",
      render: () => {
        const offStatus = context.data.on("rpc.hobbes.status", (event) => show(event.data as Status))
        const offConnected = context.data.on("server.connected", () => {
          void call("status")
          void loadMode()
        })
        const offMode = context.data.on("rpc.hobbes.mode", (event) => {
          if ((event.data as { sessionID: string | null }).sessionID === sessionID()) void loadMode()
        })
        createEffect(on(sessionID, () => void loadMode()))
        onCleanup(() => {
          offStatus()
          offConnected()
          offMode()
        })
        context.keymap.layer(() => ({
          mode: "global",
          commands: [
            {
              id: "hobbes.review",
              title: "Open the review page",
              palette: true,
              slash: { name: "review" },
              async run() {
                context.ui.dialog.clear()
                try {
                  const result = await context.client.rpc.call({ rpcID: "hobbes", method: "review", input: {} })
                  const output = result.output as { path?: string; opened?: boolean; error?: string }
                  if (output.error) context.ui.toast.show({ message: output.error, variant: "warning" })
                  else
                    context.ui.toast.show({
                      title: output.opened ? "Review opened in the browser" : "Review written",
                      message: output.path ?? "",
                      variant: "success",
                    })
                } catch (error) {
                  context.ui.toast.show({ message: `The Hobbes server did not answer: ${String(error)}`, variant: "error" })
                }
              },
            },
            {
              id: "hobbes.mode",
              title: "Pick the mode: default or agent mapped",
              palette: true,
              slash: { name: "mode" },
              run() {
                context.ui.dialog.clear()
                void pickMode()
              },
            },
            {
              id: "hobbes.toggle",
              title: "Start or stop Hobbes",
              palette: true,
              slash: { name: "hobbes" },
              run() {
                context.ui.dialog.clear()
                void toggle()
              },
            },
            {
              id: "hobbes.graph.show",
              title: "Graph view",
              palette: true,
              slash: { name: "graph" },
              run() {
                context.ui.dialog.clear()
                if (!context.ui.panel.open(PANEL)) context.ui.toast.show({ message: "Open a session to see the graph." })
              },
            },
          ],
        }))
        return null
      },
    })
    context.ui.slot({ replace: "home.logo", render: () => <HomeLogo context={context} /> })
  },
})

// A picture as terminal lines: two pixels a cell, runs of one colour pair merged into a span.
function lines(picture: Picture, text: RGBA, muted: RGBA): Span[][] {
  const cache: Record<string, RGBA> = {}
  const colour = (ch: string): RGBA | undefined => {
    if (ch === "." || ch === undefined) return undefined
    if (ch === "T") return text
    if (ch === "t") return muted
    return (cache[ch] ??= RGBA.fromHex(picture.palette[ch]))
  }
  const out: Span[][] = []
  for (let y = 0; y < picture.rows.length; y += 2) {
    const top = picture.rows[y]
    const bottom = picture.rows[y + 1] ?? ""
    const spans: Span[] = []
    for (let x = 0; x < top.length; x++) {
      const a = colour(top[x])
      const b = colour(bottom[x])
      const cell: Span = !a && !b ? { text: " " } : !b ? { text: "▀", fg: a } : !a ? { text: "▄", fg: b } : { text: "▀", fg: a, bg: b }
      const last = spans[spans.length - 1]
      if (last && last.fg === cell.fg && last.bg === cell.bg && last.text[0] === cell.text) last.text += cell.text
      else spans.push(cell)
    }
    out.push(spans)
  }
  return out
}

// Hobbes's logo on the home screen (DEC-017), in the `home.logo` slot in place of opencode's (DEC-025).
function HomeLogo(props: { context: Plugin.Context }) {
  const context = props.context
  const dimensions = useTerminalDimensions()
  const [data, setData] = createSignal<LogoData | undefined>()

  async function fetchLogo() {
    try {
      const result = await context.client.rpc.call({ rpcID: "hobbes", method: "logo", input: {} })
      setData(result.output as LogoData)
    } catch {
      setData(undefined)
    }
  }
  void fetchLogo()
  onCleanup(context.data.on("server.connected", () => void fetchLogo()))

  // The art when it fits with room for the prompt, else the plain letters, else nothing.
  const picture = createMemo(() => {
    const current = data()
    const { width, height } = dimensions()
    const fits = (p: Picture | null | undefined, room: number) =>
      p && width >= p.rows[0].length + 4 && height >= p.rows.length / 2 + room
    if (fits(current?.art, 12)) return current!.art!
    if (fits(current?.letters, 12)) return current!.letters
    return undefined
  })
  const drawn = createMemo(() => {
    const current = picture()
    return current ? lines(current, context.theme.text.base, context.theme.text.muted) : []
  })

  return (
    <box flexDirection="column" flexShrink={0}>
      <For each={drawn()}>
        {(spans) => (
          <text wrapMode="none" selectable={false}>
            <For each={spans}>{(span) => <span style={{ fg: span.fg, bg: span.bg }}>{span.text}</span>}</For>
          </text>
        )}
      </For>
    </box>
  )
}

// Hobbes's state under the prompt, on the home screen and in sessions; a click starts or stops it.
function HobbesItem(props: {
  context: Plugin.Context
  status: () => Status | undefined
  toggle: () => void
  details: boolean
}) {
  const theme = () => props.context.theme
  const [now, setNow] = createSignal(Date.now())
  let timer: ReturnType<typeof setInterval> | undefined
  createEffect(() => {
    const starting = props.status()?.state === "starting"
    if (starting && timer === undefined) timer = setInterval(() => setNow(Date.now()), 120)
    if (!starting && timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  })
  onCleanup(() => timer !== undefined && clearInterval(timer))

  const line = createMemo(() => {
    const current = props.status()
    if (!current) return { text: "", color: theme().text.muted }
    switch (current.state) {
      case "on":
        return { text: "● hobbes on", color: theme().text.feedback.success.base }
      case "starting": {
        const seconds = current.since ? Math.max(0, Math.floor((now() - current.since) / 1000)) : 0
        const frame = FRAMES[Math.floor(now() / 120) % FRAMES.length]
        return { text: `${frame} hobbes starting${props.details ? ` · ${seconds}s` : ""}`, color: theme().text.feedback.warning.base }
      }
      case "failed":
        return { text: `✕ hobbes failed${props.details ? " · retry" : ""}`, color: theme().text.feedback.error.base }
      case "unavailable":
        return { text: "◌ hobbes unavailable", color: theme().text.muted }
      default:
        return { text: `◌ hobbes off${props.details ? " · start" : ""}`, color: theme().text.muted }
    }
  })

  return (
    <Show when={props.status()}>
      <box flexShrink={0} onMouseUp={() => props.toggle()}>
        <text fg={line().color} wrapMode="none">
          {line().text}
        </text>
      </box>
    </Show>
  )
}

// The session's mode under the prompt (DEC-022); a click opens the picker.
function ModeItem(props: { context: Plugin.Context; mode: () => Mode | undefined; pick: () => void }) {
  const theme = () => props.context.theme
  return (
    <Show when={props.mode()}>
      {(current) => (
        <box flexShrink={0} onMouseUp={() => props.pick()}>
          <text fg={current().mode === "default" ? theme().text.muted : theme().text.base} wrapMode="none">
            {current().mode === "mapped" ? "◆ agent mapped" : current().mode === "mapping" ? "✎ edit mapping" : "◇ default"}
          </text>
        </box>
      )}
    </Show>
  )
}

function GraphPanel(props: { context: Plugin.Context; panel: PanelInput }) {
  const context = props.context
  const theme = () => context.theme
  const [reply, setReply] = createSignal<Reply | undefined>()
  const [selected, setSelected] = createSignal(0)
  const view = createMemo(() => {
    const current = reply()
    return current && "boxes" in current ? current : undefined
  })
  const box = createMemo(() => view()?.boxes[selected()])
  let scroll: ScrollBoxRenderable | undefined

  // Fetch view `id` (null: the repo view); `pick` chooses the row to select.
  async function load(id: string | null, pick: (boxes: Box[]) => number = () => 0) {
    try {
      const result = await context.client.rpc.call({ rpcID: "hobbes", method: "view", input: id === null ? {} : { id } })
      const output = result.output as Reply
      setReply(output)
      if ("boxes" in output) setSelected(Math.max(0, pick(output.boxes)))
    } catch (error) {
      setReply({ error: `The Hobbes server did not answer: ${String(error)}` })
    }
  }

  function reload() {
    const current = view()
    const keep = box()?.id
    void load(current ? current.id : null, (boxes) => boxes.findIndex((b) => b.id === keep))
  }

  function move(step: number) {
    const count = view()?.boxes.length ?? 0
    if (count > 0) setSelected((index) => Math.min(count - 1, Math.max(0, index + step)))
  }

  function open() {
    const target = box()?.opens
    if (target !== null && target !== undefined) void load(target)
  }

  function up() {
    const current = view()
    if (!current || current.parent === null) return
    void load(current.parent, (boxes) => boxes.findIndex((b) => b.opens === current.id))
  }

  void load(null)
  const offChanged = context.data.on("rpc.hobbes.changed", reload)
  const offStatus = context.data.on("rpc.hobbes.status", reload)
  const offConnected = context.data.on("server.connected", reload)
  onCleanup(() => {
    offChanged()
    offStatus()
    offConnected()
  })

  context.keymap.layer(() => ({
    commands: [
      { id: "hobbes.graph.down", title: "Next box", bind: "down,j", run: () => move(1) },
      { id: "hobbes.graph.up", title: "Previous box", bind: "up,k", run: () => move(-1) },
      { id: "hobbes.graph.open", title: "Open box", bind: "enter,right,l", run: open },
      { id: "hobbes.graph.parent", title: "Up a level", bind: "backspace,left,h", run: up },
      { id: "hobbes.graph.refresh", title: "Refresh graph", bind: "r", run: reload },
      { id: "hobbes.graph.fullscreen", title: "Toggle fullscreen", bind: "f", run: () => props.panel.toggleFullscreen() },
      { id: "hobbes.graph.close", title: "Close graph", bind: "escape,q", run: () => props.panel.close() },
    ],
  }))

  createEffect(() => {
    const index = selected()
    if (!scroll || scroll.isDestroyed) return
    if (index < scroll.scrollTop) scroll.scrollTo(index)
    else if (index + 1 > scroll.scrollTop + scroll.viewport.height) scroll.scrollTo(index + 1 - scroll.viewport.height)
  })

  return (
    <box flexDirection="column" flexGrow={1} minHeight={0} paddingLeft={1} paddingRight={1}>
      <Show when={reply()} fallback={<text fg={theme().text.muted}>Loading the graph…</text>}>
        <Show
          when={view()}
          fallback={
            <text fg={theme().text.feedback.warning.base}>{(reply() as { error: string }).error}</text>
          }
        >
          {(current) => (
            <>
              <box flexDirection="row" height={1} flexShrink={0}>
                <text attributes={TextAttributes.BOLD} wrapMode="none" flexShrink={0}>
                  {current().title}
                </text>
                <text fg={theme().text.muted} wrapMode="none" truncate>
                  {`  ${current().kind} · level ${current().level} · ${current().sha}${current().dirty ? " (dirty)" : ""}`}
                </text>
              </box>
              <Show when={current().parentTitle !== null}>
                <text fg={theme().text.muted} wrapMode="none" truncate flexShrink={0}>
                  {`⌫ ${current().parentTitle}`}
                </text>
              </Show>
              <For each={current().notes}>
                {(note) => (
                  <text fg={theme().text.muted} flexShrink={0}>
                    {note}
                  </text>
                )}
              </For>
              <scrollbox
                ref={(element: ScrollBoxRenderable) => (scroll = element)}
                flexGrow={1}
                minHeight={3}
                marginTop={1}
                verticalScrollbarOptions={{ visible: false }}
                horizontalScrollbarOptions={{ visible: false }}
              >
                <For each={current().boxes}>
                  {(item, index) => {
                    const chosen = () => index() === selected()
                    return (
                      <box
                        flexDirection="row"
                        height={1}
                        flexShrink={0}
                        backgroundColor={chosen() ? theme().background.raised.high : theme().background.raised.base}
                        onMouseUp={() => setSelected(index())}
                      >
                        <text fg={theme().text.muted} wrapMode="none" flexShrink={0}>
                          {item.opens !== null ? "▸ " : "  "}
                        </text>
                        <text
                          attributes={chosen() ? TextAttributes.BOLD : undefined}
                          wrapMode="none"
                          flexShrink={0}
                        >
                          {item.label + (item.root ? " (root)" : "")}
                        </text>
                        <text fg={theme().text.muted} wrapMode="none" truncate>
                          {`  ${item.detail}`}
                        </text>
                      </box>
                    )
                  }}
                </For>
              </scrollbox>
              <Show when={box()}>
                {(chosen) => (
                  <box flexDirection="column" flexShrink={0} marginTop={1}>
                    <text attributes={TextAttributes.BOLD} wrapMode="none" truncate>
                      {chosen().label}
                    </text>
                    <Show
                      when={chosen().links.length > 0}
                      fallback={<text fg={theme().text.muted}>No links within this view.</text>}
                    >
                      <For each={chosen().links.slice(0, MAX_LINKS)}>
                        {(link) => (
                          <text wrapMode="none" truncate>
                            {link}
                          </text>
                        )}
                      </For>
                      <Show when={chosen().links.length > MAX_LINKS}>
                        <text fg={theme().text.muted}>{`… ${chosen().links.length - MAX_LINKS} more`}</text>
                      </Show>
                    </Show>
                    <For each={chosen().tests}>
                      {(test) => (
                        <text fg={theme().text.muted} wrapMode="none" truncate>
                          {`tested by ${test}`}
                        </text>
                      )}
                    </For>
                  </box>
                )}
              </Show>
              <Show when={current().cycles.length > 0}>
                <text fg={theme().text.feedback.warning.base} flexShrink={0} wrapMode="none" truncate>
                  {`cycles: ${current().cycles.join("; ")}`}
                </text>
              </Show>
              <Show when={current().outside.length > 0}>
                <text fg={theme().text.muted} flexShrink={0} wrapMode="none" truncate>
                  {`outside: ${current().outside.join("; ")}`}
                </text>
              </Show>
              <text fg={theme().text.muted} flexShrink={0} wrapMode="none" truncate marginTop={1}>
                ↑↓ move · enter open · ⌫ up · r refresh · f fullscreen · esc close
              </text>
            </>
          )}
        </Show>
      </Show>
    </box>
  )
}
