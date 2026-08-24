import { describe, expect, it } from 'vitest'

import { parsePatch, shortSHA } from './diff'

const patch = `diff --git a/src/app/core.py b/src/app/core.py
index 1111111..2222222 100644
--- a/src/app/core.py
+++ b/src/app/core.py
@@ -1,3 +1,3 @@
 def run():
-    return 1
+    return 2

diff --git a/assets/logo.png b/assets/logo.png
Binary files a/assets/logo.png and b/assets/logo.png differ
`

describe('parsePatch', () => {
  const files = parsePatch(patch)

  it('splits the patch per file', () => {
    expect(files.map((f) => f.path)).toEqual(['src/app/core.py', 'assets/logo.png'])
  })

  it('classifies additions and deletions', () => {
    const kinds = files[0].lines.map((l) => l.kind)
    expect(kinds).toContain('add')
    expect(kinds).toContain('del')
    expect(kinds).toContain('hunk')
  })

  it('does not read the +++/--- headers as content', () => {
    const headers = files[0].lines.filter(
      (l) => l.text.startsWith('+++') || l.text.startsWith('---'),
    )
    expect(headers.length).toBe(2)
    expect(headers.every((l) => l.kind === 'meta')).toBe(true)
  })

  it('keeps a binary notice as a visible meta line rather than dropping it', () => {
    expect(files[1].lines.some((l) => l.kind === 'meta' && l.text.startsWith('Binary files'))).toBe(
      true,
    )
  })

  it('handles an empty patch', () => {
    expect(parsePatch('')).toEqual([])
  })

  it('reads a path containing spaces from the b-side', () => {
    const spaced = parsePatch('diff --git a/my dir/file.txt b/my dir/file.txt\n@@ -1 +1 @@\n')
    expect(spaced[0].path).toBe('my dir/file.txt')
  })
})

describe('shortSHA', () => {
  it('cites 12 characters, as the rest of Hobbes does', () => {
    expect(shortSHA('3be6bafd6612b7273880d70fe17a83a82c6209c9')).toBe('3be6bafd6612')
    expect(shortSHA('')).toBe('')
  })
})
