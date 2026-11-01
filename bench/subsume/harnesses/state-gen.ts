// The random state diagrams pinned.py's state harnesses share: every direction, nested composites with markers,
// choices, self loops, labels and notes; a `%%gap` line (a comment to the parser) carries the minimum gap.

const LABELS = ["", "", "", "go", "retry", "a<br>b", "a long label here", "x<br>yy<br>zzz"]

export function generate(rand: () => number): string {
  const pick = <T>(items: readonly T[]) => items[Math.floor(rand() * items.length)]!
  const chance = (p: number) => rand() < p
  const label = () => {
    const text = pick(LABELS)
    return text ? ` : ${text}` : ""
  }
  const lines = [`%%gap ${chance(0.2) ? 1 + Math.floor(rand() * 8) : 5}`, "stateDiagram-v2"]
  if (chance(0.7)) lines.push(`direction ${pick(["LR", "LR", "TB", "TD", "BT", "RL"])}`)
  const outer = ["A", "B", "C", "D"].slice(0, 2 + Math.floor(rand() * 3))
  const named: string[] = [...outer]
  const composites: string[] = []
  // Composites, each with a few inner states and maybe a nested one.
  for (let c = Math.floor(rand() * 3); c > 0; c--) {
    const id = `P${composites.length}`
    composites.push(id)
    lines.push(chance(0.3) ? `state "${pick(["Outer", "A long composite title"])}" as ${id} {` : `state ${id} {`)
    const inner = [`${id}x`, `${id}y`].slice(0, 1 + Math.floor(rand() * 2))
    named.push(...inner)
    if (chance(0.5)) lines.push(`[*] --> ${inner[0]}`)
    if (inner.length > 1) lines.push(`${inner[0]} --> ${inner[1]}${label()}`)
    else lines.push(`state "${pick(["In", "Inside"])}" as ${inner[0]}`)
    if (chance(0.4)) lines.push(`${inner[inner.length - 1]} --> [*]`)
    if (chance(0.2)) {
      const nested = `${id}n`
      composites.push(nested)
      lines.push(`state ${nested} {`, `${nested}z --> ${nested}w`, "}")
      named.push(`${nested}z`, `${nested}w`)
    }
    lines.push("}")
  }
  if (chance(0.3)) {
    lines.push("state ch <<choice>>")
    named.push("ch")
  }
  const targets = [...named, ...composites]
  if (chance(0.6)) lines.push(`[*] --> ${pick(outer)}`)
  for (let n = 1 + Math.floor(rand() * 6); n > 0; n--) {
    const from = pick(targets)
    const to = chance(0.15) ? from : pick(targets)
    lines.push(`${from} --> ${to}${label()}`)
  }
  if (chance(0.4)) lines.push(`${pick(outer)} --> [*]`)
  for (let n = chance(0.4) ? 1 + Math.floor(rand() * 2) : 0; n > 0; n--) {
    lines.push(`note ${pick(["left", "right"])} of ${pick(named)} : ${pick(["n", "a note", "two<br>lines"])}`)
  }
  return lines.join("\n")
}
