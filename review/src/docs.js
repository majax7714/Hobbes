// The Docs tab's pure parts (DEC-021): heading anchors, where a link in a
// document goes, and Markdown to HTML. Sanitizing needs a DOM, so the page
// runs DOMPurify on this module's output. No DOM here, so node can test it.

import { Marked } from "marked";

export const HEADING_PREFIX = "h-"; // keeps heading ids clear of the page's own

/** GitHub's heading anchor: lower case, punctuation dropped, spaces to dashes. */
export function slug(text) {
  return text.toLowerCase().trim().replace(/<[^>]*>/g, "").replace(/[^\p{L}\p{N}\s_-]/gu, "").replace(/\s/g, "-");
}

/** *href* from *base* (a file path), normalised; null when it leaves the repo. */
export function resolve(base, href) {
  const parts = href.startsWith("/") ? [] : base.split("/").slice(0, -1);
  for (const part of href.replace(/^\//, "").split("/")) {
    if (part === "" || part === ".") continue;
    if (part === "..") { if (!parts.length) return null; parts.pop(); } else parts.push(part);
  }
  return parts.join("/");
}

/** Where a link in document *from* goes: another doc (and an anchor), an
 * anchor in this one, a repo file (and a line), or outside. */
export function linkTarget(href, from, docs) {
  if (!href) return { kind: "none" };
  if (/^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith("//")) return { kind: "external", href };
  if (href.startsWith("#")) return { kind: "anchor", anchor: decodeURIComponent(href.slice(1)) };
  const [rawPath, rawHash = ""] = href.split("#");
  let path;
  try { path = resolve(from, decodeURIComponent(rawPath.split("?")[0])); } catch { path = null; }
  if (path == null) return { kind: "none" };
  if (docs.has(path)) return { kind: "doc", path, anchor: rawHash ? decodeURIComponent(rawHash) : null };
  const line = /^L(\d+)/.exec(rawHash);
  return { kind: "file", path, line: line ? Number(line[1]) : null };
}

/** Markdown to (unsanitized) HTML, headings with unique anchors. */
export function render(markdown) {
  const seen = new Map();
  const marked = new Marked({
    gfm: true,
    renderer: {
      heading({ tokens, depth, text }) {
        const base = slug(text) || "section";
        const n = seen.get(base) || 0;
        seen.set(base, n + 1);
        const id = HEADING_PREFIX + (n ? `${base}-${n}` : base);
        return `<h${depth} id="${id}"><a class="anchor" href="#${id.slice(HEADING_PREFIX.length)}">#</a>${this.parser.parseInline(tokens)}</h${depth}>\n`;
      },
    },
  });
  return marked.parse(markdown);
}

/** Docs grouped by folder, keeping the given order: [[folder, [doc…]]…]. */
export function byFolder(files) {
  const groups = new Map();
  for (const f of files) {
    const folder = f.path.includes("/") ? f.path.slice(0, f.path.lastIndexOf("/")) : "";
    if (!groups.has(folder)) groups.set(folder, []);
    groups.get(folder).push(f);
  }
  return [...groups];
}
