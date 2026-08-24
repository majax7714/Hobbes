"""Reading change-specs back (ADR-054).

``hobbes plan`` writes ``.hobbes/plans/<task>/change-spec.yaml``
(ADR-051); the run side reads it as plain dicts — the YAML is the
contract between the two halves, and a consumer that rebuilt the
dataclasses would be a second schema. A task id may be abbreviated to
any unique prefix, the way a git SHA may.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from hobbes.derive.changespec import PLANS_DIR


class SpecError(RuntimeError):
    """No such plan, an ambiguous prefix, or an unreadable spec."""


def list_plans(repo_root: Path) -> list[str]:
    """Task ids with a change-spec under ``.hobbes/plans/``, sorted."""
    root = Path(repo_root) / PLANS_DIR
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir() if (p / "change-spec.yaml").is_file()
    )


def resolve_task(repo_root: Path, task: str) -> str:
    """The full task id for *task* (an id or a unique prefix)."""
    plans = list_plans(repo_root)
    hits = [p for p in plans if p.startswith(task)]
    if not hits:
        raise SpecError(
            f"no plan {task!r} under {PLANS_DIR}/ — run `hobbes plan \"...\"` "
            "first" + (f"; known: {', '.join(plans)}" if plans else "")
        )
    if len(hits) > 1:
        raise SpecError(f"plan prefix {task!r} is ambiguous: {', '.join(hits)}")
    return hits[0]


def plan_dir(repo_root: Path, task: str) -> Path:
    """``.hobbes/plans/<task>`` for a resolved task id."""
    return Path(repo_root) / PLANS_DIR / task


def load_spec(repo_root: Path, task: str) -> dict:
    """The change-spec as written, with ``task`` resolved to its full id."""
    full = resolve_task(repo_root, task)
    path = plan_dir(repo_root, full) / "change-spec.yaml"
    try:
        spec = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise SpecError(f"{path}: {exc}") from exc
    if not isinstance(spec, dict) or "units" not in spec:
        raise SpecError(f"{path}: not a change-spec")
    spec["task"] = full
    return spec
