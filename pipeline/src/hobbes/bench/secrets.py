"""The owner's key file → environment (ADR-057).

``secrets.txt`` (gitignored, never read by anything else in Hobbes) is
``name=value`` lines in the owner's stated format. ``hobbes bench run
--secrets FILE`` maps the known names onto the environment variables
the tools read — the Modal CLI and ``swebench --modal`` read
``MODAL_TOKEN_ID``/``MODAL_TOKEN_SECRET``, the agent loop reads
``HOBBES_LLM_API_KEY``, Daytona's SDK reads ``DAYTONA_API_KEY`` — and
refuses a name it does not know rather than exporting it blind. Values
are never printed; the CLI reports names only.
"""

from __future__ import annotations

import os
from pathlib import Path

#: file key → environment variable.
KNOWN = {
    "daytona_key": "DAYTONA_API_KEY",
    "modal_key_id": "MODAL_TOKEN_ID",
    "modal_key_secret": "MODAL_TOKEN_SECRET",
    "llm_key": "HOBBES_LLM_API_KEY",
    "HF_token": "HF_TOKEN",  # DeepSWE is HF-gated; datasets/huggingface_hub read HF_TOKEN
}


class SecretsError(ValueError):
    """An unreadable file, a malformed line, or an unknown key name."""


def read(path: Path) -> dict[str, str]:
    """``{file key: value}`` from *path*; every key must be known."""
    try:
        text = Path(path).read_text()
    except OSError as exc:
        raise SecretsError(f"{path}: {exc}") from exc
    out: dict[str, str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SecretsError(f"{path}:{n}: expected name=value")
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name not in KNOWN:
            raise SecretsError(f"{path}:{n}: unknown key {name!r}; known: {', '.join(KNOWN)}")
        if not value:
            raise SecretsError(f"{path}:{n}: {name} is empty")
        out[name] = value
    return out


def export(path: Path, environ: dict | None = None) -> list[str]:
    """Put the file's keys into *environ* (default ``os.environ``) under
    their variable names, not overriding one already set; returns the
    variable names that were set."""
    environ = os.environ if environ is None else environ
    names = []
    for key, value in read(path).items():
        var = KNOWN[key]
        if environ.get(var):
            continue
        environ[var] = value
        names.append(var)
    return names
