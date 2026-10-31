import { random } from "./random"

/**
 * The root of the package a harness loads: the mirror's when pinned.py runs it as `.pinned/<name>` in the
 * package's root, or `$PINNED_PACKAGE` (a test running it against the real package).
 */
export const packageRoot = process.env.PINNED_PACKAGE ?? new URL("..", import.meta.url).pathname.replace(/\/$/, "")

/** pinned.py's protocol: `gen <seed> <count>` prints a JSON list of inputs; `eval` reads one and prints summaries. */
export async function runHarness(
  generate: (rand: () => number) => string,
  summarize: (input: string) => Record<string, unknown>,
): Promise<void> {
  const [command, seed, count] = process.argv.slice(2)
  if (command === "gen") {
    const rand = random(Number(seed))
    console.log(JSON.stringify(Array.from({ length: Number(count) }, () => generate(rand))))
  } else {
    const inputs: string[] = JSON.parse(await Bun.stdin.text())
    console.log(JSON.stringify(inputs.map(summarize)))
  }
}
