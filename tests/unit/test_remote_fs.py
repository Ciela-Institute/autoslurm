from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from autoslurm import remote_fs


def test_resolve_results_path_uses_results_root(monkeypatch) -> None:
    monkeypatch.setattr(
        remote_fs,
        "resolve_machine_config",
        lambda machine=None: (
            "cluster",
            {"results_root": "/mnt/results", "slurm_account": "x", "env_command": "y"},
        ),
    )
    out = remote_fs.resolve_results_path("substructure_lens/results/build_jacobian")
    assert out == "/mnt/results/substructure_lens/results/build_jacobian"


def test_resolve_results_path_uses_remote_storage_when_remote(monkeypatch) -> None:
    monkeypatch.setattr(
        remote_fs,
        "resolve_machine_config",
        lambda machine=None: (
            "cluster",
            {"hostname": "cluster", "slurm_account": "x", "env_command": "y"},
        ),
    )
    monkeypatch.setattr(
        remote_fs,
        "remote_storage_root_from_config",
        lambda cfg, machine_name=None: "/remote/autoslurm",
    )
    out = remote_fs.resolve_results_path("substructure_lens/results/build_jacobian")
    assert out == "/remote/autoslurm/results/substructure_lens/results/build_jacobian"


def test_path_exists_local(monkeypatch) -> None:
    monkeypatch.setattr(
        remote_fs,
        "resolve_machine_config",
        lambda machine=None: ("local", {"slurm_account": "x", "env_command": "y"}),
    )
    calls = {}

    def fake_run(cmd, capture_output, text):
        calls["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(remote_fs.subprocess, "run", fake_run)
    assert remote_fs.path_exists("/tmp/file", machine_name="local")
    assert calls["cmd"] == ["test", "-e", "/tmp/file"]


def test_path_exists_remote(monkeypatch) -> None:
    monkeypatch.setattr(
        remote_fs,
        "resolve_machine_config",
        lambda machine=None: (
            "cluster",
            {"hostname": "cluster", "slurm_account": "x", "env_command": "y"},
        ),
    )
    monkeypatch.setattr(
        remote_fs,
        "ssh_host_from_config",
        lambda cfg, name=None: "user@cluster",
    )
    calls = {}

    def fake_run(cmd, capture_output, text):
        calls["cmd"] = cmd
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(remote_fs.subprocess, "run", fake_run)
    assert not remote_fs.path_exists("/remote/path", machine_name="cluster")
    assert calls["cmd"][0] == "ssh"
    assert "test -e /remote/path" in calls["cmd"][-1]
