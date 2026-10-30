// Build the review page's drawing (DEC-019): bundle src/main.jsx into
// dist/review.js and dist/review.css, which hobbes.review inlines into the
// page. The script starts with a notice naming every bundled package, its
// version and license (elkjs is EPL-2.0: its notice and source link ship
// with the page). Run as `node build.mjs`; imported, it only exports the
// notice's two steps, which test/build.test.js checks.

import * as esbuild from "esbuild";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Each package the bundle drew a file from, once, in input order, as
 * "name version (license, repository)"; `readMeta` reads a package's
 * package.json. A scoped package keeps its scope. */
export async function bundledPackages(inputs, readMeta) {
  const packages = new Map();
  for (const input of inputs) {
    const m = /node_modules\/((?:@[^/]+\/)?[^/]+)\//.exec(input);
    if (m && !packages.has(m[1])) {
      const meta = await readMeta(m[1]);
      const repo = typeof meta.repository === "string" ? meta.repository : meta.repository?.url;
      packages.set(m[1], `${meta.name} ${meta.version} (${meta.license}${repo ? ", " + repo.replace(/^git\+/, "") : ""})`);
    }
  }
  return [...packages.values()];
}

/** The comment the script starts with: every package, sorted, then elkjs's license and source. */
export function licenseNotice(packages) {
  return "/*! hobbes review (DEC-019). Bundled packages, each under its own license:\n"
    + [...packages].sort().map((p) => " * " + p).join("\n")
    + "\n * elkjs is under EPL-2.0 (https://www.eclipse.org/legal/epl-2.0/); its source is at the repository above.\n */\n";
}

async function build() {
  const here = path.dirname(fileURLToPath(import.meta.url));
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
  const packages = await bundledPackages(Object.keys(result.metafile.inputs), async (name) =>
    JSON.parse(await readFile(path.join(here, "node_modules", name, "package.json"), "utf8")));
  const notice = licenseNotice(packages);
  await mkdir(path.join(here, "dist"), { recursive: true });
  for (const file of result.outputFiles) {
    const text = file.path.endsWith(".js") ? notice + file.text : file.text;
    await writeFile(file.path, text);
    console.log(`${path.relative(here, file.path)}  ${(Buffer.byteLength(text) / 1024).toFixed(0)} KB`);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await build();
