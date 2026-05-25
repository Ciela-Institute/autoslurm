from typing import Optional
from argparse import Namespace
from .definitions import DATE_FORMAT, MACHINE_KEYS
from datetime import datetime
import os
import json
import shlex
import subprocess


__all__ = [
    "load_config",
    "machine_config",
    "remote_storage_root_from_config",
    "activation_command_from_config",
]


def activation_command_from_config(machine_config: dict) -> str:
    """Return environment activation command from structured machine config."""
    venv_path = machine_config.get("venv_path")
    if isinstance(venv_path, str) and venv_path.strip():
        return f"source {shlex.quote(venv_path)}/bin/activate"
    env_command = machine_config.get("env_command", "")
    if isinstance(env_command, str):
        return env_command.strip()
    return ""


def name_slurm_script(job: dict, date: datetime):
    name = job["name"]
    return f"{name}_{date.strftime(DATE_FORMAT)}.sh"


from .storage import jobs_dir, ensure_storage_dirs, config_file_path


def update_job_info_with_id(bundle_name, date, job_name, job_id):
    """Updates the job JSON file with the job ID"""
    ensure_storage_dirs()
    path = jobs_dir() / f"{bundle_name}_{date.strftime(DATE_FORMAT)}.json"
    with open(path, "r") as f:
        jobs = json.load(f)
    jobs[job_name]["id"] = job_id
    with open(path, "w") as f:
        json.dump(jobs, f, indent=4)


def update_job_metadata(bundle_name, date, job_name, metadata: dict):
    """Update arbitrary metadata fields for a job inside the bundle."""
    ensure_storage_dirs()
    path = jobs_dir() / f"{bundle_name}_{date.strftime(DATE_FORMAT)}.json"
    with open(path, "r") as f:
        jobs = json.load(f)
    job = jobs.get(job_name)
    if job is None:
        raise KeyError(f"Job '{job_name}' not found in bundle '{bundle_name}'.")
    job.update(metadata)
    with open(path, "w") as f:
        json.dump(jobs, f, indent=4)


def _normalize_config(raw: dict) -> dict:
    """
    Normalize the configuration to ensure the structure contains 'machines',
    'default_machine', and an alias 'local' that points to the default machine.
    """
    raw = dict(raw)
    machines = raw.get("machines")
    if machines is None:
        machines = {
            name: value
            for name, value in raw.items()
            if name != "default_machine"
        }
    if not isinstance(machines, dict):
        raise EnvironmentError("The 'machines' entry must be a dictionary.")
    default_machine = raw.get("default_machine")
    if default_machine is None:
        if "local" in machines:
            default_machine = "local"
        elif machines:
            default_machine = next(iter(machines))
        else:
            raise EnvironmentError("No machines defined in the configuration file.")
    if default_machine not in machines:
        raise EnvironmentError(
            f"Default machine '{default_machine}' not found in the configuration file."
        )
    normalized = {"machines": machines, "default_machine": default_machine}
    normalized["local"] = machines[default_machine]
    normalized.update(machines)
    return normalized


def load_config() -> dict:
    """
    Loads the configuration file.

    Returns:
    dict: The loaded configuration.

    Raises:
    EnvironmentError: If the configuration file is not found.
    """
    path = config_file_path()
    legacy_path = path.parent / "src" / path.name
    if not path.exists() and legacy_path.exists():
        path = legacy_path
    if not path.exists():
        raise EnvironmentError(
            f"Configuration file not found at {path}. Please use `autoslurm configuration` to create the configurations for autoslurm."
        )
    with open(path, "r") as file:
        raw = json.load(file)
    return _normalize_config(raw)


def machine_config(
    args: Optional[Namespace] = None,
    machine: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> tuple[str, dict]:
    config = load_config()
    machines = config["machines"]
    final_overrides = dict(overrides or {})
    machine_name = machine
    if args is not None:
        machine_name = machine_name or args.machine
        if args.hosturl is not None or args.hostname is not None:
            for key in ["slurm_account"]:
                if getattr(args, key, None) is None:
                    raise AttributeError(
                        f"Custom machine configuration with 'hosturl' requires {key}."
                    )
            for key in MACHINE_KEYS:
                value = getattr(args, key, None)
                if value is not None:
                    final_overrides[key] = value
        over_keys = ["env_command", "venv_path", "slurm_account"]
        for key in over_keys:
            value = getattr(args, key, None)
            if value is not None:
                final_overrides[key] = value
    if machine_name is None:
        machine_name = config["default_machine"]
    if machine_name not in machines:
        raise EnvironmentError(
            f"No configuration found for machine: {machine_name}"
        )
    machine_config_ = dict(machines.get(machine_name, {}))
    machine_config_.update(final_overrides)
    if machine_config_.get("slurm_account") is None:
        raise AttributeError(
            "'slurm_account' account must be provided. Rerun with --slurm_account option or rerun autoslurm-configuration to edit the configuration for the machine."
        )
    if not activation_command_from_config(machine_config_):
        raise AttributeError(
            "Either 'venv_path' or legacy 'env_command' must be provided. "
            "Rerun with --venv_path option or rerun autoslurm-configuration."
        )
    return machine_name, machine_config_


def ssh_host_from_config(
    machine_config: dict, machine_name: Optional[str] = None
) -> str:
    hostname = machine_config.get("hostname", None)
    machine = machine_name if machine_name is not None else ""
    if hostname is None:
        if machine_config.get("username", None) is None:
            raise AttributeError(
                f"'username' must be provided when 'hostname' is not specified. "
                f"Rerun with --username option or rerun autoslurm-configuration to edit the configuration for the machine {machine}."
            )
        elif machine_config.get("hosturl", None) is None:
            raise AttributeError(
                "'hosturl' must be provided if 'hostname' is not specified. "
                "Rerun with --hosturl option or rerun autoslurm-configuration to edit the configuration for the machine {machine}."
            )
        hostname = f"{machine_config['username']}@{machine_config['hosturl']}"
        if machine_config.get("key_path", None) is not None:
            # Add the key path to the ssh command
            hostname = f"-i {machine_config['key_path']} {hostname}"
    return hostname


def scp_host_and_keypath_from_config(
    machine_config: dict, machine_name: Optional[str] = None
) -> str:
    hostname = machine_config.get("hostname", None)
    machine = machine_name if machine_name is not None else ""
    if hostname is None:
        if machine_config.get("username", None) is None:
            raise AttributeError(
                f"'username' must be provided when 'hostname' is not specified. "
                f"Rerun with --username option or rerun autoslurm-configuration to edit the configuration for the machine {machine}."
            )
        elif machine_config.get("hosturl", None) is None:
            raise AttributeError(
                "'hosturl' must be provided if 'hostname' is not specified. "
                "Rerun with --hosturl option or rerun autoslurm-configuration to edit the configuration for the machine {machine}."
            )
        hostname = f"{machine_config['username']}@{machine_config['hosturl']}"
        if machine_config.get("key_path", None) is not None:
            # # Add the key path to the ssh command
            key_path = f"-i {machine_config['key_path']}"
        else:
            key_path = ""
    else:
        key_path = ""
    return hostname, key_path


def remote_storage_root_from_config(
    machine_config: dict, machine_name: Optional[str] = None
) -> str:
    hostname = ssh_host_from_config(machine_config, machine_name)
    env_command = activation_command_from_config(machine_config)
    python_probe = "from autoslurm.storage import storage_root; print(storage_root())"
    command_parts = []
    if env_command:
        command_parts.append(env_command)
    command_parts.append(f"python -c {shlex.quote(python_probe)}")
    remote_command = " && ".join(command_parts)
    result = subprocess.run(
        ["ssh", *shlex.split(hostname), f"bash -lc {shlex.quote(remote_command)}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Unable to determine remote storage root for machine '{machine_name or ''}': {message}"
        )
    remote_root = result.stdout.strip()
    if not remote_root:
        raise RuntimeError(
            f"Unable to determine remote storage root for machine '{machine_name or ''}': empty response"
        )
    return remote_root
