// CommonJS: a declaration exported by name, and a function literal
// assigned straight onto `exports`.
function add(a, b) {
  return a + b;
}

exports.add = add;

exports.double = function (x) {
  return add(x, x);
};
