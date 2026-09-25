"""Where code may run: the container check, and the `podman run` plan that puts this package in one.

Grading executes the target's code — a body a model wrote, compiled and called — so it runs in the
sandbox image and never on the host (ADR-092, C-64). The shape is `hobbes/extract/containment.py`'s,
smaller: a plan is **pure data** built without running anything, and a refusal is **its own exception
type** (:class:`NotContained`), so a general handler cannot absorb the guarantee (P10, ADR-036).

`allow_host` exists for this package's own tests, which compile and run the fixture under
`tests/fixtures/` — this repo's pinned test data, read and reviewed, not a target checkout. The CLI
never sets it: `lattice grade --here` outside a container is an error, and without `--here` the CLI
builds a plan and runs *itself* inside the image.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["IMAGE", "NotContained", "in_container", "require_container", "package_src", "image_plan", "run_plan"]

#: The one image (ADR-092). `--image` overrides it; nothing else does.
IMAGE = "hobbes-session:local"

#: What a container leaves behind for a process to find. Podman writes the first, Docker the second.
MARKERS = ("/run/.containerenv", "/.dockerenv")


class NotContained(Exception):
    """Execution was asked for outside a container, and declined. Never degraded into host execution."""


def in_container() -> bool:
    """True when this process is inside a container."""
    return any(Path(marker).exists() for marker in MARKERS)


def require_container(*, allow_host: bool = False) -> None:
    """Refuse unless this process is contained, or the caller owns its own fixture (`allow_host`)."""
    if allow_host or in_container():
        return
    raise NotContained(
        "grading compiles and runs the target's code, which never happens on the host "
        f"(ADR-092, C-64). Run it in the image — `lattice grade --image {IMAGE}` — or, "
        "inside a container already, pass --here."
    )


def package_src() -> Path:
    """This package's `src/`, the directory a plan mounts at `/lattice`."""
    return Path(__file__).resolve().parents[1]


def image_plan(image: str, target: Path | str, workdir: Path | str, args: list[str] | tuple[str, ...]) -> list[str]:
    """The argv that runs `lattice <args>` over *target* inside *image*. Pure data; nothing runs here.

    The target rides read-only at `/target` (it is a checkout Hobbes does not own), the work dir
    read-write at `/work` (the staged copy, the objects, the results), and this package's `src/`
    read-only at `/lattice` with `PYTHONPATH` pointing at it, so the container runs *this* code and
    not a `lattice` the image might one day install. No network: a grading run fetches nothing.
    """
    return [
        "podman", "run", "--rm",
        "--network", "none",
        "--security-opt", "label=disable",
        "-v", f"{Path(target).resolve()}:/target:ro",
        "-v", f"{Path(workdir).resolve()}:/work:rw",
        "-v", f"{package_src()}:/lattice:ro",
        "--env", "PYTHONPATH=/lattice",
        "--workdir", "/work",
        image,
        "python3", "-m", "lattice.cli", *args, "--here",
    ]


def run_plan(plan: list[str], *, timeout: int = 3600) -> subprocess.CompletedProcess:
    """Execute a plan. The one place this package spawns a container."""
    return subprocess.run(plan, capture_output=True, text=True, timeout=timeout)
