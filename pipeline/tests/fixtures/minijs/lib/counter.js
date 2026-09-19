// Pre-class style: a constructor function, a method on its prototype,
// and the constructor as the module's whole export.
function Counter(start) {
  this.n = start;
}

Counter.prototype.inc = function () {
  this.n += 1;
  return this.n;
};

module.exports = Counter;
