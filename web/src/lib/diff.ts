/**
 * Patch parsing for the Diff tab — §7's tab 4, the raw line diff, read
 * last. Splitting a unified diff into per-file hunks is all the tab
 * needs; nothing here interprets the change, which is the point of
 * reaching for this tab only when the first three raise a question.
 */

export type PatchLineKind = 'add' | 'del' | 'context' | 'hunk' | 'meta'

export interface PatchLine {
  kind: PatchLineKind
  text: string
}

export interface PatchFile {
  /** The b-side path, or the a-side for a deletion. */
  path: string
  lines: PatchLine[]
}

/**
 * parsePatch splits `git diff` output into files. Unknown leading
 * characters are `meta`, so a mode change or binary notice renders as
 * itself rather than being silently dropped.
 */
export function parsePatch(patch: string): PatchFile[] {
  const files: PatchFile[] = []
  let current: PatchFile | null = null

  for (const line of patch.split('\n')) {
    if (line.startsWith('diff --git ')) {
      current = { path: pathFromHeader(line), lines: [] }
      files.push(current)
      continue
    }
    if (!current) continue
    current.lines.push({ kind: classify(line), text: line })
  }
  return files
}

function classify(line: string): PatchLineKind {
  if (line.startsWith('@@')) return 'hunk'
  // +++/--- are headers, not content, and must not read as add/delete.
  if (line.startsWith('+++') || line.startsWith('---')) return 'meta'
  if (line.startsWith('+')) return 'add'
  if (line.startsWith('-')) return 'del'
  if (line.startsWith(' ') || line === '') return 'context'
  return 'meta'
}

/** `diff --git a/x b/x` → `x`, tolerating spaces in the path. */
function pathFromHeader(line: string): string {
  const rest = line.slice('diff --git '.length)
  const bAt = rest.lastIndexOf(' b/')
  if (bAt >= 0) return rest.slice(bAt + 3)
  return rest
}

/** shortSHA is the 12 characters the rest of Hobbes cites (ADR-006). */
export function shortSHA(sha: string): string {
  return sha ? sha.slice(0, 12) : ''
}
