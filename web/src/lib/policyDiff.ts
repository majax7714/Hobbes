/**
 * The line diff shown before a policy write (ADR-026).
 *
 * If review stays on the human's side, seeing exactly what will land in
 * repo.policy is the review — so this runs client-side, before the PUT,
 * rather than reporting what already happened.
 */

/**
 * A minimal line diff — enough to see what changed in a policy file,
 * which is a few dozen lines. Common prefix and suffix are elided; the
 * middle is shown as removals then additions.
 */
export function diffLines(
  before: string,
  after: string,
): { kind: 'add' | 'del' | 'context'; text: string }[] {
  const a = before.split('\n')
  const b = after.split('\n')
  let head = 0
  while (head < a.length && head < b.length && a[head] === b[head]) head++
  let tail = 0
  while (
    tail < a.length - head &&
    tail < b.length - head &&
    a[a.length - 1 - tail] === b[b.length - 1 - tail]
  ) {
    tail++
  }
  const rows: { kind: 'add' | 'del' | 'context'; text: string }[] = []
  const contextBefore = Math.max(0, head - 2)
  for (let i = contextBefore; i < head; i++) rows.push({ kind: 'context', text: ' ' + a[i] })
  for (let i = head; i < a.length - tail; i++) rows.push({ kind: 'del', text: '-' + a[i] })
  for (let i = head; i < b.length - tail; i++) rows.push({ kind: 'add', text: '+' + b[i] })
  const contextAfter = Math.min(a.length, a.length - tail + 2)
  for (let i = a.length - tail; i < contextAfter; i++) {
    rows.push({ kind: 'context', text: ' ' + a[i] })
  }
  return rows
}
