import { Box } from "./box";
export function main() {
  const b = Box.create(1);
  return b.pick(2);
}
