const Counter = require("./lib/counter");

function build() {
  return new Counter(1);
}

module.exports = { build };
