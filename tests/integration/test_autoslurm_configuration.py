import os
import json
import pytest
from unittest.mock import patch, MagicMock
from autoslurm.apps.configuration import (
    main,
)

# Mock configuration for testing
EXAMPLE_CONFIG = {
    "local": {
        "path": "autoslurm",
        "env_command": "source /path/to/local/venv/bin/activate",
        "slurm_account": "def-bengioy",
    },
    "remote_machine_w_key": {
        "path": "autoslurm_w_key",
        "env_command": "source /path/to/remote/venv/bin/activate",
        "slurm_account": "rrg-account_name",
        "hosturl": "machine.domain.com",
        "username": "user1",
        "key_path": "~/.ssh/id1_rsa",
    },
    "remote_machine_wo_key": {
        "path": "autoslurm_wo_hostname",
        "env_command": "source /path/to/remote/venv/bin/activate",
        "slurm_account": "rrg-account_name",
        "hosturl": "machine.domain.com",
        "username": "user1",
    },
    "remote_machine_w_hostname": {
        "path": "autoslurm_w_hostname",
        "env_command": "source /path/to/remote/venv/bin/activate",
        "slurm_account": "rrg-account_name",
        "hostname": "machine",
    },
}


@pytest.fixture
def mock_os_makedirs(tmp_path):
    original_os_makedirs = os.makedirs

    def mock_makedirs(path, mode=0o777, exist_ok=False):
        if not path.startswith(str(tmp_path)):
            path = os.path.join(tmp_path, path)
        return original_os_makedirs(path, mode=mode, exist_ok=exist_ok)

    # Patch os.makedirs with the mock function
    with patch("os.makedirs", side_effect=mock_makedirs):
        yield


@pytest.fixture
def mock_os_system(tmp_path):
    """
    Fixture to mock os.system and avoid writing to actual .bashrc.
    """
    original_os_system = os.system

    def mocked_os_system(command):
        if "export AUTOSLURM=" in command:
            with open(os.path.join(tmp_path, ".bashrc"), "a") as f:
                f.write(command + "\n")
        else:
            return original_os_system(command)

    with patch("os.system", side_effect=mocked_os_system):
        yield


# Mock subprocess.run function and check that it is called correctly
def setup_mock_subprocess_run(tmp_path):
    def mock_subprocess_run(cmd, *args, **kwargs):
        # Check that command is in one of the expected one
        assert cmd[0] == "ssh"
        task = cmd[2].split(" ")[0]
        if task == "mkdir":
            assert cmd[1] in [
                "-i ~/.ssh/id1_rsa user1@machine.domain.com",
                "user1@machine.domain.com",
                "machine",
            ]
            dirname = cmd[2].split(" ")[-1]
            path = os.path.join(tmp_path, dirname)
            os.makedirs(path, exist_ok=True)
        elif task == "echo":
            assert cmd[2].startswith('echo "export AUTOSLURM=')
            if cmd[1] == "-i ~/.ssh/id1_rsa user1@machine.domain.com":
                path = EXAMPLE_CONFIG["remote_machine_w_key"]["path"]
            elif cmd[1] == "user1@machine.domain.com":
                path = EXAMPLE_CONFIG["remote_machine_wo_key"]["path"]
            elif cmd[1] == "machine":
                path = EXAMPLE_CONFIG["remote_machine_w_hostname"]["path"]
            bashrc_content = f"export AUTOSLURM={path}"
            with open(os.path.join(tmp_path, ".bashrc"), "a") as f:
                f.write(bashrc_content + "\n")
        return MagicMock(returncode=0, stderr="")

    return mock_subprocess_run


@pytest.mark.parametrize("hostname_resolvable", [True, False])
@patch("subprocess.run")
@patch("socket.gethostbyname")
@patch("socket.gaierror")
@patch("autoslurm.apps.configuration.open_editor")
def test_autoslurm_configuration(
    mock_open_editor,
    mock_gaierror,
    mock_gethostbyname,
    mock_subprocess_run,
    tmp_path,
    hostname_resolvable,
    mock_os_makedirs,
    mock_os_system,
):
    mock_gethostbyname.side_effect = lambda x: (
        "127.0.0.1" if hostname_resolvable else mock_gaierror
    )
    mock_subprocess_run.side_effect = setup_mock_subprocess_run(tmp_path)
    mock_open_editor.side_effect = (
        lambda file_path: None
    )  # Mock open_editor to do nothing

    # Write example config to a temporary file
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(EXAMPLE_CONFIG, f)

    # Run the main setup function
    with patch("autoslurm.apps.configuration.CONFIG_FILE_PATH", str(config_path)):
        main()

    calls = (
        mock_subprocess_run.call_args_list
    )  # or mock_subprocess_run.mock_calls for more details
    # Print out each call made to subprocess.run
    for call_args, call_kwargs in calls:
        print(f"Called with args: {call_args}")
        print(f"Called with kwargs: {call_kwargs}")
        print("-" * 20)

    print(os.listdir(tmp_path))
    if hostname_resolvable:
        for key in EXAMPLE_CONFIG.keys():
            path = EXAMPLE_CONFIG[key]["path"]
            assert os.path.exists(os.path.join(tmp_path, path))
            for d in ["jobs", "slurm"]:
                assert os.path.exists(os.path.join(tmp_path, path, d))
    else:
        path = EXAMPLE_CONFIG["local"]["path"]
        assert os.path.exists(os.path.join(tmp_path, path))
        for d in ["jobs", "slurm"]:
            assert os.path.exists(os.path.join(tmp_path, path, d))

    with open(tmp_path / ".bashrc", "r") as f:
        bashrc_content = f.read()
        print(bashrc_content)
        if hostname_resolvable:
            for key in EXAMPLE_CONFIG.keys():
                path = EXAMPLE_CONFIG[key]["path"]
                assert f"export AUTOSLURM={path}" in bashrc_content
        else:
            path = EXAMPLE_CONFIG["local"]["path"]
            assert f"export AUTOSLURM={path}" in bashrc_content
