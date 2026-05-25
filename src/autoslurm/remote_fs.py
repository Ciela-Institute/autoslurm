from __future__ import annotations

import shlex
import subprocess
from pathlib import PurePosixPath
from typing import Optional

from .storage import storage_root
from .utils import machine_config as resolve_machine_config
from .utils import remote_storage_root_from_config, ssh_host_from_config

__all__ = ["resolve_results_path", "path_exists"]


def _is_remote(machine_cfg: dict) -> bool:
    return any(key in machine_cfg for key in ("hostname", "hosturl", "username"))


def resolve_results_path(
    relative_path: str,
    *,
    machine_name: Optional[str] = None,
) -> str:
    """Resolve a results-relative path for a machine.

    Absolute paths are returned as-is.
    Relative paths are resolved using:
    1) machine `results_root` if configured
    2) `<remote_storage_root>/results` otherwise
    """
    candidate = PurePosixPath(relative_path)
    if candidate.is_absolute():
        return str(candidate)

    resolved_name, machine_cfg = resolve_machine_config(machine=machine_name)
    results_root = machine_cfg.get("results_root")
    if isinstance(results_root, str) and results_root.strip():
        base = PurePosixPath(results_root)
    elif _is_remote(machine_cfg):
        base = PurePosixPath(
            remote_storage_root_from_config(machine_cfg, resolved_name)
        ) / "results"
    else:
        base = PurePosixPath(str(storage_root())) / "results"
    return str(base / candidate)


def path_exists(
    path: str,
    *,
    machine_name: Optional[str] = None,
) -> bool:
    """Check if a path exists on the selected machine."""
    resolved_name, machine_cfg = resolve_machine_config(machine=machine_name)
    if _is_remote(machine_cfg):
        hostname = ssh_host_from_config(machine_cfg, resolved_name)
        cmd = ["ssh", *shlex.split(hostname), f"test -e {shlex.quote(path)}"]
    else:
        cmd = ["test", "-e", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
