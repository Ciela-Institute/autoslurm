import os
import re
import shlex
import subprocess
import tempfile
import shutil
from contextlib import contextmanager
from typing import Optional
from .utils import load_config, ssh_host_from_config, remote_storage_root_from_config
from .storage import ensure_storage_dirs, slurm_dir, storage_root

__all__ = [
    "get_job_id_from_sbatch_output",
    "run_slurm_remotely",
    "run_slurm_locally",
    "ssh_submission_session",
]


def get_job_id_from_sbatch_output(output):
    """Extracts the job ID from the output of an sbatch command."""
    match = re.search(r"Submitted batch job (\d+)", output)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Unable to capture job ID from sbatch output {output}")


def run_slurm_remotely(
    slurm_name,
    machine: Optional[str] = None,
    machine_config: Optional[dict] = None,
    ssh_options: Optional[list[str]] = None,
):
    """
    Runs a SLURM script on a remote machine via SSH and captures the job ID.

    Args:
        slurm_name (str): The name of the SLURM script to run.
        machine (Optional[str]): The name of the machine to run the script on.
        machine_config (Optional[dict]): The configuration details for the remote machine.

    Returns:
        str: The job ID assigned by SLURM.

    """
    if machine is not None:
        machine_config = load_config().get(machine)
        if not machine_config:
            raise EnvironmentError(f"No configuration found for machine: {machine}")

    hostname = ssh_host_from_config(machine_config, machine)
    remote_path = machine_config.get("path") or remote_storage_root_from_config(
        machine_config, machine
    )
    script_path = os.path.join(remote_path, "slurm", slurm_name)
    ssh_command = ["ssh"]
    if ssh_options:
        ssh_command.extend(ssh_options)
    ssh_command.extend([*shlex.split(hostname), f"sbatch {script_path}"])

    # Run the sbatch command on the remote machine
    result = subprocess.run(ssh_command, capture_output=True, text=True)

    # Check for errors
    if result.returncode != 0:
        raise ValueError(f"Error running sbatch command: {result.stderr}")

    output = result.stdout
    return get_job_id_from_sbatch_output(output)


@contextmanager
def ssh_submission_session(
    machine_config: Optional[dict],
    machine_name: Optional[str] = None,
):
    """
    Provide SSH options that reuse a single multiplexed connection for repeated submits.
    Falls back to no-op when no remote host is configured.
    """
    if machine_config is None:
        yield None
        return
    if not (machine_config.get("hostname") or machine_config.get("hosturl")):
        yield None
        return

    hostname = ssh_host_from_config(machine_config, machine_name)
    tmpdir = tempfile.mkdtemp(prefix="autoslurm-ssh-")
    control_path = os.path.join(tmpdir, "cm-%C")
    ssh_options = [
        "-o",
        "ControlMaster=auto",
        "-o",
        f"ControlPath={control_path}",
        "-o",
        "ControlPersist=600",
    ]

    try:
        open_command = ["ssh", *ssh_options, "-MNf", *shlex.split(hostname)]
        result = subprocess.run(open_command, capture_output=True, text=True)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"Unable to open SSH multiplexed session for '{machine_name or hostname}': {message}"
            )
        yield ssh_options
    finally:
        close_command = ["ssh", *ssh_options, "-O", "exit", *shlex.split(hostname)]
        subprocess.run(close_command, capture_output=True, text=True)
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_slurm_locally(slurm_name):
    """Runs a SLURM script locally and captures the job ID."""
    ensure_storage_dirs()
    script_path = os.path.join(slurm_dir(), slurm_name)

    result = subprocess.run(["sbatch", script_path], capture_output=True, text=True)
    return get_job_id_from_sbatch_output(result.stdout)
