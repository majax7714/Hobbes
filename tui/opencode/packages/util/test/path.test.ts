import { expect, test } from "bun:test"
import {
  comparablePath,
  containsDirectory,
  encodeFilePath,
  getDirectory,
  getFilename,
  getFilenameTruncated,
  isLineRangeHash,
  parsePathLineSuffix,
  sameDirectory,
  truncateMiddle,
} from "../src/path"

test("getFilename takes the last segment across both separators and trailing slashes", () => {
  expect(getFilename(undefined)).toBe("")
  expect(getFilename("a/b\\c.ts")).toBe("c.ts")
  expect(getFilename("a/b/")).toBe("b")
})

test("getDirectory keeps everything before the last segment, with a trailing slash", () => {
  expect(getDirectory("")).toBe("")
  expect(getDirectory("a\\b/c.ts//")).toBe("a/b/")
})

test("getFilenameTruncated keeps the extension and cuts the stem", () => {
  expect(getFilenameTruncated("dir/short.ts", 20)).toBe("short.ts")
  expect(getFilenameTruncated("dir/averyveryverylongname.ts", 12)).toBe("averyver….ts")
  expect(getFilenameTruncated(".averyveryverylongname", 10)).toBe(".averyver…")
  expect(getFilenameTruncated("a.verylongextension", 8)).toBe("a.veryl…")
  expect(getFilenameTruncated("abcdefghij.ts", 13)).toBe("abcdefghij.ts")
  expect(getFilenameTruncated("abcdefghijk.ts", 13)).toBe("abcdefghi….ts")
  expect(getFilenameTruncated("x/abcdefghijklmnopqrstu")).toBe("abcdefghijklmnopqrs…")
  expect(getFilenameTruncated("abcd.ext", 5)).toBe("abcd…")
  expect(getFilenameTruncated("abcdef.ts", 5)).toBe("a….ts")
})

test("truncateMiddle keeps more of the start than the end", () => {
  expect(truncateMiddle("abcdef", 6)).toBe("abcdef")
  expect(truncateMiddle("abcdefghij", 6)).toBe("abc…ij")
  expect(truncateMiddle("a".repeat(20))).toBe("a".repeat(20))
  expect(truncateMiddle("a".repeat(21))).toHaveLength(20)
})

test("comparablePath trims trailing slashes but keeps roots", () => {
  expect(comparablePath("/a/b//")).toBe("/a/b")
  expect(comparablePath("///")).toBe("/")
  expect(comparablePath("C:\\Users\\")).toBe("C:/Users")
  expect(comparablePath("C:\\")).toBe("C:/")
  expect(comparablePath("ab")).toBe("ab")
  expect(comparablePath("a/")).toBe("a")
  expect(comparablePath("/a\\b/")).toBe("/a\\b")
})

test("comparablePath roots a drive only for an ASCII letter", () => {
  expect(["A:", "Z:", "a:", "z:"].map(comparablePath)).toEqual(["A:/", "Z:/", "a:/", "z:/"])
  expect(["@:", "[:", "`:", "{:"].map(comparablePath)).toEqual(["@:", "[:", "`:", "{:"])
  expect(comparablePath("a:b")).toBe("a:b")
})

test("containsDirectory needs a segment boundary, and folds case only on Windows paths", () => {
  expect(containsDirectory("/a/b", "/a/b")).toBe(true)
  expect(containsDirectory("/a/b", "/a/b/c")).toBe(true)
  expect(containsDirectory("/a/b", "/a/bc")).toBe(false)
  expect(containsDirectory("/", "/x")).toBe(true)
  expect(containsDirectory("/A", "/a")).toBe(false)
  expect(containsDirectory("C:\\Repo", "c:/repo/src")).toBe(true)
  expect(containsDirectory("\\\\Host\\Share", "//host/share/x")).toBe(true)
  expect(containsDirectory("/A/c:/B", "/A/c:/b")).toBe(false)
  expect(containsDirectory("C:/repo", "C:\\Repo\\src")).toBe(true)
})

test("sameDirectory holds only both ways", () => {
  expect(sameDirectory("/a/b/", "/a/b")).toBe(true)
  expect(sameDirectory("/a", "/a/b")).toBe(false)
  expect(sameDirectory("/a/b", "/a")).toBe(false)
})

test("encodeFilePath roots a drive and encodes every other segment", () => {
  expect(encodeFilePath("C:\\a b\\#.ts")).toBe("/C:/a%20b/%23.ts")
  expect(encodeFilePath("/x/C:/y")).toBe("/x/C%3A/y")
  expect(encodeFilePath("/xC:/y")).toBe("/xC%3A/y")
  expect(encodeFilePath("/C:x/y")).toBe("/C%3Ax/y")
})

test("isLineRangeHash reads #L forms only", () => {
  expect(isLineRangeHash("#L3")).toBe(true)
  expect(isLineRangeHash("#l3C2-L9C1")).toBe(true)
  expect(isLineRangeHash("#L3-9")).toBe(true)
  expect(isLineRangeHash("L3")).toBe(false)
  expect(isLineRangeHash("x#L3")).toBe(false)
  expect(isLineRangeHash("#L3x")).toBe(false)
})

test("parsePathLineSuffix reads a hash range, ordered", () => {
  expect(parsePathLineSuffix("src/a.ts#L9-L3")).toEqual({ path: "src/a.ts", selection: { start: 3, end: 9 } })
  expect(parsePathLineSuffix("src/a.ts#L4")).toEqual({ path: "src/a.ts", selection: { start: 4, end: 4 } })
})

test("parsePathLineSuffix reads a colon range but not a bare drive", () => {
  expect(parsePathLineSuffix("src/a.ts:12:4-15:")).toEqual({ path: "src/a.ts", selection: { start: 12, end: 15 } })
  expect(parsePathLineSuffix("src/a.ts:7")).toEqual({ path: "src/a.ts", selection: { start: 7, end: 7 } })
  expect(parsePathLineSuffix("C:5")).toEqual({ path: "C:5", selection: undefined })
  expect(parsePathLineSuffix("plain")).toEqual({ path: "plain", selection: undefined })
  expect(parsePathLineSuffix("a#L3x")).toEqual({ path: "a#L3x", selection: undefined })
  expect(parsePathLineSuffix("a.ts:3x")).toEqual({ path: "a.ts:3x", selection: undefined })
})

test("parsePathLineSuffix refuses lines outside 1..1,000,000", () => {
  expect(parsePathLineSuffix("a#L0").selection).toBeUndefined()
  expect(parsePathLineSuffix("a#L1000000").selection).toEqual({ start: 1_000_000, end: 1_000_000 })
  expect(parsePathLineSuffix("f.ts:1000001").selection).toBeUndefined()
  expect(parsePathLineSuffix("f.ts:1-1000000").selection).toEqual({ start: 1, end: 1_000_000 })
  expect(parsePathLineSuffix("f.ts:5-1").selection).toEqual({ start: 1, end: 5 })
  // Each bound, on each end of the range, alone.
  for (const range of ["0-5", "5-0", "1000001-5", "5-1000001", "99999999999999999999-5", "5-99999999999999999999"])
    expect(parsePathLineSuffix(`f.ts:${range}`).selection).toBeUndefined()
})
