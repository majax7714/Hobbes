// A higher-order function whose parameter is typed in JSDoc: the call
// inside it has a signature but no declaration behind it.
/** @param {(s: string) => string} f */
function apply(f) {
  return f("a");
}

module.exports = { apply };
