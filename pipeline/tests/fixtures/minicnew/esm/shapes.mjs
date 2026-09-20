// The two class shapes ADR-142 tells apart: one that declares its own
// constructor, and one that declares none.
export class Circle {
  constructor(r) {
    this.r = r;
  }

  area() {
    return this.r * this.r;
  }
}

export class Square {
  area() {
    return 1;
  }
}
