"""G-compile: the target's flags as data, one object per kernel file, and clang's diagnostics parsed.

The flags are the target's `Makefile`, read at `0c2223a` and written down here rather than shelled out
to `make`: a grading run compiles six translation units and links them with G-diff's driver, and it must
compile each one the way the target does, per ISA. `-Wno-unused-function` is this package's addition,
not the target's — the fixture is the target trimmed to three type rows, so the helpers the removed rows
used are still defined and unused. **Warnings are never failures**: a body that compiles with warnings
compiled.

The object cache exists because one grading run compiles the same five unchanged files for every body it
grades. It is keyed by the source's *text* and its flags, so it is correct by construction rather than by
timestamp, and it lives for one run: a `ObjectCache` is a directory and a dict, not a store on disk that
a later run reads back.

Diagnostics are parsed from clang's `-fno-color-diagnostics -fno-caret-diagnostics` output into
`(file relative to the root, line, col, severity, message)`. What does not parse — the linker's own
lines, `clang: error: linker command failed` — stays in `Compilation.output`, which `hsr` reads for
undefined references and which never reaches a model (`feedback` is built from the parsed fields only).
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "CFLAGS",
    "DIAGNOSTIC_FLAGS",
    "ISA_FLAGS",
    "Diagnostic",
    "Compilation",
    "ObjectCache",
    "cc",
    "flags_for",
    "parse_diagnostics",
    "compile_file",
    "link",
]

#: The target's `CFLAGS` at `0c2223a`, at its `-O2`, plus this package's `-Wno-unused-function`.
CFLAGS = ("-Wall", "-Wextra", "-Wno-unused-parameter", "-Wno-unused-function", "-O2")

#: What the parser needs to read clang's output: no colour, no caret line.
DIAGNOSTIC_FLAGS = ("-fno-color-diagnostics", "-fno-caret-diagnostics")

#: Per-ISA flags, the target's `Makefile`. SSE2 is x86-64's baseline and needs none; NEON and RVV
#: compile to their `#else` stubs on x86-64, which is exactly what a run on this box wants.
ISA_FLAGS: dict[str, tuple[str, ...]] = {
    "cpu": (),
    "sse2": (),
    "avx2": ("-mavx2", "-mfma"),
    "avx512": ("-mavx512f", "-mavx512bw", "-mavx512vl", "-mavx512dq"),
    "neon": (),
    "rvv": (),
}

_DIAGNOSTIC = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s+(?P<severity>fatal error|error|warning|note):\s+(?P<message>.*)$"
)


@dataclass(frozen=True)
class Diagnostic:
    """One clang message: where it points, how bad it is, and what it says."""

    file: str
    line: int
    col: int
    severity: str
    message: str

    @property
    def fatal(self) -> bool:
        """Whether this message is one that stops a build."""
        return self.severity in ("error", "fatal error")

    def text(self) -> str:
        """The message as clang wrote it, with the path relative to the target's root."""
        return f"{self.file}:{self.line}:{self.col}: {self.severity}: {self.message}"

    def as_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class Compilation:
    """One compiler or linker invocation: what it produced, what it said, and how long it took."""

    ok: bool
    product: Path
    diagnostics: tuple[Diagnostic, ...]
    output: str
    command: tuple[str, ...]
    seconds: float

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.fatal)


class ObjectCache:
    """The objects of one grading run, keyed by the source's text and its flags.

    A key is a hash of `(flags, text)`, so a file that a body did not touch is compiled once however
    many bodies are graded, and a file whose bytes changed by one character is compiled again. Nothing
    here survives the run: the directory is the run's work dir.
    """

    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, Compilation] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(text: str, flags: tuple[str, ...]) -> str:
        digest = hashlib.sha256()
        digest.update("\0".join(flags).encode("utf-8"))
        digest.update(b"\0")
        digest.update(text.encode("utf-8"))
        return digest.hexdigest()

    def get(self, key: str) -> Compilation | None:
        found = self._entries.get(key)
        if found is not None and found.product.exists():
            self.hits += 1
            return found
        return None

    def put(self, key: str, compilation: Compilation) -> Compilation:
        self.misses += 1
        if compilation.ok:
            self._entries[key] = compilation
        return compilation


def cc(override: str | None = None) -> str:
    """The compiler: the argument, else `$CC`, else `clang`."""
    return override or os.environ.get("CC") or "clang"


def flags_for(root: Path | str, isa: str) -> tuple[str, ...]:
    """The full flag list for one ISA's translation unit, includes first."""
    root = Path(root)
    return (*CFLAGS, f"-I{root}/src", f"-I{root}/libs", *ISA_FLAGS.get(isa, ()))


def parse_diagnostics(output: str, root: Path | str) -> tuple[Diagnostic, ...]:
    """Every clang message in *output*, with paths under *root* made relative to it."""
    root = Path(root)
    found: list[Diagnostic] = []
    for line in output.splitlines():
        match = _DIAGNOSTIC.match(line.strip())
        if match is None:
            continue
        found.append(
            Diagnostic(
                file=_relative(match.group("file"), root),
                line=int(match.group("line")),
                col=int(match.group("col")),
                severity=match.group("severity"),
                message=match.group("message"),
            )
        )
    return tuple(found)


def _relative(path: str, root: Path) -> str:
    """*path* relative to the target's root, or as clang wrote it when it is not under one."""
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except (ValueError, OSError):
        return path


def compile_file(
    root: Path | str,
    relative: str,
    isa: str,
    *,
    out_dir: Path | str,
    compiler: str | None = None,
    cache: ObjectCache | None = None,
) -> Compilation:
    """Compile one of the target's files to an object with its ISA's flags."""
    root = Path(root)
    source = root / relative
    text = source.read_text(encoding="utf-8")
    flags = flags_for(root, isa)
    key = ObjectCache.key(text, flags)
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit
    obj = Path(out_dir) / f"{Path(relative).stem}-{key[:16]}.o"
    command = (cc(compiler), *flags, *DIAGNOSTIC_FLAGS, "-c", str(source), "-o", str(obj))
    done = _spawn(command, root)
    result = Compilation(done[0], obj, done[1], done[2], command, done[3])
    return cache.put(key, result) if cache is not None else result


def link(
    objects: list[Path] | tuple[Path, ...],
    exe: Path | str,
    *,
    root: Path | str,
    compiler: str | None = None,
) -> Compilation:
    """Link the objects into an executable with `-lm`, the one library the kernels need."""
    command = (cc(compiler), *[str(o) for o in objects], "-o", str(exe), "-lm")
    ok, diagnostics, output, seconds = _spawn(command, root)
    return Compilation(ok, Path(exe), diagnostics, output, command, seconds)


def _spawn(command: tuple[str, ...], root: Path | str) -> tuple[bool, tuple[Diagnostic, ...], str, float]:
    started = time.monotonic()
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return False, (), f"{command[0]} timed out after 600s", time.monotonic() - started
    output = (done.stderr or "") + (done.stdout or "")
    return done.returncode == 0, parse_diagnostics(output, root), output, time.monotonic() - started
