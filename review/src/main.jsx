// The review page (DEC-018, drawn per DEC-019): one repo's views, in four
// tabs. Architecture (DEC-020, shown first): parts, components with roles
// and summaries, entry points and outside systems. Code map: the level
// views, folder by folder (DEC-014). Docs (DEC-021): the repo's Markdown,
// unpacked and rendered when opened. Agents (DEC-023): the repo's agent
// mapping as it stood when the page was written, each role's prompt rendered.
//
// hobbes.review inlines this bundle and `const DATA = {...}` into
// pipeline/src/hobbes/review.html. Graph views are laid out by ELK and
// drawn by React Flow; flows and entry points are numbered lists. Click
// selects (and focuses the box's links), double-click or Enter opens,
// Backspace goes up; files and path:line samples open in VS Code. The
// hash names the tab and view: #a=<id>, #v=<id>, #d=<path>[#<anchor>], or #r=<role>.

import { createRoot } from "react-dom/client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DOMPurify from "dompurify";
import { Background, Controls, Handle, MiniMap, Position, ReactFlow } from "@xyflow/react";
import ELK from "elkjs/lib/elk.bundled.js";
import "@xyflow/react/dist/style.css";
import "./style.css";
import { ARCH, GROUPS, ORDERED, SPARSE, arrowHead, counts, curvePath, elkGraph, isDependency, laidOutLink, neighbours,
  strokeWidth, toFlow, trimEnd } from "./graph.js";
import { HEADING_PREFIX, byFolder, linkTarget, render } from "./docs.js";

const VIEWS = DATA.views;
const ARCH_DATA = DATA.architecture && DATA.architecture.views && DATA.architecture.root in DATA.architecture.views
  ? DATA.architecture : null;
const TABS = {
  a: { name: "Architecture", views: ARCH_DATA ? ARCH_DATA.views : {}, root: ARCH_DATA && ARCH_DATA.root },
  v: { name: "Code map", views: VIEWS, root: DATA.root },
};
const DOCS = (DATA.docs && DATA.docs.files) || [];
const DOC_BY_PATH = new Map(DOCS.map((d) => [d.path, d]));
const DOC_PATHS = new Set(DOCS.filter((d) => d.gz).map((d) => d.path));
const AGENTS = DATA.agents || null;
const ROLES = AGENTS && AGENTS.roles ? [...AGENTS.roles].sort((a, b) => b.coordinator - a.coordinator) : [];
const ROLE_BY_NAME = new Map(ROLES.map((r) => [r.name, r]));
const REPO = DATA.stamp.path;
const elk = new ELK();
const laidOut = new Map(); // view id -> promise of {nodes, edges}

const code = (path, line) => `vscode://file/${encodeURI(REPO + "/" + path)}${line ? ":" + line : ""}`;
const isArch = (view) => view.id.startsWith("arch:") && view.id in TABS.a.views;
const viewsOf = (view) => (isArch(view) ? TABS.a.views : VIEWS);
const title = (id, views = VIEWS) => (id in views ? views[id].title : id || "(repo)");
const opens = (b, views = VIEWS) => b && b.view != null && b.view in views;
const many = (n, noun) => `${n} ${noun}${n === 1 ? "" : "s"}`;

function CodeLink({ path, line, children }) {
  return <a href={code(path, line)} title="Open in VS Code">{children ?? (line ? `${path}:${line}` : path)}</a>;
}

function Sample({ s }) {
  const m = /^(.*):(\d+)$/.exec(s);
  return m ? <CodeLink path={m[1]} line={m[2]}>{s}</CodeLink> : <>{s}</>;
}

// -- navigation ---------------------------------------------------------------

TABS.d = { name: "Docs", root: DOCS.length ? DOCS[0].path : null };
TABS.r = { name: "Agents", root: "" };
const TAB_ORDER = ["a", "v", "d", "r"].filter((t) => TABS[t].root != null);

function hashView() {
  const m = /^#([avdr])=([^#]*)(?:#(.*))?$/.exec(location.hash);
  const tab = m && TAB_ORDER.includes(m[1]) ? m[1] : TAB_ORDER[0];
  const id = m && m[1] === tab ? decodeURIComponent(m[2]) : TABS[tab].root;
  if (tab === "d") return { tab, id: DOC_BY_PATH.has(id) ? id : TABS.d.root, anchor: m && m[3] ? decodeURIComponent(m[3]) : null };
  if (tab === "r") return { tab, id: ROLE_BY_NAME.has(id) ? id : "" };
  return { tab, id: id in TABS[tab].views ? id : TABS[tab].root };
}
const go = (id, tab = "v") => { location.hash = tab + "=" + encodeURIComponent(id); };
const docHref = (path, anchor) => "#d=" + encodeURIComponent(path) + (anchor ? "#" + encodeURIComponent(anchor) : "");
const goIn = (view) => (id) => go(id, isArch(view) ? "a" : "v");

function useViewId() {
  const [id, setId] = useState(hashView);
  useEffect(() => {
    const on = () => setId(hashView());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return id;
}

// -- the header ---------------------------------------------------------------

function Header({ view, tab, doc }) {
  const views = TABS[tab].views || {};
  const chain = [];
  if (tab === "d") {
    const parts = doc.split("/");
    parts.forEach((p, i) => chain.push({ id: parts.slice(0, i + 1).join("/"), title: p }));
  } else if (tab === "r") {
    chain.push({ id: "", title: "Agent mapping" });
    if (doc) chain.push({ id: doc, title: doc });
  } else {
    for (let v = view; v; v = v.parent == null ? null : views[v.parent]) chain.unshift(v);
  }
  const st = DATA.stamp;
  const options = useMemo(() => (tab === "d" ? DOCS.map((d) => ({ id: d.path, label: d.title }))
    : tab === "r" ? ROLES.map((r) => ({ id: r.name, label: `${r.name} (${r.agent})` }))
    : Object.values(views).map((v) => ({ id: v.id, label: `${v.title} (${v.kind})` }))), [views, tab]);
  const known = (id) => (tab === "d" ? DOC_BY_PATH.has(id) : tab === "r" ? ROLE_BY_NAME.has(id) : id in views);
  return (
    <header>
      <div className="brand">hobbes <span>review</span></div>
      {TAB_ORDER.length > 1 && (
        <nav className="tabs">
          {TAB_ORDER.map((t) => (
            <a key={t} className={t === tab ? "on" : ""} href={"#" + t + "=" + encodeURIComponent(TABS[t].root)}>{TABS[t].name}</a>
          ))}
        </nav>
      )}
      <nav className="crumbs">
        {chain.map((v, i) => (
          <span key={v.id}>
            {i > 0 && <span className="sep">{tab === "d" ? "/" : "›"}</span>}
            {i === chain.length - 1 || tab === "d" ? <b>{v.title}</b> : <a href={"#" + tab + "=" + encodeURIComponent(v.id)}>{v.title}</a>}
          </span>
        ))}
      </nav>
      <input className="find" list="views" autoComplete="off"
        placeholder={tab === "d" ? "Go to a document…" : tab === "r" ? "Go to a role…" : "Go to a view…"}
        onChange={(ev) => { const id = ev.target.value; if (known(id)) { go(id, tab); ev.target.value = ""; ev.target.blur(); } }} />
      <datalist id="views">
        {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
      </datalist>
      <div className="stamp" title={`${st.path}\nhobbes ${st.hobbes}, level document schema ${st.schema}`}>
        {st.repo} @ {(st.sha || "").slice(0, 7)}{st.dirty && <span className="badge warn">dirty</span>} · {st.generated}
      </div>
    </header>
  );
}

// -- folder and module views: React Flow ---------------------------------------

const ROLE_TIPS = {
  entry: "holds a command's or route's code",
  adapter: "half or more of its modules import process, network or storage libraries",
  foundation: "used by 2 or more here, uses little itself",
  coordinator: "uses 2 or more here, little used itself",
  standalone: "no links with the rest of this view",
  shared: "modules used across components, depending on little",
};
const TOUCH = { process: "processes", network: "network", storage: "storage", env: "environment" };
const KIND_NAME = { folder: "component", files: "files", prefix: "file group", module: "module", shared: "shared",
  more: "more", door: "entry points", outside: "outside", dispatch: "dispatch" };

function ArchNode({ data }) {
  const { box: b, opens: o, faded, selected } = data;
  const small = b.kind === "door" || b.kind === "outside" || b.kind === "dispatch";
  const cls = ["bx", "ax", "k-" + b.kind, o && "opens", b.root && "root", GROUPS.has(b.kind) && "group",
    small && "small", b.kind === "outside" && "o-" + b.class, selected && "sel", faded && "faded"].filter(Boolean).join(" ");
  const touches = Object.keys(b.touches || {}).filter((k) => k in TOUCH);
  const meta = [];
  if (b.reached != null) meta.push(`${many(b.reached, "function")} reached`);
  else if (b.modules != null) meta.push(many(b.modules, "module"));
  if (b.tests && b.reached == null) meta.push(many(b.tests, "test"));
  const tip = [b.label, b.summary, ...(b.roles || []).map((r) => `${r}: ${ROLE_TIPS[r]}`), o && "Double-click to open"]
    .filter(Boolean).join("\n");
  return (
    <div className={cls} title={tip}>
      <Handle type="target" position={Position.Top} isConnectable={false} />
      {small ? (
        <>
          <div className="bx-top"><span className="bx-kind">{KIND_NAME[b.kind]}</span>{o && <span className="chev">▸</span>}</div>
          <div className="bx-label">{b.label}</div>
        </>
      ) : (
        <>
          <div className="bx-top">
            {b.order != null && <span className="step-num">{b.order}</span>}
            <span className="bx-kind">{KIND_NAME[b.kind] || b.kind}</span>
            {(b.roles || []).filter((r) => r !== "shared").map((r) => <span key={r} className={"role r-" + r}>{r}</span>)}
            {b.root && <span className="bx-root" title="a language root (a folder with its own manifest)">◆</span>}
            {o && <span className="chev">▸</span>}
          </div>
          <div className="bx-label">{b.label}</div>
          {b.summary ? <div className="bx-sum">{b.summary}</div>
            : b.files ? <div className="bx-sum files">{b.files.join(", ")}</div> : null}
          <div className="bx-detail">
            {meta.join(" · ")}
            {touches.map((t) => <span key={t} className={"touch t-" + t}>{TOUCH[t]}</span>)}
          </div>
        </>
      )}
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}

function BoxNode({ data }) {
  if (data.arch) return <ArchNode data={data} />;
  const { box: b, opens: o, faded, selected } = data;
  const cls = ["bx", "k-" + b.kind, o && "opens", b.root && "root", GROUPS.has(b.kind) && "group",
    selected && "sel", faded && "faded"].filter(Boolean).join(" ");
  return (
    <div className={cls} title={`${b.label} — ${b.detail}${o ? "\nDouble-click to open" : ""}`}>
      <Handle type="target" position={Position.Top} isConnectable={false} />
      <div className="bx-top">
        <span className="bx-kind">{b.kind === "more" ? "more" : b.kind}</span>
        {b.root && <span className="bx-root" title="a language root (a folder with its own manifest)">◆</span>}
        {o && <span className="chev">▸</span>}
      </div>
      <div className="bx-label">{b.label}</div>
      <div className="bx-detail">{b.detail}</div>
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}

function RoutedEdge({ id, data, sourceX, sourceY, targetX, targetY }) {
  const { link: e, points: elkPoints, label, faded, hot, showLabel, arch } = data;
  const points = elkPoints || [{ x: sourceX, y: sourceY }, { x: sourceX, y: (sourceY + targetY) / 2 },
    { x: targetX, y: (sourceY + targetY) / 2 }, { x: targetX, y: targetY }];
  const against = arch && e.against, cycle = !arch && e.cycle;
  const cls = ["edge", cycle && "cycle", against && "against", !isDependency(e) && "aux", hot && "hot",
    faded && "faded"].filter(Boolean).join(" ");
  const note = against ? " (against the layers: closes a cycle)" : cycle ? " (cycle)" : "";
  return (
    <g className={cls}>
      <title>{`${counts(e)}${note}`}</title>
      <path className="edge-line" d={curvePath(trimEnd(points, 6))} strokeWidth={strokeWidth(e)} />
      <path className="edge-head" d={arrowHead(points, 8)} />
      {label && showLabel && (
        <g className="edge-label" transform={`translate(${label.x},${label.y})`}>
          <rect x={-(6 + label.text.length * 3.6)} y={-9} width={12 + label.text.length * 7.2} height={18} rx={9} />
          <text textAnchor="middle" dy="4">{label.text}</text>
        </g>
      )}
    </g>
  );
}

const nodeTypes = { box: BoxNode };
const edgeTypes = { routed: RoutedEdge };

function layout(view) {
  if (!laidOut.has(view.id)) laidOut.set(view.id, elk.layout(elkGraph(view)).then((laid) => toFlow(view, laid, viewsOf(view))));
  return laidOut.get(view.id);
}

function GraphView({ view, selected, onSelect }) {
  const [flow, setFlow] = useState(null);
  const [hover, setHover] = useState(null);
  useEffect(() => {
    let live = true;
    setFlow(null);
    layout(view).then((f) => live && setFlow(f), (err) => live && setFlow({ error: String(err) }));
    return () => { live = false; };
  }, [view]);
  const focus = selected ? selected.id : hover;
  const near = useMemo(() => (focus ? neighbours(view, focus) : null), [view, focus]);
  const nodes = useMemo(() => flow && !flow.error ? flow.nodes.map((n) => ({
    ...n, data: { ...n.data, selected: selected && n.id === selected.id, faded: near && !near.has(n.id) },
  })) : [], [flow, near, selected]);
  const edges = useMemo(() => flow && !flow.error ? flow.edges.map((e) => {
    const touches = focus && (e.source === focus || e.target === focus);
    const showLabel = touches || (!focus && flow.edges.filter((x) => x.data.label).length <= SPARSE);
    const hidden = !laidOutLink(e.data.link) && !touches; // outside links show on focus only
    return { ...e, hidden, zIndex: touches ? 1 : 0, data: { ...e.data, hot: touches, faded: focus && !touches, showLabel } };
  }) : [], [flow, focus]);
  const byId = useMemo(() => new Map(view.boxes.map((b) => [b.id, b])), [view]);
  if (!view.boxes.length) return <p className="empty pad">Nothing in this view.</p>;
  if (!flow) return <p className="empty pad">Laying out…</p>;
  if (flow.error) return <p className="empty pad">Layout failed: {flow.error}</p>;
  return (
    <ReactFlow key={view.id} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
      fitView fitViewOptions={{ padding: 0.12, maxZoom: 1.15 }} minZoom={0.15} maxZoom={2.5}
      nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} zoomOnDoubleClick={false}
      colorMode="system"
      onNodeClick={(_, n) => onSelect(byId.get(n.id))}
      onNodeDoubleClick={(_, n) => { const b = byId.get(n.id); if (opens(b, viewsOf(view))) goIn(view)(b.view); }}
      onNodeMouseEnter={(_, n) => setHover(n.id)} onNodeMouseLeave={() => setHover(null)}
      onPaneClick={() => onSelect(null)}>
      <Background gap={22} size={1.2} />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable nodeClassName={(n) => "mm k-" + n.data.box.kind} nodeBorderRadius={6} />
    </ReactFlow>
  );
}

// -- flows and entry points: numbered lists -----------------------------------

function StepMeta({ view, b }) {
  const meta = [];
  if (b.kind === "step") {
    meta.push(<CodeLink key="at" path={view.module} line={b.line}>{`called at line ${b.line}` + (b.sites > 1 ? ` (${b.sites} sites)` : "")}</CodeLink>);
    if (b.module) meta.push(<CodeLink key="def" path={b.module} line={b.def_line}>{b.local ? "definition" : `in ${b.module}`}</CodeLink>);
    if (b.end) meta.push(<span key="end" className="badge">ends: {b.end}</span>);
    if (b.outside) meta.push(<span key="out" className="badge">leaves: {b.outside}</span>);
    if (b.tests) meta.push(<span key="t">{b.tests} test{b.tests === 1 ? "" : "s"}</span>);
  } else if (b.kind === "entry") {
    meta.push(<span key="tg" className="mono">{b.target || "(no target)"}</span>);
    if (b.source) meta.push(<Sample key="src" s={b.source} />);
    if (b.resolved) meta.push(<span key="r" className="badge">{b.resolved}</span>);
    if (b.cut) meta.push(<span key="c" className="badge warn">cut: {b.cut}</span>);
    if (b.note) meta.push(<span key="n" className="badge">dispatch not extracted (gap 3)</span>);
  } else {
    meta.push(<span key="d">{b.detail}</span>);
  }
  return <div className="meta">{meta}</div>;
}

function ListView({ view, selected, onSelect }) {
  const views = viewsOf(view), open = goIn(view);
  const opens = (b) => b && b.view != null && b.view in views;
  const go = (id) => open(id);
  return (
    <div className="list">
      {view.kind === "flow" && (
        <div className="card head">
          <div className="label">{view.title}</div>
          <div className="meta"><CodeLink path={view.module}>{view.module}</CodeLink></div>
        </div>
      )}
      {(view.notes || []).map((n, i) => <p key={i} className="note">{n}</p>)}
      <div className={view.kind === "flow" ? "spine" : ""}>
        {view.boxes.length ? view.boxes.map((b) => (
          <div key={b.id} className={"card" + (selected === b ? " sel" : "") + (opens(b) ? " opens" : "")}
            onClick={(ev) => { if (!ev.target.closest("a")) onSelect(b); }}
            onDoubleClick={(ev) => { if (!ev.target.closest("a") && opens(b)) go(b.view); }}>
            {b.order != null && <span className="num">{b.order}</span>}
            <div className="label">{b.label}{opens(b) && <span className="chev"> ▸</span>}</div>
            <StepMeta view={view} b={b} />
          </div>
        )) : <p className="empty">No steps.</p>}
      </div>
    </div>
  );
}

// -- the side panel -------------------------------------------------------------

function EdgeItem({ e, other, arrow, labels, arch }) {
  const mark = arch ? (e.against ? " · against the layers" : "") : e.cycle ? " · cycle" : "";
  return (
    <li>
      {arrow} <b>{labels.get(other) || other}</b> <span className="sub">{counts(e)}{mark}</span>
      {e.samples && e.samples.length > 0 && (
        <div className="mono">{e.samples.map((s, i) => <div key={i}><Sample s={s} /></div>)}</div>
      )}
    </li>
  );
}

function Side({ view, selected }) {
  const labels = new Map(view.boxes.map((b) => [b.id, b.label]));
  if (selected) {
    const b = selected;
    const out = view.edges.filter((e) => e.from === b.id), inn = view.edges.filter((e) => e.to === b.id);
    let file = null;
    if (b.kind === "module" && b.path) file = <CodeLink path={b.path} />;
    else if (b.path && b.line) file = <CodeLink path={b.path} line={b.line} />;
    else if (b.kind === "step" && b.module) file = <CodeLink path={b.module} line={b.def_line} />;
    return (
      <aside className="side">
        <h2>{b.label}</h2>
        <div className="sub">{b.kind} · {b.detail}</div>
        {opens(b) && <button className="open" onClick={() => go(b.view)}>Open {title(b.view)} ▸</button>}
        {file && <><h3>Code</h3><ul className="plain"><li>{file}</li></ul></>}
        {out.length > 0 && <><h3>Uses</h3><ul className="plain">{out.map((e) => <EdgeItem key={e.to} e={e} other={e.to} arrow="→" labels={labels} />)}</ul></>}
        {inn.length > 0 && <><h3>Used by</h3><ul className="plain">{inn.map((e) => <EdgeItem key={e.from} e={e} other={e.from} arrow="←" labels={labels} />)}</ul></>}
        {b.test_samples && b.test_samples.length > 0 && (
          <><h3>Tested by</h3><ul className="plain mono">{b.test_samples.map((t) => <li key={t}>{t}</li>)}</ul></>
        )}
      </aside>
    );
  }
  const isRoot = view.id === DATA.root;
  const notes = (isRoot ? DATA.notes || [] : []).concat(ORDERED.has(view.kind) ? [] : view.notes || []);
  const STUBS = 15;
  const ctx = DATA.context || {}, om = DATA.omitted || {};
  return (
    <aside className="side">
      <h2>{view.title}</h2>
      <div className="sub">{view.kind} view · level {view.level} · {view.boxes.length} boxes</div>
      {ARCH_DATA && ("arch:" + view.id) in TABS.a.views && (
        <button className="open alt" onClick={() => go("arch:" + view.id, "a")}>Open in architecture ▸</button>
      )}
      {notes.map((n, i) => <p key={i} className="note">{n}</p>)}
      {view.cycles && view.cycles.length > 0 && (
        <><h3>Cycles</h3><ul className="plain">{view.cycles.map((c, i) => <li key={i}>{c.map((id) => labels.get(id) || id).join(" ↔ ")}</li>)}</ul></>
      )}
      {view.stubs && view.stubs.length > 0 && (
        <><h3>Outside this view</h3><ul className="plain">
          {view.stubs.slice(0, STUBS).map((st) => (
            <li key={st.id} className="mono">{st.id}<div className="sub">
              {[counts(st.out) && "out " + counts(st.out), counts(st.in) && "in " + counts(st.in)].filter(Boolean).join(" · ")}
            </div></li>
          ))}
          {view.stubs.length > STUBS && <li className="sub">… and {view.stubs.length - STUBS} more</li>}
        </ul></>
      )}
      {isRoot && ctx.externals && ctx.externals.length > 0 && (
        <><h3>Uses from outside</h3><ul className="plain mono">
          {ctx.externals.slice(0, 12).map((x) => <li key={x.id}>{x.id.replace(/^ext:/, "")} <span className="sub">{x.modules} modules</span></li>)}
        </ul></>
      )}
      {isRoot && <p className="sub gap">Left out: {om.test_modules || 0} test and {om.fixture_modules || 0} fixture modules.</p>}
      {!ORDERED.has(view.kind) && (
        <><h3>Key</h3><ul className="plain">
          <li>◆ a language root (a folder with its own manifest)</li>
          <li>▸ opens a view of its own</li>
          <li>dashed box: a group of files or symbols</li>
          <li><span className="cycle-text">dashed red arrow</span>: part of a cycle</li>
          <li>callers sit above what they use; thicker arrows carry more links</li>
          <li>hover or select a box to focus its links and show their counts (shown always when a view has few arrows)</li>
        </ul></>
      )}
      <p className="sub gap">Click a box to see its links; double-click (or Enter) opens it; Backspace goes up.</p>
    </aside>
  );
}

// -- the architecture side panel --------------------------------------------------

/** A summary's source: in the Docs tab when it is a document, else in VS Code. */
function SourceLink({ path }) {
  return DOC_PATHS.has(path) ? <a href={docHref(path)} title="Read in the Docs tab">{path}</a> : <CodeLink path={path} />;
}

function Touches({ touches }) {
  const names = { ...TOUCH, files: "files" };
  return (
    <ul className="plain">
      {Object.entries(touches).map(([k, v]) => (
        <li key={k}><b>{names[k] || k}</b> <span className="mono sub">{v.join(", ")}</span></li>
      ))}
    </ul>
  );
}

function ArchSide({ view, selected }) {
  const views = TABS.a.views;
  const labels = new Map(view.boxes.map((b) => [b.id, b.label]));
  const codeLink = (id, text) => id != null && id in VIEWS
    ? <button className="open alt" onClick={() => go(id, "v")}>{text || "Open in code map"} ▸</button> : null;
  if (selected) {
    const b = selected;
    const out = view.edges.filter((e) => e.from === b.id), inn = view.edges.filter((e) => e.to === b.id);
    const dep = (e) => isDependency(e);
    return (
      <aside className="side">
        <h2>{b.label}</h2>
        <div className="sub">{KIND_NAME[b.kind] || b.kind}{b.path ? <> · <span className="mono">{b.path}</span></> : null}</div>
        {(b.roles || []).length > 0 && (
          <ul className="plain roles">{b.roles.map((r) => <li key={r}><span className={"role r-" + r}>{r}</span> {ROLE_TIPS[r]}</li>)}</ul>
        )}
        {b.order != null && <p className="sub">Step {b.order} of this pipeline · {many(b.reached, "function")} reached here</p>}
        {b.via && (
          <p className="about">Entered when <b className="mono">{b.via.from}</b> calls <b className="mono">{b.via.to}</b>{" "}
            <span className="sub">(<Sample s={b.via.at} />)</span></p>
        )}
        {b.about && <p className="about">{b.about}{b.source && <> <span className="sub">— <SourceLink path={b.source} /></span></>}</p>}
        {!b.about && !["door", "outside", "shared", "more", "files", "prefix", "dispatch"].includes(b.kind) && (
          <p className="sub">No docstring or README says what this holds.</p>
        )}
        <div className="buttons">
          {opens(b, views) && <button className="open" onClick={() => go(b.view, "a")}>
            {view.kind === "pipeline" && b.order != null ? `Follow inside ${b.label}` : `Open ${title(b.view, views)}`} ▸</button>}
          {b.component && b.component in views && <button className="open alt" onClick={() => go(b.component, "a")}>Component view ▸</button>}
          {codeLink(b.code)}
        </div>
        {b.handlers && <><h3>Handlers</h3><ul className="plain mono">{b.handlers.map((h) => <li key={h}>{h}</li>)}</ul></>}
        {b.functions && b.functions.length > 0 && (
          <><h3>Functions reached here</h3><ul className="plain mono">
            {b.functions.map((f, i) => <li key={i}><CodeLink path={f.path} line={f.line}>{f.label}</CodeLink></li>)}
            {b.reached > b.functions.length && <li className="sub">… and {b.reached - b.functions.length} more</li>}
          </ul></>
        )}
        {b.modules != null && <p className="sub">{many(b.modules, "module")} · {many(b.tests || 0, "test")}{b.users || b.uses ? ` · used by ${b.users}, uses ${b.uses} here` : ""}</p>}
        {b.commands && b.commands.length > 0 && <><h3>Commands</h3><ul className="plain mono">{b.commands.map((c) => <li key={c}>{c}</li>)}</ul></>}
        {b.routes && b.routes.length > 0 && <><h3>Routes</h3><ul className="plain mono">{b.routes.map((c) => <li key={c}>{c}</li>)}</ul></>}
        {b.entries && b.entries.length > 0 && b.kind !== "door" && <><h3>Entry points</h3><ul className="plain mono">{b.entries.map((c) => <li key={c}>{c}</li>)}</ul></>}
        {b.kind === "outside" && <><h3>Names imported</h3><p className="mono sub">{b.names.join(", ")}</p></>}
        {b.touches && <><h3>Reaches outside</h3><Touches touches={b.touches} /></>}
        {b.libraries && b.libraries.length > 0 && <><h3>Libraries</h3><p className="mono sub">{b.libraries.join(", ")}</p></>}
        {b.files && b.files.length > 0 && (
          <><h3>Files</h3><ul className="plain mono">{b.files.map((f) => <li key={f}>{f.includes("/") ? <CodeLink path={f} /> : f}</li>)}</ul></>
        )}
        {out.filter(dep).length > 0 && <><h3>Uses</h3><ul className="plain">{out.filter(dep).map((e) => <EdgeItem key={e.to} e={e} other={e.to} arrow="→" labels={labels} arch />)}</ul></>}
        {inn.filter(dep).length > 0 && <><h3>Used by</h3><ul className="plain">{inn.filter(dep).map((e) => <EdgeItem key={e.from} e={e} other={e.from} arrow="←" labels={labels} arch />)}</ul></>}
        {b.kind === "outside" && inn.length > 0 && (
          <><h3>Reached from</h3><ul className="plain">{inn.map((e) => <li key={e.from}><b>{labels.get(e.from)}</b> <span className="mono sub">{e.names.join(", ")}</span></li>)}</ul></>
        )}
      </aside>
    );
  }
  const isRoot = view.id === TABS.a.root;
  const notes = (isRoot ? ARCH_DATA.notes : []).concat(view.notes || []);
  const against = view.edges.filter((e) => e.against);
  return (
    <aside className="side">
      <h2>{view.title}</h2>
      <div className="sub">{{ system: "system view", components: "component view", pipeline: "pipeline" }[view.kind]}{view.path ? <> · <span className="mono">{view.path}</span></> : null}</div>
      {view.kind === "pipeline" && view.start && (
        <p className="about">Starts at <CodeLink path={view.start.path} line={view.start.line}>{view.start.label}</CodeLink>
          {view.entry && view.entry.source && <> <span className="sub">(declared at <Sample s={view.entry.source} />)</span></>}
          {view.inside && <>, shown inside <b>{view.inside}</b></>}.</p>
      )}
      {view.kind === "system" && TAB_ORDER.length > 0 && view.boxes.some((b) => b.kind === "door" && b.view) && (
        <><h3>Entry points</h3><ul className="plain">
          {view.boxes.filter((b) => b.kind === "door" && b.view).map((b) => (
            <li key={b.id}><a href={"#a=" + encodeURIComponent(b.view)}>{title(b.view, views)}</a> <span className="sub">{b.label}</span></li>
          ))}
        </ul></>
      )}
      {view.summary && <p className="about">{view.summary}{view.source && <> <span className="sub">— <SourceLink path={view.source} /></span></>}</p>}
      <div className="buttons">{codeLink(view.code)}</div>
      {against.length > 0 && (
        <><h3>Against the layers</h3>
          <p className="sub">These links point up: they close cycles. The layers are drawn without them.</p>
          <ul className="plain">{against.map((e) => <li key={e.from + e.to}>{labels.get(e.from)} → {labels.get(e.to)} <span className="sub">{counts(e)}</span></li>)}</ul></>
      )}
      {view.stubs && view.stubs.length > 0 && (
        <><h3>Outside this view</h3><ul className="plain">
          {view.stubs.slice(0, 12).map((st) => (
            <li key={st.id} className="mono">{st.id}<div className="sub">
              {[counts(st.out) && "uses: " + counts(st.out), counts(st.in) && "used by: " + counts(st.in)].filter(Boolean).join(" · ")}
            </div></li>
          ))}
          {view.stubs.length > 12 && <li className="sub">… and {view.stubs.length - 12} more</li>}
        </ul></>
      )}
      {notes.map((n, i) => <p key={i} className="note">{n}</p>)}
      <h3>Roles</h3><ul className="plain roles">
        {Object.entries(ROLE_TIPS).map(([r, tip]) => <li key={r}><span className={"role r-" + r}>{r}</span> {tip}</li>)}
        <li className="sub">"Here" is this view: a box's links to the other boxes in it.</li>
      </ul>
      <h3>Key</h3><ul className="plain">
        <li>users sit above what they use; thicker arrows carry more links</li>
        <li><span className="cycle-text">dashed red arrow</span>: {view.kind === "pipeline" ? "a call back to an earlier step" : "against the layers (closes a cycle)"}</li>
        {view.kind === "pipeline" && <li>numbered boxes: steps, in the order the flow first reaches them</li>}
        <li>dashed box: a group of files</li>
        <li>dotted arrow: an entry point, or (on focus) an outside system a part reaches</li>
        <li>◆ a language root · ▸ opens a view of its own</li>
        <li>summaries are the code's own docstrings and READMEs</li>
      </ul>
      <p className="sub gap">Click a box for its details; double-click (or Enter) opens it; Backspace goes up.</p>
    </aside>
  );
}

// -- the docs tab -------------------------------------------------------------------

const unpacked = new Map(); // path -> promise of the document's text

function unpack(doc) {
  if (!unpacked.has(doc.path)) {
    const bytes = Uint8Array.from(atob(doc.gz), (c) => c.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    unpacked.set(doc.path, new Response(stream).text());
  }
  return unpacked.get(doc.path);
}

/** Point a rendered document's links and images where they belong (see
 * docs.linkTarget) and label Mermaid blocks, which are not drawn. */
function fixUp(root, path) {
  for (const a of root.querySelectorAll("a[href]")) {
    const t = linkTarget(a.getAttribute("href"), path, DOC_PATHS);
    if (t.kind === "doc") a.setAttribute("href", docHref(t.path, t.anchor));
    else if (t.kind === "anchor") a.setAttribute("href", docHref(path, t.anchor));
    else if (t.kind === "file") { a.setAttribute("href", code(t.path, t.line)); a.title = "Open in VS Code"; }
    else if (t.kind === "external") { a.target = "_blank"; a.rel = "noopener noreferrer"; }
  }
  for (const img of root.querySelectorAll("img[src]")) {
    const t = linkTarget(img.getAttribute("src"), path, new Set());
    if (t.kind === "file") img.src = "file://" + encodeURI(REPO + "/" + t.path);
  }
  for (const c of root.querySelectorAll("pre > code.language-mermaid")) {
    const note = document.createElement("div");
    note.className = "doc-note";
    note.textContent = "Mermaid diagram, shown as text (not drawn here)";
    c.parentElement.before(note);
  }
}

function DocsPage({ path, anchor }) {
  const doc = DOC_BY_PATH.get(path);
  const ref = useRef(null);
  const [state, setState] = useState({ path: null });
  const [filter, setFilter] = useState("");
  useEffect(() => {
    let live = true;
    if (!doc.gz) { setState({ path, skipped: true }); return undefined; }
    setState({ path, loading: true });
    unpack(doc).then((text) => live && setState({ path, html: DOMPurify.sanitize(render(text)) }),
      (err) => live && setState({ path, error: String(err) }));
    return () => { live = false; };
  }, [path]);
  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = state.path === path && state.html ? state.html : "";
    if (state.html) fixUp(ref.current, path);
  }, [state]);
  useEffect(() => {
    if (!ref.current || !state.html) return;
    const target = anchor && (document.getElementById(HEADING_PREFIX + anchor) || document.getElementById(anchor));
    if (target) target.scrollIntoView();
    else ref.current.parentElement.scrollTop = 0;
  }, [state, anchor]);
  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return byFolder(f ? DOCS.filter((d) => d.path.toLowerCase().includes(f) || d.title.toLowerCase().includes(f)) : DOCS);
  }, [filter]);
  useEffect(() => { document.title = `${doc.title} · Docs · hobbes review`; }, [doc]);
  return (
    <main className="docs">
      <nav className="doc-nav">
        <input className="find" placeholder={`Filter ${DOCS.length} documents…`} value={filter}
          onChange={(ev) => setFilter(ev.target.value)} />
        {(DATA.docs.notes || []).map((n, i) => <p key={i} className="note">{n}</p>)}
        {shown.map(([folder, files]) => (
          <div key={folder} className="doc-group">
            <div className="doc-folder">{folder || "(repo)"}</div>
            {files.map((d) => (
              <a key={d.path} href={docHref(d.path)} className={d.path === path ? "on" : ""} title={`${d.title}\n${d.path}`}>
                {d.path.slice(folder ? folder.length + 1 : 0)}
              </a>
            ))}
          </div>
        ))}
        {!shown.length && <p className="empty">No document matches.</p>}
      </nav>
      <section className="doc-scroll">
        <div className="doc-head">
          <span className="mono">{path}</span>
          <CodeLink path={path}>Open in VS Code</CodeLink>
        </div>
        {state.skipped && <p className="empty pad">Not embedded: {doc.skipped} ({Math.round(doc.bytes / 1024)} KB). <CodeLink path={path}>Open in VS Code</CodeLink>.</p>}
        {state.loading && <p className="empty pad">Opening…</p>}
        {state.error && <p className="empty pad">Could not open: {state.error}</p>}
        <article className="doc" ref={ref} />
      </section>
    </main>
  );
}

// -- the agents tab -------------------------------------------------------------------

/** The repo's agent mapping (DEC-023): the roles beside the chosen one's facts and prompt. */
function AgentsPage({ name }) {
  const ref = useRef(null);
  const role = ROLE_BY_NAME.get(name) || ROLES[0];
  useEffect(() => { document.title = `${role ? role.name + " · " : ""}Agents · hobbes review`; }, [role]);
  useEffect(() => {
    if (ref.current) ref.current.innerHTML = role && role.prompt != null ? DOMPurify.sanitize(render(role.prompt)) : "";
  }, [role]);
  if (!AGENTS) {
    return (
      <main className="agents-none pad">
        <p className="empty">This repo has no agent mapping (<span className="mono">.hobbes/roles.toml</span>).</p>
        <p>Make one in the TUI with <span className="mono">/mode</span> → edit mapping, or with{" "}
          <span className="mono">hobbes roles --edit "…"</span>.</p>
      </main>
    );
  }
  if (AGENTS.error) {
    return (
      <main className="agents-none pad">
        <p className="note">The mapping does not load: {AGENTS.error}</p>
        <pre className="mono">{AGENTS.text}</pre>
      </main>
    );
  }
  return (
    <main className="docs">
      <nav className="doc-nav">
        <div className="doc-folder">Mapping</div>
        <dl className="facts">
          <dt>test</dt><dd className="mono">{AGENTS.test.join(" ")}</dd>
          <dt>merges into</dt><dd className="mono">{AGENTS.branch}</dd>
          <dt>workers</dt><dd>{AGENTS.workers} at a time in a job</dd>
          <dt>coordinator</dt><dd>{AGENTS.coordinator || <span className="empty">none: no jobs</span>}</dd>
        </dl>
        <div className="doc-folder">Roles</div>
        {ROLES.map((r) => (
          <a key={r.name} href={"#r=" + encodeURIComponent(r.name)} className={role && r.name === role.name ? "on" : ""}>
            {r.name} <span className="muted">· {r.agent}{r.coordinator ? " · coordinator" : ""}</span>
          </a>
        ))}
        {!ROLES.length && <p className="empty">No roles.</p>}
        <p className="note">As .hobbes/roles.toml stood when this page was written.</p>
      </nav>
      <section className="doc-scroll">
        {role && (
          <>
            <div className="doc-head">
              <b>{role.name}</b>
              {role.coordinator && <span className="badge">coordinator</span>}
              {role.review && <span className="badge warn">review before merge</span>}
              <span className="muted">{role.agent} · route {role.route} · knowledge {role.knowledge ? "on" : "off"}</span>
              <CodeLink path={role.prompt_path}>Open the prompt in VS Code</CodeLink>
            </div>
            <dl className="facts pad-x">
              <dt>writes</dt>
              <dd>{role.writes.length ? role.writes.map((w) => <span key={w} className="mono chip">{w}</span>)
                : <span className="empty">nothing</span>}</dd>
            </dl>
            {role.prompt == null && <p className="empty pad">The prompt file {role.prompt_path} is missing.</p>}
            <article className="doc" ref={ref} />
          </>
        )}
      </section>
    </main>
  );
}

// -- the page -------------------------------------------------------------------

function App() {
  const where = useViewId();
  if (where.tab === "r") {
    return (
      <>
        <Header tab="r" doc={where.id} />
        <AgentsPage name={where.id} />
      </>
    );
  }
  if (where.tab === "d") {
    return (
      <>
        <Header tab="d" doc={where.id} />
        <DocsPage path={where.id} anchor={where.anchor} />
      </>
    );
  }
  return <Views tab={where.tab} id={where.id} />;
}

function Views({ tab, id }) {
  const views = TABS[tab].views;
  const view = views[id];
  const [selected, setSelected] = useState(null);
  useEffect(() => { setSelected(null); document.title = `${view.title} · ${TABS[tab].name} · hobbes review`; }, [view, tab]);
  const onSelect = useCallback((b) => setSelected((cur) => (b && cur !== b ? b : null)), []);
  useEffect(() => {
    const key = (ev) => {
      if (ev.target.tagName === "INPUT") return;
      if (ev.key === "Backspace" && view.parent != null) { ev.preventDefault(); go(view.parent, tab); }
      else if (ev.key === "Enter" && opens(selected, views)) go(selected.view, tab);
      else if (ev.key === "Escape") setSelected(null);
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [view, selected, tab, views]);
  return (
    <>
      <Header view={view} tab={tab} />
      <main>
        <section className="canvas">
          {ORDERED.has(view.kind)
            ? <ListView view={view} selected={selected} onSelect={onSelect} />
            : <GraphView view={view} selected={selected} onSelect={onSelect} />}
        </section>
        {tab === "a" ? <ArchSide view={view} selected={selected} /> : <Side view={view} selected={selected} />}
      </main>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
