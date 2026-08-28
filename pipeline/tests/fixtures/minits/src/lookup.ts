// Element-access callees, one per shape (A-4 / H-17): a string literal
// key, a well-known Symbol member, and a computed key. What the scip
// lane emits for each decides the oracle's site rule (D-O4).
import { normalize } from "./util.js";

const table = {
  norm: normalize,
  quoted: (s: string) => s,
};

export function viaLiteral(s: string) {
  return table["norm"](s);
}

export function viaSymbol(xs: string[]) {
  return xs[Symbol.iterator]();
}

export function viaComputed(k: "norm" | "quoted", s: string) {
  return table[k](s);
}
