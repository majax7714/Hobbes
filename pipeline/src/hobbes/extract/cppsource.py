"""Lane A for C++: structure, symbols, and call *sites*.

The eighth walk (architecture §3.7 step 2, ADR-113 §1), on the
:mod:`hobbes.extract.csource` contract — the same bundle shape, the same
division of labour, so the graph builder and the range join need no
C++-specific code (P7). **Where a rule is C's, this module calls C's**:
include resolution and its degradation record, the fallback's three
ranks, the one-symbol-per-id rule, the function-pointer bindings and the
symbol and site dict shapes are all imported from ``csource``. What is
written here is the walk, because the grammar is a different one.

**No lane B in this unit** (that is ADR-113 §2). Every C++ edge is lane
A's fallback, at ``syntactic`` tier: the join's normal degraded path
(P6), not a special case.

**Discovery.** ``.cpp``, ``.cc``, ``.cxx``, ``.hpp``, ``.hh`` and
``.hxx`` are C++. A ``.h`` is **claimed** by C++ when the repo has C++
files and either (a) it has no ``.c`` sources at all, or (b) some C++
file includes it (by C's three include steps) and no ``.c`` file does.
Every other ``.h`` stays C — including one both languages include, which
no evidence in the tree can settle. :func:`hobbes.extract.csource.extract_c`
is handed the claimed set and skips it, so one header is read by exactly
one language. A repo holding both languages gets one ``cpp-headers``
degradation record saying how many headers went each way and which ones
both include. Pruned like C: ``build/`` and any ``cmake-build-*``.

**Module ids** follow C's rule for C's reason: a source drops its
extension (``src/shapes.cpp`` → ``src/shapes``), a header keeps it
(``src/util.h`` stays ``src/util.h``), so a ``shapes.cpp``/``shapes.h``
pair in one directory never collides. A ``foo.cpp`` beside a ``foo.c``
*does* collide, on the id ``foo``: C-15's shape, and this layer records
it in a ``parse`` record rather than guessing which file wins.

**Symbols come from definitions only**, never a declaration. A free
function with a body is kind ``function``; a member function with a body
— in-class or written out of line (``int A::f() {}``) — is ``method``,
with ``qualname`` the ``::``-joined path (``ns::A::f``); a constructor
and a destructor are ``method``s named by the class (``A``, ``~A``); an
operator is named as written (``operator+``); a class, struct, union or
enum with a body, a ``typedef`` and a ``using`` alias are ``type``; a
function-like macro is ``macro`` (macros ignore every scope, as the
preprocessor does). A template declaration is the entity it declares,
once, at the entity's own line — which is where clang puts a
specialisation too, so the lanes will meet there. A namespace is not a
symbol: it is the qualname's prefix. A lambda is below the symbol floor
(C-58's face) and its body's calls attribute to the enclosing function.
Prototypes, object-like macros and ``using namespace`` are not symbols.

**A qualifier alone cannot say whether a definition is a member.**
``int A::f() {}`` is a method when ``A`` is a class and a free function
when ``A`` is a namespace, and the class is usually in a header rather
than in the file being walked. So the walk records the qualifier chain
and :func:`_settle_member_kinds` settles the kind once the whole repo is
parsed, against every namespace the repo opens: qualifiers that are all
namespace names make a ``function``, anything else a ``method``.

**Call sites** are recorded at the terminal identifier, in five shapes:
``plain`` (``f(x)``, and a function-like macro invocation, which parses
identically), ``qualified`` (``ns::f(x)``, ``A::s(x)`` — the site also
carries the qualifier chain, with any template arguments dropped),
``member`` (``a.f(x)``, ``p->f(x)``, ``this->f(x)``), ``deref``
(``(*fp)(x)``) and ``construct`` (``new A(x)`` and ``A a(x)``, named by
the type's terminal, Java's ``new Foo(..)`` rule so the two lanes meet
on the class name). An operator applied by symbol (``a + b``) is not a
site: the provider sees no call (C-63's face). The four named casts
(``static_cast`` and its three siblings) parse as calls and are not
ones; they are dropped rather than recorded as calls to a function no
repo defines. **A call written inside an unevaluated operand is not a
site either** (C-155's fix, ADR-121 §1): nothing under a
``sizeof_expression``, an ``alignof_expression``, a ``decltype``, a
``requires_expression`` or a ``noexcept(..)`` expression is recorded,
however deep — the program never evaluates it, so the provider sees no
call — with ``typeid(..)`` excepted, because its operand *is* evaluated
when it is a polymorphic glvalue and the syntax cannot tell. ``noexcept``
and ``typeid`` themselves parse as a call of a bare identifier: each is a
keyword and not a callee, and records no site of its own, the named
casts' rule one set over.

**The fallback** (:func:`_call_fallback`, the syntactic floor) resolves a
plain call by name in C's three ranks (``csource._resolve_fallback``
itself: same-file function or macro; a macro in a directly included
header; the unique non-``static`` free function repo-wide), and a
qualified call by the unique symbol whose qualname matches — tried
against the enclosing scope's prefixes first (inside ``namespace ns``,
``A::f()`` means ``ns::A::f``), then bare. **A name defined more than
once at a rank is a tie and abstains**: that is an overload set, and the
site is reported to the tail as ``overload-set`` rather than resolved to
whichever definition parsed first. A member call is never resolved here
— the receiver's type is lane B's to know (``attr-call``) — and neither
is a name bound to a function pointer or a lambda (``local-binding``).

**One symbol per id** is C's rule with C++'s overloads told apart
(:func:`_dedupe_symbols`, ADR-113 §2, C-144's fix). In file order the
first definition of a qualname keeps it; a later ``function`` or
``method`` definition whose *signature* differs — the declarator's
parameter list and the qualifiers trailing it — is an overload and takes
``~2``, ``~3``, … on its qualname (Java's convention, ADR-096), so lane
B's answer to each overload lands on a symbol of its own. A repeat of the
same signature, and any repeated ``type`` or ``macro``, is C's duplicate
still: the first is kept and the rest are named in one ``errors`` entry
per file, as the preprocessor alternatives they are. **The fallback does
not move**: :func:`_tables` keys on the bare qualname and the bare name,
so an overload set is the tie it always was and every rank abstains on
it.

**Tests.** gtest's ``TEST``, ``TEST_F``, ``TEST_P`` and ``TYPED_TEST``
parse as a function definition whose declarator names the macro; each is
a test ``Suite.Name``, framework ``gtest``, and the walk gives it a
file-local symbol of that name so its body's calls attribute to the test
and its reach is measured like any other test's. ``BOOST_AUTO_TEST_CASE(name)``
has the same shape and is framework ``boost-test``. Catch2's and
doctest's ``TEST_CASE("…")`` and ``SCENARIO("…")`` do not: the macro is
an expression and the body a block the parse leaves adrift, so the test
is named by its string and the walk has **no symbol to attach it to** —
its body's calls attribute to the module, and one ``cpp-tests``
degradation record per file says how many bodies that was. The framework
is ``catch2`` or ``doctest`` by the header the file includes, ``catch2``
when it includes neither. C's ``test_*`` naming convention does not
apply.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import tree_sitter_cpp
from tree_sitter import Language, Node, Parser

from hobbes.extract import csource, laneacache
from hobbes.extract.csource import _text, _walk
from hobbes.extract.discover import SKIPPED_DIR_NAMES, is_linked_copy
from hobbes.extract.graph import _edge_list

_PARSER = Parser(Language(tree_sitter_cpp.language()))

#: The six extensions that are C++ on sight (ADR-113 §1). A ``.h`` is
#: not among them: it is claimed, or left to C, by :func:`_claim_headers`.
CPP_SOURCE_SUFFIXES = (".cpp", ".cc", ".cxx")
CPP_HEADER_SUFFIXES = (".hpp", ".hh", ".hxx")
CPP_SUFFIXES = CPP_SOURCE_SUFFIXES + CPP_HEADER_SUFFIXES

#: Directories pruned in addition to the shared set — C's own list, for
#: the same builds.
_CPP_SKIPPED = SKIPPED_DIR_NAMES | {"build"}

#: The gtest-shaped macros: a ``function_definition`` whose declarator
#: names one of these is a test, not a function called ``TEST``.
_GTEST_MACROS = {"TEST", "TEST_F", "TEST_P", "TYPED_TEST"}

#: Boost.Test's single-argument form, the same shape one macro over.
_BOOST_MACRO = "BOOST_AUTO_TEST_CASE"

#: Catch2's and doctest's expression-shaped forms, named by a string.
_STRING_TEST_MACROS = {"TEST_CASE", "SCENARIO"}

#: C++'s named casts parse as a call of a template function and are not
#: calls at all; recording them would put every cast in the tail.
_NAMED_CASTS = {"static_cast", "dynamic_cast", "const_cast", "reinterpret_cast"}

#: The node types whose whole subtree is an unevaluated operand: a call
#: written anywhere inside one is a call the program never makes (C-155,
#: ADR-121 §1). A ``noexcept(..)`` *expression* is a fifth shape the
#: grammar spells as a call rather than a node type, so
#: :func:`_unevaluated` reads it there; ``typeid`` is absent on purpose,
#: for the reason that function gives.
_UNEVALUATED_OPERANDS = {
    "sizeof_expression",
    "alignof_expression",
    "decltype",
    "requires_expression",
}

#: The bare identifiers that parse in call position and are keywords, not
#: callees: neither names anything any repo defines, so neither records a
#: site of its own (ADR-121 §1). Their *operands* are another question —
#: ``noexcept``'s are unevaluated, ``typeid``'s keep their sites.
_KEYWORD_CALLEES = {"noexcept", "typeid"}


@dataclass
class CppFile:
    """One parsed C++ file, in the shape the join consumes — ``csource.CFile``
    with the two fields C++ needs of its own (:attr:`namespaces`,
    :attr:`unattached_tests`) and none of C's registration machinery."""

    path: str
    includes: list[dict] = field(default_factory=list)
    symbols: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    #: ``(name, start, end)`` — a parameter, a local function pointer or a
    #: lambda bound in the enclosing function, with that function's line
    #: extent. Never resolved by the fallback, and fed to the tail as this
    #: language's ``local_bindings``.
    local_bindings: list[tuple[str, int, int]] = field(default_factory=list)
    #: Qualnames this file defines more than once *with the same
    #: parameters* — preprocessor alternatives, not overloads. The kept
    #: symbol is the first in file order; every fallback rank abstains on
    #: these.
    duplicate_names: set[str] = field(default_factory=set)
    #: Every namespace this file opens — the evidence
    #: :func:`_settle_member_kinds` reads to tell a member definition from
    #: a namespace-qualified free function.
    namespaces: set[str] = field(default_factory=set)
    #: The qualnames of the classes this file declares as **explicit full
    #: specialisations** — ``template <> struct S<0> {..}`` (ADR-125's
    #: third condition). A primary template and a partial specialisation
    #: both spell parameters rather than concrete arguments, so neither
    #: is here and neither can make the projection abstain.
    full_specializations: list[str] = field(default_factory=list)
    #: The qualnames of the functions and methods this file defines inside
    #: a **template pattern** — what ADR-125 §4 surfaces of C-153. See
    #: :func:`_pattern_header` for the shape and for what a lost
    #: ``template <…>`` header (C-145) costs here.
    template_patterns: list[str] = field(default_factory=list)
    #: Count of ``TEST_CASE``/``SCENARIO`` bodies this file has: tests the
    #: walk names but can attach no symbol to, tallied for the file's
    #: ``cpp-tests`` degradation record.
    unattached_tests: int = 0


def has_cpp_files(repo_root: Path) -> bool:
    """Cheap detection: does this repo contain C++ at all?"""
    return any(True for _ in iter_cpp_files(Path(repo_root)))


def iter_cpp_files(repo_root: Path):
    """Repo-relative paths with one of the six C++ extensions, pruned like
    every other walk. The ``.h`` files C++ claims are not here: they are
    :func:`_claim_headers`' answer, which needs these files' includes
    first."""
    stack = [Path(repo_root)]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if (
                    child.name not in _CPP_SKIPPED
                    and not child.name.startswith(".")
                    and not child.name.startswith("cmake-build-")
                    and not is_linked_copy(child, repo_root)
                ):
                    stack.append(child)
            elif child.suffix in CPP_SUFFIXES:
                yield child


def module_id(path: str) -> str:
    """C's id rule, for C's reason: a source drops its extension, a header
    keeps it, so a ``shapes.cpp``/``shapes.h`` pair in one directory never
    collides."""
    pure = PurePosixPath(path)
    if pure.suffix in CPP_SOURCE_SUFFIXES:
        return str(pure.with_suffix(""))
    return str(pure)


def extract_cpp(repo_root: Path) -> dict | None:
    """The C++ layer for *repo_root*, or ``None`` when it has no C++.

    Never raises: a file that will not read or will not parse yields
    whatever the walk could see and one degradation record names it —
    tree-sitter is error-tolerant by design (§3.1), and the layer must
    never take an ingest down.

    Two passes, because the second depends on the first: the six
    extensions are parsed, their includes decide which ``.h`` files C++
    claims, and the claimed headers are then parsed as C++ too.
    """
    repo_root = Path(repo_root).resolve()
    sources = [p.relative_to(repo_root).as_posix() for p in iter_cpp_files(repo_root)]
    if not sources:
        return None
    files: list[CppFile] = []
    errors: list[dict] = []
    lossy: set[str] = set()
    for rel in sorted(sources):
        errors += _read_and_parse(repo_root, rel, files, lossy)

    claim = _claim_headers(repo_root, files)
    for rel in sorted(claim.claimed):
        errors += _read_and_parse(repo_root, rel, files, lossy)
    errors += _header_degradation(claim)
    errors += _id_collisions(files, claim.c_sources)

    _settle_member_kinds(files)
    files.sort(key=lambda parsed: parsed.path)
    errors += _test_degradations(files)

    bundle = _join(files, claim)
    errors.extend(bundle.pop("include_errors"))
    bundle["errors"] = errors
    bundle["claimed_headers"] = set(claim.claimed)
    #: The files whose parse had ERROR nodes — ADR-129's first condition,
    #: read off the walk itself rather than off the record's message text.
    #: A definition lane B holds in one of these is a definition this
    #: parse *lost*; in any other file it is lane A's floor by decision.
    bundle["lossy_files"] = frozenset(lossy)
    return bundle


def _read_and_parse(
    repo_root: Path, rel: str, files: list[CppFile], lossy: set[str] | None = None
) -> list[dict]:
    """Read and parse one file into *files*, returning its degradation
    records — C's own reporting, one entry per unreadable file, one per
    file with syntax errors, one per file defining a name twice.

    *lossy* collects the paths whose parse had ERROR nodes (ADR-129). The
    cache returns ``had_error`` in its triple, so a hit reports it exactly
    as a parse does."""
    try:
        source = (repo_root / rel).read_bytes()
    except OSError as exc:
        return [{"path": rel, "stage": "discover", "message": f"could not read {rel}: {exc}"}]
    # An unchanged file is read back rather than walked again (ADR-128 §4);
    # the cache is a pure wrapper of `_parse_file` and returns its triple.
    parsed, had_error, duplicated = laneacache.cached_parse(rel, source, _parse_file)
    files.append(parsed)
    errors: list[dict] = []
    if had_error:
        if lossy is not None:
            lossy.add(rel)
        errors.append(
            {
                "path": rel,
                "stage": "parse",
                "message": (
                    f"{rel} parsed with syntax errors (tree-sitter ERROR nodes); "
                    "the sites it could still see are kept"
                ),
            }
        )
    if duplicated:
        errors.append(
            {
                "path": rel,
                "stage": "parse",
                "message": (
                    f"{', '.join(duplicated)} defined more than once with the "
                    f"same parameters in {rel} (preprocessor alternatives); "
                    "calls to them are left unresolved rather than guessed"
                ),
            }
        )
    return errors


# ---------------------------------------------------------------- the claim


@dataclass(frozen=True)
class _HeaderClaim:
    """Which ``.h`` files C++ took, which C kept, and what the record says.

    *shared* are the headers both languages include: no evidence in the
    tree settles those, so they stay C. *mixed* is the repo shape the
    ``cpp-headers`` record exists for — C++ files and ``.c`` sources in
    one tree.
    """

    claimed: frozenset[str]
    left_to_c: frozenset[str]
    shared: frozenset[str]
    c_sources: frozenset[str]
    mixed: bool


def _claim_headers(repo_root: Path, files: list[CppFile]) -> _HeaderClaim:
    """ADR-113 §1's claim rule, on the includes lane A can place."""
    c_paths = {p.relative_to(repo_root).as_posix() for p in csource.iter_c_files(repo_root)}
    headers = {p for p in c_paths if p.endswith(".h")}
    c_sources = frozenset(p for p in c_paths if p.endswith(".c"))
    if not headers:
        return _HeaderClaim(frozenset(), frozenset(), frozenset(), c_sources, False)
    if not c_sources:
        # (a) C++ and no C at all: every `.h` in the repo is C++'s.
        return _HeaderClaim(frozenset(headers), frozenset(), frozenset(), c_sources, False)

    known = {parsed.path for parsed in files} | c_paths
    candidates = csource.HeaderIndex(
        headers | {p for p in known if PurePosixPath(p).suffix in CPP_HEADER_SUFFIXES}
    )
    by_cpp: set[str] = set()
    for parsed in files:
        by_cpp |= _included_headers(parsed.path, parsed.includes, known, candidates, headers)
    by_c: set[str] = set()
    for path in sorted(c_sources):
        includes = _includes_of(repo_root / path)
        by_c |= _included_headers(path, includes, known, candidates, headers)

    claimed = frozenset(by_cpp - by_c)
    return _HeaderClaim(
        claimed=claimed,
        left_to_c=frozenset(headers - claimed),
        shared=frozenset(by_cpp & by_c),
        c_sources=c_sources,
        mixed=True,
    )


def _included_headers(
    path: str,
    includes: list[dict],
    known: set[str],
    candidates: csource.HeaderIndex,
    headers: set[str],
) -> set[str]:
    """The ``.h`` files *path*'s includes resolve to, by C's three steps
    (:func:`csource._resolve_include`) over every C and C++ file in the
    repo — an include neither language can place claims nothing."""
    out: set[str] = set()
    for inc in includes:
        resolution = csource._resolve_include(path, inc["spec"], known, candidates)
        if resolution.path in headers:
            out.add(resolution.path)
    return out


def _includes_of(absolute: Path) -> list[dict]:
    """The includes of a file this layer does not otherwise parse (a
    ``.c`` source, for the claim's other half). An include directive is
    spelled the same in both languages, so the C++ grammar reads it."""
    try:
        source = absolute.read_bytes()
    except OSError:
        return []
    root = _PARSER.parse(source).root_node
    return [
        entry
        for node in csource._flatten_top_level(root)
        if node.type == "preproc_include" and (entry := csource._include_entry(node)) is not None
    ]


def _header_degradation(claim: _HeaderClaim) -> list[dict]:
    """The ``cpp-headers`` record a mixed repo gets: how many headers went
    each way, and the ones both languages include (left to C)."""
    if not claim.mixed:
        return []
    parts = [
        f"{len(claim.claimed)} `.h` read as C++ and {len(claim.left_to_c)} as C"
    ]
    if claim.shared:
        parts.append(
            f"{len(claim.shared)} included from both languages and left to C "
            + csource._capped_specs(sorted(claim.shared))
        )
    return [
        {
            "path": ".",
            "stage": "cpp-headers",
            "message": (
                ", ".join(parts)
                + "; a header's language is read from the includes lane A can "
                "place, never from the build's own include path (ADR-113 §1)"
            ),
        }
    ]


def _id_collisions(files: list[CppFile], c_sources: frozenset[str]) -> list[dict]:
    """C-15's shape, recorded rather than guessed: a ``foo.cpp`` beside a
    ``foo.c`` wants the same module id, and the layer merge keeps whichever
    layer got there first."""
    c_ids = {csource.module_id(path): path for path in sorted(c_sources)}
    records = []
    for parsed in files:
        mid = module_id(parsed.path)
        if mid in c_ids:
            records.append(
                {
                    "path": parsed.path,
                    "stage": "parse",
                    "message": (
                        f"module id {mid!r} is also {c_ids[mid]}'s: a C++ source "
                        "beside a C source of the same stem, so one of the two is "
                        "omitted from the graph (C-15)"
                    ),
                }
            )
    return records


# ---------------------------------------------------------------- parsing


def _parse_file(rel: str, source: bytes) -> tuple[CppFile, bool, list[str]]:
    tree = _PARSER.parse(source)
    root = tree.root_node
    parsed = CppFile(path=rel)
    _walk_declarations(root, parsed, ())
    # An identifier node's text is a slice of the source, so a file whose
    # bytes hold no macro name has no node the scan could take (ADR-128).
    if any(macro.encode() in source for macro in _STRING_TEST_MACROS):
        _scan_string_tests(root, parsed)
    # One symbol per id, before `_calls` runs — so a call written inside an
    # overload is scoped to that overload, not to the first of the set.
    duplicated = _dedupe_symbols(parsed)
    parsed.calls = _calls(root, parsed.symbols)
    return parsed, root.has_error, duplicated


#: The kinds an overload set can hold. Everything else — a ``type``, a
#: ``macro`` — repeats only by defining one name twice.
_OVERLOADABLE = ("function", "method")


def _dedupe_symbols(parsed: CppFile) -> list[str]:
    """One symbol per id, with C++'s overloads told apart (ADR-113 §2).

    C's rule (:func:`csource._dedupe_symbols`) keeps the first definition
    of a qualname and drops the rest, which in C++ costs an overload set
    every symbol but one (C-144, read on fmtlib/fmt). Here, in file order:
    the first definition keeps its qualname; a later ``function`` or
    ``method`` definition whose signature differs takes ``~2``, ``~3``, …;
    a later definition of the same signature, or any other repeat, is the
    preprocessor alternative C's rule was written for and is dropped.

    Returns the qualnames that were dropped, so the caller can register
    one ``errors`` record per file. The bare ``name`` never moves.
    """
    taken: dict[str, list[str] | None] = {}  # qualname -> its signatures, or None
    duplicated: set[str] = set()
    kept: list[dict] = []
    for symbol in parsed.symbols:
        base = symbol["qualname"]
        signature = symbol.pop("_signature", "")
        if base not in taken:
            taken[base] = [signature] if symbol["kind"] in _OVERLOADABLE else None
            kept.append(symbol)
            continue
        signatures = taken[base]
        if signatures is None or symbol["kind"] not in _OVERLOADABLE or signature in signatures:
            duplicated.add(base)
            continue
        signatures.append(signature)
        symbol["qualname"] = f"{base}~{len(signatures)}"
        kept.append(symbol)
    parsed.symbols = kept
    parsed.duplicate_names = duplicated
    return sorted(duplicated)


def _bare(qualname: str) -> str:
    """A qualname without its overload suffix — what every fallback rank
    keys on, so an overload set stays the tie it is (C-143). A destructor
    (``A::~A``) carries a ``~`` that is part of its name, not a suffix."""
    base, tilde, suffix = qualname.rpartition("~")
    return base if tilde and suffix.isdigit() else qualname


def _signature(function_declarator: Node) -> str:
    """A definition's signature: the declarator's parameter list and the
    qualifiers trailing it (``const``, ``volatile``, ``&``, ``&&``,
    ``noexcept``, a trailing return type), whitespace-collapsed. Two
    definitions of one qualname are overloads when these differ, and
    preprocessor alternatives when they do not."""
    params = function_declarator.child_by_field_name("parameters")
    if params is None:
        return ""
    written = [_text(params)] + [
        _text(child)
        for child in function_declarator.children
        if child.start_byte >= params.end_byte
    ]
    return " ".join(" ".join(written).split())


def _walk_declarations(
    node: Node,
    parsed: CppFile,
    scope: tuple[tuple[str, bool], ...],
    pattern: bool = False,
) -> None:
    """The declarations at this level, in *scope* — a stack of
    ``(name, is_class)`` pairs, since a definition inside a class body is
    a method and one inside a namespace is not. Transparent through
    header guards and ``extern "C"`` exactly as C's walk is.

    *pattern* is whether this level is inside a template pattern
    (:func:`_pattern_header`); it is carried down rather than derived,
    since a member is a pattern's because of a header written above its
    enclosing class, at any depth."""
    for child in csource._flatten_top_level(node):
        _declaration(child, parsed, scope, pattern)


def _declaration(
    node: Node,
    parsed: CppFile,
    scope: tuple[tuple[str, bool], ...],
    pattern: bool = False,
) -> None:
    if node.type == "preproc_include":
        entry = csource._include_entry(node)
        if entry is not None:
            parsed.includes.append(entry)
    elif node.type == "preproc_function_def":
        name = node.child_by_field_name("name")
        if name is not None:
            # The preprocessor knows no namespace: a macro's qualname is
            # its bare name wherever it was written.
            parsed.symbols.append(_symbol(_text(name), _text(name), "macro", name, node))
    elif node.type == "namespace_definition":
        name = node.child_by_field_name("name")
        body = node.child_by_field_name("body")
        inner = scope
        if name is not None:
            parsed.namespaces.add(_text(name))
            inner = scope + ((_text(name), False),)
        if body is not None:
            _walk_declarations(body, parsed, inner, pattern)
    elif node.type == "template_declaration":
        # The entity it declares, once, at the entity's own line.
        _record_full_specialisation(node, parsed, scope)
        # A non-empty header makes what it declares a pattern; an empty one
        # (`template <>`) declares a full specialisation, which is concrete.
        # Never *un*-set: a member of a class template is a pattern's
        # whatever header it carries itself.
        inner = pattern or _pattern_header(node)
        for child in node.children:
            if child.is_named and child.type != "template_parameter_list":
                _declaration(child, parsed, scope, inner)
    elif node.type in ("class_specifier", "struct_specifier", "union_specifier"):
        name = node.child_by_field_name("name")
        body = node.child_by_field_name("body")
        if name is None or body is None:
            return  # a bare tag reference: not a definition
        tag = _text(name)
        parsed.symbols.append(_symbol(tag, _qualname(scope, tag), "type", name, node))
        if name.type == "template_type" and _lost_template_header(node):
            parsed.full_specializations.append(_qualname(scope, tag))
        _walk_declarations(body, parsed, scope + ((tag, True),), pattern)
    elif node.type == "enum_specifier":
        name = node.child_by_field_name("name")
        if name is not None and node.child_by_field_name("body") is not None:
            parsed.symbols.append(
                _symbol(_text(name), _qualname(scope, _text(name)), "type", name, node)
            )
    elif node.type == "type_definition":
        declarator = node.child_by_field_name("declarator")
        ident = csource._type_identifier(declarator) if declarator is not None else None
        if ident is not None:
            parsed.symbols.append(
                _symbol(_text(ident), _qualname(scope, _text(ident)), "type", ident, node)
            )
    elif node.type == "alias_declaration":
        name = node.child_by_field_name("name")
        if name is not None:
            parsed.symbols.append(
                _symbol(_text(name), _qualname(scope, _text(name)), "type", name, node)
            )
    elif node.type == "function_definition":
        _function_definition(node, parsed, scope, pattern)
    # A `declaration` (a prototype, an out-of-line member declaration, a
    # variable), a `preproc_def` (an object-like macro) and a
    # `using_declaration` are never symbols.


def _symbol(name: str, qualname: str, kind: str, ident: Node, extent: Node) -> dict:
    """C's symbol dict (:func:`csource._symbol`) with C++'s one difference:
    *qualname* is the ``::``-joined path to the definition, not the bare
    name."""
    return csource._symbol(name, kind, ident, extent) | {"qualname": qualname}


def _qualname(scope: tuple[tuple[str, bool], ...], *names: str) -> str:
    return "::".join([name for name, _ in scope] + [n for n in names if n])


def _record_full_specialisation(
    node: Node, parsed: CppFile, scope: tuple[tuple[str, bool], ...]
) -> None:
    """Note a ``template <> struct S<0> {..}`` — ADR-125's third condition.

    The shape is read off the declaration and nothing else: an **empty**
    template parameter list, on a class or struct whose name is a
    ``template_type`` (a name written with arguments). A primary template
    (``template <typename T> struct S``) and a partial specialisation
    (``template <typename T> struct S<std::vector<T>>``) both carry
    parameters in that list, so neither is recorded — the amendment's own
    two cases, where an argument list differing from the written one is a
    *right* resolution rather than a contradiction.

    The qualname recorded is the one :func:`_declaration` gives the class
    itself, arguments included, so the projection's owner lookup and this
    set speak the same ids.
    """
    parameters = node.child_by_field_name("parameters")
    if parameters is None or parameters.named_child_count:
        return
    for child in node.children:
        if child.type not in ("class_specifier", "struct_specifier"):
            continue
        name = child.child_by_field_name("name")
        if (
            name is not None
            and name.type == "template_type"
            and child.child_by_field_name("body") is not None
        ):
            parsed.full_specializations.append(_qualname(scope, _text(name)))


def _lost_template_header(node: Node) -> bool:
    """Whether a class written with arguments (``struct S<X> {..}``) is
    an explicit full specialisation whose ``template <>`` the parse lost.

    A macro the grammar cannot read (``FMT_BEGIN_NAMESPACE``, C-145) can
    pull the header into an ERROR node just before the class, which then
    parses bare. The tokens are still there: the ERROR node immediately
    before the class ends in exactly ``template`` ``<`` ``>``. Nothing
    looser counts (ADR-125 as amended, §10.11's P69) — a header with a
    parameter in it, or anything after the ``>``, is not this shape, and
    the class is then not recorded, which only makes the rule fire less.
    """
    previous = node.prev_sibling
    if previous is None or previous.type != "ERROR" or previous.child_count < 3:
        return False
    tail = [_text(child) for child in previous.children[-3:]]
    return tail == ["template", "<", ">"]


def _pattern_header(node: Node) -> bool:
    """Whether a ``template_declaration``'s header is a **pattern**'s —
    ADR-125 §4's condition, the region C-153's error lives in.

    A non-empty ``template <…>`` is a pattern: a function template, a class
    template, or a partial specialisation, each written once with
    parameters and instantiated per argument list. scip-clang indexes that
    one text once, so its single answer at a call inside it can name
    another specialisation's declaration. An **empty** list is
    ``template <>``, an explicit full specialisation — concrete code, one
    instantiation, and the shape ADR-125's R-qual already withholds the
    wrong edges of; it is not a pattern and neither are its members.

    Where a macro the grammar cannot read pulls the header into an ERROR
    node (``FMT_BEGIN_NAMESPACE``, C-145), there is no
    ``template_declaration`` to ask, and nothing here guesses one: the
    class parses bare, its members are not recorded, and the region goes
    unmarked. That surfaces *less* than the truth, never more — the
    direction a marking rule must fail in. :func:`_lost_template_header`
    reads the tokens back for the other rule, whose recovery needs the
    exact ``template`` ``<`` ``>``; a pattern's header holds a parameter
    whose text no rule can bound, so it is not recovered here.
    """
    parameters = node.child_by_field_name("parameters")
    return parameters is not None and bool(parameters.named_child_count)


def _function_definition(
    node: Node,
    parsed: CppFile,
    scope: tuple[tuple[str, bool], ...],
    pattern: bool = False,
) -> None:
    """A definition with a body: a function, a method, or a test."""
    body = node.child_by_field_name("body")
    declarator = node.child_by_field_name("declarator")
    if body is None or declarator is None:
        return
    function_declarator = csource._function_declarator_of(declarator)
    if function_declarator is None:
        return
    ident = function_declarator.child_by_field_name("declarator")
    if ident is None:
        return
    if _test_definition(node, function_declarator, ident, parsed):
        return
    name, qualifiers, terminal = _definition_name(ident)
    if terminal is None:
        return
    in_class = bool(scope) and scope[-1][1]
    kind = "method" if in_class else "function"
    qualname = _qualname(scope, *qualifiers, name)
    symbol = _symbol(name, qualname, kind, terminal, node)
    if pattern:
        # The caller's own symbol, so the join can mark the edges that
        # start here without reading a site (ADR-125 §4).
        parsed.template_patterns.append(qualname)
    # Read off the declarator, dropped by `_dedupe_symbols`: it decides
    # whether a repeated qualname is an overload or a duplicate.
    symbol["_signature"] = _signature(function_declarator)
    if qualifiers:
        # Settled against the repo's namespaces once every file is parsed.
        symbol["kind"] = "method"
        symbol["qualifiers"] = qualifiers
    symbol["static"] = any(
        c.type == "storage_class_specifier" and _text(c) == "static" for c in node.children
    )
    parsed.symbols.append(symbol)
    csource._collect_bindings(node, declarator, parsed)
    _collect_lambda_bindings(node, parsed)


def _definition_name(ident: Node) -> tuple[str, tuple[str, ...], Node | None]:
    """``(name, qualifiers, terminal)`` for a definition's declarator name:
    a plain or member identifier, an out-of-line ``A::f``, a destructor,
    an operator, or an explicit specialisation ``f<int>``."""
    qualifiers: tuple[str, ...] = ()
    if ident.type == "qualified_identifier":
        qualifiers, ident = _qualified_terminal(ident)
        if ident is None:
            return "", qualifiers, None
    if ident.type == "template_function":
        name_node = ident.child_by_field_name("name")
        ident = name_node if name_node is not None else ident
    if ident.type in ("identifier", "field_identifier", "type_identifier", "operator_name"):
        return _text(ident), qualifiers, ident
    if ident.type == "destructor_name":
        return _text(ident), qualifiers, ident
    return "", qualifiers, None


def _qualified_terminal(node: Node) -> tuple[tuple[str, ...], Node | None]:
    """The qualifier chain and the terminal name of a ``a::b::c``, with a
    template argument list dropped (``ns::h<int>`` is ``ns::h``)."""
    qualifiers: list[str] = []
    current: Node | None = node
    while current is not None and current.type == "qualified_identifier":
        scope = current.child_by_field_name("scope")
        if scope is not None:
            qualifiers.append(_text(scope))
        current = current.child_by_field_name("name")
    if current is not None and current.type == "template_function":
        current = current.child_by_field_name("name")
    return tuple(qualifiers), current


def _settle_member_kinds(files: list[CppFile]) -> None:
    """Decide the out-of-line definitions' kind, once the whole repo is
    parsed: a qualifier chain that is all namespace names is a free
    function, anything else a member of a class the walk may never see
    (module docstring). Removes the walk's bookkeeping from the symbol."""
    namespaces = {name for parsed in files for name in parsed.namespaces}
    for parsed in files:
        for symbol in parsed.symbols:
            qualifiers = symbol.pop("qualifiers", None)
            if qualifiers and all(q in namespaces for q in qualifiers):
                symbol["kind"] = "function"


def _collect_lambda_bindings(func_node: Node, parsed: CppFile) -> None:
    """``auto f = [](..){..}`` — C++'s own binding, beside the
    function-pointer parameters and locals C already collects. A call
    through one is never resolved: the lambda is below the symbol floor."""
    start = func_node.start_point.row + 1
    end = func_node.end_point.row + 1
    body = func_node.child_by_field_name("body")
    if body is None:
        return
    for node in _walk(body):
        if node.type != "init_declarator":
            continue
        value = node.child_by_field_name("value")
        declarator = node.child_by_field_name("declarator")
        if (
            value is not None
            and value.type == "lambda_expression"
            and declarator is not None
            and declarator.type == "identifier"
        ):
            parsed.local_bindings.append((_text(declarator), start, end))


def _enclosing(symbols: list[dict], line: int) -> str | None:
    """The definition containing *line* — a function, a method or a test
    body, the only kinds whose body can hold a call."""
    best = None
    for symbol in symbols:
        if symbol["kind"] not in ("function", "method"):
            continue
        if symbol["line"] <= line <= symbol["end_line"]:
            best = symbol["qualname"]
    return best


def _callee_shape(function: Node) -> tuple[str, Node | None, tuple[str, ...]]:
    """``(shape, terminal identifier, qualifiers)`` for a call's callee.

    ``plain`` for an identifier (and for an unqualified ``f<int>(x)``,
    whose template arguments are dropped), ``qualified`` for ``ns::f``,
    ``member`` for ``a.f``/``p->f``/``this->f``, ``deref`` for ``(*fp)``.
    Anything else records no site: there is no terminal identifier to put
    it on.
    """
    if function.type == "identifier":
        return "plain", function, ()
    if function.type == "template_function":
        name = function.child_by_field_name("name")
        return "plain", name if name is not None and name.type == "identifier" else None, ()
    if function.type == "qualified_identifier":
        qualifiers, terminal = _qualified_terminal(function)
        if terminal is not None and terminal.type not in ("identifier", "operator_name"):
            return "qualified", None, qualifiers
        return "qualified", terminal, qualifiers
    if function.type == "field_expression":
        field_node = function.child_by_field_name("field")
        named = field_node is not None and field_node.type == "field_identifier"
        return "member", field_node if named else None, ()
    if function.type == "parenthesized_expression":
        shape, terminal = csource._callee_shape(function)
        return ("deref", terminal, ()) if shape == "deref" else ("other", None, ())
    return "other", None, ()


def _type_terminal(node: Node) -> tuple[Node | None, tuple[str, ...]]:
    """The terminal identifier of a constructed type and its qualifiers —
    ``new ns::A(x)`` is a site on ``A``, so the two lanes meet on the
    class name (Java's rule, ADR-096)."""
    if node.type == "type_identifier":
        return node, ()
    if node.type == "qualified_identifier":
        qualifiers, terminal = _qualified_terminal(node)
        if terminal is not None and terminal.type == "type_identifier":
            return terminal, qualifiers
    if node.type == "template_type":
        name = node.child_by_field_name("name")
        return _type_terminal(name) if name is not None else (None, ())
    return None, ()


def _unevaluated(node: Node) -> bool:
    """Whether *node* sits inside an operand the program never evaluates —
    a ``sizeof``, an ``alignof``, a ``decltype``, a requires-expression or
    a ``noexcept(..)`` expression (C-155, ADR-121 §1).

    ``typeid(f())`` is not one of them: its operand is evaluated when it is
    a glvalue of polymorphic class type ([expr.typeid]/3), which lane A
    cannot type, so a call written there keeps its site — the conservative
    side of a case the syntax cannot decide. The walk to the root is
    unbounded: a lambda's body, or a definition, inside a ``decltype`` is
    still inside it.
    """
    parent = node.parent
    while parent is not None:
        if parent.type in _UNEVALUATED_OPERANDS:
            return True
        if parent.type == "call_expression":
            function = parent.child_by_field_name("function")
            if function is not None and function.type == "identifier" and _text(function) == "noexcept":
                return True
        parent = parent.parent
    return False


def _site(
    name: str,
    shape: str,
    terminal: Node,
    node: Node,
    qualifiers: tuple[str, ...],
    symbols: list[dict],
) -> dict:
    """One call site: C's dict, plus the qualifier chain C has no use for.
    Positioned on *terminal*, scoped by the definition *node* sits in."""
    return {
        "name": name,
        "shape": shape,
        "qualifiers": qualifiers,
        "line": terminal.start_point.row + 1,
        "col": terminal.start_point.column,
        "scope": _enclosing(symbols, node.start_point.row + 1),
    }


def _calls(root: Node, symbols: list[dict]) -> list[dict]:
    """Every call site — the module docstring's five shapes. Position is
    the terminal identifier's, so lane B's join keys on where the name is,
    same as every other language."""
    found: list[dict] = []
    for node in _walk(root):
        if node.type not in ("call_expression", "new_expression", "declaration"):
            continue
        # Every shape below, dropped in one place: inside an unevaluated
        # operand there is no call to record (ADR-121 §1).
        if _unevaluated(node):
            continue
        if node.type == "call_expression":
            function = node.child_by_field_name("function")
            if function is None:
                continue
            shape, terminal, qualifiers = _callee_shape(function)
            if terminal is None:
                continue
            name = _text(terminal)
            if name in _NAMED_CASTS or name in _KEYWORD_CALLEES:
                continue
            found.append(_site(name, shape, terminal, node, qualifiers, symbols))
        elif node.type == "new_expression":
            type_node = node.child_by_field_name("type")
            if type_node is None:
                continue
            terminal, qualifiers = _type_terminal(type_node)
            if terminal is None:
                continue
            found.append(_site(_text(terminal), "construct", terminal, node, qualifiers, symbols))
        elif node.type == "declaration":
            found += _construction_sites(node, symbols)
    return sorted(found, key=lambda call: (call["line"], call["col"], call["name"]))


def _construction_sites(node: Node, symbols: list[dict]) -> list[dict]:
    """``A a(x)`` — a declaration whose declarator carries an argument
    list is a constructor call, named by the type's terminal."""
    type_node = node.child_by_field_name("type")
    if type_node is None:
        return []
    terminal, qualifiers = _type_terminal(type_node)
    if terminal is None:
        return []
    out = []
    for child in node.children:
        if child.type != "init_declarator":
            continue
        value = child.child_by_field_name("value")
        if value is not None and value.type == "argument_list":
            out.append(_site(_text(terminal), "construct", terminal, node, qualifiers, symbols))
    return out


# ---------------------------------------------------------------- tests


def _test_definition(
    node: Node, function_declarator: Node, ident: Node, parsed: CppFile
) -> bool:
    """gtest's and Boost.Test's macro-shaped definitions, which parse as a
    function whose declarator names the macro. Records the test and a
    file-local symbol of the test's own name, so its body's calls
    attribute to it. Returns whether *node* was one."""
    if ident.type != "identifier":
        return False
    macro = _text(ident)
    if macro not in _GTEST_MACROS and macro != _BOOST_MACRO:
        return False
    params = function_declarator.child_by_field_name("parameters")
    args = [c for c in params.children if c.is_named] if params is not None else []
    names = [_text(a) for a in args if a.type == "parameter_declaration"]
    if len(names) != len(args) or not names:
        return False
    if macro == _BOOST_MACRO:
        if len(names) != 1:
            return False
        name, framework = names[0], "boost-test"
    else:
        if len(names) != 2:
            return False
        name, framework = f"{names[0]}.{names[1]}", "gtest"
    symbol = _symbol(name, name, "function", ident, node)
    # A test is not callable from anywhere else: file-local, so no
    # fallback rank can ever land on it. Its signature is the macro's own
    # arguments, so two tests of one name are duplicates, never overloads.
    symbol["_signature"] = _signature(function_declarator)
    symbol["static"] = True
    parsed.symbols.append(symbol)
    parsed.tests.append(
        {
            "id": f"{parsed.path}::{name}",
            "name": name,
            "file": parsed.path,
            "line": symbol["line"],
            "framework": framework,
        }
    )
    return True


def _string_framework(parsed: CppFile) -> str:
    """Catch2 or doctest, by the header the file includes — ``catch2``
    when it includes neither, since Catch2 is the older and commoner
    spelling of the same macro."""
    for inc in parsed.includes:
        spec = inc["spec"].lower()
        if "doctest" in spec:
            return "doctest"
    return "catch2"


def _scan_string_tests(root: Node, parsed: CppFile) -> None:
    """Catch2's and doctest's ``TEST_CASE("…")``/``SCENARIO("…")``: a call
    the parse leaves beside a block it cannot attach, so the test is named
    by its string and gets no symbol (module docstring). Walked over every
    node, ERROR nodes included — that is where such a body often lands."""
    framework = _string_framework(parsed)
    seen: set[tuple[str, int]] = set()
    for node in _walk(root):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None or function.type != "identifier":
            continue
        if _text(function) not in _STRING_TEST_MACROS:
            continue
        args = csource._call_arguments(node)
        if not args or args[0].type != "string_literal":
            continue
        content = csource._child_of_type(args[0], "string_content")
        name = _text(content) if content is not None else _text(args[0]).strip('"')
        line = node.start_point.row + 1
        if (name, line) in seen:
            continue
        seen.add((name, line))
        parsed.unattached_tests += 1
        parsed.tests.append(
            {
                "id": f"{parsed.path}::{name}",
                "name": name,
                "file": parsed.path,
                "line": line,
                "framework": framework,
            }
        )


def _test_degradations(files: list[CppFile]) -> list[dict]:
    """One ``cpp-tests`` record per file whose ``TEST_CASE``/``SCENARIO``
    bodies the walk could attach no symbol to: their calls attribute to
    the module, so the test's reach is empty rather than wrong."""
    records = []
    for parsed in files:
        if not parsed.unattached_tests:
            continue
        n = parsed.unattached_tests
        noun = "body" if n == 1 else "bodies"
        records.append(
            {
                "path": parsed.path,
                "stage": "cpp-tests",
                "message": (
                    f"{n} `TEST_CASE`/`SCENARIO` {noun} named but not attached: the "
                    "macro is an expression, not a definition the walk can name, so "
                    "the calls inside attribute to the module and the test reaches "
                    "nothing (ADR-113 §1)"
                ),
            }
        )
    return records


def collect_cpp_tests(files: list[CppFile], symbol_edges: list[dict]) -> list[dict]:
    """C++ test inventory with reach, measured over the join's edges — the
    same rule every other framework's reach uses (ADR-007). A test the
    walk could attach no symbol to carries no symbol and reaches nothing;
    its ``cpp-tests`` record says why."""
    from hobbes.extract.testmap import _closure

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in symbol_edges:
        if edge["type"] == "calls":
            adjacency[edge["from"]].add(edge["to"])

    known_modules = {module_id(parsed.path) for parsed in files}
    out = []
    for parsed in files:
        mid = module_id(parsed.path)
        qualnames = {symbol["qualname"] for symbol in parsed.symbols}
        for test in parsed.tests:
            symbol_id = f"{mid}.{test['name']}" if test["name"] in qualnames else ""
            reached = _closure(symbol_id, adjacency) if symbol_id else set()
            out.append(
                {
                    "id": test["id"],
                    "file": test["file"],
                    "line": test["line"],
                    "framework": test["framework"],
                    "symbol": symbol_id,
                    "reaches": sorted(reached),
                    "reaches_modules": sorted(
                        {r.rsplit(".", 1)[0] for r in reached} & known_modules
                    ),
                }
            )
    return out


# ---------------------------------------------------------------- joining


def _join(files: list[CppFile], claim: _HeaderClaim) -> dict:
    """Assemble the layer bundle — the ``csource._join`` contract."""
    nodes: dict[str, dict] = {}
    module_edges: dict[tuple, list] = defaultdict(list)
    symbols: list[dict] = []
    owned = {parsed.path for parsed in files}
    # Includes resolve against every C and C++ file in the repo: a C++
    # source including a header C kept still names a real module, and the
    # C layer merges its node right after this one.
    known_files = owned | set(claim.c_sources) | set(claim.left_to_c)
    headers = csource.HeaderIndex(
        p for p in known_files if PurePosixPath(p).suffix in CPP_HEADER_SUFFIXES + (".h",)
    )
    unmatched_by_dir: dict[str, list[str]] = defaultdict(list)
    ambiguous_by_dir: dict[str, list[str]] = defaultdict(list)

    for parsed in files:
        nodes[module_id(parsed.path)] = {
            "id": module_id(parsed.path), "kind": "module", "path": parsed.path
        }

    for parsed in files:
        mid = module_id(parsed.path)
        directory = str(PurePosixPath(parsed.path).parent)
        for inc in parsed.includes:
            resolution = csource._resolve_include(parsed.path, inc["spec"], known_files, headers)
            if resolution.path is not None:
                target_mid = (
                    module_id(resolution.path)
                    if resolution.path in owned
                    else csource.module_id(resolution.path)
                )
                if target_mid != mid:
                    module_edges[(mid, target_mid, "imports")].append(
                        {"path": parsed.path, "line": inc["line"]}
                    )
                continue
            if inc["angle"]:
                ext_id = f"ext:{inc['spec']}"
                nodes.setdefault(ext_id, {"id": ext_id, "kind": "external", "name": inc["spec"]})
                module_edges[(mid, ext_id, "imports")].append(
                    {"path": parsed.path, "line": inc["line"]}
                )
            rendered = f"<{inc['spec']}>" if inc["angle"] else f'"{inc["spec"]}"'
            if resolution.ambiguous:
                if rendered not in ambiguous_by_dir[directory]:
                    ambiguous_by_dir[directory].append(rendered)
            elif not inc["angle"]:
                if rendered not in unmatched_by_dir[directory]:
                    unmatched_by_dir[directory].append(rendered)

        for symbol in parsed.symbols:
            symbols.append({"id": f"{mid}.{symbol['qualname']}", "module": mid, **symbol})

    fallback, overloads = _call_fallback(files, known_files, headers)
    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "module_edges": _edge_list(module_edges),
        "symbols": sorted(symbols, key=lambda s: s["id"]),
        "call_sites": _call_sites(files),
        "call_fallback": fallback,
        #: Sites the fallback abstained on because the name has more than
        #: one definition at a rank — the tail's `overload-set` (C++'s own
        #: class), keyed like the fallback.
        "overload_sites": overloads,
        #: The first qualifier of every qualified site, so the tail can
        #: read `std::` as the standard library it is (a namespace, not a
        #: pinned list).
        "qualified_sites": _qualified_sites(files),
        #: The symbol ids of the classes declared as explicit full
        #: specialisations (ADR-125's third condition) — the projection's
        #: whole answer to "is this owner's argument list concrete?".
        #: Nothing in `symbols` changes: this is a set over ids it
        #: already holds.
        "full_specializations": frozenset(
            f"{module_id(parsed.path)}.{qualname}"
            for parsed in files
            for qualname in parsed.full_specializations
        ),
        #: The symbol ids of the functions and methods defined in a
        #: template pattern (ADR-125 §4) — the region C-153's wrong answer
        #: can occur in, which the join marks in `who_calls`. Nothing in
        #: `symbols` changes: this is a set over ids it already holds.
        "template_patterns": frozenset(
            f"{module_id(parsed.path)}.{qualname}"
            for parsed in files
            for qualname in parsed.template_patterns
        ),
        "local_bindings": {
            parsed.path: tuple(parsed.local_bindings) for parsed in files if parsed.local_bindings
        },
        "files": files,
        "tests": sorted(
            (test for parsed in files for test in parsed.tests), key=lambda t: t["id"]
        ),
        "languages": ["cpp"],
        "errors": [],
        "include_errors": csource._include_degradations(unmatched_by_dir, ambiguous_by_dir),
    }


def _call_sites(files: list[CppFile]) -> list:
    """Lane A's C++ call sites, in evidence-IR shape (ADR-029)."""
    from hobbes.extract import evidence as ev

    return [
        ev.Site(
            provider=ev.TREE_SITTER,
            kind=ev.CALL_SITE,
            file=parsed.path,
            line=call["line"],
            name=call["name"],
            col=call["col"],
            scope=(
                f"{module_id(parsed.path)}.{call['scope']}"
                if call["scope"]
                else module_id(parsed.path)
            ),
            qualifier=_written_qualifier(call),
        )
        for parsed in files
        for call in parsed.calls
    ]


def _written_qualifier(call: dict) -> str:
    """The qualifier a call names its class through, where it carries
    template arguments (ADR-125) — the **immediate** one, ``test_format<20>``
    in ``ns::test_format<20>::format(..)``. Empty for every other site: a
    plain or member call has no qualifier, ``ns::f()`` names a namespace,
    and ``f<int>()`` is a template argument on the callee rather than on
    a class. Nothing but the projection reads it."""
    if call["shape"] != "qualified" or not call["qualifiers"]:
        return ""
    immediate = call["qualifiers"][-1]
    return immediate if "<" in immediate else ""


def _qualified_sites(files: list[CppFile]) -> dict[tuple[str, int, str], str]:
    """Every qualified site's first qualifier, keyed like the fallback."""
    return {
        (parsed.path, call["line"], call["name"]): call["qualifiers"][0]
        for parsed in files
        for call in parsed.calls
        if call["qualifiers"]
    }


def _tables(files: list[CppFile]) -> tuple:
    """The lookups the ranks read: C's three (same-file definitions, the
    ambiguous ones, per-file macros, repo-wide free functions) and C++'s
    fourth, by qualname.

    Every lookup is keyed by the **bare** qualname and the bare name, so
    the ranks read an overload set exactly as they read a preprocessor
    alternative: more than one definition, and nothing but argument types
    to pick between them (C-143). A name whose definitions the dedupe
    dropped appears once in ``parsed.symbols`` and is entered twice here;
    an overload set's definitions are each their own row already.
    """
    local_defs: dict[tuple[str, str], tuple[str, int]] = {}
    ambiguous_locals: set[tuple[str, str]] = set()
    macros_by_file: dict[str, dict[str, tuple[str, int]]] = defaultdict(dict)
    globals_by_name: dict[str, list[tuple[str, int]]] = defaultdict(list)
    by_qualname: dict[str, list[tuple[str, int]]] = defaultdict(list)
    functions_seen: set[tuple[str, str]] = set()
    for parsed in files:
        for symbol in parsed.symbols:
            here = (parsed.path, symbol["line"])
            qualname = _bare(symbol["qualname"])
            duplicated = qualname in parsed.duplicate_names
            if symbol["kind"] in ("function", "macro"):
                key = (parsed.path, symbol["name"])
                repeated = symbol["kind"] == "function" and key in functions_seen
                if duplicated or repeated:
                    ambiguous_locals.add(key)
                    local_defs.pop(key, None)
                elif key not in ambiguous_locals:
                    local_defs[key] = here
                if symbol["kind"] == "function":
                    functions_seen.add(key)
            if symbol["kind"] == "macro":
                macros_by_file[parsed.path][symbol["name"]] = here
            if symbol["kind"] == "function" and not symbol.get("static", False):
                globals_by_name[symbol["name"]].append(here)
                if duplicated:
                    globals_by_name[symbol["name"]].append(here)
            if symbol["kind"] in ("function", "method", "macro"):
                by_qualname[qualname].append(here)
                if duplicated:
                    by_qualname[qualname].append(here)
    return local_defs, ambiguous_locals, macros_by_file, globals_by_name, by_qualname


def _qualified_candidates(scope: str | None, qualname: str):
    """The qualnames a qualified call can mean, nearest scope first:
    inside ``ns::A::f``, a call written ``B::g()`` means ``ns::A::B::g``,
    then ``ns::B::g``, then ``B::g``."""
    parts = scope.split("::")[:-1] if scope else []
    for i in range(len(parts), 0, -1):
        yield "::".join(parts[:i] + [qualname])
    yield qualname


def _resolve_qualified(
    call: dict, by_qualname: dict[str, list[tuple[str, int]]]
) -> tuple[tuple[str, int] | None, bool]:
    """``(target, tie)`` for a qualified call: the unique symbol whose
    qualname matches, tried against the enclosing scope's prefixes first.
    More than one definition under a matching qualname is an overload set,
    and abstains."""
    qualname = "::".join(call["qualifiers"] + (call["name"],))
    for candidate in _qualified_candidates(call["scope"], qualname):
        matches = by_qualname.get(candidate, [])
        if len(matches) == 1:
            return matches[0], False
        if matches:
            return None, True
    return None, False


def _is_tie(
    parsed: CppFile, call: dict, tables: tuple, includes_by_file: dict[str, list[str]]
) -> bool:
    """Whether a plain call's abstention was a *tie* — a name with more
    than one definition at the rank that answered — rather than a name
    with no definition at all. C never asks it, having no overload sets;
    C++ needs the answer to tell the tail's `overload-set` from
    `unclassified`, so the ranks are walked a second time for this one
    question. The resolution itself stays C's
    (:func:`csource._resolve_fallback`) — nothing here decides a target."""
    local_defs, ambiguous_locals, macros_by_file, globals_by_name, _ = tables
    name = call["name"]
    if (parsed.path, name) in ambiguous_locals:
        return True
    if (parsed.path, name) in local_defs:
        return False
    header_matches = [
        inc for inc in includes_by_file[parsed.path] if name in macros_by_file.get(inc, {})
    ]
    if header_matches:
        return len(header_matches) > 1
    return len(globals_by_name.get(name, [])) > 1


def _call_fallback(
    files: list[CppFile], known_files: set[str], headers: csource.HeaderIndex
) -> tuple[dict[tuple[str, int, str], tuple[str, int]], set[tuple[str, int, str]]]:
    """Lane A's own resolutions and its overload-set abstentions, both
    keyed by call site — the syntactic floor this unit's whole graph rests
    on, since there is no semantic lane to hand off to."""
    tables = _tables(files)
    local_defs, ambiguous_locals, macros_by_file, globals_by_name, by_qualname = tables

    includes_by_file: dict[str, list[str]] = {}
    for parsed in files:
        includes_by_file[parsed.path] = [
            resolution.path
            for inc in parsed.includes
            if (
                resolution := csource._resolve_include(
                    parsed.path, inc["spec"], known_files, headers
                )
            ).path
            is not None
        ]

    fallback: dict[tuple[str, int, str], tuple[str, int]] = {}
    overloads: set[tuple[str, int, str]] = set()
    for parsed in files:
        for call in parsed.calls:
            key = (parsed.path, call["line"], call["name"])
            if call["shape"] == "qualified":
                target, tie = _resolve_qualified(call, by_qualname)
            elif call["shape"] == "plain":
                if any(
                    n == call["name"] and start <= call["line"] <= end
                    for (n, start, end) in parsed.local_bindings
                ):
                    continue  # a function pointer or a lambda: never resolved
                target = csource._resolve_fallback(
                    parsed,
                    call,
                    local_defs,
                    ambiguous_locals,
                    macros_by_file,
                    includes_by_file,
                    globals_by_name,
                )
                tie = target is None and _is_tie(parsed, call, tables, includes_by_file)
            else:
                continue  # member, dereference and construction: lane B's
            if tie:
                overloads.add(key)
            if target is None or target == (parsed.path, call["line"]):
                continue
            fallback[key] = target
    return fallback, overloads
