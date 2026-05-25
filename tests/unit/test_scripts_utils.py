import pytest
from argparse import Namespace
from unittest.mock import patch
from autoslurm.utils import machine_config


@pytest.fixture
def args():
    return Namespace(
        machine=None,
        hostname=None,
        hosturl=None,
        username=None,
        key_path=None,
        path=None,
        venv_path=None,
        env_command=None,
        slurm_account=None,
    )


@pytest.fixture
def mock_load_config(tmp_path):
    mock_config = {
        "machines": {
            "local": {
                "path": tmp_path,
                "slurm_account": "def-bengioy",
                "env_command": "source /path/to/env/bin/activate",
            },
            "remote_machine": {
                "hostname": "remote_host",
                "path": "/path/to/dir",
                "env_command": "source activate env",
                "slurm_account": "def-bengioy",
            },
        },
        "default_machine": "local",
    }
    with patch(
        "autoslurm.utils.load_config", return_value=mock_config
    ) as mock_load_config:
        yield mock_load_config


def test_machine_config_custom_machine_complete(mock_load_config, args):
    """
    Test that the function returns the custom machine configuration when all keys are provided.
    """
    mock_config = {
        "machines": {
            "local": {
                "hostname": "localhost",
                "hosturl": "host.url.com",
                "username": "user",
                "key_path": "/path/to/key",
                "path": "/path/to/dir",
                "env_command": "source activate env",
                "slurm_account": "account",
            }
        },
        "default_machine": "local",
    }
    mock_load_config.return_value = mock_config
    machine_name, result = machine_config(args)
    assert result == mock_config["machines"]["local"]  # Check config unchanged


def test_machine_config_incomplete(mock_load_config, args):
    """
    Test that the function raises a ValueError when the custom machine configuration is incomplete.
    """
    mock_config = {"machines": {"local": {}}, "default_machine": "local"}
    mock_load_config.return_value = mock_config
    with pytest.raises(AttributeError):
        machine_config(args)


def test_machine_config_custom_remote_machine_missing_keys(args, mock_load_config):
    """
    Test that the function raises a ValueError when the custom remote machine configuration is missing keys.
    """
    args.hostname = "remote_host"
    args.path = "/path/to/dir"
    args.slurm_account = "account"

    # Backward-compatible behavior: falls back to existing configured activation settings.
    _, result = machine_config(args)
    assert result["hostname"] == "remote_host"
    assert result["slurm_account"] == "account"


def test_machine_config_custom_invalid_remote_machine(args, mock_load_config):
    args.machine = "some_invalid_machine"

    with pytest.raises(EnvironmentError):
        machine_config(args)


def test_machine_config_custom_remote_machine(args, mock_load_config):
    args.machine = "remote_machine"

    machine_name, result = machine_config(args)
    print(result)

    expected_result = {  # See the mock_load_config fixture
        "hostname": "remote_host",
        "path": "/path/to/dir",
        "env_command": "source activate env",
        "slurm_account": "def-bengioy",
    }

    for key, value in expected_result.items():
        assert result[key] == value
    assert machine_name == "remote_machine"


def test_machine_config_custom_local_parameters(args, mock_load_config):
    args.path = "/path/to/dir"
    args.env_command = "source activate env"
    args.slurm_account = "account"

    _, result = machine_config(args)

    expected_result = {
        "path": mock_load_config.return_value["machines"]["local"]["path"],
        "env_command": "source activate env",
        "slurm_account": "account",
    }

    assert result == expected_result


def test_machine_config_local_machine_default(args, mock_load_config):
    args.path = "/path/to/dir"
    args.env_command = "source activate env"

    _, result = machine_config(args)
    assert result["path"] == mock_load_config.return_value["machines"]["local"]["path"]
    assert result["env_command"] == args.env_command
    assert (
        result["slurm_account"] == "def-bengioy"
    )  # See fixture, check that local machine default is used


def test_missing_slurm_account(args, mock_load_config):
    mock_config = {
        "machines": {
            "local": {
                "path": "/path/to/dir",
                "env_command": "source activate env",
            }
        },
        "default_machine": "local",
    }
    mock_load_config.return_value = mock_config

    with pytest.raises(AttributeError, match="slurm_account"):
        machine_config(args)


def test_missing_path(args, mock_load_config):
    mock_config = {
        "machines": {
            "local": {
                "env_command": "source activate env",
                "slurm_account": "account",
            }
        },
        "default_machine": "local",
    }
    mock_load_config.return_value = mock_config

    # Path is no longer required
    _, result = machine_config(args)
    assert result["env_command"] == "source activate env"


def test_missing_env_command(args, mock_load_config):
    mock_config = {
        "machines": {
            "local": {
                "path": "/path/to/dir",
                "slurm_account": "account",
            }
        },
        "default_machine": "local",
    }
    mock_load_config.return_value = mock_config

    with pytest.raises(AttributeError, match="venv_path|env_command"):
        machine_config(args)
