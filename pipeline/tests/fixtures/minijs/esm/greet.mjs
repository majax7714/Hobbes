export function greet(name) {
  return "hi " + name;
}

export class Greeter {
  hello() {
    return greet("x");
  }
}
