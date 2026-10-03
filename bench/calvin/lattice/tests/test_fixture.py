"""The real-source fixture is present and says where it came from, and `scripts/make_fixture.py` rebuilds it."""

import shutil
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


def test_fixture_has_every_isa_file_and_its_provenance():
    names = {p.name for p in (FIXTURE / "src").glob("distance-*.c")}
    assert names == {f"distance-{isa}.c" for isa in ("cpu", "sse2", "avx2", "avx512", "neon", "rvv")}
    assert "0c2223ada9dce1fa33248c8835a15f51d9a0f655" in (FIXTURE / "PROVENANCE.md").read_text()
    assert (FIXTURE / "LICENSE.md").read_text().lstrip().startswith("Apache License")


SCRIPTS = Path(__file__).parents[1] / "scripts"
ISA_FILES = [f"distance-{isa}.c" for isa in ("cpu", "sse2", "avx2", "avx512", "neon", "rvv")]


def test_make_fixture_drops_the_dropped_types_and_their_table_lines(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import make_fixture

    source = (
        "float float32_distance_l2_cpu (const void *a) {\n    return 0;\n}\n\n"
        "static inline float float16_distance_l2_cpu (const void *a) {\n    if (a) { return 1; }\n    return 0;\n}\n\n\n"
        "float bfloat16_distance_dot_cpu(const void *a) {\n    return 2;\n}\n"
        "    table[0] = float32_distance_l2_cpu;\n"
        "    table[1] = float16_distance_l2_cpu;\n"
    )
    trimmed = make_fixture.trim(source)
    assert "float16_distance" not in trimmed and "bfloat16_distance" not in trimmed
    assert trimmed.startswith("float float32_distance_l2_cpu (const void *a) {")
    assert "table[0] = float32_distance_l2_cpu;" in trimmed


def test_make_fixture_over_the_fixture_is_the_fixture(monkeypatch, tmp_path):
    """The real-source case: the fixture is the script's output, so running it again changes nothing."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import make_fixture

    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    for name in ISA_FILES:
        shutil.copy(FIXTURE / "src" / name, src / name)
    make_fixture.main(["make_fixture.py", str(src), str(dst)])
    for name in ISA_FILES:
        assert (dst / name).read_text() == (FIXTURE / "src" / name).read_text(), name
