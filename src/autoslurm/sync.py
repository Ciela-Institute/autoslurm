from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Optional

from .storage import storage_root
from .utils import (
    activation_command_from_config,
    machine_config as resolve_machine_config,
    scp_host_and_keypath_from_config,
    ssh_host_from_config,
)

SYNC_DIRECTORIES = ("jobs", "slurm", "out")


def _is_remote(machine: dict) -> bool:
    return any(key in machine for key in ("hostname", "hosturl", "username"))


def _remote_ssh_command(machine: dict, machine_name: str, remote_command: str) -> list[str]:
    hostname = ssh_host_from_config(machine, machine_name)
    return ["ssh", *shlex.split(hostname), remote_command]


def _remote_storage_root(machine: dict, machine_name: str) -> str:
    python_probe = "from autoslurm.storage import storage_root; print(storage_root())"
    env_command = activation_command_from_config(machine)
    command_parts = []
    if env_command:
        command_parts.append(env_command)
    command_parts.append(f"python -c {shlex.quote(python_probe)}")
    remote_command = " && ".join(command_parts)
    result = subprocess.run(
        _remote_ssh_command(machine, machine_name, f"bash -lc {shlex.quote(remote_command)}"),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Unable to determine remote storage root for machine '{machine_name}': {message}"
        )
    remote_root = result.stdout.strip()
    if not remote_root:
        raise RuntimeError(
            f"Unable to determine remote storage root for machine '{machine_name}': empty response"
        )
    return remote_root


def _rsync_command(remote_source: str, local_target: Path, key_path: str = "") -> list[str]:
    ssh_parts = ["ssh"]
    if key_path:
        ssh_parts.extend(shlex.split(key_path))
    ssh_transport = shlex.join(ssh_parts)
    return [
        "rsync",
        "-a",
        "--ignore-existing",
        "-e",
        ssh_transport,
        remote_source,
        f"{local_target}/",
    ]


def _remote_dir_exists(machine: dict, machine_name: str, remote_path: str) -> bool:
    result = subprocess.run(
        _remote_ssh_command(machine, machine_name, f"test -d {shlex.quote(remote_path)}"),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def sync_machine(machine_name: Optional[str] = None) -> None:
    resolved_name, machine = resolve_machine_config(machine=machine_name)

    if not _is_remote(machine):
        print(f"Machine '{resolved_name}' is local; nothing to sync.")
        return

    remote_root = _remote_storage_root(machine, resolved_name)
    remote_target, key_path = scp_host_and_keypath_from_config(machine, resolved_name)
    local_root = storage_root()

    for directory in SYNC_DIRECTORIES:
        remote_source = f"{remote_root.rstrip('/')}/{directory}/"
        local_target = local_root / directory
        local_target.mkdir(parents=True, exist_ok=True)
        if not _remote_dir_exists(machine, resolved_name, remote_source.rstrip("/")):
            print(f"Skipping missing remote directory '{directory}' on '{resolved_name}'.")
            continue
        result = subprocess.run(
            _rsync_command(f"{remote_target}:{remote_source}", local_target, key_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"Failed to sync '{directory}' from machine '{resolved_name}': {message}"
            )

        if result.stdout.strip():
            print(result.stdout.strip())

    print(f"Synced jobs, slurm, and out from '{resolved_name}'.")
