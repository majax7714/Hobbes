"""The real-source fixture is present and says where it came from."""

from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


def test_fixture_has_every_isa_file_and_its_provenance():
    names = {p.name for p in (FIXTURE / "src").glob("distance-*.c")}
    assert names == {f"distance-{isa}.c" for isa in ("cpu", "sse2", "avx2", "avx512", "neon", "rvv")}
    assert "0c2223ada9dce1fa33248c8835a15f51d9a0f655" in (FIXTURE / "PROVENANCE.md").read_text()
    assert (FIXTURE / "LICENSE.md").read_text().lstrip().startswith("Apache License")
