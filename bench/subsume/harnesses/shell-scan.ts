// pinned.py's harness for core's shell scanner: random scripts, each summarized as the reason it was refused or as
// its commands, one key per value. An input's first line names its dialect (`%%bash`, `%%zsh`, `%%posix`, `%%pwsh`),
// so a shrink keeps it; the script is the rest. Never run these inputs: they are read, and a random one can do anything.
// The words come from what the shells read, not from the scanner, which the generator does not load.
import { packageRoot, runHarness } from "./cli"

const { ShellScan } = await import(`${packageRoot}/src/shell/scan.ts`)

const BUILTINS = "declare typeset export readonly local private unset unsetenv let read getln vared getopts mapfile readarray compgen zparseopts zregexparse zformat zstyle zstat stat printf print wait test [ set setopt unsetopt emulate alias eval integer float exit return shift break continue bye logout command builtin exec noglob nocorrect time coproc".split(" ")
const WORDS = ["a", "b", "x", "foo", "1", "2", "0", "-n", "-v", "-t", "-p", "-k", "-m", "-o", "-A", "-a", "-E", "-C", "-F", "-eq", "-ne", "-lt", "-le", "-gt", "-ge", "==", "=~", "!=", "=", "in", "do", "done", "then", "fi", "esac", "keyword", "globsubst", "GLOB_SUBST", "no_prompt_subst", "kshglob", "promptvars", "aliases", "nullglob"]
const SPECIAL = "PS4 NULLCMD READNULLCMD functions dis_functions aliases galiases saliases dis_aliases options commands x y".split(" ")
const QUOTED = ["'a b'", '"a b"', "'$(x)'", "'`x`'", "'a[$(x)]'", "'a[`x`]'", '"$x"', '"$(a)"', "$'a'", "$'\\t'", "$'\\x41'", "$'\\101'", "$'a\\'b'", "$'\\0'", '$"a"', "\\a", "\\ ", "a\\\nb", "$$", "$$'a'", "$$'\\a'", "'\\x41'", "'\\101'", "'$'", "'('"]
const EXPANSIONS = ["$x", "${x}", "$(a)", "`a`", "$((1))", "$(( x ))", "$[1]", "$[x]", "${x:-a}", "${x:=a}", "${x=a}", "${x:1}", "${x:'$(a)'}", "${x:='$(a)'}", "${x[1]}", "${x[$(a)]}", "${x['$(a)']}", "${!x}", "${!x[1]}", "${x@P}", "${x@Q}", "${(e)x}", "${(q)x}", "${(s:,:)x}", "${~x}", "$~x", "$^~x", "${=x}", "${ a; }", "${|a; }", "$x[1]", "$x[$(a)]", '"$x[$(a)]"', "<(a)", ">(a)", "=(a)", "@(a|b)", "*(a)", "?(a)", "${\\\nx}", "${PS4}", "${NULLCMD}", "${functions[a]}", "${options:-a}", "${x:-(a)}", '"${x:-(a)}"', '"${x:-\'a\'}"', '"${x:-$(a)}"', '"${x:-$\'a\'}"']
const REDIRECTS = [">", ">>", "<", "<>", ">&", "<&", ">|", "&>", "&>>", "<<<", "2>", "{fd}>", "1>&2", "> >"]
const OPERATORS = [";", "&&", "||", "|", "|&", "&", ";;", "\n"]

function bashGenerator(rand: () => number) {
  const pick = <T>(items: readonly T[]) => items[Math.floor(rand() * items.length)]!
  const chance = (p: number) => rand() < p
  const word = (): string => {
    const r = rand()
    if (r < 0.35) return pick(WORDS)
    if (r < 0.55) return pick(QUOTED)
    if (r < 0.8) return pick(EXPANSIONS)
    if (r < 0.9) return `${pick(SPECIAL)}${pick(["=", "+=", "[", "[1]=", "=("])}${pick(["a", "$(a)", "'$(a)'", "a)"])}`
    return `${pick(WORDS)}${pick(EXPANSIONS)}`
  }
  const words = (most = 3) => Array.from({ length: Math.floor(rand() * (most + 1)) }, word).join(" ")
  const simple = (): string => {
    const head = chance(0.2) ? `${pick(["A=1", "A=$(a)", "A='$(a)'", "A=(a b)", "a[1]=b", "a[$b]=c"])} ` : ""
    const name = chance(0.5) ? pick(BUILTINS) : pick(["foo", "a", "b", "git"])
    const tail = chance(0.25) ? ` ${pick(REDIRECTS)} ${word()}${chance(0.3) ? ` ${word()}` : ""}` : ""
    return `${head}${name} ${words()}${tail}`.trimEnd()
  }
  const statement = (depth: number): string => {
    if (depth <= 0 || chance(0.6)) return simple()
    const inner = () => statement(depth - 1)
    return pick<() => string>([
      () => `if ${inner()}; then ${inner()}; fi`,
      () => `if ${inner()}; then ${inner()}; elif ${inner()}; then ${inner()}; else ${inner()}; fi`,
      () => `while ${inner()}; do ${inner()}; done`,
      () => `until ${inner()}; do ${inner()}; done`,
      () => `for x in ${words()}; do ${inner()}; done`,
      () => `for x; do ${inner()}; done`,
      () => `for x do ${inner()}; done`,
      () => `for x (${words()}) ${inner()}`,
      () => `for x (${words()}); do ${inner()}; done`,
      () => `for ((${pick(["i=0;i<1;i++", "$(a);;", "a[$(b)]"])})); do ${inner()}; done`,
      () => `select x in ${words()}; do ${inner()}; done`,
      () => `repeat ${word()} do ${inner()}; done`,
      () => `repeat 3 ${inner()}`,
      () => `case ${word()} in ${pick(["a", "(a", "a|b", "@(a|b)", word()])}) ${inner()}${pick([";;", ";&", ";;&", ";|"])} esac`,
      () => `case ${word()} in\na) ${inner()};;\nesac`,
      () => `{ ${inner()}; }`,
      () => `( ${inner()} )`,
      () => `((${word()}))`,
      () => `(( ${word()} ))`,
      () => `[[ ${word()} ${pick(WORDS)} ${word()} ]]`,
      () => `[[ ${pick(["-n", "-v", "-t"])} ${word()} ]]`,
      () => `[[ ( ${word()} ) && ${word()} == (a|b) ]]`,
      () => `f() { ${inner()}; }`,
      () => `function f { ${inner()}; }`,
      () => `function f() ( ${inner()} )`,
      () => `! ${inner()}`,
      () => `time ${pick(["", "-p "])}{ ${inner()}; }`,
      () => `coproc ${pick(["", "n "])}{ ${inner()}; }`,
      () => `${inner()} ${pick(REDIRECTS)} ${word()}`,
      () => `cat ${pick(["<<EOF", "<<-EOF", "<<'EOF'", '<<"EOF"', "<<\\EOF", "<<$'EOF'", "<<E'O'F"])}\n${pick(["body", "$(a)", "'$(a)'", "\tbody", "E\\", "`a`"])}\n${pick(["EOF", "\tEOF", "OF"])}`,
      () => `read a <<EOF\n$(a)\nEOF\n${inner()}`,
    ])()
  }
  const lines = Array.from({ length: 1 + Math.floor(rand() * 4) }, () => {
    let line = statement(2)
    while (chance(0.3)) line += `${pick(OPERATORS)} ${statement(1)}`
    if (chance(0.15)) line = `${line} ${pick(OPERATORS)}`
    if (chance(0.05)) line = `${line} # ${word()}`
    return line
  })
  return lines
}

const PS_WORDS = ["a", "b", "foo", "1", "2", "-x", "-a:", "-Path", "*", "--%", "--`%", "'--%'", "'a b'", "'a''b'", '"a b"', '"a""b"', '"a`tb"', "a`tb", "`$a", "`u{41}", "`u{110000}", "`\n", "$x", "$x.y", "$x.y.", "$x::y", "$x?.y", "${x}", "$env:x", "$(a)", "@(a)", "(a)", "{a}", "@{a=b}", "@{a=(b)}", "$x[0]", "$x[(a)]", "a[0]", "a,", "a, b", '"$(a)"', '"${x}"', '"a$(b)c"', "[int]", "[int]$x", "[x](a)", "1kb", "0x10", "-not", "!$x", "--$x", "+$x", "a<#b", "<# c #>", "a#b", "@'\na\n'@", '@"\n$(a)\n"@', '@"\n`a\n"@', "$a.# x\n", "$a.<#c#>\n"]
const PS_REDIRECTS = [">", ">>", "2>", "*>", "2>&1", "*>&1", "1>&2", ">&1", "7>"]
const PS_OPERATORS = [";", "|", "&&", "||", "&", "\n", "\r\n", "\r"]

function psGenerator(rand: () => number) {
  const pick = <T>(items: readonly T[]) => items[Math.floor(rand() * items.length)]!
  const chance = (p: number) => rand() < p
  const words = () => Array.from({ length: Math.floor(rand() * 4) }, () => pick(PS_WORDS)).join(chance(0.9) ? " " : "  ")
  const simple = (): string => {
    const head = chance(0.15) ? pick(["& ", ". ", "$x = ", "$x += ", "[int]$x = ", "return ", "throw ", ":l "]) : ""
    const name = chance(0.8) ? pick(["foo", "a", "git", "Get-Thing", "if", "foreach", "else"]) : pick(PS_WORDS)
    const tail = chance(0.2) ? ` ${pick(PS_REDIRECTS)} ${pick(PS_WORDS)}` : ""
    return `${head}${name} ${words()}${tail}`.trimEnd()
  }
  const statement = (depth: number): string => {
    if (depth <= 0 || chance(0.6)) return simple()
    const inner = () => statement(depth - 1)
    return pick<() => string>([
      () => `if (${inner()}) { ${inner()} }`,
      () => `if (${inner()}) { ${inner()} } elseif (${inner()}) { ${inner()} } else { ${inner()} }`,
      () => `while (${inner()}) { ${inner()} }`,
      () => `for ($i = 0; ${inner()}; ${inner()}) { ${inner()} }`,
      () => `foreach ($x in ${inner()}) { ${inner()} }`,
      () => `do { ${inner()} } ${pick(["while", "until"])} (${inner()})`,
      () => `try { ${inner()} } catch { ${inner()} } finally { ${inner()} }`,
      () => `try { ${inner()} } catch [X] { ${inner()} }`,
      () => `switch (${inner()}) { a { ${inner()} } }`,
      () => `function f${pick(["", "($x)"])} { ${inner()} }`,
      () => `${pick(["filter", "begin", "process", "end", "clean", "trap", "data", "dynamicparam", "workflow", "parallel", "sequence", "configuration"])} { ${inner()} }`,
      () => `${pick(["class C", "enum E"])} { ${pick(["", "A", "[int]$x"])} }`,
      () => `param($x${pick(["", " = (a)", ", $y"])})`,
      () => `using namespace ${pick(PS_WORDS)}`,
      () => `${pick(["break", "continue"])}${pick(["", " l"])}`,
      () => `:l ${pick(["while", "for", "foreach", "do", "switch"])} (${inner()}) { ${inner()} }`,
      () => `foo --% ${pick(["a; b", 'a "b | c"', "$x"])} ${pick(["", "| b", "&& b", "\nb"])}`,
      () => `(${inner()})`,
      () => `$(${inner()})`,
      () => `@(${inner()})`,
      () => `{ ${inner()} }`,
      () => `@{a = ${inner()}; b = 1}`,
      () => `$x[${pick(["0", "(a)", "a|b", "a;b"])}]`,
      () => `foo "$(${inner()})"`,
    ])()
  }
  return Array.from({ length: 1 + Math.floor(rand() * 4) }, () => {
    let line = statement(2)
    while (chance(0.3)) line += ` ${pick(PS_OPERATORS)} ${statement(1)}`
    if (chance(0.05)) line = `${line} ${pick(PS_OPERATORS)}`
    if (chance(0.05)) line = `${line} # ${pick(PS_WORDS)}`
    return line
  })
}

export function generate(rand: () => number): string {
  const dialect = ["bash", "zsh", "posix", "pwsh"][Math.floor(rand() * 4)]!
  return [`%%${dialect}`, ...(dialect === "pwsh" ? psGenerator(rand) : bashGenerator(rand))].join("\n")
}

export function summarize(input: string): Record<string, unknown> {
  const [header, ...lines] = input.split("\n")
  const dialect = header!.slice(2)
  const script = lines.join("\n")
  try {
    const result = dialect === "pwsh" ? ShellScan.scanPowerShell(script) : ShellScan.scan(script, dialect)
    if (result.kind === "opaque") return { reason: result.reason }
    const summary: Record<string, unknown> = { commands: result.commands.length }
    result.commands.forEach((command: Record<string, unknown>, index: number) => {
      for (const [key, value] of Object.entries(command)) summary[`${index}.${key}`] = JSON.stringify(value)
    })
    return summary
  } catch (error) {
    return { error: String(error) }
  }
}

if (import.meta.main) await runHarness(generate, summarize)
