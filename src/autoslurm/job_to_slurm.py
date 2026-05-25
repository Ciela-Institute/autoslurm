import os
from io import TextIOWrapper
from datetime import datetime
from pathlib import PurePosixPath
from .utils import name_slurm_script
from .storage import ensure_storage_dirs, slurm_dir, storage_root
from .utils import activation_command_from_config, remote_storage_root_from_config


__all__ = ["create_slurm_script"]


def create_slurm_script(job: dict, date: datetime, machine_config: dict) -> str:
    """Creates a SLURM script and saves it locally"""
    ensure_storage_dirs()
    path = slurm_dir()
    slurm_name = name_slurm_script(job, date)
    file_path = path / slurm_name
    with open(file_path, "w") as f:
        write_slurm_content(f, job, machine_config)
    print(f"Saved SLURM script {slurm_name} locally")
    return slurm_name


def _format_script_args(job_args: dict) -> list[str]:
    normalized = []
    positional = job_args.get("__positionals__", [])
    for key, value in job_args.items():
        if key == "__positionals__":
            continue
        if value is None:
            continue
        flag = key.replace("_", "-")
        if isinstance(value, bool):
            if not value:
                continue
            normalized.append(f"  --{flag}")
            continue
        if isinstance(value, list):
            if not value:
                continue
            normalized.append(f"  --{flag} {' '.join(map(str, value))}")
            continue
        normalized.append(f"  --{flag}={value}")
    normalized.extend(f"  {pos}" for pos in positional)
    return normalized


def _normalize_script_args(
    job_args: dict,
    machine_config: dict,
    remote_storage: str,
    path_args: list[str] | tuple[str, ...] | None = None,
) -> dict:
    normalized = dict(job_args)
    declared = set(path_args or [])
    declared.add("output_dir")
    results_root = machine_config.get("results_root")
    if isinstance(results_root, str) and results_root.strip():
        base = PurePosixPath(results_root)
    else:
        base = PurePosixPath(remote_storage) / "results"
    for key in declared:
        value = normalized.get(key)
        if not isinstance(value, str) or value.strip() == "":
            continue
        as_path = PurePosixPath(value)
        if as_path.is_absolute():
            continue
        normalized[key] = str(base / as_path)
    return normalized


def _write_script_args(file: TextIOWrapper, job_args: list[str]) -> None:
    for idx, line in enumerate(job_args):
        suffix = " \\\n" if idx < len(job_args) - 1 else "\n"
        file.write(line + suffix)


def write_slurm_content(file: TextIOWrapper, job: dict, machine_config: dict) -> None:
    """
    Writes the content of the SLURM script with formatted arguments, handling list arguments differently based on their type.
    """
    env_command = activation_command_from_config(machine_config)
    slurm_account = machine_config.get("slurm_account", "")

    file.write("#!/bin/bash\n")
    if slurm_account:
        file.write(f"#SBATCH --account={slurm_account}\n")
    if machine_config.get("path"):
        remote_storage = machine_config.get("path")
    elif machine_config.get("hostname") or machine_config.get("hosturl"):
        remote_storage = remote_storage_root_from_config(machine_config)
    else:
        remote_storage = str(storage_root())
    output_dir = os.path.join(remote_storage, "out")
    file.write(f"#SBATCH --output={os.path.join(output_dir, '%x-%j.out')}\n")
    file.write(f"#SBATCH --job-name={job['name']}\n")

    # SLURM directives
    for key, value in job["slurm"].items():
        if value is not None:
            file.write(f"#SBATCH --{key.replace('_', '-')}={value}\n")

    # Environment activation command
    if env_command:
        file.write(f"{env_command}\n")

    # Main command and arguments
    job_args = job.get("script_args", {})
    normalized_job_args = _normalize_script_args(
        job_args,
        machine_config,
        remote_storage,
        path_args=job.get("path_args"),
    )
    lines = _format_script_args(normalized_job_args)
    if lines:
        file.write(f"{job['script']} \\\n")
        _write_script_args(file, lines)
    else:
        file.write(f"{job['script']}\n")
