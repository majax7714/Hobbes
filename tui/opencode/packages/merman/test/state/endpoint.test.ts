import { expect, test } from "bun:test"
import {
  normalizeStateDiagramEndpoint,
  stateDiagramEndMarkerId,
  stateDiagramMarkerId,
  stateDiagramStartMarkerId,
} from "../../src/state/endpoint"

test("a marker's id is __start or __end, prefixed by the composite it is in", () => {
  expect([
    stateDiagramStartMarkerId(),
    stateDiagramEndMarkerId(),
    stateDiagramStartMarkerId("P"),
    stateDiagramEndMarkerId("P"),
  ]).toEqual(["__start", "__end", "P.__start", "P.__end"])
  expect([stateDiagramMarkerId("from"), stateDiagramMarkerId("to", "Q")]).toEqual(["__start", "Q.__end"])
})

test("only [*] becomes a marker: a start as a source, an end as a target", () => {
  expect([
    normalizeStateDiagramEndpoint("[*]", "from"),
    normalizeStateDiagramEndpoint("[*]", "to", "P"),
    normalizeStateDiagramEndpoint("A", "from", "P"),
    normalizeStateDiagramEndpoint("[*]x", "to"),
  ]).toEqual(["__start", "P.__end", "A", "[*]x"])
})
