"""A C++ function tree-sitter-cpp named for a trailing annotation macro is
named per ingest (C-164's remainder, ADR-135's amendment).

The case is fmt's bundled gtest: `void UnitTest::AddTestPartResult(…)
GTEST_LOCK_EXCLUDED_(mutex_) {` parses as a function called
`GTEST_LOCK_EXCLUDED_`. Where an index ran, ADR-135's R1 removes it; where
none did, only this record says the name may be the macro's.
"""

import os

from hobbes.extract import _cpp_macro_name_record, _cpp_macro_names, extract_repo

SOURCE = """int helper() { return 1; }
void OsStackTraceGetter::UponLeavingGTest() GTEST_LOCK_EXCLUDED_(mutex_) {
  helper();
}
int MAX_SIZE() { return 2; }
struct Fstring {
  int str_;
  Fstring(int s) : str_(s) {}
};
"""


def test_lane_a_names_the_macro_named_function(tmp_path, monkeypatch):
    monkeypatch.setenv("HOBBES_SCIP", "0")
    (tmp_path / "unit.cc").write_text(SOURCE)
    graph = extract_repo(tmp_path).graph
    records = [e for e in graph["extraction_errors"] if e["stage"] == "cpp-macro-names"]
    assert len(records) == 1
    message = records[0]["message"]
    # The misnamed method is named; a real function spelled like a macro is
    # not, since no parameter list precedes its name.
    assert "GTEST_LOCK_EXCLUDED_ at unit:2" in message
    assert "MAX_SIZE" not in message
    assert "(ADR-135, C-164)" in message
    assert "helper" not in message


def test_only_names_after_a_declarator(tmp_path):
    (tmp_path / "a.cc").write_text(
        "void f() const FMT_CATCH(x) {}\n"     # 1: after a qualifier: named
        "static void OPL_CALC_CH(int c) {}\n"  # 2: a real caps function: not
        "C(int s) : size_(s) {}\n"            # 3: a member initialiser: named
        "void Max() {}\n"                     # 4: not
        "void g() {\n  try {\n  }\n  FMT_TRY_END(x) {}\n}\n"  # 8: after a block: named
    )
    (tmp_path / "b.c").write_text("void f() FMT_CATCH(x) {}\n")
    nodes = [{"id": "a", "path": "a.cc"}, {"id": "b", "path": "b.c"}]
    symbols = [
        {"id": "a.FMT_CATCH", "name": "FMT_CATCH", "kind": "function", "module": "a", "line": 1},
        {"id": "a.OPL_CALC_CH", "name": "OPL_CALC_CH", "kind": "function", "module": "a", "line": 2},
        {"id": "a.C.size_", "name": "size_", "kind": "method", "module": "a", "line": 3},
        {"id": "a.Max", "name": "Max", "kind": "function", "module": "a", "line": 4},
        {"id": "a.FMT_TRY_END", "name": "FMT_TRY_END", "kind": "function", "module": "a", "line": 8},
        {"id": "b.FMT_CATCH", "name": "FMT_CATCH", "kind": "function", "module": "b", "line": 1},
    ]
    named = _cpp_macro_names(tmp_path, symbols, nodes, {"a.cc": "cpp"})
    assert [s["id"] for s in named] == ["a.C.size_", "a.FMT_CATCH", "a.FMT_TRY_END"]


def test_record_shows_five_and_says_there_are_more():
    named = [
        {"id": f"m.F_{i}", "name": f"F_{i}", "module": "m", "line": i} for i in range(7)
    ]
    message = _cpp_macro_name_record(named)["message"]
    assert message.startswith("7 C++ function(s) are named for what follows their declarator")
    assert "F_4 at m:4 …" in message and "F_5" not in message
