/**
 * Graph — architecture §7's first tab, the one a concept-level review
 * starts from. Cytoscape (D3) over graph.json, on ADR-023's conventions:
 * module level only, shape by kind, externals hidden by default, focus
 * mode instead of drawing 600 edges at once, and an inspector that joins
 * what the artifacts keep apart.
 */

import cytoscape from 'cytoscape'
import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api'
import { Badge, PinList, StaleBadge } from '../components'
import { useAsync } from '../hooks'
import {
  allKinds,
  buildElements,
  commonRoot,
  defaultKinds,
  labelOf,
  nodeDetail,
  packages,
} from '../lib/graphModel'
import type { Graph, GraphEdge, NodeKind, Pin, Tests } from '../types'

/** ADR-023's kind styling: shape and color carry what a node is. */
type KindStyle = { shape: cytoscape.Css.NodeShape; color: string }

const KIND_STYLE: Record<string, KindStyle> = {
  module: { shape: 'round-rectangle', color: '#7cc4ff' },
  package: { shape: 'round-rectangle', color: '#5aa7e0' },
  external: { shape: 'hexagon', color: '#8b93a1' },
  env: { shape: 'ellipse', color: '#f5c86b' },
  resource: { shape: 'diamond', color: '#c9a2ff' },
  data: { shape: 'diamond', color: '#a98ede' },
  'tf-module': { shape: 'diamond', color: '#b78fff' },
}

const FALLBACK: KindStyle = { shape: 'octagon', color: '#6ee7a0' }

function styleFor(kind: string): KindStyle {
  return KIND_STYLE[kind] ?? FALLBACK
}

export function GraphTab({
  graph,
  tests,
  onOpenPin,
  initialSelection = null,
}: {
  graph: Graph
  tests: Tests | null
  onOpenPin: (pin: Pin) => void
  /** A module another tab asked to show — "what guards this" in reverse. */
  initialSelection?: string | null
}) {
  // A selection arriving from another tab may name a node the default
  // filters hide (an external, say); showing its kind is the only way
  // the request can be honoured.
  const [kinds, setKinds] = useState<Set<NodeKind>>(() => {
    const initial = defaultKinds(graph.nodes)
    const asked = initialSelection && graph.nodes.find((n) => n.id === initialSelection)
    if (asked) initial.add(asked.kind)
    return initial
  })
  const [pkg, setPkg] = useState<string>('')
  const [focus, setFocus] = useState<string | null>(null)
  const [depth, setDepth] = useState(1)
  const [selected, setSelected] = useState<string | null>(initialSelection)
  const cy = useRef<cytoscape.Core | null>(null)

  // Path-shaped ids (ADR-021) all start with the same directory; strip
  // it so labels differ from each other.
  const root = useMemo(() => commonRoot(graph.nodes), [graph])

  const elements = useMemo(
    () =>
      buildElements(graph, {
        kinds,
        packages: pkg ? new Set([pkg]) : null,
        focus,
        depth,
        root,
      }),
    [graph, kinds, pkg, focus, depth, root],
  )

  const pkgs = useMemo(() => packages(graph.nodes, root), [graph, root])
  const kindList = useMemo(() => allKinds(graph.nodes), [graph])

  return (
    <div className="content" style={{ flexDirection: 'column' }}>
      <div className="toolbar">
        <span className="row wrap" style={{ gap: 4 }}>
          {kindList.map((kind) => (
            <button
              key={kind}
              className={kinds.has(kind) ? 'on' : ''}
              onClick={() =>
                setKinds((prev) => {
                  const next = new Set(prev)
                  if (next.has(kind)) next.delete(kind)
                  else next.add(kind)
                  return next
                })
              }
              title={`show or hide ${kind} nodes`}
            >
              {kind}
            </button>
          ))}
        </span>

        <select value={pkg} onChange={(e) => setPkg(e.target.value)} title="package filter">
          <option value="">all packages{root && ` (under ${root})`}</option>
          {pkgs.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <label className="row" style={{ gap: 5 }}>
          <input
            type="checkbox"
            checked={focus !== null}
            disabled={!selected}
            onChange={(e) => setFocus(e.target.checked ? selected : null)}
          />
          focus
        </label>
        <select
          value={depth}
          onChange={(e) => setDepth(Number(e.target.value))}
          disabled={focus === null}
          title="neighborhood depth"
        >
          {[1, 2, 3].map((d) => (
            <option key={d} value={d}>
              {d} hop{d > 1 ? 's' : ''}
            </option>
          ))}
        </select>

        <span className="spacer" />
        <span className="legend">
          {kindList.map((kind) => (
            <span key={kind}>
              <i
                className={`swatch ${kind === 'env' ? 'env' : kind === 'external' ? 'external' : kind.startsWith('tf') || kind === 'resource' || kind === 'data' ? 'tf' : 'module'}`}
                style={{ borderColor: styleFor(kind).color, background: styleFor(kind).color + '33' }}
              />
              {kind}
            </span>
          ))}
        </span>
        <button onClick={() => cy.current?.fit(undefined, 40)} title="fit the whole graph">
          fit
        </button>
        <span className="badge muted">
          {elements.filter((e) => !('source' in e.data)).length} nodes ·{' '}
          {elements.filter((e) => 'source' in e.data).length} edges
        </span>
      </div>

      <div className="content">
        <div className="main" style={{ overflow: 'hidden' }}>
          <Canvas
            cyRef={cy}
            elements={elements}
            focus={focus}
            selected={selected}
            onSelect={(id) => {
              setSelected(id)
              if (focus !== null) setFocus(id)
            }}
          />
        </div>
        <div className="inspector">
          {selected ? (
            <Inspector
              graph={graph}
              tests={tests}
              id={selected}
              root={root}
              onOpenPin={onOpenPin}
              onSelect={setSelected}
            />
          ) : (
            <p style={{ color: 'var(--muted)' }}>
              Select a node to inspect it — its symbols, its narrative purpose, the tests that
              guard it, and every typed edge with the line the extractor saw.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Canvas owns the Cytoscape instance. Elements are replaced wholesale on
 * a filter change (the graphs are small enough that diffing would be
 * complexity for its own sake); a focus change only re-runs layout,
 * which is where breadthfirst earns its place (ADR-023).
 */
function Canvas({
  cyRef,
  elements,
  focus,
  selected,
  onSelect,
}: {
  cyRef: React.MutableRefObject<cytoscape.Core | null>
  elements: ReturnType<typeof buildElements>
  focus: string | null
  selected: string | null
  onSelect: (id: string) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const cy = cyRef

  useEffect(() => {
    if (!box.current) return
    const instance = cytoscape({
      container: box.current,
      elements: [],
      wheelSensitivity: 0.2,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'font-size': 9,
            'font-family': 'ui-monospace, monospace',
            color: '#d6dae0',
            'text-valign': 'bottom',
            'text-margin-y': 3,
            'text-wrap': 'ellipsis',
            'text-max-width': '110px',
            // Labels vanish rather than pile up when zoomed out; the
            // shape still carries the kind, and zooming in restores them.
            'min-zoomed-font-size': 7,
            width: 16,
            height: 16,
            'border-width': 1.5,
          },
        },
        ...Object.entries(KIND_STYLE).map(([kind, s]) => ({
          selector: `node[kind = "${kind}"]`,
          style: {
            shape: s.shape,
            'background-color': s.color + '44',
            'border-color': s.color,
          },
        })),
        {
          selector: 'node[?faded]',
          style: { opacity: 0.16, 'text-opacity': 0 },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#ffffff',
            width: 22,
            height: 22,
            'text-opacity': 1,
            'font-size': 11,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1,
            'line-color': '#3a4150',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#4a5361',
            'arrow-scale': 0.7,
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': 8,
            color: '#8b93a1',
            'text-rotation': 'autorotate',
          },
        },
        // Edge styling by type, as ADR-008 does for the export: any type
        // without a rule still draws solid and labeled, never invisible.
        {
          selector: 'edge[type = "env-read"], edge[type = "env-set"]',
          style: { 'line-style': 'dashed', 'line-color': '#7a6636', 'target-arrow-color': '#7a6636' },
        },
        {
          selector: 'edge[type = "references"], edge[type = "packages"]',
          style: { 'line-style': 'dotted', 'line-color': '#6b5a8a', 'target-arrow-color': '#6b5a8a' },
        },
        // Tier before type: a guessed dependency and a proven one must not
        // look identical (§3.4). Syntactic edges are drawn thinner and
        // dimmer — present and readable, visibly less certain. Edges with
        // no tier are pre-v4 artifacts and keep the default weight rather
        // than being demoted for a field they could not have carried.
        {
          selector: 'edge[tier = "syntactic"]',
          style: { width: 0.6, opacity: 0.55, 'line-style': 'dashed' },
        },
        { selector: 'edge[tier = "semantic"]', style: { width: 1.4 } },
        { selector: 'edge[?faded]', style: { opacity: 0.06, 'text-opacity': 0 } },
      ],
    })
    instance.on('tap', 'node', (e) => onSelect(e.target.id()))
    cy.current = instance
    return () => {
      instance.destroy()
      cy.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Which elements are present, ignoring their faded flags: a focus
  // change alters only the flags, and re-adding every element for that
  // would throw away the layout the dimmed remainder is meant to keep.
  const signature = useMemo(() => elements.map((e) => e.data.id).join('\n'), [elements])
  const lastSignature = useRef<string | null>(null)
  const wasFocused = useRef(false)

  useEffect(() => {
    const instance = cy.current
    if (!instance) return

    const structural = signature !== lastSignature.current
    lastSignature.current = signature

    instance.batch(() => {
      if (structural) {
        instance.elements().remove()
        instance.add(elements as cytoscape.ElementDefinition[])
      } else {
        for (const el of elements) {
          const target = instance.$id(el.data.id)
          if (target.nonempty()) target.data('faded', el.data.faded ?? false)
        }
      }
    })

    // Built-in layouts only (ADR-023). Spacing is tuned for label
    // legibility, not compactness: at real-repo sizes an unspaced cose
    // piles module names on top of each other.
    const settle = (instance: cytoscape.Core) => {
      // Fitting a big graph to the viewport zooms out past the point
      // where labels render at all, so legibility wins over seeing
      // everything: below the floor the view stays readable and pans.
      instance.fit(undefined, 40)
      if (instance.zoom() < MIN_READABLE_ZOOM) {
        instance.zoom({ level: MIN_READABLE_ZOOM, renderedPosition: viewportCenter(instance) })
      }
    }

    // Re-lay the whole graph when its membership changed, or when focus
    // was just released and the neighborhood needs folding back in.
    if (structural || (!focus && wasFocused.current)) {
      const full = instance.layout({
        name: 'cose',
        animate: false,
        nodeRepulsion: 20000,
        idealEdgeLength: 95,
        nodeOverlap: 16,
        gravity: 0.6,
        componentSpacing: 110,
        padding: 50,
      } as cytoscape.LayoutOptions)
      if (!focus) full.one('layoutstop', () => settle(instance))
      full.run()
    }

    if (focus) {
      // Only the neighborhood is re-laid out — breadthfirst so a
      // dependency chain reads as layers — while the dimmed remainder
      // keeps its positions, which is what makes it context rather than
      // a row of leftovers.
      const near = instance.elements().filter((e) => !e.data('faded'))
      const chain = near.layout({
        name: 'breadthfirst',
        directed: true,
        roots: `#${cssEscape(focus)}`,
        spacingFactor: 1.4,
        padding: 40,
      } as cytoscape.LayoutOptions)
      chain.one('layoutstop', () => {
        instance.fit(near, 60)
        // A two-node neighborhood would otherwise fill the viewport at
        // absurd magnification; clamp both ends.
        const clamped = Math.min(Math.max(instance.zoom(), MIN_READABLE_ZOOM), MAX_FOCUS_ZOOM)
        if (clamped !== instance.zoom()) {
          instance.zoom({ level: clamped, renderedPosition: viewportCenter(instance) })
          instance.center(near)
        }
      })
      chain.run()
    }
    wasFocused.current = focus !== null
  }, [elements, signature, focus])

  useEffect(() => {
    const instance = cy.current
    if (!instance) return
    instance.$(':selected').unselect()
    if (selected) instance.$id(selected).select()
  }, [selected, elements])

  return <div ref={box} className="graph-canvas" />
}

/** Cytoscape selectors are CSS-ish; ids carry `.`, `:` and `/`. */
function cssEscape(id: string): string {
  return id.replace(/[^a-zA-Z0-9_-]/g, (c) => '\\' + c)
}

/** Below this zoom, node labels stop being readable. */
const MIN_READABLE_ZOOM = 0.62

/** Above this, a small neighborhood fills the viewport at absurd scale. */
const MAX_FOCUS_ZOOM = 1.3

function viewportCenter(instance: cytoscape.Core): { x: number; y: number } {
  return { x: instance.width() / 2, y: instance.height() / 2 }
}

/**
 * Inspector answers, for one node, the questions the artifacts store
 * separately: what it is, what it holds, what it says about itself, what
 * guards it, and what it depends on — every claim and edge citable.
 */
function Inspector({
  graph,
  tests,
  id,
  root,
  onOpenPin,
  onSelect,
}: {
  graph: Graph
  tests: Tests | null
  id: string
  root: string
  onOpenPin: (pin: Pin) => void
  onSelect: (id: string) => void
}) {
  const detail = useMemo(() => nodeDetail(graph, id), [graph, id])
  const doc = useAsync(
    () => api.moduleDoc(id).catch(() => null),
    [id],
  )
  const guarding = useMemo(
    () => (tests?.tests ?? []).filter((t) => t.reaches_modules?.includes(id)),
    [tests, id],
  )

  if (!detail) return <p className="err">no node {id}</p>
  const { node, symbols, outgoing, incoming } = detail

  return (
    <>
      <div className="section">
        <div className="row wrap" style={{ marginBottom: 4 }}>
          <Badge kind="info">{node.kind}</Badge>
          {doc.data && <StaleBadge status={doc.data.status} changed={doc.data.changed} />}
        </div>
        <h3 style={{ fontSize: 14, textTransform: 'none', letterSpacing: 0, color: 'var(--text)' }}>
          <span className="mono">{node.id}</span>
        </h3>
        {node.path && (
          <button className="pin" onClick={() => onOpenPin({ path: node.path!, line: 1 })}>
            {node.path}
          </button>
        )}
      </div>

      {doc.data && (
        <div className="section">
          <h3>purpose</h3>
          <p style={{ margin: 0 }}>{doc.data.purpose.text}</p>
          <PinList pins={doc.data.purpose.pins} onOpen={onOpenPin} />
        </div>
      )}

      <div className="section">
        <h3>
          depends on ({outgoing.length})
        </h3>
        <EdgeList edges={outgoing} pick="to" root={root} onSelect={onSelect} onOpenPin={onOpenPin} />
      </div>

      <div className="section">
        <h3>depended on by ({incoming.length})</h3>
        <EdgeList edges={incoming} pick="from" root={root} onSelect={onSelect} onOpenPin={onOpenPin} />
      </div>

      <div className="section">
        <h3>tests guarding ({guarding.length})</h3>
        {guarding.length === 0 ? (
          <p style={{ color: 'var(--muted)', margin: 0 }}>
            {node.kind === 'module' || node.kind === 'package'
              ? 'no test statically reaches this module'
              : '—'}
          </p>
        ) : (
          <ul className="plain">
            {guarding.slice(0, 12).map((t) => (
              <li key={t.id}>
                <button className="pin" onClick={() => onOpenPin({ path: t.file, line: t.line })}>
                  {t.id.split('::').slice(1).join('::') || t.id}
                </button>
              </li>
            ))}
            {guarding.length > 12 && (
              <li style={{ color: 'var(--muted)' }}>+{guarding.length - 12} more</li>
            )}
          </ul>
        )}
      </div>

      <div className="section">
        <h3>symbols ({symbols.length})</h3>
        <ul className="plain">
          {symbols.slice(0, 40).map((s) => (
            <li key={s.id} className="row" style={{ gap: 6 }}>
              <span className="badge muted">{s.kind}</span>
              <button
                className="pin"
                onClick={() => node.path && onOpenPin({ path: node.path, line: s.line })}
              >
                {s.qualname ?? s.name ?? s.id}
              </button>
            </li>
          ))}
          {symbols.length > 40 && (
            <li style={{ color: 'var(--muted)' }}>+{symbols.length - 40} more</li>
          )}
        </ul>
      </div>
    </>
  )
}

function EdgeList({
  edges,
  pick,
  root,
  onSelect,
  onOpenPin,
}: {
  edges: GraphEdge[]
  pick: 'to' | 'from'
  root: string
  onSelect: (id: string) => void
  onOpenPin: (pin: Pin) => void
}) {
  if (edges.length === 0) return <p style={{ color: 'var(--muted)', margin: 0 }}>—</p>
  return (
    <ul className="plain">
      {edges.map((e, i) => {
        const other = e[pick]
        return (
          <li key={`${e.from}|${e.type}|${e.to}|${i}`} className="row wrap" style={{ gap: 6 }}>
            <span className="badge muted">{e.type}</span>
            <button className="pin" onClick={() => onSelect(other)}>
              {labelOf({ id: other, kind: 'module' }, root)}
            </button>
            {e.evidence?.slice(0, 2).map((ev, j) => (
              <button key={j} className="pin" onClick={() => onOpenPin(ev)} title={ev.path}>
                :{ev.line}
              </button>
            ))}
          </li>
        )
      })}
    </ul>
  )
}
