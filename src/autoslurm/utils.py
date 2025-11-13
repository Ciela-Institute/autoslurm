from typing import Optional
from argparse import Namespace
from .definitions import CONFIG_FILE_PATH, DATE_FORMAT, MACHINE_KEYS
from datetime import datetime
import os
import json


__all__ = ["load_config", "machine_config"]


def name_slurm_script(job: dict, date: datetime):
    name = job["name"]
    return f"{name}_{date.strftime(DATE_FORMAT)}.sh"


def update_job_info_with_id(bundle_name, date, job_name, job_id):
    """Updates the job JSON file with the job ID"""
    path = os.path.join(
        load_config()["local"]["path"],
        "jobs",
        f"{bundle_name}_{date.strftime(DATE_FORMAT)}.json",
    )
    with open(path, "r") as f:
        jobs = json.load(f)
    jobs[job_name]["id"] = job_id
    with open(path, "w") as f:
        json.dump(jobs, f, indent=4)


def load_config() -> dict:
    """
    Loads the configuration file.

    Returns:
    dict: The loaded configuration.

    Raises:
    EnvironmentError: If the configuration file is not found.
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        raise EnvironmentError(
            f"Configuration file not found at {CONFIG_FILE_PATH}. Please use `autoslurm-configuration` to create the configurations for autoslurm."
        )
    with open(CONFIG_FILE_PATH, "r") as file:
        return json.load(file)


def machine_config(args: Namespace) -> dict:
    machine_config_ = {}
    if args.machine is not None:
        config = load_config()
        if not config.get(args.machine):
            raise EnvironmentError(
                f"No configuration found for machine: {args.machine}"
            )
        machine_config_.update(config.get(args.machine))
    else:
        if args.hosturl is not None or args.hostname is not None:
            for key in ["slurm_account", "path", "env_command"]:
                if getattr(args, key, None) is None:
                    raise AttributeError(
                        f"Custom machine configuration with 'hosturl' requires {key}."
                    )
            machine_config_.update(
                {
                    key: getattr(args, key, None)
                    for key in MACHINE_KEYS
                    if getattr(args, key, None) is not None
                }
            )
        else:
            machine_config_ = load_config()["local"]

    # Update the machine configuration with custom parameters for environment, path and slurm account
    for key in ["path", "env_command", "slurm_account"]:
        v = getattr(args, key, None)
        if v is not None:
            machine_config_[key] = v

    # Enforce required keys
    if machine_config_.get("slurm_account", None) is None:
        raise AttributeError(
            "'slurm_account' account must be provided. Rerun with --slurm_account option or rerun autoslurm-configuration to edit the configuration for the machine."
        )

    if machine_config_.get("path", None) is None:
        raise AttributeError(
            "'path' must be provided. Rerun with --path option or rerun autoslurm-configuration to edit the configuration for the machine."
        )

    if machine_config_.get("env_command", None) is None:
        raise AttributeError(
            "'env_command' must be provided. Rerun with --env_command option or rerun autoslurm-configuration to edit the configuration for the machine."
        )

    return machine_config_


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
