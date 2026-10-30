// The review page's logic that needs no browser (DEC-018): its links, titles,
// counts and hash routing. main.jsx binds these to the page's inline DATA and
// renders; test/page.test.js checks them. Nothing here touches the DOM.

/** A VS Code link to a repo path, at a line when given. */
export const vscodeLink = (repo, path, line) => `vscode://file/${encodeURI(repo + "/" + path)}${line ? ":" + line : ""}`;

/** A view's title, its id when it has none in `views`, "(repo)" for the root. */
export const viewTitle = (id, views) => (id in views ? views[id].title : id || "(repo)");

/** Whether a box opens a view `views` holds. */
export const opensView = (box, views) => Boolean(box && box.view != null && box.view in views);

/** "1 module", "2 modules". */
export const many = (n, noun) => `${n} ${noun}${n === 1 ? "" : "s"}`;

/** The tabs that have a root, in the page's order. */
export const tabOrder = (tabs) => ["a", "v", "d", "r"].filter((t) => tabs[t] && tabs[t].root != null);

/** The tab and view a location hash names (#a=, #v=, #d=<path>[#<anchor>], #r=<role>), falling back to the
 * first tab, a tab's root, the first document or no role when the hash names nothing the page holds. */
export function parseHash(hash, { tabs, docPaths, roleNames }) {
  const order = tabOrder(tabs);
  const m = /^#([avdr])=([^#]*)(?:#(.*))?$/.exec(hash);
  const tab = m && order.includes(m[1]) ? m[1] : order[0];
  const id = m && m[1] === tab ? decodeURIComponent(m[2]) : tabs[tab].root;
  if (tab === "d") return { tab, id: docPaths.has(id) ? id : tabs.d.root, anchor: m && m[3] ? decodeURIComponent(m[3]) : null };
  if (tab === "r") return { tab, id: roleNames.has(id) ? id : "" };
  return { tab, id: id in tabs[tab].views ? id : tabs[tab].root };
}

/** The hash that opens view `id` in `tab`. */
export const viewHash = (id, tab = "v") => tab + "=" + encodeURIComponent(id);

/** The hash that opens a document, at an anchor when given. */
export const docHref = (path, anchor) => "#d=" + encodeURIComponent(path) + (anchor ? "#" + encodeURIComponent(anchor) : "");

/** What a rendered document's link becomes, from docs.linkTarget's answer: a document or an anchor in this
 * one opens in the Docs tab, a repo file in VS Code, an outside link in a new tab; anything else is left. */
export function linkAttributes(target, path, repo) {
  if (target.kind === "doc") return { href: docHref(target.path, target.anchor) };
  if (target.kind === "anchor") return { href: docHref(path, target.anchor) };
  if (target.kind === "file") return { href: vscodeLink(repo, target.path, target.line), title: "Open in VS Code" };
  if (target.kind === "external") return { target: "_blank", rel: "noopener noreferrer" };
  return {};
}

/** Where a rendered document's image of a repo file loads from; null for anything else. */
export const imageSource = (target, repo) => (target.kind === "file" ? "file://" + encodeURI(repo + "/" + target.path) : null);
