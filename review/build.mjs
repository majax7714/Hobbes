// Build the review page's drawing (DEC-019): bundle src/main.jsx into
// dist/review.js and dist/review.css, which hobbes.review inlines into the
// page. The script starts with a notice naming every bundled package, its
// version and license (elkjs is EPL-2.0: its notice and source link ship
// with the page).

import * as esbuild from "esbuild";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const here = path.dirname(new URL(import.meta.url).pathname);
const result = await esbuild.build({
  absWorkingDir: here,
  entryPoints: ["src/main.jsx"],
  bundle: true,
  minify: true,
  format: "iife",
  target: "es2020",
  jsx: "automatic",
  legalComments: "none",
  define: { "process.env.NODE_ENV": '"production"' },
  outdir: "dist",
  entryNames: "review",
  metafile: true,
  write: false,
  logLevel: "warning",
});

const packages = new Map();
for (const input of Object.keys(result.metafile.inputs)) {
  const m = /node_modules\/((?:@[^/]+\/)?[^/]+)\//.exec(input);
  if (m && !packages.has(m[1])) {
    const meta = JSON.parse(await readFile(path.join(here, "node_modules", m[1], "package.json"), "utf8"));
    const repo = typeof meta.repository === "string" ? meta.repository : meta.repository?.url;
    packages.set(m[1], `${meta.name} ${meta.version} (${meta.license}${repo ? ", " + repo.replace(/^git\+/, "") : ""})`);
  }
}
const notice = "/*! hobbes review (DEC-019). Bundled packages, each under its own license:\n"
  + [...packages.values()].sort().map((p) => " * " + p).join("\n")
  + "\n * elkjs is under EPL-2.0 (https://www.eclipse.org/legal/epl-2.0/); its source is at the repository above.\n */\n";

await mkdir(path.join(here, "dist"), { recursive: true });
for (const file of result.outputFiles) {
  const text = file.path.endsWith(".js") ? notice + file.text : file.text;
  await writeFile(file.path, text);
  console.log(`${path.relative(here, file.path)}  ${(Buffer.byteLength(text) / 1024).toFixed(0)} KB`);
}
