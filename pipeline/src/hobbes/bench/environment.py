"""The benchmark's environment, bound to both arms (ADR-058).

The first live run found that neither arm could run the target repo's
tests: the session image is a bare Alpine with python3 and git, and the
pure arm ran on the host — no pytest, no dependencies, no compiled
extensions. An agent that cannot run a test cannot verify a fix, so the
arm's outcome was empty by construction, whatever the model did.

The fix is a **benchmark practice**, stated as one: each SWE-bench
instance publishes an image with the repo installed at the base commit
and its per-version environment (the evaluator judges in exactly that
image, C-40). Both arms now run *in that image*, with the workspace
mounted at ``/work`` and bound to the environment by two mechanisms:

1. ``PYTHONPATH=/work`` — the image's editable install points at
   ``/testbed``; a path entry precedes the editable finder on
   ``sys.meta_path``, so the agent's worktree shadows the installed
   copy for every import.
2. a pre-command that copies ``/testbed``'s **untracked** files (the
   in-place build artifacts — ``.so`` extensions, generated version
   modules) into ``/work``, so a compiled repo imports without a
   rebuild. A change that needs a rebuild of a compiled extension is
   not seen by the tests — C-43 names that edge.

Neither mechanism is Hobbes's sandbox; they are the benchmark's
environment handed to it, visible in every dry run and recorded per
instance (image + digest) so a verdict can be tied to the environment
that produced it.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

from hobbes.bench.instances import Instance

#: The evaluator's image namespace (swebench 5.x publishes here).
IMAGE_NAMESPACE = "docker.io/swebench"
#: The instance image's layout, as swebench builds it.
TESTBED = "/testbed"
CONDA_ENV_BIN = "/opt/miniconda3/envs/testbed/bin"
CONDA_BIN = "/opt/miniconda3/bin"
#: A modern interpreter for the owned loop: the conda env carries the
#: target's python (3.6 on old django), the base carries the image's.
RUNTIME_PYTHON = CONDA_BIN + "/python3"
KINDS = ("none", "swebench")


class EnvironmentError_(RuntimeError):
    """The environment image cannot be had."""


@dataclass
class Environment:
    """What binds an arm to the benchmark's environment: the image and
    the three things that make ``/work`` the tree under test inside it."""

    image: str
    path: str
    runtime_python: str
    pre: str
    env: dict[str, str] = field(default_factory=dict)
    digest: str = ""

    def session_args(self) -> list[str]:
        """Flags for ``hobbes-session`` (the harness arm)."""
        args = ["--image", self.image, "--path", self.path, "--runtime-python", self.runtime_python]
        if self.pre:
            args += ["--pre", self.pre]
        for key, value in sorted(self.env.items()):
            args += ["--env", f"{key}={value}"]
        return args

    def podman_env(self) -> list[str]:
        """``--env`` flags for a bare ``podman run`` (the pure arm)."""
        out = ["--env", f"PATH={self.path}"]
        for key, value in sorted(self.env.items()):
            out += ["--env", f"{key}={value}"]
        return out

    def to_dict(self) -> dict:
        return {"image": self.image, "digest": self.digest, "path": self.path,
                "runtime_python": self.runtime_python, "pre": self.pre, "env": dict(self.env)}


def image_name(instance_id: str, namespace: str = IMAGE_NAMESPACE) -> str:
    """swebench's image key: ``__`` becomes ``_1776_`` (their convention)."""
    return f"{namespace}/sweb.eval.x86_64.{instance_id.replace('__', '_1776_')}:latest"


#: The binding pre-command: every untracked file in the image's testbed
#: (build artifacts; git lists ignored ones too since no exclude is
#: applied) lands in the worktree. Tracked files are the worktree's own.
BIND_PRE = (
    f"cd {TESTBED} && git ls-files -o -z | tar --null -T - -cf - | tar -C /work -xf -"
)


def swebench_environment(instance: Instance) -> Environment:
    """The instance's own image, bound to ``/work``."""
    return Environment(
        image=image_name(instance.instance_id),
        path=f"{CONDA_ENV_BIN}:{CONDA_BIN}:/usr/local/bin:/usr/bin:/bin",
        runtime_python=RUNTIME_PYTHON,
        pre=BIND_PRE,
        env={"PYTHONPATH": "/work"},
    )


def ensure_image(env: Environment, runner=subprocess.run, log=print) -> Environment:
    """Pull the image unless present; record its digest on *env*.
    Raises :class:`EnvironmentError_` when podman is missing or the
    pull fails — an arm without its environment must not run."""
    if shutil.which("podman") is None and runner is subprocess.run:
        raise EnvironmentError_("podman not found; the benchmark environment needs a container engine")
    exists = runner(["podman", "image", "exists", env.image], capture_output=True, text=True)
    if exists.returncode != 0:
        log(f"  environment: pulling {env.image}")
        pulled = runner(["podman", "pull", "-q", env.image], capture_output=True, text=True)
        if pulled.returncode != 0:
            raise EnvironmentError_(f"podman pull {env.image}: {(pulled.stderr or pulled.stdout).strip()[-300:]}")
    digest = runner(["podman", "image", "inspect", "--format", "{{.Digest}}", env.image],
                    capture_output=True, text=True)
    env.digest = digest.stdout.strip() if digest.returncode == 0 else ""
    return env
