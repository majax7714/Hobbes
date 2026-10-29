import { expect, mock, test } from "bun:test"

const opened: string[] = []
mock.module("open", () => ({ default: async (target: string) => void opened.push(target) }))
const { openPath, openUrl } = await import("../src/open")

test("openUrl opens only an http or https URL, normalized", async () => {
  await openUrl("https://example.com/a b")
  await openUrl("http://example.com")
  for (const input of ["file:///etc/passwd", "javascript:alert(1)", "not a url"])
    await expect(openUrl(input)).rejects.toThrow(`Only http and https links can be opened in the browser: ${input}`)
  expect(opened.splice(0)).toEqual(["https://example.com/a%20b", "http://example.com/"])
})

test("openPath opens the path as given", async () => {
  await openPath("/tmp/some file")
  expect(opened.splice(0)).toEqual(["/tmp/some file"])
})
