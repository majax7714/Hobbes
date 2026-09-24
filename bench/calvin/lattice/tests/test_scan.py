"""The C scanner on small inline strings: what must not count as a brace, and what must not count as a definition."""

import pytest

from lattice.scan import ScanError, scan

C_WITH_DECOYS = """\
#if defined(X) && (0) {
static int noisy (int a) {
    // }
    const char *s = "}";
    char c = '{';
    /* } */
    return a;
}
#endif
"""


def test_braces_in_comments_strings_char_literals_and_directives_do_not_count():
    result = scan(C_WITH_DECOYS)
    assert [fn.name for fn in result.functions] == ["noisy"]
    (fn,) = result.functions
    body = C_WITH_DECOYS[fn.body_span.start : fn.body_span.end]
    assert body.startswith("{\n    // }")
    assert body.endswith("return a;\n}")
    assert fn.static and not fn.inline
    assert fn.signature == "static int noisy (int a)"
    assert fn.signature_span.line == 2 and fn.body_span.end_line == 8


def test_a_prototype_and_an_array_initialiser_are_not_definitions():
    text = """\
float f(int);

static const char lut[4] = {0, 1, 2, 3};

float g (int x) { return x; }
"""
    assert [fn.name for fn in scan(text).functions] == ["g"]


def test_the_name_is_found_with_and_without_a_space_before_the_paren():
    text = "int a (void) { return 0; }\nint b(void) { return 1; }\n"
    names = [fn.name for fn in scan(text).functions]
    assert names == ["a", "b"]


def test_a_define_continued_over_two_lines_is_one_define():
    text = """\
#define FOO(x) \\
    ((x) + 1)
#define BAR 2

int f(void) { return FOO(BAR); }
"""
    result = scan(text)
    assert result.defines == ("FOO", "BAR")
    assert [fn.name for fn in result.functions] == ["f"]


def test_inline_and_static_are_read_from_the_declaration_only():
    text = "static inline float h (float inline_arg) { return inline_arg; }\n"
    (fn,) = scan(text).functions
    assert fn.static and fn.inline


def test_the_signature_starts_below_the_comment_and_directive_above_it():
    text = """\
#endif

// MARK: - the init -

bool init_distance_functions_avx2 (void) {
    return true;
}
"""
    (fn,) = scan(text).functions
    assert text[: fn.signature_span.start].endswith("- the init -\n\n")
    assert fn.signature == "bool init_distance_functions_avx2 (void)"


def test_both_arms_of_a_conditional_are_definitions_here():
    # no preprocessor runs and no -D is known, so choosing an arm would be a guess: distance-cpu.c
    # really does define cpu_supports_neon three times this way.
    text = """\
#if defined(A)
bool supports (void) { return true; }
#else
bool supports (void) { return false; }
#endif
"""
    assert [fn.name for fn in scan(text).functions] == ["supports", "supports"]


def test_an_unbalanced_brace_is_refused():
    with pytest.raises(ScanError):
        scan("int f(void) { return 0;\n")
