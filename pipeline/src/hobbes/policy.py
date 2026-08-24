"""Shell-out wrapper around the Go ``hobbes-policy`` binary.

The Go engine is the only implementation of policy resolution (build plan
M0); this module's contract with it — flags, JSON output, decision-coded
exits — is frozen in ADR-003. Nothing here interprets policy: it locates the
binary, invokes ``resolve``, and hands back the parsed result.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass

#: Exit codes the Go binary uses to encode decisions (ADR-003).
DECISION_EXIT_CODES = {0: "allow", 10: "deny", 20: "escalate"}

BINARY_ENV_VAR = "HOBBES_POLICY_BIN"
BINARY_NAME = "hobbes-policy"


class PolicyBinaryNotFound(RuntimeError):
    """Raised when the hobbes-policy binary cannot be located."""


class PolicyResolveError(RuntimeError):
    """Raised when hobbes-policy exits with a non-decision status."""


@dataclass(frozen=True)
class Resolution:
    """Outcome of resolving one command against the merged policy chain."""

    decision: str
    """One of ``allow``, ``deny``, ``escalate``."""

    exit_code: int
    """The decision-coded exit status, propagated by the CLI."""

    raw: dict
    """The full JSON resolution from hobbes-policy (command, decisive rule,
    all matches — shape per ADR-003)."""


def find_binary() -> str:
    """Locate hobbes-policy: ``$HOBBES_POLICY_BIN`` first, then ``$PATH``.

    Raises :class:`PolicyBinaryNotFound` with build instructions otherwise.
    """
    env = os.environ.get(BINARY_ENV_VAR)
    if env:
        if not os.path.isfile(env) or not os.access(env, os.X_OK):
            raise PolicyBinaryNotFound(
                f"{BINARY_ENV_VAR}={env} is not an executable file"
            )
        return env
    found = shutil.which(BINARY_NAME)
    if found:
        return found
    raise PolicyBinaryNotFound(
        f"{BINARY_NAME} not found. Build it with "
        "`go build -o bin/hobbes-policy ./cmd/hobbes-policy` in go/ and put "
        f"it on PATH, or point {BINARY_ENV_VAR} at it."
    )


def resolve(
    command: str,
    *,
    dir: str | None = None,
    repo: str | None = None,
    box: str | None = None,
    binary: str | None = None,
) -> Resolution:
    """Resolve *command* against the merged box → repo → folder policy chain.

    Optional *dir*, *repo*, and *box* map to the corresponding
    ``hobbes-policy resolve`` flags; *binary* overrides binary discovery
    (used by tests). Raises :class:`PolicyResolveError` if the binary exits
    with anything other than a decision code.
    """
    argv = [binary or find_binary(), "resolve"]
    if repo:
        argv += ["--repo", repo]
    if dir:
        argv += ["--dir", dir]
    if box:
        argv += ["--box", box]
    argv.append(command)

    proc = subprocess.run(argv, capture_output=True, text=True)
    decision = DECISION_EXIT_CODES.get(proc.returncode)
    if decision is None:
        raise PolicyResolveError(
            f"{argv[0]} exited {proc.returncode}: {proc.stderr.strip()}"
        )
    return Resolution(
        decision=decision, exit_code=proc.returncode, raw=json.loads(proc.stdout)
    )
