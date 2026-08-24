import { describe, expect, it } from 'vitest'

import {
  allKinds,
  buildElements,
  commonRoot,
  defaultKinds,
  labelOf,
  neighborhood,
  nodeDetail,
  packageOf,
  packages,
  type GraphFilters,
} from './graphModel'
import type { Graph, GraphNode, NodeKind } from '../types'

function node(id: string, kind: NodeKind, path?: string): GraphNode {
  return { id, kind, path }
}

const graph: Graph = {
  schema_version: 3,
  sha: 'abc',
  dirty: false,
  languages: ['python', 'typescript'],
  nodes: [
    node('hobbes.cli', 'module', 'pipeline/src/hobbes/cli.py'),
    node('hobbes.extract', 'package', 'pipeline/src/hobbes/extract/__init__.py'),
    node('hobbes.extract.graph', 'module', 'pipeline/src/hobbes/extract/graph.py'),
    node('src/flow', 'module', 'src/flow.ts'),
    node('ext:pytest', 'external'),
    node('env:HOBBES_HOME', 'env'),
    node('tf:aws_lambda_function.worker', 'resource', 'infra/main.tf'),
  ],
  module_edges: [
    { from: 'hobbes.cli', to: 'hobbes.extract', type: 'imports', evidence: [{ path: 'p', line: 1 }] },
    { from: 'hobbes.extract', to: 'hobbes.extract.graph', type: 'imports' },
    { from: 'hobbes.extract.graph', to: 'ext:pytest', type: 'imports' },
    { from: 'hobbes.cli', to: 'env:HOBBES_HOME', type: 'env-read' },
    { from: 'tf:aws_lambda_function.worker', to: 'env:HOBBES_HOME', type: 'env-set' },
  ],
  symbols: [
    { id: 'hobbes.cli.main', module: 'hobbes.cli', kind: 'function', line: 40 },
    { id: 'hobbes.cli.build', module: 'hobbes.cli', kind: 'function', line: 10 },
    { id: 'src/flow.run', module: 'src/flow', kind: 'function', line: 3 },
  ],
  symbol_edges: [],
}

describe('kind filtering', () => {
  it('hides externals by default and keeps everything else', () => {
    const kinds = defaultKinds(graph.nodes)
    expect(kinds.has('external')).toBe(false)
    expect(kinds.has('module')).toBe(true)
    expect(kinds.has('resource')).toBe(true)
    expect(kinds.has('env')).toBe(true)
  })

  it('lists kinds in a stable order, unknown kinds last', () => {
    const withNew = [...graph.nodes, node('q:topic', 'queue' as NodeKind)]
    expect(allKinds(withNew)).toEqual([
      'module',
      'package',
      'external',
      'env',
      'resource',
      'queue',
    ])
  })
})

describe('packageOf', () => {
  it('groups dotted, path, and prefixed ids', () => {
    expect(packageOf(node('hobbes.extract.graph', 'module'))).toBe('hobbes')
    expect(packageOf(node('src/flow', 'module'))).toBe('src')
    expect(packageOf(node('driver', 'module'))).toBe('driver')
    expect(packageOf(node('ext:pytest', 'external'))).toBe('ext')
    expect(packageOf(node('env:HOME', 'env'))).toBe('env')
    expect(packageOf(node('tf:aws_iam_role.worker', 'resource'))).toBe('tf')
  })

  it('keeps a root-disambiguated id whole, as ADR-008 does', () => {
    // `pipeline:tests` is one group, not a `pipeline` group — the two
    // renderers must not disagree about what a package is.
    expect(packageOf(node('pipeline:tests.test_cli', 'module'))).toBe('pipeline:tests')
  })

  it('sorts the package list', () => {
    expect(packages(graph.nodes)).toEqual(['env', 'ext', 'hobbes', 'src', 'tf'])
  })
})

describe('commonRoot', () => {
  it('strips the directory every path-shaped module shares', () => {
    // kbet's ids all start betchat/frontend/src/, so without this every
    // label renders as the same truncated prefix.
    const kbet = [
      node('betchat/frontend/src/components/BetCard', 'module'),
      node('betchat/frontend/src/stores/authStore', 'module'),
      node('betchat/frontend/src/api/bets', 'module'),
    ]
    expect(commonRoot(kbet)).toBe('betchat/frontend/src/')
    expect(labelOf(kbet[0], commonRoot(kbet))).toBe('components/BetCard')
    expect(packages(kbet, commonRoot(kbet))).toEqual(['api', 'components', 'stores'])
  })

  it('never consumes the module name itself', () => {
    // Two modules in one directory share it, but the label must keep a
    // name — stripping to "" would leave unlabelled nodes.
    const pair = [node('src/a', 'module'), node('src/b', 'module')]
    expect(commonRoot(pair)).toBe('src/')
    expect(labelOf(pair[0], commonRoot(pair))).toBe('a')

    const one = [node('deep/nested/only', 'module')]
    expect(commonRoot(one)).toBe('deep/nested/')
    expect(labelOf(one[0], commonRoot(one))).toBe('only')
  })

  it('is empty when paths diverge at the top, or when there are none', () => {
    expect(commonRoot([node('src/a', 'module'), node('lib/b', 'module')])).toBe('')
    expect(commonRoot([node('hobbes.cli', 'module')])).toBe('')
    expect(commonRoot([])).toBe('')
  })

  it('ignores namespaced ids, whose colon is not a path', () => {
    const mixed = [
      node('src/app/flow', 'module'),
      node('src/app/util', 'module'),
      node('ext:react', 'external'),
      node('env:API_URL', 'env'),
    ]
    expect(commonRoot(mixed)).toBe('src/app/')
    expect(labelOf(mixed[2], 'src/app/')).toBe('react')
    expect(packageOf(mixed[3], 'src/app/')).toBe('env')
  })
})

describe('labelOf', () => {
  it('drops the prefix the shape already conveys', () => {
    expect(labelOf(node('ext:express', 'external'))).toBe('express')
    expect(labelOf(node('env:API_URL', 'env'))).toBe('API_URL')
    expect(labelOf(node('tf:aws_iam_role.worker', 'resource'))).toBe('aws_iam_role.worker')
    expect(labelOf(node('hobbes.cli', 'module'))).toBe('hobbes.cli')
  })
})

describe('neighborhood', () => {
  it('walks undirected hops, so callers and callees both appear', () => {
    const one = neighborhood(graph.module_edges, 'hobbes.extract', 1)
    expect([...one].sort()).toEqual(['hobbes.cli', 'hobbes.extract', 'hobbes.extract.graph'])
  })

  it('grows with depth and stops when the component is exhausted', () => {
    const two = neighborhood(graph.module_edges, 'hobbes.extract', 2)
    expect(two.has('ext:pytest')).toBe(true)
    expect(two.has('env:HOBBES_HOME')).toBe(true)
    const deep = neighborhood(graph.module_edges, 'src/flow', 5)
    expect([...deep]).toEqual(['src/flow'])
  })
})

describe('buildElements', () => {
  const base: GraphFilters = {
    kinds: new Set<NodeKind>(['module', 'package', 'external', 'env', 'resource']),
    packages: null,
    focus: null,
    depth: 1,
  }

  it('emits every node before any edge', () => {
    const elements = buildElements(graph, base)
    const firstEdge = elements.findIndex((e) => 'source' in e.data)
    const lastNode = elements.map((e) => 'source' in e.data).lastIndexOf(false)
    expect(lastNode).toBeLessThan(firstEdge)
  })

  it('drops edges whose endpoint was filtered out', () => {
    // Hiding externals must not leave an edge pointing at nothing.
    const elements = buildElements(graph, { ...base, kinds: defaultKinds(graph.nodes) })
    const ids = elements.map((e) => e.data.id)
    expect(ids).not.toContain('ext:pytest')
    expect(ids).not.toContain('hobbes.extract.graph|imports|ext:pytest')
    expect(ids).toContain('hobbes.cli|imports|hobbes.extract')
  })

  it('filters by package', () => {
    const elements = buildElements(graph, { ...base, packages: new Set(['hobbes']) })
    expect(elements.every((e) => !e.data.id.startsWith('src/'))).toBe(true)
    expect(elements.some((e) => e.data.id === 'hobbes.cli')).toBe(true)
  })

  it('labels with the id stripped of the common root, keeping ids intact', () => {
    const paths: Graph = {
      ...graph,
      nodes: [
        { id: 'app/web/src/components/Card', kind: 'module' },
        { id: 'app/web/src/stores/auth', kind: 'module' },
      ],
      module_edges: [
        { from: 'app/web/src/components/Card', to: 'app/web/src/stores/auth', type: 'imports' },
      ],
    }
    const root = commonRoot(paths.nodes)
    const elements = buildElements(paths, { ...base, root })
    const card = elements.find((e) => e.data.id === 'app/web/src/components/Card')!
    // The id is what the API and the graph speak; only the label shortens.
    expect((card.data as { label: string }).label).toBe('components/Card')
    expect(card.data.id).toBe('app/web/src/components/Card')
  })

  it('fades rather than removes when focused, so the shape stays visible', () => {
    const elements = buildElements(graph, { ...base, focus: 'hobbes.extract', depth: 1 })
    const byID = new Map(elements.map((e) => [e.data.id, e.data]))
    expect(byID.get('hobbes.extract')!.faded).toBe(false)
    expect(byID.get('hobbes.cli')!.faded).toBe(false)
    // Two hops away: still drawn, dimmed.
    expect(byID.get('ext:pytest')).toBeDefined()
    expect(byID.get('ext:pytest')!.faded).toBe(true)
  })

  it('ignores a focus on a node the filters removed', () => {
    const elements = buildElements(graph, {
      ...base,
      kinds: defaultKinds(graph.nodes),
      focus: 'ext:pytest',
    })
    expect(elements.every((e) => e.data.faded === false)).toBe(true)
  })

  it('labels only edge types that carry information', () => {
    const elements = buildElements(graph, base)
    const imports = elements.find((e) => e.data.id === 'hobbes.cli|imports|hobbes.extract')!
    const envRead = elements.find((e) => e.data.id === 'hobbes.cli|env-read|env:HOBBES_HOME')!
    expect((imports.data as { label: string }).label).toBe('')
    expect((envRead.data as { label: string }).label).toBe('env-read')
  })
})

describe('nodeDetail', () => {
  it('gathers symbols in source order and edges in both directions', () => {
    const detail = nodeDetail(graph, 'hobbes.cli')!
    expect(detail.symbols.map((s) => s.id)).toEqual(['hobbes.cli.build', 'hobbes.cli.main'])
    expect(detail.outgoing.map((e) => e.to)).toEqual(['hobbes.extract', 'env:HOBBES_HOME'])
    expect(detail.incoming).toEqual([])
  })

  it('answers null for an id the graph does not have', () => {
    expect(nodeDetail(graph, 'nope')).toBeNull()
  })
})

describe('edge tiers reach the renderer (ADR-028)', () => {
  const filters: GraphFilters = {
    kinds: new Set<NodeKind>(['module', 'package', 'external', 'env', 'resource']),
    packages: null,
    focus: null,
    depth: 1,
  }
  const tiered = (tier?: string) =>
    ({
      ...graph,
      module_edges: [
        {
          from: 'hobbes.cli',
          to: 'hobbes.extract',
          type: 'imports',
          ...(tier ? { tier } : {}),
        },
      ],
      symbol_edges: [],
    }) as unknown as Graph

  const edgeOf = (tier?: string) =>
    buildElements(tiered(tier), filters).find((e) => 'source' in e.data)!

  it('carries a semantic tier onto the element', () => {
    expect((edgeOf('semantic').data as { tier?: string }).tier).toBe('semantic')
  })

  it('carries a syntactic tier onto the element', () => {
    expect((edgeOf('syntactic').data as { tier?: string }).tier).toBe('syntactic')
  })

  it('leaves tier undefined on a pre-v4 artifact rather than guessing one', () => {
    // A missing tier must not be styled as "guessed" — the artifact simply
    // predates the field, and demoting it would misreport confidence.
    expect((edgeOf(undefined).data as { tier?: string }).tier).toBeUndefined()
  })
})
