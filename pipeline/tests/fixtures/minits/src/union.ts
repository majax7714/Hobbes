// A member call on a union-typed receiver — the oracle lane's
// `static→union-member` shape (ajv 3 rows, hono 7; ADR-104, C-97). Three
// cases: the members override the method (distinct declarations — lane A
// abstains and the join vetoes lane B's first-member pick), the members
// share the base's method (one declaration — resolved), and the call sits
// inside a class with its own override (ajv's `If`: the receiver's union
// decides, not the enclosing class).
export class Base {
  render(): string { return "base"; }
  tag(): string { return "b"; }
}
export class Alpha extends Base {
  render(): string { return "alpha"; }
}
export class Beta extends Base {
  render(): string { return "beta"; }
}
export type Either = Alpha | Beta;

export function draw(n: Either): string {
  return n.render();
}
export function label(n: Either): string {
  return n.tag();
}
export class Holder extends Base {
  items: Either[] = [];
  render(): string {
    return this.items.map((i) => i.render()).join(",");
  }
}
