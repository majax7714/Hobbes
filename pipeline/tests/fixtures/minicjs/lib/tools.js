'use strict';

function alpha() {
  return 1;
}

function beta() {
  return 2;
}

const other = { alpha: beta };

module.exports = { alpha, beta, gamma() { return 3 }, delta: alpha };
