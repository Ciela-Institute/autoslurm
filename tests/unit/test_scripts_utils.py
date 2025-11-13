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
        env_command=None,
        slurm_account=None,
    )


@pytest.fixture
def mock_load_config(tmp_path):
    mock_config = {
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
        "local": {
            "hostname": "localhost",
            "hosturl": "host.url.com",
            "username": "user",
            "key_path": "/path/to/key",
            "path": "/path/to/dir",
            "env_command": "source activate env",
            "slurm_account": "account",
        }
    }
    mock_load_config.return_value = mock_config
    result = machine_config(args)
    assert result == mock_config["local"]  # Check that config has not changed


def test_machine_config_incomplete(mock_load_config, args):
    """
    Test that the function raises a ValueError when the custom machine configuration is incomplete.
    """
    mock_config = {"local": {}}
    mock_load_config.return_value = mock_config
    with pytest.raises(AttributeError):
        machine_config(args)


def test_machine_config_custom_remote_machine_missing_keys(args):
    """
    Test that the function raises a ValueError when the custom remote machine configuration is missing keys.
    """
    args.hostname = "remote_host"
    args.path = "/path/to/dir"
    args.slurm_account = "account"

    with pytest.raises(
        AttributeError, match="env_command"
    ):  # Check that the error message contains specific info about missing key
        machine_config(args)


def test_machine_config_custom_invalid_remote_machine(args, mock_load_config):
    args.machine = "some_invalid_machine"

    with pytest.raises(EnvironmentError):
        machine_config(args)


def test_machine_config_custom_remote_machine(args, mock_load_config):
    args.machine = "remote_machine"

    result = machine_config(args)
    print(result)

    expected_result = {  # See the mock_load_config fixture
        "hostname": "remote_host",
        "path": "/path/to/dir",
        "env_command": "source activate env",
        "slurm_account": "def-bengioy",
    }

    for key, value in expected_result.items():
        assert result[key] == value


def test_machine_config_custom_local_parameters(args, mock_load_config):
    args.path = "/path/to/dir"
    args.env_command = "source activate env"
    args.slurm_account = "account"

    result = machine_config(args)

    expected_result = {
        "path": "/path/to/dir",
        "env_command": "source activate env",
        "slurm_account": "account",
    }

    assert result == expected_result


def test_machine_config_local_machine_default(args, mock_load_config):
    args.path = "/path/to/dir"
    args.env_command = "source activate env"

    result = machine_config(args)
    assert result["path"] == args.path
    assert result["env_command"] == args.env_command
    assert (
        result["slurm_account"] == "def-bengioy"
    )  # See fixture, check that local machine default is used


def test_missing_slurm_account(args, mock_load_config):
    mock_config = {
        "local": {
            "path": "/path/to/dir",
            "env_command": "source activate env",
            # "slurm_account": "account",
        }
    }
    mock_load_config.return_value = mock_config

    with pytest.raises(AttributeError, match="slurm_account"):
        machine_config(args)


def test_missing_path(args, mock_load_config):
    mock_config = {
        "local": {
            # "path": "/path/to/dir",
            "env_command": "source activate env",
            "slurm_account": "account",
        }
    }
    mock_load_config.return_value = mock_config

    with pytest.raises(AttributeError, match="path"):
        machine_config(args)


def test_missing_env_command(args, mock_load_config):
    mock_config = {
        "local": {
            "path": "/path/to/dir",
            # "env_command": "source activate env",
            "slurm_account": "account",
        }
    }
    mock_load_config.return_value = mock_config

    with pytest.raises(AttributeError, match="env_command"):
        machine_config(args)
