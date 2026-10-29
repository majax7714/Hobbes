import { expect, test } from "bun:test"
import { Binary } from "../src/binary"

const id = (item: { id: string }) => item.id
const items = ["b", "d", "f"].map((id) => ({ id }))

test("search finds an item or the index it would take", () => {
  expect(Binary.search(items, "d", id)).toEqual({ found: true, index: 1 })
  expect(Binary.search(items, "f", id)).toEqual({ found: true, index: 2 })
  expect(Binary.search(items, "a", id)).toEqual({ found: false, index: 0 })
  expect(Binary.search(items, "c", id)).toEqual({ found: false, index: 1 })
  expect(Binary.search(items, "e", id)).toEqual({ found: false, index: 2 })
  expect(Binary.search(items, "g", id)).toEqual({ found: false, index: 3 })
  expect(Binary.search([], "a", id)).toEqual({ found: false, index: 0 })
})

test("insert keeps the order and places an equal id before its peers", () => {
  const array = [{ id: "b" }, { id: "d", n: 1 }]
  Binary.insert(array, { id: "a" }, id)
  Binary.insert(array, { id: "e" }, id)
  Binary.insert(array, { id: "d", n: 2 }, id)
  Binary.insert(array, { id: "c" }, id)
  expect(array).toEqual([{ id: "a" }, { id: "b" }, { id: "c" }, { id: "d", n: 2 }, { id: "d", n: 1 }, { id: "e" }])
})
