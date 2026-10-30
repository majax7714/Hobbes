// Tests for the review bundle's license notice (build.mjs). Importing the
// module does not build: the bundle itself is built by `npm run build`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { bundledPackages, licenseNotice } from "../build.mjs";

const META = {
  react: { name: "react", version: "19.3.0", license: "MIT", repository: { url: "git+https://github.com/facebook/react.git" } },
  "@xyflow/react": { name: "@xyflow/react", version: "12.12.0", license: "MIT", repository: "https://github.com/xyflow/xyflow" },
  elkjs: { name: "elkjs", version: "0.12.0", license: "EPL-2.0" },
};

test("each bundled package is named once, scoped ones whole, with its version, license and repository", async () => {
  const read = [];
  const packages = await bundledPackages(
    [
      "src/main.jsx",
      "node_modules/react/index.js",
      "node_modules/@xyflow/react/dist/esm/index.js",
      "node_modules/react/cjs/react.production.js",
      "node_modules/elkjs/lib/elk.bundled.js",
      "node_modules/react",
    ],
    async (name) => {
      read.push(name);
      return META[name];
    },
  );
  assert.deepEqual(read, ["react", "@xyflow/react", "elkjs"]);
  assert.deepEqual(packages, [
    "react 19.3.0 (MIT, https://github.com/facebook/react.git)",
    "@xyflow/react 12.12.0 (MIT, https://github.com/xyflow/xyflow)",
    "elkjs 0.12.0 (EPL-2.0)",
  ]);
});

test("the notice lists the packages sorted, one per line, then elkjs's license and where its source is", () => {
  assert.equal(
    licenseNotice(["react 19.3.0 (MIT)", "elkjs 0.12.0 (EPL-2.0)"]),
    "/*! hobbes review (DEC-019). Bundled packages, each under its own license:\n"
      + " * elkjs 0.12.0 (EPL-2.0)\n"
      + " * react 19.3.0 (MIT)\n"
      + " * elkjs is under EPL-2.0 (https://www.eclipse.org/legal/epl-2.0/); its source is at the repository above.\n */\n",
  );
});
