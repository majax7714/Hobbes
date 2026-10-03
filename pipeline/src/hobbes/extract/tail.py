"""The tail view: classify unresolved call sites by observation (ADR-045).

Resolution coverage (ADR-029, C-2) counts how many detected call sites
have no known destination. This module says what the uncounted remainder
*is* — by observation only, never by inference. Every class states a
checkable fact about the site:

- ``fallback-resolved`` — lane A's resolver produced a (syntactic) edge
  for this site; only the semantic provider came up empty.
- ``local-binding`` — the callee is a binding **below the modelled
  vocabulary in the same file** (C-9): a destructured setter, a handler
  ``const``, a nested function, a fixture parameter, a closure-typed
  ``:=`` target. Seen and deliberately not modelled — not unknown. Two
  proof grades, both observations (ADR-046): for TS/JS the checker
  resolved the declaration; for Python and Go, lane A's own parse
  recorded the binding *with its enclosing function's extent*, and the
  site matches only when that extent spans the call's line — scope
  containment, not a file-wide name coincidence.
- ``nested-decl`` — same, but the declaration lives in another repo file.
- ``external-origin`` — every declaration the checker found lives outside
  the repo: a dependency or an ambient lib. Known origin, unresolved call.
- ``import-binding`` — a bare call whose name an import statement **in
  the same file** binds (``from x import y as z`` binds ``z``). The
  binding is lane A's own parse, not a guess; what stays open is only
  where the imported thing's call would land — often a dependency the
  environment is missing (C-23/C-27/C-30), which is exactly when this
  class carries the tail. Added after the private-repo-A/qwen run: their
  ``unclassified`` was almost entirely this (``PG_UUID``,
  ``load_dataset``, ``LLM`` — imports of the very packages
  ``dependency_coverage`` reported missing).
- ``stdlib-import`` — a Python call whose name, or whose direct
  receiver, an import of the **standard library** in the same file binds:
  ``from urllib.parse import urlsplit`` … ``urlsplit(..)``, ``import
  importlib.metadata`` … ``importlib.metadata.version(..)``, ``from
  urllib import parse`` … ``parse.urlsplit(..)``. The module's top-level
  name is in the pinned :data:`PY_STDLIB_MODULES` and names no repo
  module, and no non-stdlib import in the file binds the same name. The
  call lands outside the repo, and no provider placed it: scip-python
  0.6.6 names what several stdlib modules define with a document-local
  symbol (``urllib.parse``, ``email.utils``, ``importlib.metadata``,
  ``ctypes.wintypes``, ``sys.exit`` …) and writes no occurrence at all
  for gettext's ``_`` (ADR-164, C-181); it is silent in code Pyright
  reads as never run (C-173), and names a member of a stdlib star
  re-export as another symbol (C-178); without lane B nothing resolves
  outside the repo. The class says where the call is rooted, not which
  of these it was. Decided before ``import-binding``, whose "missing
  environment" it is not, and before ``attr-call``, whose receiver is
  here a module the file imports, not a value no provider could type.
- ``builtin-name`` — a bare call whose name matches the language's pinned
  builtin list. The class says "matches": a local shadowing ``len`` would
  match too, and the name is honest about that. An import binding
  outranks a builtin match — ``from rich import print`` makes the
  import the truer observation about ``print(...)``. C++ has one more
  form of the same observation: its standard library is the namespace
  ``std``, so a qualified site whose first qualifier is ``std`` matches
  it without any list being able to hold it (ADR-113 §1).
- ``attr-call`` — an attribute call (``x.foo()``): a receiver no static
  provider could type. The genuine static-analysis limit, C-2's core.
- ``expr-callee`` — the callee is itself an expression (``handlers[k]()``,
  ``f()()``, ``(a or b)()``): there is no identifier for the semantic
  lane to put an occurrence on, so nothing can resolve it. A parse
  observation — the syntax provider recorded the site under the marker
  name ``<expr>`` — Python and TS/JS only (C-63, surfaced 2026-09-05;
  C-80's residual). Before it the site was not counted at all.
- ``union-member`` — a member call on a union-typed receiver whose
  members do not share one declaration of that member (``n: A | B``,
  both overriding ``render``; ``n.render()``): the checker resolves it
  to the *first* member's declaration and so does scip-typescript, and
  neither is the static answer — any one target is a possible dispatch
  presented as the resolved one. Lane A abstains (the helper's
  ``ambiguous`` field), the join vetoes lane B's occurrence there, and
  the site is counted here. TS/JS (ADR-104, C-97; the oracle lane's
  ``static→union-member`` on ajv and hono, 2026-09-09); and Python since
  ADR-168 (C-184), where lane A reads the union from the annotations it can
  see — a parameter's, a return's, an attribute's, an alias. The typed
  form of C-58's interface dispatch, which likewise draws no edge.
- ``path-call`` — a ``::``-qualified call (Rust) the index left dark.
  Java has no ``::`` call (a method reference is a use, not a call); its
  bare sites are unqualified methods of the enclosing type chain, static
  imports, and ``new T(..)`` — so its classes are ``import-binding`` (a
  type or static member an ``import`` binds) and ``builtin-name``
  (``java.lang``, implicitly imported everywhere), beside the shared set.
- ``overload-set`` — lane A located the declaration set the name binds
  to and it holds more than one member (a Java overload set, a
  constructor pair): the resolver abstained rather than pick one, and
  only argument types — lane B's — can (ADR-096). C++'s overloads
  classify here for the same reason: a name with more than one definition
  at a fallback rank is a tie, and a tie abstains (ADR-113 §1).
- ``inherited-member`` — a Java call bound into a type that declares
  supertypes (a bare call inside one, a static call through one):
  whether the callee is that type's own declaration or an inherited
  overload of the same arity depends on argument types lane A does not
  have, so it abstains; only the hierarchy lane B sees says which
  (ADR-096). Constructors are never inherited and are excepted.
- ``unclassified`` — none of the above observations applies. This is the
  residue that stays honestly unknown.
- ``qualifier-mismatch`` — a C++ call written through one explicit
  specialisation's name (``test_format<20>::format(..)``) that lane B
  resolved to a **different** explicit full specialisation's member
  (``test_format<0>::format``): scip-clang indexes a template's pattern
  once, and the program text contradicts the answer it gives here, so no
  edge is drawn (ADR-125, C-153). Like ``below-floor`` it is not a
  :func:`classify` verdict — the projection decides it, from the written
  qualifier and the owner's own declaration.
- ``arity-mismatch`` — a C++ call written with **more arguments** than
  the declaration lane B resolved it to can take
  (``copy<Char>(begin, end, out)`` onto a ``copy`` of two parameters):
  scip-clang's one answer at a call in a template can be the wrong
  overload, and no default argument, conversion or deduction makes the
  call land there, so no edge is drawn (ADR-130, C-153). Fewer arguments
  than parameters is never this class — a default argument lives on a
  declaration elsewhere. The projection decides it too.
- ``shared-qualname`` — a Rust call written inside, or resolved onto, a
  def whose symbol id another, differently written ``impl`` block in the
  same file mints too (``impl Pointer for *const T`` and ``impl Pointer
  for *mut T`` both name ``T.distance``). The node is the first def; a
  later one is another function with no node, so no edge is drawn
  (ADR-163, C-180). The projection decides it; a site only lane A had
  answered is moved here from ``fallback-resolved``, whose edge it no
  longer has.

The classes roll up into the two statements the ingest summary prints
(architecture §3.4): *seen and not modelled by design* (local-binding,
nested-decl, builtin-name) versus *cannot resolve* (everything else but
fallback-resolved, which has an edge and merely lacks proof).

Checker-origin classes are **TypeScript/JavaScript only** in this
version — the tsextract helper's checker knows declarations; the other
syntax providers do not resolve. The asymmetry, the pinned (not
runtime) builtin lists, and the text-based shape read are the
classifier's own boundaries, registered as C-32 — and the asymmetry is
*stated* per language by :data:`CLASSES_AVAILABLE`, which
``graph.json`` carries as ``tail_classes_available`` so a reader can
tell "no external-origin sites" from "no provider that reports them".
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path, PurePosixPath

#: Classes, in the order they are decided. First observation wins.
FALLBACK = "fallback-resolved"
LOCAL = "local-binding"
NESTED = "nested-decl"
EXTERNAL_ORIGIN = "external-origin"
IMPORT_BINDING = "import-binding"
#: A Python call rooted at a same-file import of the standard library
#: that no provider placed (ADR-164, C-181).
STDLIB_IMPORT = "stdlib-import"
BUILTIN = "builtin-name"
ATTR = "attr-call"
#: A callee that is itself an expression — no name to resolve (C-63).
EXPR_CALLEE = "expr-callee"
#: The site name a syntax provider records for such a callee
#: (``pysource.EXPR_RECEIVER`` alone; the TS helper's ``<expr>``) —
#: pinned here so the tail reads the evidence IR, never a provider.
EXPR_NAME = "<expr>"
#: A member of a union receiver with more than one declaration in play;
#: lane A abstained and the join vetoed lane B (ADR-104, C-97). The
#: value the syntax provider puts in ``Site.ambiguous``.
UNION_MEMBER = "union-member"
PATH_CALL = "path-call"
OVERLOAD = "overload-set"
INHERITED = "inherited-member"
#: A Go name declared more than once in its package under build
#: constraints the caller's own configuration does not single out; lane
#: A abstained rather than pick a file (ADR-098, C-71).
BUILD_TAG = "build-tag-set"
UNCLASSIFIED = "unclassified"
#: A C++ call whose written qualifier names one explicit specialisation
#: and whose lane B answer is a different explicit full specialisation's
#: member (ADR-125, C-153); the projection abstains and the site is
#: counted here. Not a :func:`classify` verdict, like ``below-floor``.
QUALIFIER_MISMATCH = "qualifier-mismatch"
#: A C++ call written with more arguments than lane B's answer can take
#: (ADR-130, C-153); the projection abstains and the site is counted
#: here. Not a :func:`classify` verdict either, and R-qual's neighbour.
ARITY_MISMATCH = "arity-mismatch"
#: A Rust call written inside, or resolved onto, a later def of a symbol
#: id two differently written impl headers share (ADR-163, C-180); the
#: projection refuses it and the site is counted here. Not a
#: :func:`classify` verdict either.
SHARED_QUALNAME = "shared-qualname"
#: The semantic lane resolved the site to a declaration lane A keeps no
#: symbol for — an interface method, a closure, a nested function (C-9's
#: floor) — so the site counts as resolved and draws no edge (C-58).
#: Not an unresolved site: the row's ``floored`` count, named here so
#: the tail says where the call graph's known hole is, per file.
BELOW_FLOOR = "below-floor"

#: Rollup: sites the graph sees and deliberately does not model. The
#: complement (minus FALLBACK) is what it cannot resolve — the register's
#: "concentrated need" (ADR-045).
NOT_MODELLED = frozenset({LOCAL, NESTED, BUILTIN, BELOW_FLOOR})

_LANG_BY_EXT = {
    ".py": "python",
    ".ts": "ts/js",
    ".tsx": "ts/js",
    ".mts": "ts/js",
    ".cts": "ts/js",
    ".js": "ts/js",
    ".jsx": "ts/js",
    ".mjs": "ts/js",
    ".cjs": "ts/js",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    # A `.h` is C by extension. It is the one extension two languages
    # share, and the only one a coverage row can override: the C++ walk
    # stamps `language: cpp` on the headers it claimed (ADR-113 §1), and
    # `language_of` prefers that over this table.
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
}

#: Pinned, not read from the running interpreter (determinism across
#: boxes; the C-3 lift documented what a runtime-bound list costs).
#: Python 3.13 ``builtins``, underscored names dropped.
PY_BUILTINS = frozenset({
    "ArithmeticError", "AssertionError", "AttributeError", "BaseException",
    "BaseExceptionGroup", "BlockingIOError", "BrokenPipeError",
    "BufferError", "BytesWarning", "ChildProcessError",
    "ConnectionAbortedError", "ConnectionError", "ConnectionRefusedError",
    "ConnectionResetError", "DeprecationWarning", "EOFError", "Ellipsis",
    "EncodingWarning", "EnvironmentError", "Exception", "ExceptionGroup",
    "False", "FileExistsError", "FileNotFoundError", "FloatingPointError",
    "FutureWarning", "GeneratorExit", "IOError", "ImportError",
    "ImportWarning", "IndentationError", "IndexError", "InterruptedError",
    "IsADirectoryError", "KeyError", "KeyboardInterrupt", "LookupError",
    "MemoryError", "ModuleNotFoundError", "NameError", "None",
    "NotADirectoryError", "NotImplemented", "NotImplementedError",
    "OSError", "OverflowError", "PendingDeprecationWarning",
    "PermissionError", "ProcessLookupError", "PythonFinalizationError",
    "RecursionError", "ReferenceError", "ResourceWarning", "RuntimeError",
    "RuntimeWarning", "StopAsyncIteration", "StopIteration", "SyntaxError",
    "SyntaxWarning", "SystemError", "SystemExit", "TabError",
    "TimeoutError", "True", "TypeError", "UnboundLocalError",
    "UnicodeDecodeError", "UnicodeEncodeError", "UnicodeError",
    "UnicodeTranslateError", "UnicodeWarning", "UserWarning", "ValueError",
    "Warning", "ZeroDivisionError", "abs", "aiter", "all", "anext", "any",
    "ascii", "bin", "bool", "breakpoint", "bytearray", "bytes", "callable",
    "chr", "classmethod", "compile", "complex", "copyright", "credits",
    "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec",
    "exit", "filter", "float", "format", "frozenset", "getattr",
    "globals", "hasattr", "hash", "help", "hex", "id", "input", "int",
    "isinstance", "issubclass", "iter", "len", "license", "list",
    "locals", "map", "max", "memoryview", "min", "next", "object", "oct",
    "open", "ord", "pow", "print", "property", "quit", "range", "repr",
    "reversed", "round", "set", "setattr", "slice", "sorted",
    "staticmethod", "str", "sum", "super", "tuple", "type", "vars", "zip",
})

#: The Python standard library's top-level modules, for ``stdlib-import``
#: (ADR-164, C-181): Python 3.12's ``sys.stdlib_module_names``,
#: underscored names dropped like :data:`PY_BUILTINS`'s. Pinned, not read
#: from the running interpreter, for the same reason. 3.12 rather than
#: 3.13 because it still holds the modules 3.13 removed (``cgi``,
#: ``telnetlib`` …), which a repo written for an older Python imports
#: from the standard library all the same.
PY_STDLIB_MODULES = frozenset({
    "abc", "aifc", "antigravity", "argparse", "array", "ast", "asyncio",
    "atexit", "audioop", "base64", "bdb", "binascii", "bisect", "builtins",
    "bz2", "cProfile", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd",
    "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "crypt", "csv", "ctypes", "curses", "dataclasses",
    "datetime", "dbm", "decimal", "difflib", "dis", "doctest", "email",
    "encodings", "ensurepip", "enum", "errno", "faulthandler", "fcntl",
    "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "genericpath", "getopt", "getpass", "gettext", "glob",
    "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "idlelib", "imaplib", "imghdr", "importlib", "inspect", "io",
    "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache",
    "locale", "logging", "lzma", "mailbox", "mailcap", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt",
    "multiprocessing", "netrc", "nis", "nntplib", "nt", "ntpath",
    "nturl2path", "numbers", "opcode", "operator", "optparse", "os",
    "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes",
    "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath",
    "pprint", "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc", "pydoc_data", "pyexpat", "queue", "quopri", "random", "re",
    "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
    "secrets", "select", "selectors", "shelve", "shlex", "shutil",
    "signal", "site", "smtplib", "sndhdr", "socket", "socketserver",
    "spwd", "sqlite3", "sre_compile", "sre_constants", "sre_parse", "ssl",
    "stat", "statistics", "string", "stringprep", "struct", "subprocess",
    "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
    "tarfile", "telnetlib", "tempfile", "termios", "textwrap", "this",
    "threading", "time", "timeit", "tkinter", "token", "tokenize",
    "tomllib", "trace", "traceback", "tracemalloc", "tty", "turtle",
    "turtledemo", "types", "typing", "unicodedata", "unittest", "urllib",
    "uu", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser",
    "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp",
    "zipfile", "zipimport", "zlib", "zoneinfo"
})

#: The Go spec's predeclared functions and convertible predeclared types
#: — both are spelled exactly like calls at a call site (ADR-037).
GO_BUILTINS = frozenset({
    "append", "cap", "clear", "close", "complex", "copy", "delete",
    "imag", "len", "make", "max", "min", "new", "panic", "print",
    "println", "real", "recover",
    "bool", "byte", "complex64", "complex128", "error", "float32",
    "float64", "int", "int8", "int16", "int32", "int64", "rune",
    "string", "uint", "uint8", "uint16", "uint32", "uint64", "uintptr",
})

#: ``java.lang``'s public top-level types — implicitly imported into every
#: compilation unit, so a bare ``new Runnable() {..}`` or ``Thread.sleep``
#: names one without any import statement. Pinned from the image's
#: Temurin JDK 21 (``jimage list``, ADR-096); the JDK-internal helpers
#: (``CharacterData*``, ``ProcessImpl``) are dropped — a repo never
#: spells them.
JAVA_BUILTINS = frozenset({
    "AbstractMethodError", "Appendable", "ArithmeticException",
    "ArrayIndexOutOfBoundsException", "ArrayStoreException", "AssertionError",
    "AutoCloseable", "Boolean", "BootstrapMethodError", "Byte", "CharSequence",
    "Character", "Class", "ClassCastException", "ClassCircularityError",
    "ClassFormatError", "ClassLoader", "ClassNotFoundException", "ClassValue",
    "CloneNotSupportedException", "Cloneable", "Comparable", "Deprecated",
    "Double", "Enum", "EnumConstantNotPresentException", "Error", "Exception",
    "ExceptionInInitializerError", "Float", "FunctionalInterface",
    "IllegalAccessError", "IllegalAccessException", "IllegalArgumentException",
    "IllegalCallerException", "IllegalMonitorStateException",
    "IllegalStateException", "IllegalThreadStateException",
    "IncompatibleClassChangeError", "IndexOutOfBoundsException",
    "InheritableThreadLocal", "InstantiationError", "InstantiationException",
    "Integer", "InternalError", "InterruptedException", "Iterable",
    "LayerInstantiationException", "LinkageError", "Long", "MatchException",
    "Math", "Module", "ModuleLayer", "NegativeArraySizeException",
    "NoClassDefFoundError", "NoSuchFieldError", "NoSuchFieldException",
    "NoSuchMethodError", "NoSuchMethodException", "NullPointerException",
    "Number", "NumberFormatException", "Object", "OutOfMemoryError",
    "Override", "Package", "Process", "ProcessBuilder", "ProcessHandle",
    "Readable", "Record", "ReflectiveOperationException", "Runnable",
    "Runtime", "RuntimeException", "RuntimePermission", "SafeVarargs",
    "ScopedValue", "SecurityException", "SecurityManager", "Short",
    "StackOverflowError", "StackTraceElement", "StackWalker", "StrictMath",
    "String", "StringBuffer", "StringBuilder",
    "StringIndexOutOfBoundsException", "StringTemplate", "SuppressWarnings",
    "System", "Thread", "ThreadDeath", "ThreadGroup", "ThreadLocal",
    "Throwable", "TypeNotPresentException", "UnknownError",
    "UnsatisfiedLinkError", "UnsupportedClassVersionError",
    "UnsupportedOperationException", "VerifyError", "VirtualMachineError",
    "Void", "WrongThreadException",
})

#: The C11 standard library's public function names, from the <stdio.h>,
#: <stdlib.h>, <string.h>, <ctype.h>, <math.h> and <assert.h> family —
#: pinned, not read from a real header (the C-3 lift's reasoning, one
#: language over). ``__builtin_*`` (any name with that prefix — a GCC/
#: clang compiler intrinsic) is matched separately in :func:`_is_builtin`,
#: since no finite list could pin it.
C_BUILTINS = frozenset({
    # stdio.h
    "fopen", "fclose", "fread", "fwrite", "fprintf", "fscanf", "printf",
    "scanf", "sprintf", "snprintf", "vprintf", "vfprintf", "vsprintf",
    "vsnprintf", "fgets", "fputs", "fgetc", "fputc", "getc", "putc",
    "getchar", "putchar", "puts", "perror", "rewind", "fseek", "ftell",
    "fflush", "remove", "rename", "tmpfile", "tmpnam", "setvbuf", "setbuf",
    "ungetc", "feof", "ferror", "clearerr",
    # stdlib.h
    "malloc", "calloc", "realloc", "free", "exit", "abort", "atexit",
    "at_quick_exit", "quick_exit", "_Exit", "system", "getenv", "atoi",
    "atol", "atoll", "atof", "strtol", "strtoul", "strtoll", "strtoull",
    "strtod", "strtof", "strtold", "rand", "srand", "qsort", "bsearch",
    "abs", "labs", "llabs", "div", "ldiv", "lldiv", "mblen", "mbtowc",
    "wctomb", "mbstowcs", "wcstombs",
    # string.h
    "strlen", "strcpy", "strncpy", "strcat", "strncat", "strcmp",
    "strncmp", "strcoll", "strxfrm", "strchr", "strrchr", "strstr",
    "strtok", "strspn", "strcspn", "strpbrk", "memcpy", "memmove",
    "memset", "memcmp", "memchr", "strerror",
    # ctype.h
    "isalnum", "isalpha", "isblank", "iscntrl", "isdigit", "isgraph",
    "islower", "isprint", "ispunct", "isspace", "isupper", "isxdigit",
    "tolower", "toupper",
    # math.h
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh",
    "tanh", "asinh", "acosh", "atanh", "exp", "frexp", "ldexp", "log",
    "log10", "modf", "exp2", "expm1", "ilogb", "log1p", "log2", "logb",
    "scalbn", "scalbln", "pow", "sqrt", "cbrt", "hypot", "ceil", "floor",
    "fmod", "trunc", "round", "lround", "llround", "rint", "nearbyint",
    "fdim", "fmax", "fmin", "fabs", "copysign", "nan", "isnan", "isinf",
    "isfinite", "isnormal",
    # assert.h
    "assert", "static_assert",
})

#: C++ takes C's list unchanged: every C11 name above is callable from
#: C++ and spelled the same. What C++ adds is not a list — its standard
#: library is the namespace ``std``, read from a qualified site's first
#: qualifier in :func:`classify` (ADR-113 §1).
_BUILTINS = {
    "python": PY_BUILTINS, "go": GO_BUILTINS, "java": JAVA_BUILTINS,
    "c": C_BUILTINS, "cpp": C_BUILTINS,
}


def _is_builtin(lang: str | None, name: str) -> bool:
    """A pinned-list match, plus C's one prefix rule: any ``__builtin_*``
    name is a compiler intrinsic no finite list could enumerate. Both hold
    for C++'s unqualified names too."""
    if name in _BUILTINS.get(lang or "", frozenset()):
        return True
    return lang in ("c", "cpp") and name.startswith("__builtin_")

#: Which classes each language's providers can actually produce (C-32's
#: candidate fix, applied). A class absent from a language's set is one
#: that language *could not have reported* — so a Python tail with no
#: ``external-origin`` is not "no external origins", it is "no checker
#: that reports origins". Pinned beside the mechanisms that decide it:
#: checker origins come from tsextract alone; builtin lists exist for
#: Python and Go; ``import-binding`` is lane A's Python parse; the
#: ``local-binding`` collectors are Python/Go (ADR-046), Java (anonymous
#: class members, ADR-096) and TS (checker); ``expr-callee`` is recorded
#: by the Python and TS providers only (C-63); ``union-member`` needs the
#: receiver typed: the TS helper's checker (ADR-104), and Python's lane A
#: reading the annotations it can see (ADR-168);
#: ``path-call`` needs ``::``, which only Rust's grammar spells. The
#: test suite pins this table against :func:`classify`'s decision tree,
#: so a provider that learns a new class must widen its row here too.
CLASSES_AVAILABLE: dict[str, frozenset[str]] = {
    # `stdlib-import` (ADR-164): Python's alone — the pinned module list
    # and the import parse it reads are Python's.
    # `union-member` (ADR-168): lane A reads the receiver's union from the
    # annotations it can see, where TS's helper has a checker.
    "python": frozenset({FALLBACK, LOCAL, STDLIB_IMPORT, IMPORT_BINDING,
                         BUILTIN, ATTR, EXPR_CALLEE, UNION_MEMBER, UNCLASSIFIED,
                         BELOW_FLOOR}),
    "ts/js": frozenset({FALLBACK, LOCAL, NESTED, EXTERNAL_ORIGIN, ATTR,
                        EXPR_CALLEE, UNION_MEMBER, UNCLASSIFIED, BELOW_FLOOR}),
    "go": frozenset({FALLBACK, LOCAL, BUILTIN, ATTR, BUILD_TAG, UNCLASSIFIED,
                     BELOW_FLOOR}),
    # `shared-qualname` (ADR-163): only Rust names an impl's methods after
    # a type identifier two impl blocks can share.
    "rust": frozenset({FALLBACK, ATTR, PATH_CALL, UNCLASSIFIED, SHARED_QUALNAME,
                       BELOW_FLOOR}),
    "java": frozenset({FALLBACK, LOCAL, IMPORT_BINDING, BUILTIN, ATTR, OVERLOAD,
                       INHERITED, UNCLASSIFIED, BELOW_FLOOR}),
    # Lane A's five, plus below-floor since C's lane B (ADR-109): scip-clang
    # resolves a call through a struct's function-pointer field to the
    # field, a declaration the graph keeps no symbol for. There is still
    # no checker to see an import binding, an overload set, or an
    # expression callee.
    "c": frozenset({FALLBACK, LOCAL, BUILTIN, ATTR, UNCLASSIFIED, BELOW_FLOOR}),
    # C's five, plus the three classes C++ needs and C cannot have: a name
    # defined more than once is an overload set, and lane A abstains on
    # it (ADR-113 §1); a call written through one explicit
    # specialisation that the index resolved to another's member is a
    # `qualifier-mismatch`, which needs template arguments C has no
    # grammar for (ADR-125); and a call written with more arguments than
    # the resolved declaration takes is an `arity-mismatch` (ADR-130),
    # which needs the overloads C does not have — in C a name is defined
    # once, and K&R's `f()` takes any arguments at all. `path-call` is not
    # here — C++ spells `::`, but a qualified site is either the standard
    # library (`builtin-name`, by its first qualifier) or a name this lane
    # could not place.
    "cpp": frozenset({FALLBACK, LOCAL, BUILTIN, ATTR, OVERLOAD, UNCLASSIFIED,
                      QUALIFIER_MISMATCH, ARITY_MISMATCH, BELOW_FLOOR}),
}

#: Every class, in decision order — the vocabulary the table draws from.
#: The last four are not :func:`classify` verdicts: each is counted from
#: the projection and added to the tail beside the unresolved classes —
#: ``qualifier-mismatch`` a resolved site the written qualifier
#: contradicted (ADR-125), ``arity-mismatch`` one the written argument
#: count contradicted (ADR-130), ``shared-qualname`` one at a later def
#: of a Rust id two impl headers share (ADR-163), ``below-floor``, last,
#: a resolved site with no symbol to land on.
ALL_CLASSES = (FALLBACK, LOCAL, NESTED, EXTERNAL_ORIGIN, STDLIB_IMPORT,
               IMPORT_BINDING, BUILTIN, ATTR, EXPR_CALLEE, UNION_MEMBER,
               PATH_CALL, OVERLOAD, INHERITED, BUILD_TAG, UNCLASSIFIED,
               QUALIFIER_MISMATCH, ARITY_MISMATCH, SHARED_QUALNAME,
               BELOW_FLOOR)


def classes_available(coverage_rows: list[dict]) -> dict[str, list[str]]:
    """Per-language ``classes_available`` for the languages that have
    detected call sites in *coverage_rows* — the artifact form of C-32's
    note, keyed by the tail-view language bucket and listed in decision
    order. Emitted into ``graph.json`` so every consumer (the ingest
    summary, ``list_blind_spots``) states what a language's tail *could*
    have said next to what it did say, rather than holding a second copy
    of this table."""
    present = {language_of(row["file"], row.get("language")) for row in coverage_rows}
    return {
        lang: [c for c in ALL_CLASSES if c in CLASSES_AVAILABLE[lang]]
        for lang in sorted(present - {None})
        if lang in CLASSES_AVAILABLE
    }

#: Checker origin (tsextract v4) -> tail class.
_ORIGIN_CLASS = {"local": LOCAL, "nested": NESTED, "external": EXTERNAL_ORIGIN}


def language_of(file: str, row_language: str | None = None) -> str | None:
    """The tail-view language bucket for *file*, or None (e.g. ``.tf``).

    *row_language* is the language the provider that owns the file
    claimed, carried on its coverage row: a ``.h`` the C++ walk claimed is
    C++, and no extension could say so (ADR-113 §1). A row that carries
    one always wins — the provider read the file, this table only reads
    its name.
    """
    return row_language or _LANG_BY_EXT.get(PurePosixPath(file).suffix)


#: Languages whose grammar forbids a statement from ending in ``.`` — so
#: a previous line ending there can only be a wrapped chain, and reading
#: it is an observation. Python is excluded: its chains wrap with the dot
#: *leading* the next line (already read same-line), and a trailing dot
#: inside parentheses, while legal, is a shape this classifier abstains on.
_TRAILING_CHAIN_LANGS = frozenset({"go", "rust", "ts/js"})

#: Line openers that make the previous line prose, not code.
_COMMENT_OPENERS = ("//", "/*", "*", "#")


def _continuation(prev_text: str) -> str | None:
    """``attr``/``path`` when *prev_text* ends mid-chain, else None.

    gofmt *mandates* the trailing dot for a wrapped method chain
    (semicolon insertion forbids a leading one), which is why dagger's
    fluent integration tests put thousands of call openers at line
    starts. A trailing ``//`` comment is cut first so prose ending in a
    period cannot fake a chain; a line that *is* a comment never
    continues anything.
    """
    stripped = prev_text.strip()
    if not stripped or stripped.startswith(_COMMENT_OPENERS):
        return None
    code = prev_text.split("//", 1)[0].rstrip()
    if code.endswith("::"):
        return "path"
    if code.endswith("."):
        return "attr"
    return None


def _locate(line_text: str, name: str, col: int) -> int | None:
    """Where *name* starts on its line: the occurrence nearest *col*
    (the first when the provider gave none), or None when the line does
    not hold it."""
    hits, start = [], 0
    while (found := line_text.find(name, start)) != -1:
        hits.append(found)
        start = found + 1
    if not hits:
        return None
    return min(hits, key=lambda h: abs(h - col)) if col >= 0 else hits[0]


#: A dotted name chain ending in the ``.`` before an attribute call's
#: name, read back from the name: ``importlib.metadata.`` in
#: ``importlib.metadata.version(..)``.
_RECEIVER_CHAIN = re.compile(r"([A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*)\s*\.\s*$")


def _receiver(line_text: str, name: str, col: int) -> str | None:
    """The receiver of an attribute call *name* when it is a plain dotted
    name chain written on the call's own line (``importlib.metadata`` for
    ``importlib.metadata.version(..)``), whitespace dropped; None for any
    other receiver — a call's result (``f().x``), a subscript, a chain
    hanging off one of those, or a chain wrapped onto an earlier line.
    ``stdlib-import`` reads it (ADR-164): it is the text, never a type."""
    at = _locate(line_text, name, col)
    if at is None:
        return None
    m = _RECEIVER_CHAIN.search(line_text[:at])
    if m is None:
        return None
    j = m.start() - 1
    while j >= 0 and line_text[j] in " \t":
        j -= 1
    # The chain is the whole receiver only when nothing it hangs off
    # precedes it: `f().os.x` and `a[0].b.x` are not module reads.
    if j >= 0 and line_text[j] in ".)]}'\"":
        return None
    return re.sub(r"\s+", "", m.group(1))


def _shape(
    line_text: str, name: str, col: int, prev_text: str | None = None
) -> str | None:
    """What immediately precedes *name* on its line: ``attr``, ``path``,
    ``bare`` — or None when the name cannot be located (wrapped chains
    put the terminal on a line the recorded text may not contain). When
    the name opens its line, *prev_text* (the previous source line, only
    passed for the trailing-chain languages) answers instead."""
    at = _locate(line_text, name, col)
    if at is None:
        return None
    j = at - 1
    while j >= 0 and line_text[j] in " \t":
        j -= 1
    if j < 0:
        if prev_text is not None and (cont := _continuation(prev_text)):
            return cont
        return "bare"
    if line_text[j] == ":" and j >= 1 and line_text[j - 1] == ":":
        return "path"
    if line_text[j] in ".?!":
        return "attr"
    return "bare"


class _Lines:
    """Source lines per file, read once, repo-root-relative, read-only."""

    def __init__(self, repo_root: Path):
        self.root = Path(repo_root)
        self.cache: dict[str, list[str]] = {}

    def line(self, file: str, number: int) -> str | None:
        if file not in self.cache:
            try:
                text = (self.root / file).read_text(errors="replace")
            except OSError:
                text = ""
            self.cache[file] = text.splitlines()
        lines = self.cache[file]
        return lines[number - 1] if 0 < number <= len(lines) else None


def classify(
    unresolved: list,
    repo_root: Path,
    origins: dict[tuple[str, int, str], str] | None = None,
    fallback: dict[tuple[str, int, str], tuple] | None = None,
    import_bindings: dict[str, frozenset[str]] | None = None,
    local_bindings: dict[str, tuple] | None = None,
    overloads: set[tuple[str, int, str]] | None = None,
    inherited: set[tuple[str, int, str]] | None = None,
    build_tags: set[tuple[str, int, str]] | None = None,
    qualified: dict[tuple[str, int, str], str] | None = None,
    languages: dict[str, str] | None = None,
    stdlib_bindings: dict[str, frozenset[str]] | None = None,
) -> dict[str, Counter]:
    """Per-file tail classes for the *unresolved* call sites.

    *origins* is the checker's verdict per site (tsextract v4), keyed
    like the fallback dict: ``(file, line, name)``. *import_bindings*
    maps a file to the names its import statements bind (lane A's own
    parse — Python's ``FromImport`` bound names today).
    *overloads* is the set of ``(file, line, name)`` sites whose name
    lane A bound to more than one declaration and abstained on (Java);
    *inherited* the bare sites whose callee can only come from a
    supertype lane A cannot see (Java); *build_tags* the Go sites whose
    name has several declarations under build constraints the caller's
    configuration does not single out (ADR-098).
    *qualified* maps a C++ site to the first qualifier its provider saw
    (``std::move`` → ``std``), since C++ spells its standard library as a
    namespace rather than as a list a builtin table could pin (ADR-113
    §1); *languages* maps a file to the language its provider claimed,
    for the one extension two of them share (a ``.h`` C++ took).
    *stdlib_bindings* maps a Python file to what its imports of the
    standard library bind (:func:`stdlib_bindings`): the bound names and
    each ``import a.b`` path; a bare site of one, or an attribute site
    whose whole receiver is one, is ``stdlib-import`` (ADR-164).
    *local_bindings* maps a file to ``(name, start, end)`` tuples — lane
    A's sub-module bindings with enclosing-function extents (ADR-046);
    a bare site matches only when an extent spans its line, and a
    scope-contained local outranks an import binding because a binding
    inside the enclosing function shadows a module-level import. Every
    input site lands in exactly one class, so per file the counts sum
    to the coverage row's ``unresolved`` — an invariant the tests pin.
    """
    origins = origins or {}
    fallback = fallback or {}
    import_bindings = import_bindings or {}
    local_bindings = local_bindings or {}
    overloads = overloads or set()
    inherited = inherited or set()
    build_tags = build_tags or set()
    qualified = qualified or {}
    languages = languages or {}
    lines = _Lines(repo_root)
    out: dict[str, Counter] = {}
    stdlib_bindings = stdlib_bindings or {}
    for site in unresolved:
        key = (site.file, site.line, site.name)
        lang = language_of(site.file, languages.get(site.file))
        if key in fallback:
            cls = FALLBACK
        elif key in overloads:
            cls = OVERLOAD
        elif key in inherited:
            cls = INHERITED
        elif key in build_tags:
            cls = BUILD_TAG
        elif site.name == EXPR_NAME:
            # The provider's own parse: the callee was not a name or an
            # attribute chain. No line read can add to that (C-63).
            cls = EXPR_CALLEE
        elif site.ambiguous == UNION_MEMBER:
            # The provider's own checker: a union receiver whose members
            # resolve the member differently; abstained, lane B vetoed
            # (ADR-104, C-97). The site carries the observation itself.
            cls = UNION_MEMBER
        elif key in origins and origins[key] in _ORIGIN_CLASS:
            cls = _ORIGIN_CLASS[origins[key]]
        else:
            text = lines.line(site.file, site.line)
            prev = (
                lines.line(site.file, site.line - 1)
                if lang in _TRAILING_CHAIN_LANGS
                else None
            )
            shape = (
                _shape(text, site.name, site.col, prev)
                if text is not None
                else None
            )
            bound = import_bindings.get(site.file, frozenset())
            stdlib = stdlib_bindings.get(site.file, frozenset())
            locals_ = local_bindings.get(site.file, ())
            qualifier = qualified.get(key)
            if shape == "bare" and any(
                name == site.name and start <= site.line <= end
                for (name, start, end) in locals_
            ):
                cls = LOCAL
            elif shape == "bare" and site.name in stdlib:
                cls = STDLIB_IMPORT
            elif (
                shape == "attr"
                and stdlib
                and (receiver := _receiver(text, site.name, site.col)) in stdlib
                # A parameter or local named like the module shadows the
                # import inside its function (ADR-046's extent).
                and not any(
                    name == receiver.split(".")[0] and start <= site.line <= end
                    for (name, start, end) in locals_
                )
            ):
                cls = STDLIB_IMPORT
            elif shape == "bare" and site.name in bound:
                cls = IMPORT_BINDING
            elif shape == "bare" and _is_builtin(lang, site.name):
                cls = BUILTIN
            elif qualifier is not None:
                # C++'s qualified site: the standard library is a
                # namespace, so `std::` *is* the builtin list. Any other
                # qualifier is a name this lane could not place — never
                # `path-call`, which is Rust's class (ADR-113 §1).
                cls = BUILTIN if qualifier == "std" else UNCLASSIFIED
            elif shape == "attr":
                cls = ATTR
            elif shape == "path":
                cls = UNCLASSIFIED if lang == "cpp" else PATH_CALL
            else:
                cls = UNCLASSIFIED
        out.setdefault(site.file, Counter())[cls] += 1
    return out


def stdlib_bindings(imports, repo_roots=frozenset()) -> frozenset[str]:
    """What one Python file's imports of the standard library bind, for
    ``stdlib-import`` (ADR-164, C-181): read from lane A's own import
    facts (``PlainImport``, ``FromImport``), never from an index.

    - ``from a.b import x as y`` binds ``y``; ``from a import b`` binds
      ``b`` whether ``b`` is a function or a submodule;
    - ``import a.b as c`` binds ``c``;
    - ``import a.b.c`` binds the paths ``a``, ``a.b`` and ``a.b.c``, each
      a receiver an attribute call can be written through.

    An import counts when its module's top-level name is in
    :data:`PY_STDLIB_MODULES` and is not the top-level name of any repo
    module (*repo_roots*: a repo's own ``types`` or ``test`` package is
    not the standard library's), and is absolute (a relative import is
    the repo's). A name some other import in the same file also binds —
    ``try: from urllib.parse import quote`` … ``except ImportError: from
    .compat import quote`` — is left out: which one runs is not a fact
    the file states.
    """
    std: set[str] = set()
    other: set[str] = set()
    for imp in imports:
        module = getattr(imp, "module", "") or ""
        root = module.split(".")[0]
        is_std = (
            getattr(imp, "level", 0) == 0
            and root in PY_STDLIB_MODULES
            and root not in repo_roots
        )
        if hasattr(imp, "names"):
            names = {bound for _, bound in imp.names if bound != "*"}
        elif getattr(imp, "alias", None):
            names = {imp.alias}
        else:
            parts = module.split(".")
            names = {".".join(parts[: i + 1]) for i in range(len(parts))}
        (std if is_std else other).update(names)
    return frozenset(std - other)


def rollup(coverage_rows: list[dict]) -> dict[str, dict]:
    """Per-language tail totals from ``resolution_coverage`` rows.

    Pure read over the artifact — the CLI summary and any other consumer
    derive the rollup rather than storing it twice.
    """
    langs: dict[str, dict] = {}
    for row in coverage_rows:
        lang = language_of(row["file"], row.get("language"))
        if lang is None:
            continue
        agg = langs.setdefault(
            lang, {"sites": 0, "unresolved": 0, "tail": Counter()}
        )
        agg["sites"] += row["sites"]
        agg["unresolved"] += row["unresolved"]
        for cls, count in (row.get("tail") or {}).items():
            agg["tail"][cls] += count
    return langs


def directory_of(file: str, depth: int = 2) -> str:
    """The directory bucket for *file*: the first *depth* segments of its
    containing directory, or ``"."`` for a root-level file. Depth 2 is
    the summary's grain — deep enough to split a heterogeneous top-level
    directory (``sdk/python`` vs ``sdk/typescript``), shallow enough to
    stay a summary; the per-file rows remain the full-resolution record.
    """
    parts = PurePosixPath(file).parts[:-1][:depth]
    return "/".join(parts) if parts else "."


def rollup_directories(
    coverage_rows: list[dict], depth: int = 2
) -> dict[tuple[str, str], dict]:
    """Per-(directory, language) tail totals from ``resolution_coverage``
    rows, keyed ``(directory, language)`` with the same aggregate shape
    as :func:`rollup`.

    Language stays a key inside the directory because the capture
    statement is per-language by construction (each denominator is that
    language's detected call sites) — collapsing ``sdk/python`` and a
    stray shell of TS in the same directory into one number would blur
    whose sites went unresolved. Like :func:`rollup`, a pure read over
    the artifact: nothing here is stored twice.
    """
    dirs: dict[tuple[str, str], dict] = {}
    for row in coverage_rows:
        lang = language_of(row["file"], row.get("language"))
        if lang is None:
            continue
        key = (directory_of(row["file"], depth), lang)
        agg = dirs.setdefault(
            key, {"sites": 0, "unresolved": 0, "tail": Counter()}
        )
        agg["sites"] += row["sites"]
        agg["unresolved"] += row["unresolved"]
        for cls, count in (row.get("tail") or {}).items():
            agg["tail"][cls] += count
    return dirs
