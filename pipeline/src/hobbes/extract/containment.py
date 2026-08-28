"""Ingest containers — lane B runs inside the sandbox image (ADR-092).

The rule the session sandbox was drawn around was the wrong adversary:
the model was never inside the containers (a session is a tool loop
calling an endpoint); Podman contains *processes*. The corrected rule is
**sandbox whatever executes repo-authored code**, and the ingest lane
does — rust-analyzer's loader runs a repo's ``build.rs`` and proc macros
(C-29), and the venv listing runs the venv's own interpreter. The
guarantee (P10-specific, so the general degrade machinery may not absorb
it): **repo code never executes on the host.**

Lane B is contained *uniformly* — every provider, not only the executing
ones — so the guarantee never rests on a per-provider judgment about what
"doesn't execute" (a tsconfig plugin, a future provider change): one code
path, per P6's no-second-path rule. The cost is near zero because the
image exists (§7: one image, role-shaped mounts). Ingest is a new mount
shape on the session image, not a new image.

This module is the planner: a :class:`Plan` is pure data — the podman
argv, the mounts, the environment — built without running anything, so
the design is inspectable and unit-testable the way ``go/internal/sandbox``
is. :func:`run` executes a plan and is the **only** place lane B spawns a
process.

Mounts are derived, never authored, and every mount sits at its **host
path** inside the container:

- the Hobbes cache root (``staging.cache_root()``) **rw** — the stage,
  the SCIP output, the helper config, the provisioned ``node_modules``,
  the cargo/go/npm caches all live there; it is Hobbes's copy (ADR-027's
  contract already guarantees nothing writes back to the repo);
- the hobbes checkout's ``scip/`` (the helper and its pinned indexers)
  **ro**;
- every symlink target the stage points at outside the cache — a
  repo-owned ``node_modules`` (ADR-032/050), the repo's venv and the
  interpreter it links to — **ro**, at the identical absolute path, so
  the links simply resolve inside the container. (Declined alternative:
  rewriting links to container paths at staging — more moving parts for
  the same property.)

Network: every *index* step runs with ``--network none``. The steps that
need a registry — ``npm ci --ignore-scripts``, ``cargo fetch``,
``go mod download`` — are separate **fetch** containers that download
and execute no repo code; rootless podman offers no per-route packet
filter, so "the registry route only" (C-30/C-34) is achieved by phase
separation: the container that can reach the network never runs the
repo's code, and the container that runs the repo's code has no network.

No policy chain here. An ingest container carries a static per-step
profile — fixed mounts, fixed network, no escalation, nothing to approve
mid-ingest and no one to ask. Non-model processes make the policy story
simpler, not richer.

On a box without containment (no ``podman``, or the image not built):
steps that execute repo code **refuse** (:class:`ContainmentRefusal`, the
``PackRefusal`` shape of ADR-036 — a distinct type the general catches
name and re-raise first, never a fallback to host execution); steps that
execute no repo code may run on the host, and say so in a degradation
record the ingest summary and ``list_blind_spots`` both print (C-64).
``HOBBES_UNCONTAINED=1`` is the named escape hatch: everything runs on
the host and every provider's facts carry the disclosure. Never a
default, never silent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from hobbes.extract import staging

#: The one image (§7). Overridable for a box that tags it differently.
IMAGE_ENV = "HOBBES_SANDBOX_IMAGE"
DEFAULT_IMAGE = "hobbes-session:local"

#: The named escape hatch — host execution, disclosed on every provider.
UNCONTAINED_ENV = "HOBBES_UNCONTAINED"

#: Image-neutral PATH: the toolchains the Containerfile installs, in the
#: order the helper resolves them (`rust-analyzer`/`cargo` are rustup
#: proxies under /usr/local/cargo/bin; `scip-go` lands in /usr/local/bin).
CONTAINER_PATH = "/usr/local/cargo/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin"

#: Prefixes the image supplies itself. A symlink target under one of
#: these is never mounted: bind-mounting the host's /usr over the
#: image's would replace the toolchain the profile pins.
SYSTEM_PREFIXES = ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/proc", "/sys", "/dev", "/run")


class ContainmentError(RuntimeError):
    """A container could not be launched for a reason that is not the
    guarantee — the plan was fine, podman failed. Degrades like any other
    lane B failure."""


class ContainmentRefusal(RuntimeError):
    """A step that executes repo code was asked to run on a box without
    containment, and declined. **Never degraded into host execution.**

    The P10 shape (ADR-036): the general catch-and-continue handlers in
    lane B name this type and re-raise it before their broad ``except``,
    so the guarantee cannot be hollowed out by a handler written for the
    unknown case. Deliberately *not* a subclass of ``ScipError`` or
    ``OSError`` — the unit and language catches must not match it by
    accident.
    """


@dataclass(frozen=True)
class Profile:
    """A static per-step containment profile. No policy chain: fixed."""

    step: str
    #: Whether this step runs repo-authored code (build scripts, proc
    #: macros, the venv's interpreter). Decides refusal vs host fallback
    #: when containment is unavailable.
    executes_repo_code: bool
    #: ``"none"`` for every index step; ``"default"`` (podman's rootless
    #: default, unfiltered) only for fetch steps, which run no repo code.
    network: str
    #: Extra environment the step needs inside the container.
    env: tuple[str, ...] = ()


def _cache_env(root: Path) -> tuple[str, ...]:
    """The tool caches, all under the cache root so one rw mount covers
    them and nothing lands in the container's throwaway layer."""
    return (
        f"CARGO_HOME={root}/cargo",
        f"GOMODCACHE={root}/go/mod",
        f"GOCACHE={root}/go/build",
        f"npm_config_cache={root}/npm-cache",
        "GOTOOLCHAIN=local",
        "PYTHONDONTWRITEBYTECODE=1",
        "COREPACK_ENABLE_DOWNLOAD_PROMPT=0",
    )


#: Stated once, so nobody re-derives it (ADR-092 §1): what executes repo
#: code in lane B. scip-python (Pyright), scip-typescript, scip-go and the
#: fetch steps do not; rust-analyzer's `scip` export does (C-29); the venv
#: listing runs the venv's own interpreter, a binary under the repo tree.
PROFILES: dict[str, Profile] = {
    "index-python": Profile("index-python", False, "none"),
    "index-typescript": Profile("index-typescript", False, "none"),
    "index-go": Profile("index-go", False, "none", ("GOPROXY=off",)),
    "index-rust": Profile("index-rust", True, "none", ("CARGO_NET_OFFLINE=true",)),
    "python-env": Profile("python-env", True, "none"),
    "fetch-npm": Profile("fetch-npm", False, "default"),
    "fetch-go": Profile("fetch-go", False, "default"),
    # `cargo fetch` downloads and parses manifests; it does not build.
    # The `--config` pins in `rust_fetch_command` keep a staged
    # `.cargo/config.toml` from redirecting `rustc` to a repo binary.
    "fetch-rust": Profile("fetch-rust", False, "default"),
}

def rust_fetch_command(manifest: str) -> list[str]:
    """``cargo fetch`` for one manifest, with every knob a staged
    ``.cargo/config.toml`` could use to run a repo binary pinned back to
    the toolchain's: fetch executes nothing, and stays that way."""
    return [
        "cargo", "fetch", "--manifest-path", manifest,
        "--config", 'build.rustc="rustc"',
        "--config", 'build.rustc-wrapper=""',
        "--config", 'build.rustc-workspace-wrapper=""',
    ]


def go_fetch_command() -> list[str]:
    """``go mod download`` in the module root: no repo code runs."""
    return ["go", "mod", "download"]


#: The steps whose helper language maps onto them.
INDEX_STEP = {
    "python": "index-python",
    "typescript": "index-typescript",
    "go": "index-go",
    "rust": "index-rust",
}


@dataclass(frozen=True)
class Plan:
    """A ready-to-run ingest container. Pure data."""

    profile: Profile
    command: tuple[str, ...]
    cwd: str
    image: str
    cache_root: str
    ro: tuple[str, ...] = ()
    env: tuple[str, ...] = ()

    def mounts(self) -> list[str]:
        """The ``-v`` specs, stable order: cache rw, then every ro path."""
        specs = [f"{self.cache_root}:{self.cache_root}:rw"]
        specs.extend(f"{p}:{p}:ro" for p in self.ro)
        return specs

    def podman_args(self) -> list[str]:
        """The full argv after ``podman``.

        ``--security-opt label=disable`` rather than ``:z`` relabels: the
        ro mounts are the user's own directories (a venv, a dependency
        tree, an interpreter install) and relabeling them would change
        their SELinux context in place — the overlay/label trade ADR-060
        made for the worktree, taken the other way for trees Hobbes does
        not own. ``--pull=never``: the image is built locally, and a
        registry lookup for it is never the right failure.
        """
        args = [
            "run", "--rm",
            "--pull=never",
            "--security-opt", "label=disable",
            "--network", self.profile.network if self.profile.network != "default" else "pasta",
            "--env", f"HOME={self.cache_root}/home",
            "--env", f"PATH={CONTAINER_PATH}",
        ]
        for kv in (*_cache_env(Path(self.cache_root)), *self.profile.env, *self.env):
            args.extend(["--env", kv])
        args.extend(["--workdir", self.cwd])
        for spec in self.mounts():
            args.extend(["-v", spec])
        args.append(self.image)
        args.extend(self.command)
        return args


def image() -> str:
    return os.environ.get(IMAGE_ENV) or DEFAULT_IMAGE


def uncontained_requested() -> bool:
    return os.environ.get(UNCONTAINED_ENV, "") not in ("", "0", "false", "no")


_availability: dict[str, str | None] = {}


def unavailable_reason() -> str | None:
    """Why containment cannot run here, or None when it can.

    Cached per process: the answer does not change mid-ingest, and the
    image check is a podman round trip per provider otherwise.
    """
    key = image()
    if key in _availability:
        return _availability[key]
    reason: str | None
    if shutil.which("podman") is None:
        reason = "podman is not installed"
    else:
        try:
            proc = subprocess.run(
                ["podman", "image", "exists", key],
                capture_output=True, timeout=60,
            )
            reason = None if proc.returncode == 0 else (
                f"image {key} is not built (sandbox/README.md: `podman build`)"
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            reason = f"podman is not usable: {exc}"
    _availability[key] = reason
    return reason


def helper_dir() -> Path:
    """The hobbes checkout's ``scip/`` — the helper and its indexers."""
    return Path(__file__).resolve().parents[4] / "scip"


def mount_roots(paths: list[Path]) -> tuple[str, ...]:
    """Reduce *paths* to the ro mounts they need, derived from the same
    walk that placed the links (ADR-050): outside the cache (which is
    already rw), outside the image's own prefixes, and with a path under
    another dropped — podman refuses a mount inside a mount.

    Paths are mounted **unresolved**: a hop may pass through a directory
    that is itself a symlink on the host (uv's ``cpython-3.12-…`` →
    ``cpython-3.12.13-…``), and the container must see the path the link
    names, not the one it resolves to. Podman binds the real directory
    at that path.
    """
    cache = staging.cache_root()
    keep: list[Path] = []
    for path in sorted({Path(os.path.normpath(p)) for p in paths if p}):
        if not path.exists():
            continue
        if _under(path, cache) or _under(path.resolve(), cache):
            continue
        if any(_under(path, Path(p)) for p in SYSTEM_PREFIXES):
            continue
        if any(_under(path, k) for k in keep):
            continue
        keep.append(path)
    return tuple(str(p) for p in keep)


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def interpreter_mounts(python: Path) -> list[str]:
    """The installs a venv's ``bin/python`` links through, hop by hop.

    A venv's python is a symlink — to an interpreter install, or to
    another venv's python which links on — and every hop must be visible
    inside the container or the link dangles there. Each hop's install
    is ``<prefix>/bin/pythonX`` taken two levels up, so ``lib/`` rides
    along. A hop under a system prefix is the image's to supply.
    """
    mounts: list[str] = []
    cur = Path(python)
    seen: set[Path] = set()
    while cur.is_symlink() and cur not in seen:
        seen.add(cur)
        target = Path(os.readlink(cur))
        if not target.is_absolute():
            target = cur.parent / target
        cur = Path(os.path.normpath(target))
        prefix = cur.parent.parent
        if not any(_under(prefix, Path(p)) for p in SYSTEM_PREFIXES):
            if str(prefix) not in mounts:
                mounts.append(str(prefix))
    return mounts


def plan(
    step: str,
    command: list[str],
    *,
    cwd: Path | str,
    ro: tuple[str, ...] | list[str] = (),
    env: tuple[str, ...] | list[str] = (),
) -> Plan:
    """Build the plan for *step*: the profile is looked up, the helper
    dir is always mounted, the cache root is always rw."""
    profile = PROFILES[step]
    cache = staging.cache_root()
    ro_paths = mount_roots([helper_dir(), *(Path(p) for p in ro)])
    return Plan(
        profile=profile,
        command=tuple(command),
        cwd=str(cwd),
        image=image(),
        cache_root=str(cache),
        ro=ro_paths,
        env=tuple(env),
    )


#: Every step this process ran, in order — the ingest stamps it into
#: graph.json (`containment`) so the artifact says where lane B ran
#: (ADR-092 phase 3). Reset per ingest.
LEDGER: list[dict] = []


def reset_ledger() -> None:
    LEDGER.clear()


def summary() -> dict:
    """What graph.json records: each step and where it ran, whether
    every step was contained, and whether the escape hatch was set."""
    return {
        "steps": list(LEDGER),
        "all_contained": all(s["contained"] for s in LEDGER),
        "escape_hatch": uncontained_requested(),
    }


@dataclass(frozen=True)
class Outcome:
    """What :func:`run` produced, and where it ran."""

    proc: subprocess.CompletedProcess
    contained: bool
    #: Set when the step ran on the host: the disclosure the facts carry.
    host_reason: str | None = None


def run(p: Plan, *, timeout: int) -> Outcome:
    """Execute *p*: contained when the box can, on the host only when the
    step executes no repo code (disclosed) or the escape hatch is set
    (disclosed); refused otherwise. The one place lane B spawns."""
    reason = "HOBBES_UNCONTAINED is set" if uncontained_requested() else unavailable_reason()
    if reason is None:
        cache = Path(p.cache_root)
        (cache / "home").mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(
                ["podman", *p.podman_args()],
                capture_output=True, text=True, timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise ContainmentError(f"podman vanished mid-ingest: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ContainmentError(
                f"{p.profile.step} timed out after {timeout}s in its container"
            ) from exc
        if proc.returncode == 125:
            # podman's own failure code (image, mounts, runtime) — not the
            # command's; name it so a missing image reads as one.
            raise ContainmentError(
                f"podman could not start {p.profile.step}: {proc.stderr.strip()[-500:]}"
            )
        LEDGER.append({"step": p.profile.step, "contained": True})
        return Outcome(proc, True)

    if p.profile.executes_repo_code and not uncontained_requested():
        raise ContainmentRefusal(
            f"{p.profile.step} refused: repo code never executes on the host "
            f"(ADR-092) and {reason}. Build the sandbox image, or set "
            f"{UNCONTAINED_ENV}=1 to run it here — disclosed, never default."
        )
    env = {**os.environ}
    for kv in (*p.profile.env, *p.env):
        k, _, v = kv.partition("=")
        env[k] = v
    try:
        proc = subprocess.run(
            list(p.command), cwd=p.cwd, capture_output=True, text=True,
            timeout=timeout, env=env,
        )
    except FileNotFoundError:
        raise  # the caller names how its tool is installed
    except subprocess.TimeoutExpired as exc:
        raise ContainmentError(f"{p.profile.step} timed out after {timeout}s") from exc
    LEDGER.append({"step": p.profile.step, "contained": False, "reason": reason})
    return Outcome(proc, False, host_reason=reason)


def host_record(path: str, stage: str, p: Plan, outcome: Outcome) -> dict | None:
    """The degradation record a host-run step earns, or None when it ran
    contained. Lands in ``degraded`` → ``extraction_errors`` → the ingest
    summary and ``list_blind_spots`` (C-64's surfacing)."""
    if outcome.contained:
        return None
    what = "executes repo code and " if p.profile.executes_repo_code else ""
    return {
        "path": path,
        "stage": stage,
        "message": (
            f"{p.profile.step} ran on the host, not in the sandbox image: "
            f"{outcome.host_reason}. This step {what}"
            "was not contained (ADR-092, C-64)."
        ),
    }
