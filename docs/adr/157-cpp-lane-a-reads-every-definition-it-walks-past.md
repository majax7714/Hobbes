# ADR-157 — C++ lane A reads every definition it walks past

**Date:** 2026-10-01 · **Status:** accepted (Max, 2026-10-01: "proceed with the recommended first fix"; route 1
of the honesty audit) and **built** (0.2.81-beta) · **Owner:** Max · **Source:** C-175 (registered at
0.2.80-beta by the honesty audit). Pre-registered and measured: `~/.hobbes/bench/c175-cpp-defs/` (`PREREG.md`
with its amendment, `regrade.sh`, `posdiff.py`, `RESULTS.md`).

Lifts C-175. Amends ADR-129's `lane-a-has-type` refusal.

## The cause

C++ lane A dropped four kinds of definition with a body, in a file tree-sitter parsed clean:

1. **A reference return** (`T&`, `const T&`, `T&&`, also `int (&f())[3]`). C++ reused C's
   `_function_declarator_of`, which unwraps a pointer and an array, but no `reference_declarator` or
   `parenthesized_declarator`.
2. **A conversion operator** (`operator int()`). Its declarator is an `operator_cast`, and no
   `function_declarator` holds its parameters.
3. **A friend defined in its class.** The walk never looked inside a `friend_declaration`.
4. **A type defined inside a class body or with a variable** (`struct In { … };` in a class, or
   `struct X { … } x;`). It parses as a member or variable declaration, and the walk stopped there.

Each such definition had no node, and calls to it were tallied `below-floor`, "seen, not modelled by design".
This was no decision of anyone's. In a file parsed with errors, ADR-129's mint read some of them back from the
index.

## Decision

1. C++ has its own `_function_declarator_of`. It unwraps pointer, array, reference and parenthesized
   declarators, the last two through their one unnamed declarator child. C's helper is unchanged, since C has
   no references.
2. **A conversion operator** is a method named as written up to its parameter list, whitespace collapsed
   (`operator const std::locale&`). Its parameters come from the `abstract_function_declarator`. The index
   spells the type its own way (`operator unsigned int` for `operator unsigned`). The join pairs a definition
   by line, so the difference reaches only the id.
3. **A friend defined in its class** is a `function` of the innermost enclosing namespace, which is the
   language's reading and the mint's (`fmt::v12::detail::operator==`). The clang key's caller names qualify it
   by the lexical class, but no grade reads a caller.
4. **A type in a member or variable declaration** is walked as any type is, in that scope. Its methods are
   methods, and a class template's nested members carry the template-pattern flag (ADR-125 §4).
5. **ADR-129's `lane-a-has-type`** refuses a minted type only where lane A holds a type that is the same type:
   one qualname is the other's trailing components, compared without template arguments (`same_type`). Lane A's
   `day` is the index's `fmt::v12::day`, because the macro hid the namespace. C's `cJSON` is the tag's `cJSON`.
   `UntypedOnCallSpecBase::Clause` is not `ExpectationBase::Clause`. Once rule 4 read nested types, the
   terminal name alone refused that row: a regression this change caused, and fixed in it.

## Measured (before = HEAD at 0.2.80-beta, after = this change; standing keys, poison on)

| | fmt | args | cJSON | sqlite-vector |
|---|---|---|---|---|
| Confirmed | 7,012 → **7,026** | 2,567 → 2,567 | 1,188 → 1,188 | 851 → 851 |
| Contradicted | 0 → 0 | 0 → 0 | 0 | 0 |
| Strict | 99.62% → 99.62% (7,026/7,053) | — | — | — |
| Symbols | 6,203 → 6,243 | 699 → 701 | identical graph | identical graph |

- **By position,** no `calls` row was lost on any cell. Every `uses` row that moved went to the nested class
  or function that now exists, apart from one type's reference to itself, which the projection drops.
- **Callers against the key's names** (the probe, not a grade): on fmt, agree 7,629 → 7,642, wrong 3 → 3.
- **The narrowed refusal** mints three types the old rule wrongly refused on fmt, each read right:
  `detail::type`, `scan_buffer::iterator` and `scan_buffer::sentinel`.
- **Lane A alone,** the clean-file losses of the first three shapes go to 0 on six clones. godot-orchestrator
  had 67, TinyGSM 10, libcuckoo 9, Ros_Qt5_Gui_App 7 and args 2. Rule 4 clears godot's 22 and Ros's 7 nested
  ones.

## What it does not do

- **An unnamed class's methods** (`struct { void f() {} } x;`) have no name to give. A class defined inside a
  function body stays below the floor (C-9).
- **A definition inside an error region** is still the mint's or nobody's (C-145).
- **The conversion operator's id** spells the type as written, not as the index does.
