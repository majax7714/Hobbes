"""The knowledge-only proxy launcher (ADR-094): `.mcp.json` starts
`sandbox/knowledge-serve`, which runs the IMAGE's hobbes-proxy in a
read-only, network-less container — never a binary a PATH resolves.
Driven with a fake podman on PATH; no container is started."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "sandbox" / "knowledge-serve"

FAKE_PODMAN = """#!/bin/sh
# records every argv line; `image exists` answers from FAKE_IMAGE_EXISTS
printf '%s\n' "$*" >> "$FAKE_LOG"
if [ "$1" = image ] && [ "$2" = exists ]; then
  [ "${FAKE_IMAGE_EXISTS:-1}" = 1 ] && exit 0 || exit 1
fi
exit 0
"""


@pytest.fixture
def fake_podman(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "podman"
    script.write_text(FAKE_PODMAN)
    script.chmod(0o755)
    log = tmp_path / "podman.log"
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("HOBBES_SESSIONS_ROOT", str(tmp_path / "sessions"))
    monkeypatch.delenv("HOBBES_KNOWLEDGE_HOST", raising=False)
    return log


def run() -> subprocess.CompletedProcess:
    return subprocess.run([str(SCRIPT)], capture_output=True, text=True, stdin=subprocess.DEVNULL)


class TestKnowledgeServe:
    def test_mcp_json_points_at_the_launcher(self):
        cfg = json.loads((ROOT / ".mcp.json").read_text())
        assert cfg["mcpServers"]["hobbes-knowledge"]["command"] == "sandbox/knowledge-serve"
        assert os.access(SCRIPT, os.X_OK)

    def test_runs_the_images_proxy_read_only_and_offline(self, fake_podman, tmp_path):
        proc = run()
        assert proc.returncode == 0, proc.stderr
        lines = fake_podman.read_text().splitlines()
        assert lines[0] == "image exists hobbes-session:local"
        argv = lines[1].split()
        assert argv[:3] == ["run", "-i", "--rm"]
        assert "--pull=never" in argv and "--network" in argv and argv[argv.index("--network") + 1] == "none"
        assert argv[argv.index("--security-opt") + 1] == "label=disable"
        mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
        assert f"{ROOT}:/work:ro" in mounts
        assert f"{tmp_path / 'sessions'}:/sessions:rw" in mounts
        assert (tmp_path / "sessions").is_dir()
        # the image's binary, by bare name, after the image — never a host path
        image_at = argv.index("hobbes-session:local")
        assert argv[image_at + 1:image_at + 4] == ["hobbes-proxy", "serve", "--repo"]
        assert "--knowledge-only" in argv and argv[argv.index("--repo") + 1] == "/work"
        assert argv[argv.index("--log-dir") + 1] == "/sessions"
        assert not any(a.startswith(str(ROOT / "go")) for a in argv)

    def test_no_image_refuses_and_names_the_hatch(self, fake_podman, monkeypatch):
        monkeypatch.setenv("FAKE_IMAGE_EXISTS", "0")
        proc = run()
        assert proc.returncode == 1
        assert "is not built" in proc.stderr and "HOBBES_KNOWLEDGE_HOST=1" in proc.stderr and "C-65" in proc.stderr
        assert fake_podman.read_text().splitlines() == ["image exists hobbes-session:local"]

    def test_no_podman_refuses(self, tmp_path, monkeypatch):
        # a PATH with the coreutils the script needs and no podman
        import shutil
        bare = tmp_path / "bare"
        bare.mkdir()
        for tool in ("dirname", "mkdir"):
            os.symlink(shutil.which(tool), bare / tool)
        monkeypatch.setenv("PATH", str(bare))
        monkeypatch.setenv("HOBBES_SESSIONS_ROOT", str(tmp_path / "sessions"))
        monkeypatch.delenv("HOBBES_KNOWLEDGE_HOST", raising=False)
        proc = subprocess.run(["/bin/sh", str(SCRIPT)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        assert proc.returncode == 1 and "podman is not installed" in proc.stderr

    def test_the_host_hatch_runs_this_checkouts_binary_and_says_so(self, fake_podman, monkeypatch, tmp_path):
        # The hatch execs go/bin/hobbes-proxy of THIS checkout; point the
        # script at a stand-in tree so no real proxy is needed.
        tree = tmp_path / "tree"
        (tree / "sandbox").mkdir(parents=True)
        (tree / "go" / "bin").mkdir(parents=True)
        (tree / "sandbox" / "knowledge-serve").write_text(SCRIPT.read_text())
        (tree / "sandbox" / "knowledge-serve").chmod(0o755)
        stub = tree / "go" / "bin" / "hobbes-proxy"
        stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n")
        stub.chmod(0o755)
        monkeypatch.setenv("HOBBES_KNOWLEDGE_HOST", "1")
        proc = subprocess.run([str(tree / "sandbox" / "knowledge-serve")], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        assert "HOST" in proc.stderr and "C-65" in proc.stderr
        assert proc.stdout.split()[:4] == ["serve", "--repo", str(tree), "--role"]
        assert not fake_podman.exists()  # podman never consulted
