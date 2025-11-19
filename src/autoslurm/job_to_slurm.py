import os
from io import TextIOWrapper
from datetime import datetime
from .utils import name_slurm_script
from .storage import ensure_storage_dirs, slurm_dir


__all__ = ["create_slurm_script"]


def create_slurm_script(job: dict, date: datetime, machine_config: dict) -> str:
    """Creates a SLURM script and saves it locally"""
    ensure_storage_dirs()
    path = slurm_dir()
    slurm_name = name_slurm_script(job, date)
    file_path = path / slurm_name
    with open(file_path, "w") as f:
        write_slurm_content(f, job, machine_config)
    print(f"Saved SLURM script for job {job['name']} saved to {file_path}")
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


def _write_script_args(file: TextIOWrapper, job_args: list[str]) -> None:
    for idx, line in enumerate(job_args):
        suffix = " \\\n" if idx < len(job_args) - 1 else "\n"
        file.write(line + suffix)


def write_slurm_content(file: TextIOWrapper, job: dict, machine_config: dict) -> None:
    """
    Writes the content of the SLURM script with formatted arguments, handling list arguments differently based on their type.
    """
    env_command = machine_config.get("env_command", "")
    slurm_account = machine_config.get("slurm_account", "")

    file.write("#!/bin/bash\n")
    if slurm_account:
        file.write(f"#SBATCH --account={slurm_account}\n")
    remote_storage = machine_config.get("path", "~/.autoslurm")
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

    # Pre-commands
    for cmd in job.get("pre_commands", []):
        file.write(f"{cmd}\n")

    # Main command and arguments
    job_args = job.get("script_args", {})
    lines = _format_script_args(job_args)
    if lines:
        file.write(f"{job['script']} \\\n")
        _write_script_args(file, lines)
    else:
        file.write(f"{job['script']}\n")
