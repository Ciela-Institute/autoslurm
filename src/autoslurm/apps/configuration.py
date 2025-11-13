import os
import subprocess
import json
import socket
from ..definitions import CONFIG_FILE_PATH
from ..utils import ssh_host_from_config


def expand_path(path):
    """Expand environment variables, the tilde, and the current directory in a file path."""
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def setup_directories(base_path, directories, hostname=None):
    """Create required directories at the specified base path"""
    for directory in directories:
        path = os.path.join(base_path, directory)
        if hostname is not None:
            ssh_command = ["ssh", hostname, f"mkdir -p {path}"]
            result = subprocess.run(ssh_command, capture_output=True, text=True)
            # Check for errors
            if result.returncode != 0:
                print(f"Error creating {path} directory on remote machine.")
                print(f"Error message: {result.stderr}")
            else:
                print(f"Created or found existing remote directory: {path}")
        else:
            if not os.path.exists(path):
                os.makedirs(path)
                print(f"Created directory: {path}")
            else:
                print(f"Directory already exists: {path}")


def update_bashrc(base_path, hostname=None):
    """Append AUTOSLURM environment variable to .bashrc for persistence, locally or remotely."""
    bash_command = f'echo "export AUTOSLURM=\\"{base_path}\\"" >> ~/.bashrc'
    if hostname is not None:
        ssh_command = ["ssh", hostname, bash_command]
        subprocess.run(ssh_command)
    else:
        os.system(bash_command)


def check_host(hostname):
    """Check if the SSH hostname is resolvable."""
    try:
        socket.gethostbyname(hostname)
    except socket.gaierror:
        return False
    return True


def get_git_editor():
    """Get the default editor set in Git's configuration."""
    try:
        return subprocess.check_output(
            ["git", "config", "--global", "core.editor"], encoding="utf-8"
        ).strip()
    except subprocess.CalledProcessError:
        # Fallback to a default editor if Git's editor is not set
        return "nano"


def open_editor(file_path):
    """Open the file in Git's default text editor or a fallback editor."""
    editor = get_git_editor()
    subprocess.call([editor, file_path])


def main():
    if os.path.exists(CONFIG_FILE_PATH):
        open_editor(CONFIG_FILE_PATH)
    else:
        example_config = {
            "local": {
                "path": "/path/to/local/autoslurm",
                "env_command": "source /path/to/local/venv/bin/activate",
                "slurm_account": "def-bengioy",
            },
            "remote_machine": {
                "path": "/path/to/remote/autoslurm",
                "env_command": "source /path/to/remote/venv/bin/activate",
                "slurm_account": "rrg-account_name",
                "hostname": "machine",
                "hosturl": "machine.domain.com",
                "username": "user1",
                "key_path": "~/.ssh/id_rsa",
            },
        }
        with open(CONFIG_FILE_PATH, "w") as file:
            json.dump(example_config, file, indent=4)
        open_editor(CONFIG_FILE_PATH)

    with open(CONFIG_FILE_PATH, "r") as file:
        config = json.load(file)

    # Check if local entry is present and has a valid path
    if "local" not in config:
        raise ValueError(
            "Invalid configuration. Please make sure the 'local' machine is present in the configuration file."
        )
    if "path" not in config["local"]:
        raise ValueError(
            "Invalid configuration. Please make sure the 'local' has a path specified."
        )

    # Handle machines setup
    for machine_name, machine_config in config.items():
        print(f"Setting up {machine_name} machine...")

        if machine_name == "local":
            setup_directories(
                machine_config["path"], ["data", "models", "slurm", "jobs", "results"]
            )
            update_bashrc(machine_config["path"])

        else:
            # Check if config has a 'path' key
            if "path" not in machine_config:
                print(
                    f"Error: No 'path' key found in the configuration for {machine_name}. Skipping..."
                )
                continue
            # Check if machine is a remote machine
            if any(
                key in machine_config for key in ["hostname", "username", "hosturl"]
            ):
                # Check if hostname is resolvable
                hostname = ssh_host_from_config(machine_config, machine_name)
                if not check_host(hostname):
                    print(
                        f"Error: Unable to resolve hostname '{machine_config['hostname']}' for {machine_name}."
                    )
                    continue
                else:
                    # Machine is resolvable, proceed with setting up directories
                    setup_directories(
                        machine_config["path"],
                        ["data", "models", "slurm", "jobs", "results"],
                        hostname=hostname,
                    )
                    update_bashrc(machine_config["path"], hostname=hostname)
            else:  # Local machine
                if machine_config["path"] != config["local"]["path"]:
                    print(
                        f"Machine {machine_name} path '{machine_config['path']}' does not match the local machine path '{config['local']['path']}'. "
                        f"Only one path is supported per machine. Skipping..."
                    )
                continue

    print("AutoSlurm setup is complete.")
