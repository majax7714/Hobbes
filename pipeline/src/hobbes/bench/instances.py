"""Benchmark instances and the instance protocol (ADR-055).

The schema is SWE-bench's (``princeton-nlp/SWE-bench_Verified`` and
its relatives — SWE-bench Lite, SWE-rebench, SWE-bench-Live share the
fields used here). Instances are read from a **local JSONL export**;
``pipeline/scripts/bench_fetch.py`` writes one from the Hugging Face
hub, so the pipeline itself carries no dataset dependency.

**The instance protocol** is the contamination rule ADR-052 asked for:
a known benchmark is in training corpora, and a pure model that
answers from memory biases the comparison *against* the harness. The
protocol cannot prove an instance uncontaminated (C-39); what it can do
is bound the set by ``created_at`` against a stated cutoff and record
every drop by reason, so the selection is reproducible and the claim
it licenses is scoped (P11).

**Depth** is H2's axis. SWE-bench Verified carries a human-rated
``difficulty`` per instance (``<15 min fix``, ``15 min - 1 hour``,
``1-4 hours``, ``>4 hours``) — that is the axis when present, and the
two upper bands are the **complex multi-step** set the owner's bar is
set on (benchmark-hypotheses.md, H1's rung form). Datasets without it
fall back to a proxy: the number of files the *gold* patch touches,
declared a proxy in every report.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

#: The fields an instance must carry to run at all.
REQUIRED = ("instance_id", "repo", "base_commit", "problem_statement")

#: H2's depth buckets over the gold-patch file count — the proxy, used
#: when the dataset rates no difficulty.
DEPTH_BUCKETS = (("1 file", 1, 1), ("2-3 files", 2, 3), ("4+ files", 4, None))

#: Verified's human-rated difficulty bands, in order; the last two are
#: the complex multi-step set.
DIFFICULTY_BANDS = ("<15 min fix", "15 min - 1 hour", "1-4 hours", ">4 hours")
COMPLEX_BANDS = DIFFICULTY_BANDS[2:]

_DIFF_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)


class InstanceError(ValueError):
    """An instance file that cannot be read or lacks required fields."""


@dataclass
class Instance:
    """One benchmark instance, SWE-bench shape."""

    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    patch: str = ""
    test_patch: str = ""
    created_at: str = ""
    version: str = ""
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    hints_text: str = ""
    difficulty: str = ""

    @property
    def gold_files(self) -> list[str]:
        """Files the gold patch touches — the depth proxy's raw value."""
        return sorted({b for _, b in _DIFF_HEADER.findall(self.patch or "")})

    @property
    def depth(self) -> int:
        return len(self.gold_files)

    @property
    def depth_bucket(self) -> str:
        """The rated difficulty band when the dataset has one, else the
        gold-patch proxy."""
        return self.difficulty if self.difficulty in DIFFICULTY_BANDS else depth_bucket(self.depth)

    @property
    def complex(self) -> bool:
        """In the complex multi-step set (rated ``1-4 hours`` or ``>4 hours``)."""
        return self.difficulty in COMPLEX_BANDS

    def to_dict(self) -> dict:
        return asdict(self)


def depth_bucket(depth: int) -> str:
    """The H2 bucket for a gold-patch file count."""
    for name, low, high in DEPTH_BUCKETS:
        if depth >= low and (high is None or depth <= high):
            return name
    return "0 files (no gold patch)"


def _as_list(value) -> list[str]:
    """SWE-bench exports FAIL_TO_PASS as a JSON-encoded string; some
    mirrors as a list. Accept both."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        return [str(v) for v in parsed] if isinstance(parsed, list) else [value]
    return []


def parse_instance(row: dict) -> Instance:
    """An :class:`Instance` from one dataset row; raises on a missing
    required field rather than running a half-instance."""
    missing = [k for k in REQUIRED if not row.get(k)]
    if missing:
        raise InstanceError(
            f"instance {row.get('instance_id', '?')!r} lacks {', '.join(missing)}"
        )
    return Instance(
        instance_id=row["instance_id"],
        repo=row["repo"],
        base_commit=row["base_commit"],
        problem_statement=row["problem_statement"],
        patch=row.get("patch") or "",
        test_patch=row.get("test_patch") or "",
        created_at=row.get("created_at") or "",
        version=str(row.get("version") or ""),
        fail_to_pass=_as_list(row.get("FAIL_TO_PASS")),
        pass_to_pass=_as_list(row.get("PASS_TO_PASS")),
        hints_text=row.get("hints_text") or "",
        difficulty=str(row.get("difficulty") or ""),
    )


def load_instances(path: Path) -> list[Instance]:
    """Instances from a JSONL file (one row per line) or a JSON array."""
    path = Path(path)
    try:
        text = path.read_text()
    except OSError as exc:
        raise InstanceError(f"{path}: {exc}") from exc
    rows: list[dict]
    stripped = text.lstrip()
    if stripped.startswith("["):
        rows = json.loads(text)
    else:
        rows = []
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise InstanceError(f"{path}:{n}: {exc}") from exc
    return [parse_instance(r) for r in rows]


@dataclass
class Selection:
    """The instance protocol's output: what ran, what was dropped, why."""

    source: str
    cutoff: str | None
    repos: list[str]
    ids: list[str]
    limit: int | None
    selected: list[Instance]
    dropped: dict[str, int]
    created_range: tuple[str, str] | None
    difficulty: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "cutoff": self.cutoff,
            "repos": self.repos,
            "ids": self.ids,
            "limit": self.limit,
            "difficulty": self.difficulty,
            "selected": [i.instance_id for i in self.selected],
            "dropped": self.dropped,
            "created_range": list(self.created_range) if self.created_range else None,
            "contamination": (
                "bounded by created_at against the stated cutoff, not proven: "
                "an instance may still be in a model's training data (C-39)"
            ),
            "depth": ("rated difficulty band where the dataset carries one (Verified), "
                      "else gold-patch file count — a proxy, declared"),
        }


def select(
    instances: list[Instance],
    source: str = "",
    cutoff: str | None = None,
    repos: list[str] | None = None,
    ids: list[str] | None = None,
    limit: int | None = None,
    difficulty: list[str] | None = None,
) -> Selection:
    """Apply the protocol. *cutoff* is an ISO date; instances created on
    or before it are dropped (``created_at`` missing counts as a drop
    too — an undated instance cannot be placed against a cutoff).
    *difficulty* keeps only the named bands (``complex`` expands to the
    two upper ones). Order is the dataset's, so a limit is a prefix,
    not a sample."""
    dropped = {"before_cutoff": 0, "undated": 0, "repo": 0, "id": 0, "difficulty": 0, "limit": 0}
    kept: list[Instance] = []
    repos = repos or []
    ids = ids or []
    bands: list[str] = []
    for band in difficulty or []:
        bands += list(COMPLEX_BANDS) if band == "complex" else [band]
    for inst in instances:
        if ids and inst.instance_id not in ids:
            dropped["id"] += 1
            continue
        if repos and inst.repo not in repos:
            dropped["repo"] += 1
            continue
        if bands and inst.difficulty not in bands:
            dropped["difficulty"] += 1
            continue
        if cutoff:
            if not inst.created_at:
                dropped["undated"] += 1
                continue
            if inst.created_at[:10] <= cutoff[:10]:
                dropped["before_cutoff"] += 1
                continue
        kept.append(inst)
    if limit is not None and len(kept) > limit:
        dropped["limit"] += len(kept) - limit
        kept = kept[:limit]
    dates = sorted(i.created_at for i in kept if i.created_at)
    return Selection(
        source=source, cutoff=cutoff, repos=repos, ids=ids, limit=limit,
        selected=kept, dropped={k: v for k, v in dropped.items() if v},
        created_range=(dates[0], dates[-1]) if dates else None,
        difficulty=bands or None,
    )


def format_selection(sel: Selection) -> str:
    lines = [f"selection: {len(sel.selected)} instances from {sel.source or 'stdin'}"]
    if sel.cutoff:
        lines.append(f"  cutoff: created after {sel.cutoff} (contamination bounded, not proven — C-39)")
    else:
        lines.append("  cutoff: none — every instance may be in a model's training data (C-39)")
    if sel.created_range:
        lines.append(f"  created: {sel.created_range[0][:10]} … {sel.created_range[1][:10]}")
    if sel.dropped:
        lines.append("  dropped: " + ", ".join(f"{k} {v}" for k, v in sel.dropped.items()))
    buckets: dict[str, int] = {}
    for inst in sel.selected:
        buckets[inst.depth_bucket] = buckets.get(inst.depth_bucket, 0) + 1
    if buckets:
        rated = any(i.difficulty in DIFFICULTY_BANDS for i in sel.selected)
        label = "depth (rated difficulty)" if rated else "depth (gold-patch files, a proxy)"
        order = {b: n for n, b in enumerate(DIFFICULTY_BANDS)}
        lines.append(f"  {label}: " + ", ".join(
            f"{b} {n}" for b, n in sorted(buckets.items(), key=lambda kv: (order.get(kv[0], 99), kv[0]))))
        if rated:
            lines.append(f"  complex multi-step (1-4 hours, >4 hours): {sum(1 for i in sel.selected if i.complex)}")
    return "\n".join(lines)
