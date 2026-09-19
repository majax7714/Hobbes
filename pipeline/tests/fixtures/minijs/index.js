// The four require shapes, and one call of each on its own line.
const math = require("./lib/math");
const Counter = require("./lib/counter");
const { add } = require("./lib/math");
const { apply } = require("./lib/apply");

function main() {
  const c = new Counter(1);
  c.inc();
  math.double(2);
  add(1, 2);
  apply((s) => s);
}

module.exports = { main };
