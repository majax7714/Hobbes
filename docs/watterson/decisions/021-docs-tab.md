# 021: A Docs tab on the review page, to read the repo's documentation

- Status: accepted; built (see note)
- Date: 2026-10-17
- Builds on: DEC-018 (the review page), DEC-020 (its tabs); open-work
  item 4

## Context
The user (2026-10-17) is replacing VS Code with `watterson review` and
asked for "a tab for docs which is just a space to read the repos
documentation". The page is one stamped offline file with no server
(DEC-018), so a browser on it cannot read other local files: the docs
must be inside the page. hobbes-public has 464 Markdown files, 8.3 MB
(3.7 MB gzipped and base64-encoded), with Mermaid blocks in four of them.

## Decision
1. **A third tab, Docs**, after Architecture and Code map (`#d=<path>`).
   A file list grouped by folder, filtered by name, beside the open
   document. The repo's root README opens first.
2. **Which files:** Markdown (`.md`, `.markdown`, `.mdx`) that git tracks
   or would track (`git ls-files --cached --others --exclude-standard`),
   without test fixtures and `node_modules`; a walk of the tree when git
   is unavailable. Files over `MAX_DOC_BYTES` (2 MB) are listed, not
   embedded. Read from the working tree at review time, like DEC-020's
   summaries, with the same note when HEAD has moved past the graph's
   commit.
3. **Embedded compressed:** each file gzipped and base64-encoded in the
   page data, unpacked in the browser (`DecompressionStream`) when opened.
4. **Rendering:** `marked` (MIT) to HTML, then DOMPurify (MPL-2.0 or
   Apache-2.0) so a document's raw HTML cannot run script in the page;
   exact pins in `review/`. Headings get anchors. Links to other docs open
   in the tab; links to other repo files open in VS Code (as elsewhere on
   the page); outside links open a new browser tab. Relative images load
   from the working tree (`file://`), not embedded.
5. **Not now:** drawing Mermaid blocks (they show as code; Mermaid would
   add megabytes to every page), search inside documents, other formats
   (reStructuredText, AsciiDoc).

## Consequences
- Pages grow by the repo's docs, compressed: hobbes-public's goes from
  6.3 MB to about 10 MB.
- Two more bundled packages to keep current by hand.
- A box whose summary came from a README links to it in the Docs tab.

### Note, 2026-10-17: built
- `hobbes.repodocs` collects the files; `review.page_data` embeds them as
  `docs`. The page: `review/src/docs.js` (anchors, link targets, Markdown
  to HTML), the tab in `src/main.jsx`. Pinned `marked` 18.0.14 and
  `dompurify` 3.4.16, both at least two weeks old; the bundle's notice
  lists them. The bundle is 1.94 MB (was 1.86).
- hobbes-public: 462 documents (none over 2 MB); its page is 10.1 MB (was
  6.3). Collecting takes about 0.25 s.
- Checked in headless Firefox on hobbes-public: the README with its
  image from the working tree, a document with Mermaid blocks (labelled,
  shown as text), the name filter, and the README's links (to other
  documents, to anchors, outside). A component whose summary came from a
  README links to it in the tab. Not checked: a real browser, keys in
  this tab.
