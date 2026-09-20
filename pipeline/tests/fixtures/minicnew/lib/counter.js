// Pre-class style: a constructor function that is the module's whole
// export, which is what `new Counter(1)` in index.js runs.
function Counter(start) {
  this.n = start;
}

Counter.prototype.inc = function () {
  this.n += 1;
  return this.n;
};

module.exports = Counter;
