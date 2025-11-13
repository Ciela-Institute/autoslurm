import os
from io import TextIOWrapper
from datetime import datetime
from .utils import name_slurm_script, load_config


__all__ = ["create_slurm_script"]


def create_slurm_script(job: dict, date: datetime, machine_config: dict) -> str:
    """Creates a SLURM script and saves it locally"""
    user_settings = load_config()
    path = os.path.join(user_settings["local"]["path"], "slurm")
    slurm_name = name_slurm_script(job, date)
    file_path = os.path.join(path, slurm_name)
    with open(file_path, "w") as f:
        write_slurm_content(f, job, machine_config)
    print(f"Saved SLURM script for job {job['name']} saved to {file_path}")
    return slurm_name


def write_slurm_content(file: TextIOWrapper, job: dict, machine_config: dict) -> None:
    """
    Writes the content of the SLURM script with formatted arguments, handling list arguments differently based on their type.
    """
    env_command = machine_config.get("env_command", "")
    slurm_account = machine_config.get("slurm_account", "")

    file.write("#!/bin/bash\n")
    if slurm_account:
        file.write(f"#SBATCH --account={slurm_account}\n")
    output_dir = os.path.join(machine_config["path"], "slurm")
    file.write(f"#SBATCH --output={os.path.join(output_dir, '%x-%j.out')}\n")
    file.write(f"#SBATCH --job-name={job['name']}\n")

    # SLURM directives
    for key, value in job["slurm"].items():
        if value is not None:
            file.write(f"#SBATCH --{key.replace('_', '-')}={value}\n")

    # Make sure path is exported to environment
    file.write(f"export AUTOSLURM=\"{machine_config['path']}\"\n")

    # Environment activation command
    if env_command:
        file.write(f"{env_command}\n")

    # Pre-commands
    for cmd in job.get("pre_commands", []):
        file.write(f"{cmd}\n")

    # Main command and arguments
    file.write(f"{job['script']} \\\n")
    job_args = job.get("script_args", {})

    for i, (k, v) in enumerate(job_args.items()):
        if v is None:
            continue
        if isinstance(v, bool):
            if v:  # If True, include the flag without '=True'
                arg_line = f"  --{k}"
            else:
                continue
        elif isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
            arg_line = f"  --{k} {' '.join(map(str, v))}"
        elif isinstance(v, list):
            arg_line = f"  --{k}"
            for item in v:
                arg_line += f" \\\n    {item}"
        else:
            arg_line = f"  --{k}={v}"

        if i < len(job_args) - 1:
            arg_line += " \\\n"
        else:
            arg_line += "\n"
        file.write(arg_line)
