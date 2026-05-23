import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from ..utils import load_config, ssh_host_from_config
from ..storage import ensure_storage_dirs, storage_root, config_file_path



def _ensure_config_dir():
    config_file_path().parent.mkdir(parents=True, exist_ok=True)


def _save_config(config: Dict[str, Dict]):
    _ensure_config_dir()
    data = {
        "machines": config["machines"],
        "default_machine": config["default_machine"],
    }
    with open(config_file_path(), "w") as file:
        json.dump(data, file, indent=4)


def _refresh_config_aliases(config: Dict[str, Dict]):
    default = config["default_machine"]
    config["local"] = config["machines"][default]
    for name, machine in config["machines"].items():
        config[name] = machine


def check_host(hostname):
    try:
        socket.gethostbyname(hostname)
    except socket.gaierror:
        return False
    return True


def _is_remote(machine: Dict) -> bool:
    return any(key in machine for key in ("hostname", "hosturl", "username"))


def _local_machine_actions():
    ensure_storage_dirs()


def _remote_machine_actions(machine: Dict, name: str):
    try:
        hostname = ssh_host_from_config(machine, name)
    except AttributeError as exc:
        print(f"Skipping {name}: {exc}")
        return
    if not check_host(hostname):
        print(f"Unable to resolve hostname for {name}. Skipping setup.")
        return
    remote_root = machine.get("path") or str(storage_root())
    for directory in ("jobs", "slurm", "out"):
        remote_dir = os.path.join(remote_root, directory)
        ssh_command = ["ssh", hostname, f"mkdir -p {remote_dir}"]
        result = subprocess.run(ssh_command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error creating {remote_dir} on remote machine {name}.")
            print(f"Error message: {result.stderr}")
        else:
            print(f"Remote directory ensured: {remote_dir}")


def _setup_all_machines(config: Dict):
    for name, machine in config["machines"].items():
        print(f"\nConfiguring machine '{name}':")
        if _is_remote(machine):
            _remote_machine_actions(machine, name)
        else:
            _local_machine_actions()

def _prompt_text(prompt: str, default: Optional[str] = None, required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        if required:
            print("This field is required.")
            continue
        return ""


def _prompt_yes_no(prompt: str, default: str = "n") -> bool:
    default = default.lower()
    choices = "Y/n" if default == "y" else "y/N"
    while True:
        value = input(f"{prompt} [{choices}]: ").strip().lower()
        if not value:
            value = default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'.")


def _prompt_machine_name(config: Dict, default: str = "machine") -> str:
    existing = set(config["machines"].keys())
    suggested = default
    counter = 1
    while suggested in existing:
        suggested = f"{default}_{counter}"
        counter += 1
    while True:
        name = _prompt_text("Machine name", default=suggested, required=True)
        if name in existing:
            print(f"A machine named '{name}' already exists. Choose another name.")
            continue
        return name


def _prompt_machine_details(existing: Optional[Dict] = None) -> Dict:
    existing = existing or {}
    env_command = _prompt_text(
        "Command to activate the environment (e.g., source /path/to/venv/bin/activate)",
        existing.get("env_command"),
        required=True,
    )
    slurm_account = _prompt_text(
        "SLURM account name",
        existing.get("slurm_account"),
        required=True,
    )
    remote_default = bool(existing.get("hostname") or existing.get("hosturl"))
    is_remote = _prompt_yes_no("Is this a remote machine?", default="y" if remote_default else "n")
    machine = {"env_command": env_command, "slurm_account": slurm_account}
    if is_remote:
        print("Choose how to describe the remote machine:")
        print("  1) Use an SSH config alias (hostname only)")
        print("  2) Provide host URL + username")
        while True:
            connection_type = input("Connection type [1/2]: ").strip()
            if not connection_type:
                connection_type = "1"
            if connection_type in {"1", "2"}:
                break
            print("Please enter 1 or 2.")
        key_path = _prompt_text("SSH key path (optional)", existing.get("key_path"))
        if connection_type == "1":
            hostname = _prompt_text(
                "SSH hostname alias", existing.get("hostname"), required=True
            )
            machine["hostname"] = hostname
        else:
            hosturl = _prompt_text(
                "SSH host URL", existing.get("hosturl"), required=True
            )
            username = _prompt_text(
                "SSH username", existing.get("username"), required=True
            )
            machine["hosturl"] = hosturl
            machine["username"] = username
        if key_path:
            machine["key_path"] = key_path
    else:
        machine.pop("hostname", None)
        machine.pop("hosturl", None)
        machine.pop("username", None)
        machine.pop("key_path", None)
    return machine


def _select_machine(config: Dict, prompt: str) -> Optional[str]:
    machines = list(config["machines"].keys())
    if not machines:
        print("No machines are configured yet.")
        return None
    print(prompt)
    for idx, name in enumerate(machines, start=1):
        default_marker = " (default)" if name == config["default_machine"] else ""
        print(f"  {idx}) {name}{default_marker}")
    while True:
        selection = input("Select a number: ").strip()
        if not selection:
            return machines[0]
        if not selection.isdigit():
            print("Please enter a valid number.")
            continue
        idx = int(selection) - 1
        if 0 <= idx < len(machines):
            return machines[idx]
        print("Selection out of range.")


def _create_machine(config: Dict):
    name = _prompt_machine_name(config)
    machine = _prompt_machine_details()
    config["machines"][name] = machine
    _refresh_config_aliases(config)
    _save_config(config)
    if _prompt_yes_no("Make this the default machine?", default="n"):
        config["default_machine"] = name
        _refresh_config_aliases(config)
        _save_config(config)


def _update_machine(config: Dict):
    name = _select_machine(config, "Choose a machine to update:")
    if not name:
        return
    machine = _prompt_machine_details(existing=config["machines"][name])
    config["machines"][name] = machine
    _refresh_config_aliases(config)
    _save_config(config)


def _change_default_machine(config: Dict):
    name = _select_machine(config, "Choose a machine to become the default:")
    if not name:
        return
    if name == config["default_machine"]:
        print(f"'{name}' is already the default machine.")
        return
    config["default_machine"] = name
    _refresh_config_aliases(config)
    _save_config(config)


def _set_default_machine_by_name(config: Dict, name: str):
    if name not in config["machines"]:
        raise SystemExit(f"Machine '{name}' not found in configuration.")
    if name == config["default_machine"]:
        print(f"'{name}' is already the default machine.")
        return
    config["default_machine"] = name
    _refresh_config_aliases(config)
    _save_config(config)


def _create_default_machine():
    print("No configuration file detected. Let's configure the default machine.")
    config = {"machines": {}, "default_machine": "local"}
    machine = _prompt_machine_details()
    config["machines"]["local"] = machine
    _refresh_config_aliases(config)
    _save_config(config)
    print("Default machine configured.")
    _setup_all_machines(config)
    return config


def _menu_loop(config: Dict):
    while True:
        print("\nConfigured machines:")
        for name in config["machines"]:
            default_marker = " (default)" if name == config["default_machine"] else ""
            print(f"  - {name}{default_marker}")
        print("\nSelect an option:")
        print("  1) Update an existing machine")
        print("  2) Add a new machine")
        print("  3) Change the default machine")
        print("  4) Exit")
        choice = input("Choice: ").strip()
        if choice == "1":
            _update_machine(config)
        elif choice == "2":
            _create_machine(config)
        elif choice == "3":
            _change_default_machine(config)
        elif choice == "4":
            print("Configuration complete.")
            break
        else:
            print("Please choose a valid option (1-4).")


def display_config():
    path = config_file_path()
    if not os.path.exists(path):
        print("No configuration found.")
        return
    with open(path, "r") as file:
        data = json.load(file)
    print(json.dumps(data, indent=4))


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Configure AutoSlurm machines and view the stored config.")
    parser.add_argument("--view", action="store_true", help="Print the current configuration file and exit.")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open the interactive machine configuration flow.",
    )
    parser.add_argument(
        "--set-default",
        help="Set the default machine by name and exit.",
    )
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return
    args = parser.parse_args(argv)

    if args.view:
        display_config()
        return

    if args.interactive:
        if not os.path.exists(config_file_path()):
            _create_default_machine()
            return
        try:
            config = load_config()
        except EnvironmentError:
            print("Found an invalid configuration file. Creating a fresh default configuration.")
            _create_default_machine()
            return
        _menu_loop(config)
        _setup_all_machines(config)
        return

    if args.set_default:
        if not os.path.exists(config_file_path()):
            raise EnvironmentError(
                f"Configuration file not found at {config_file_path()}."
            )
        config = load_config()
        _set_default_machine_by_name(config, args.set_default)
        return

    if not os.path.exists(config_file_path()):
        _create_default_machine()
        return
    try:
        config = load_config()
    except EnvironmentError:
        print("Found an invalid configuration file. Creating a fresh default configuration.")
        _create_default_machine()
        return
    _menu_loop(config)
    _setup_all_machines(config)
