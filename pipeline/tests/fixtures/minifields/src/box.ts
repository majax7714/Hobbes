export function f(): number { return 1; }
export class Box {
  static create = (n: number): Box => { f(); return new Box(); };
  pick = (a: number): number => f() + a;
  plain = f();
  run() { return this.pick(1); }
}
