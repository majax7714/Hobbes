"""A module loaded by name is recorded and placed, never drawn (ADR-167, C-179).

The cases are this repo's own shapes: ``test_ttt_probe.py`` loads
``scripts/ttt_probe.py`` through a module-level path built with ``/``;
``test_calvin_probe.py`` writes the chain inline; ``atlas0/check.py`` calls
``__import__("atlas0.world", …)``; three tests ``__import__`` a stdlib name.
"""

from pathlib import Path

from hobbes.extract import extract_repo
from hobbes.extract.discover import ModuleInfo
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import DynamicLoad, parse_source


def loads(source: str):
    return parse_source(source.encode()).dynamic_loads


class TestTheRead:
    def test_a_module_level_path_followed_through_its_name(self):
        source = (
            "import importlib.util\n"
            "from pathlib import Path\n"
            'SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ttt_probe.py"\n'
            "def load():\n"
            '    spec = importlib.util.spec_from_file_location("ttt_probe", SCRIPT)\n'
        )
        assert loads(source) == (DynamicLoad(5, "spec_from_file_location", "scripts/ttt_probe.py"),)

    def test_an_inline_chain_and_the_location_keyword(self):
        source = (
            "import importlib.util as u\n"
            'a = u.spec_from_file_location("p", Path(x).parents[1] / "scripts" / "calvin_probe.py")\n'
            'b = u.spec_from_file_location("q", location="tools/run.py")\n'
        )
        assert [(l.line, l.written) for l in loads(source)] == [
            (2, "scripts/calvin_probe.py"), (3, "tools/run.py")
        ]

    def test_a_name_literal(self):
        source = (
            "import importlib\n"
            "from importlib import import_module\n"
            'a = importlib.import_module("pkg.lit")\n'
            'b = import_module("pkg.other")\n'
            'c = __import__("atlas0.world", fromlist=["training_pairs"])\n'
        )
        assert [(l.via, l.written) for l in loads(source)] == [
            ("import_module", "pkg.lit"), ("import_module", "pkg.other"), ("__import__", "atlas0.world")
        ]

    def test_nothing_literal_is_recorded_with_nothing_written(self):
        source = (
            "import importlib\n"
            "name = pick()\n"
            "a = importlib.import_module(name)\n"
            'b = importlib.import_module(f"pkg.{name}")\n'
            "c = importlib.util.spec_from_file_location('m', base / name)\n"
            "d = importlib.util.spec_from_file_location('m', 'data/notes.txt')\n"
        )
        assert [l.written for l in loads(source)] == ["", "", "", ""]

    def test_a_name_assigned_twice_is_not_followed(self):
        source = (
            'P = "a/one.py"\n'
            'P = "a/two.py"\n'
            "s = spec_from_file_location('m', P)\n"
        )
        assert [l.written for l in loads(source)] == [""]


def _graph(files: dict[str, str]):
    modules = [
        ModuleInfo(id=mid, import_name=mid, path=path, root=".", kind="module") for mid, path in files
    ]
    parsed = {m.id: parse_source(files[(m.id, m.path)].encode()) for m in modules}
    return build_graph(modules, parsed)


class TestThePlacement:
    def test_exact_or_unique_suffix_names_a_module_and_nothing_else(self):
        graph = _graph({
            ("ttt_probe", "pipeline/scripts/ttt_probe.py"): "",
            ("pkg.lit", "src/pkg/lit.py"): "",
            ("test_x", "pipeline/tests/test_x.py"): (
                'S = Path(__file__).parents[1] / "scripts" / "ttt_probe.py"\n'
                "a = spec_from_file_location('t', S)\n"
                'b = importlib.import_module("pkg.lit")\n'
                'c = __import__("os")\n'
            ),
        })
        assert [(l["line"], l["target"]) for l in graph["dynamic_loads"]] == [
            (2, "ttt_probe"), (3, "pkg.lit"), (4, "")
        ]
        # No edge: a load is named, not drawn.
        assert not [e for e in graph["module_edges"] if e["from"] == "test_x" and e["type"] == "imports"]

    def test_two_candidates_are_not_placed(self):
        graph = _graph({
            ("a.run", "a/scripts/run.py"): "",
            ("b.run", "b/scripts/run.py"): "",
            ("t", "t.py"): "s = spec_from_file_location('r', ROOT / 'scripts' / 'run.py')\n",
        })
        assert [l["target"] for l in graph["dynamic_loads"]] == [""]

    def test_a_repo_with_no_load_has_no_key(self):
        assert "dynamic_loads" not in _graph({("m", "m.py"): "import os\n"})


def test_one_record_counts_the_loads_and_names_the_entry(tmp_path: Path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "probe.py").write_text("def run():\n    return 1\n")
    (tmp_path / "test_probe.py").write_text(
        "import importlib.util\n"
        "from pathlib import Path\n"
        'SCRIPT = Path(__file__).parent / "scripts" / "probe.py"\n'
        'spec = importlib.util.spec_from_file_location("probe", SCRIPT)\n'
        'other = __import__("collections")\n'
    )
    graph = extract_repo(tmp_path).graph
    [record] = [e for e in graph["extraction_errors"] if e["stage"] == "python-loads"]
    assert record["message"].startswith("2 Python call(s) in 1 file(s) load a module by name")
    assert "C-179" in record["message"] and "1 name an in-repo module" in record["message"]
    assert "test_probe.py:5 (__import__ 'collections')" in record["message"]
