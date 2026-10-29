import { expect, mock, test } from "bun:test"
import { Effect, Layer } from "effect"
import { runID } from "../src/observability/shared"

// The logger's options are opaque once made, so its maker is replaced to read them.
mock.module("effect/observability", () => ({ OtlpLogger: { make: (options: unknown) => options } }))
// The tracing SDK's pieces are replaced the same way: each records how it was made.
const tracing = { config: undefined as any, enabled: 0, global: undefined as unknown }
mock.module("@effect/opentelemetry/NodeSdk", () => ({
  layer: (make: () => unknown) => {
    tracing.config = make()
    return Layer.empty
  },
}))
mock.module("@opentelemetry/exporter-trace-otlp-http", () => ({
  OTLPTraceExporter: class {
    constructor(readonly options: unknown) {}
  },
}))
mock.module("@opentelemetry/sdk-trace-base", () => ({
  BatchSpanProcessor: class {
    constructor(readonly exporter: { options: unknown }) {}
  },
}))
mock.module("@opentelemetry/context-async-hooks", () => ({
  AsyncLocalStorageContextManager: class {
    enable() {
      tracing.enabled++
    }
  },
}))
mock.module("@opentelemetry/api", () => ({
  context: { setGlobalContextManager: (manager: unknown) => void (tracing.global = manager) },
}))
const { Otlp } = await import("../src/observability/otlp")

const app = { client: "cli", version: "1.2.3", channel: "beta" }

function withAttributes<T>(value: string | undefined, fn: () => T) {
  const before = process.env.OTEL_RESOURCE_ATTRIBUTES
  if (value === undefined) delete process.env.OTEL_RESOURCE_ATTRIBUTES
  else process.env.OTEL_RESOURCE_ATTRIBUTES = value
  try {
    return fn()
  } finally {
    if (before === undefined) delete process.env.OTEL_RESOURCE_ATTRIBUTES
    else process.env.OTEL_RESOURCE_ATTRIBUTES = before
  }
}

test("resource names the app and its run, and the app's fields win over the environment's", () => {
  const resource = withAttributes("team=core,opencode.client=env", () => Otlp.resource(app))
  expect(resource).toEqual({
    serviceName: "opencode",
    serviceVersion: "1.2.3",
    attributes: {
      team: "core",
      "deployment.environment.name": "beta",
      "opencode.client": "cli",
      "opencode.run": runID(),
      "service.instance.id": runID(),
    },
  })
  const plain = withAttributes(undefined, () => Otlp.resource())
  expect(plain.serviceVersion).toBe("unknown")
  expect(plain.attributes["opencode.client"]).toBe("opencode")
  expect(plain.attributes["deployment.environment.name"]).toBe("local")
  // Entries are percent-decoded and split at the first =; a one-character key is a key.
  const { attributes } = withAttributes("a%20b=c=d%2C,k=v", () => Otlp.resource(app))
  expect(attributes["a b"]).toBe("c=d,")
  expect(attributes.k).toBe("v")
})

test("one malformed OTEL_RESOURCE_ATTRIBUTES entry drops them all", () => {
  for (const value of ["good=1,=bad", "good=1,novalue", "good=%E0%A4%A"]) {
    const { attributes } = withAttributes(value, () => Otlp.resource(app))
    expect(attributes.good).toBeUndefined()
    expect(attributes["opencode.client"]).toBe("cli")
  }
})

test("loggers and tracing are off without an endpoint", async () => {
  expect(Otlp.loggers(undefined, app)).toEqual([])
  expect(Otlp.loggers({ headers: "a=b" }, app)).toEqual([])
  expect(await Effect.runPromise(Otlp.tracingLayer(undefined, app))).toBe(Layer.empty)
})

test("a logger posts to the endpoint's /v1/logs with the parsed headers and the app's resource", () => {
  const [logger] = Otlp.loggers({ endpoint: "http://collector", headers: "auth=a=b,x=1" }, app) as unknown as [
    { url: string; headers: unknown; resource: ReturnType<typeof Otlp.resource> },
  ]
  expect(logger.url).toBe("http://collector/v1/logs")
  expect(logger.headers).toEqual({ auth: "a=b", x: "1" })
  expect(logger.resource.attributes["opencode.client"]).toBe("cli")
  const [bare] = Otlp.loggers({ endpoint: "http://collector" }, app) as unknown as [{ headers: unknown }]
  expect(bare.headers).toBeUndefined()
})

test("with an endpoint, tracing exports to /v1/traces with the parsed headers, under a global context manager", async () => {
  const layer = await Effect.runPromise(Otlp.tracingLayer({ endpoint: "http://collector", headers: "a=1" }, app))
  expect(tracing.config.spanProcessor.exporter.options).toEqual({
    url: "http://collector/v1/traces",
    headers: { a: "1" },
  })
  expect(tracing.config.resource.attributes["opencode.client"]).toBe("cli")
  expect(tracing.enabled).toBe(1)
  expect(tracing.global).toBeDefined()
  // The layer builds in a scope of its own, closed with it.
  await Effect.runPromise(Effect.scoped(Layer.build(layer)))
})
