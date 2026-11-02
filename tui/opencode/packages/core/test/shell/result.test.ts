import { describe, expect, test } from "bun:test"
import type { Shell } from "@opencode/schema/shell"
import { ShellResult } from "../../src/shell/result"

const info = (fields: Partial<Shell.Info> = {}) =>
  ({ id: "sh_1", command: "ls", status: "exited", ...fields }) as Shell.Info
const captured = (output: string, truncated = false) => ({ output, truncated })

describe("unavailable", () => {
  test("says the output is gone, its cursor and size the message's bytes", () => {
    expect(ShellResult.unavailable).toEqual({
      output: "Shell command output is no longer available.",
      cursor: 44,
      size: 44,
      truncated: false,
    })
  })
})

describe("output", () => {
  test("is the capture, with an exit (even 0) or a signal only when the shell has one", () => {
    expect(ShellResult.output({ info: info(), capture: captured("hi", true) })).toEqual({
      output: "hi",
      truncated: true,
    })
    expect(ShellResult.output({ info: info({ exit: 0, signal: "SIGTERM" }), capture: captured("") })).toEqual({
      output: "",
      truncated: false,
      exit: 0,
      signal: "SIGTERM",
    })
  })

  test("with no capture, is the unavailable message, not truncated", () => {
    expect(ShellResult.output({ info: info(), capture: undefined })).toEqual({
      output: "Shell command output is no longer available.",
      truncated: false,
    })
  })

  test("marks a timed-out shell", () => {
    expect(ShellResult.output({ info: info({ status: "timeout" }), capture: captured("") }).timeout).toBe(true)
  })
})

describe("notice", () => {
  test("a timeout comes before a signal, a signal before an exit code", () => {
    expect(ShellResult.notice({ timeout: true, signal: "SIGTERM", exit: 1 })).toBe("Timed out before completion")
    expect(ShellResult.notice({ signal: "SIGTERM", exit: 1 })).toBe("Killed by SIGTERM")
    expect(ShellResult.notice({ exit: 2 })).toBe("Exited with code 2")
  })

  test("exit 0, or nothing known, has no notice", () => {
    expect(ShellResult.notice({ exit: 0 })).toBeUndefined()
    expect(ShellResult.notice({})).toBeUndefined()
  })
})

describe("metadata", () => {
  test("keeps truncated and only the fields that are set, without the output", () => {
    expect(ShellResult.metadata({ output: "x", truncated: false })).toEqual({ truncated: false })
    expect(ShellResult.metadata({ output: "x", truncated: true, exit: 0, signal: "SIGINT", timeout: false })).toEqual({
      truncated: true,
      exit: 0,
      signal: "SIGINT",
      timeout: false,
    })
  })
})

describe("notification", () => {
  test("wraps the text in a tag named by the shell, or by a job if there is one, whose output's metadata joins", () => {
    expect(ShellResult.notification({ shellID: "s", command: "ls", state: "error", text: "boom" })).toEqual({
      text: '<shell id="s" state="error" command="ls">\nboom\n</shell>',
      metadata: { source: "shell", shellID: "s", state: "error" },
    })
    expect(
      ShellResult.notification({
        shellID: "s",
        jobID: "j",
        command: "ls",
        state: "completed",
        text: "ok",
        output: { output: "ok", truncated: true, exit: 0 },
      }),
    ).toEqual({
      text: '<shell id="j" state="completed" command="ls">\nok\n</shell>',
      metadata: { source: "shell", shellID: "s", jobID: "j", state: "completed", truncated: true, exit: 0 },
    })
  })
})

describe("userNotification", () => {
  const text = (body: string, state = "completed") =>
    `The following shell command was executed by the user:\n<shell id="sh_1" state="${state}" command="ls">\n${body}\n</shell>`

  test("exit 0 is the output alone; a failure follows it after a blank line, or stands alone if it is empty", () => {
    expect(ShellResult.userNotification({ info: info({ exit: 0 }), capture: captured("hi") }).text).toBe(text("hi"))
    expect(ShellResult.userNotification({ info: info({ exit: 3 }), capture: captured("hi") }).text).toBe(
      text("hi\n\nExited with code 3"),
    )
    expect(ShellResult.userNotification({ info: info({ exit: 3 }), capture: captured("") }).text).toBe(
      text("Exited with code 3"),
    )
  })

  test("no exit known reads as unknown", () => {
    expect(ShellResult.userNotification({ info: info(), capture: captured("hi") }).text).toBe(
      text("hi\n\nExited with code unknown"),
    )
  })

  test("a killed shell is cancelled, whatever its signal", () => {
    const result = ShellResult.userNotification({
      info: info({ status: "killed", signal: "SIGKILL" }),
      capture: captured("hi"),
    })
    expect(result.text).toBe(text("hi\n\nCancelled", "cancelled"))
    expect(result.metadata).toEqual({
      source: "shell",
      shellID: "sh_1",
      state: "cancelled",
      truncated: false,
      signal: "SIGKILL",
    })
  })
})
