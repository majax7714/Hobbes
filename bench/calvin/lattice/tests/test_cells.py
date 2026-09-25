"""The lattice over the real-source fixture: the grid, its quirks, and the neighbours."""

from pathlib import Path

import pytest

from lattice.cells import ISAS, NATIVE, build, parse_name

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


def test_every_isa_file_maps_thirteen_cells_and_nothing_is_unmatched(lattice):
    assert set(lattice.sources) == set(ISAS)
    for isa in ISAS:
        assert len(lattice.by_isa(isa)) == 13, isa
    assert lattice.unmatched == ()


def test_a_native_isa_is_two_impls_four_wrappers_seven_bodies_and_eleven_slots(lattice):
    for isa in sorted(NATIVE):
        cells = lattice.by_isa(isa)
        kinds = [c.kind for c in cells]
        assert (kinds.count("impl"), kinds.count("wrapper"), kinds.count("body")) == (2, 4, 7), isa
        assert sum(len(c.slots) for c in cells) == 11, isa
        assert all(c.native for c in cells)


def test_the_reference_and_the_isas_this_box_does_not_run_are_not_native(lattice):
    for isa in ("cpu", "neon", "rvv"):
        assert not any(c.native for c in lattice.by_isa(isa)), isa


def test_avx512s_hamming_kernel_is_static_and_holds_one_slot(lattice):
    cell = lattice.get("avx512/bit1/hamming")
    assert cell.name == "bit1_distance_hamming_avx512"
    assert cell.static and not cell.inline
    assert cell.slots == (("HAMMING", "BIT"),)
    assert cell.graded_via == (("HAMMING", "BIT"),)
    assert cell.kind == "body"


def test_an_impl_has_no_slot_and_is_graded_through_its_wrappers(lattice):
    impl = lattice.get("avx2/float32/l2_impl")
    assert impl.kind == "impl" and impl.static and impl.inline
    assert impl.slots == ()
    assert impl.graded_via == (("L2", "F32"), ("SQUARED_L2", "F32"))


def test_a_wrapper_is_recognised_by_its_body_not_its_name(lattice):
    assert lattice.get("avx2/float32/l2").kind == "wrapper"
    assert lattice.get("avx2/float32/l2_squared").kind == "wrapper"
    # same name shape, a real body: l1 and dot are never wrappers
    assert lattice.get("avx2/float32/l1").kind == "body"


def test_neons_abbreviated_helper_is_the_int8_impl_cell(lattice):
    assert parse_name("int8_distance_l2_neon_imp") == ("int8", "l2_impl", "neon")
    cell = lattice.get("neon/int8/l2_impl")
    assert cell.name == "int8_distance_l2_neon_imp"
    assert cell.kind == "impl"
    assert cell.graded_via == (("L2", "I8"), ("SQUARED_L2", "I8"))


def test_the_cpu_reference_fills_its_table_in_a_shape_the_map_does_not_read(lattice):
    # distance-cpu.c installs through a local cpu_table initialiser and memcpy, not by assignment:
    # the reference is not graded, so its cells carry no slots and that is said, not hidden.
    assert lattice.sources["cpu"].init is None
    assert all(c.slots == () for c in lattice.by_isa("cpu"))


def test_neighbours_are_the_steps_that_exist_in_the_documented_order(lattice):
    cell = lattice.get("avx2/int8/dot")
    assert [n.id for n in lattice.neighbours(cell)] == [
        # the ISA axis, in the order of ISAS
        "cpu/int8/dot",
        "sse2/int8/dot",
        "avx512/int8/dot",
        "neon/int8/dot",
        "rvv/int8/dot",
        # the type axis, in the order of TYPES (the fixture keeps float32 and int8 only)
        "avx2/float32/dot",
        # the metric axis, in the order of METRICS
        "avx2/int8/l2_impl",
        "avx2/int8/l2",
        "avx2/int8/l2_squared",
        "avx2/int8/l1",
        "avx2/int8/cosine",
    ]


def test_hamming_keeps_its_isa_siblings_and_has_no_axis_of_its_own(lattice):
    cell = lattice.get("avx2/bit1/hamming")
    assert [n.id for n in lattice.neighbours(cell)] == [
        "cpu/bit1/hamming",
        "sse2/bit1/hamming",
        "avx512/bit1/hamming",
        "neon/bit1/hamming",
        "rvv/bit1/hamming",
    ]


def test_an_impl_and_its_wrappers_are_metric_neighbours(lattice):
    impl = lattice.get("sse2/float32/l2_impl")
    ids = [n.id for n in lattice.neighbours(impl)]
    assert "sse2/float32/l2" in ids and "sse2/float32/l2_squared" in ids


# MARK: - the same grid under other names -


def test_without_a_rename_a_cells_name_is_its_own_original(lattice):
    for cell in lattice.cells.values():
        assert cell.original == cell.name


def test_a_rename_reads_the_grid_off_the_originals_and_keeps_what_the_file_writes(tmp_path):
    """The narrow change item 2 asks for: `build(target, rename=…)`, the reverse of a shadow's map."""
    renamed = tmp_path / "renamed"
    (renamed / "src").mkdir(parents=True)
    source = (FIXTURE / "src" / "distance-avx2.c").read_text()
    swap = {
        "float32_distance_dot_avx2": "kernel_one",
        "init_distance_functions_avx2": "kernel_setup",
    }
    for old, new in swap.items():
        source = source.replace(old, new)
    (renamed / "src" / "distance-avx2.c").write_text(source)

    back = {new: old for old, new in swap.items()}
    built = build(renamed, rename=back)
    cell = built.get("avx2/float32/dot")
    assert cell.name == "kernel_one" and cell.original == "float32_distance_dot_avx2"
    assert cell.slots == (("DOT", "F32"),)  # the init function was found under its written name
    assert built.sources["avx2"].init == "kernel_setup"
    assert len(built.by_isa("avx2")) == 13 and built.unmatched == ()

    # and without the map the grid is simply not there, rather than there and wrong
    assert "avx2/float32/dot" not in build(renamed).cells


def test_a_name_outside_the_grid_does_not_parse():
    assert parse_name("init_distance_functions_avx2") is None
    assert parse_name("turbo_lut_dot_cpu") is None
    assert parse_name("float32_distance_nonsense_avx2") is None
    assert parse_name("float32_distance_l2_impl_avx2") == ("float32", "l2_impl", "avx2")
