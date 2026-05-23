import json
import socket
import pytest
from unittest.mock import patch, MagicMock
from autoslurm.apps.configuration import main
from autoslurm.storage import jobs_dir, slurm_dir, storage_root, config_file_path

EXAMPLE_CONFIG = {
    "local": {
        "env_command": "source /path/to/local/venv/bin/activate",
        "slurm_account": "def-bengioy",
    },
    "remote_machine_w_key": {
        "env_command": "source /path/to/remote/venv/bin/activate",
        "slurm_account": "rrg-account_name",
        "hosturl": "machine.domain.com",
        "username": "user1",
        "key_path": "~/.ssh/id1_rsa",
    },
    "remote_machine_wo_key": {
        "env_command": "source /path/to/remote/venv/bin/activate",
        "slurm_account": "rrg-account_name",
        "hosturl": "machine.domain.com",
        "username": "user1",
    },
    "remote_machine_w_hostname": {
        "env_command": "source /path/to/remote/venv/bin/activate",
        "slurm_account": "rrg-account_name",
        "hostname": "machine",
    },
}


def setup_mock_subprocess_run():
    def mock_subprocess_run(cmd, *args, **kwargs):
        assert cmd[0] == "ssh"
        assert cmd[2].startswith(f"mkdir -p {storage_root()}/")
        return MagicMock(returncode=0, stderr="")

    return mock_subprocess_run


@pytest.mark.parametrize("hostname_resolvable", [True, False])
def test_autoslurm_configuration(
    hostname_resolvable,
    tmp_path,
    monkeypatch,
):
    from autoslurm.storage import set_storage_root, ensure_storage_dirs
    storage_root = tmp_path / "storage"
    set_storage_root(storage_root)
    ensure_storage_dirs()

    with patch("builtins.input", return_value="4"), patch(
        "socket.gethostbyname"
    ) as mock_gethostbyname, patch("subprocess.run") as mock_run:
        if hostname_resolvable:
            mock_gethostbyname.return_value = "127.0.0.1"
        else:
            mock_gethostbyname.side_effect = socket.gaierror
        mock_run.side_effect = setup_mock_subprocess_run()

        config_path = config_file_path()
        with open(config_path, "w") as f:
            json.dump(EXAMPLE_CONFIG, f)

        monkeypatch.setattr("sys.argv", ["autoslurm-configuration"])
        main()

    assert jobs_dir().exists(), "Jobs directory should be created under storage root."
    assert slurm_dir().exists(), "SLURM directory should be created under storage root."
    assert mock_run.call_count == 0


def test_autoslurm_configuration_set_default_machine(
    tmp_path,
    monkeypatch,
    capsys,
):
    from autoslurm.storage import set_storage_root, ensure_storage_dirs

    storage = tmp_path / "storage"
    set_storage_root(storage)
    ensure_storage_dirs()

    config_path = config_file_path()
    config = {
        "machines": {
            "local": {
                "env_command": "source /path/to/local/venv/bin/activate",
                "slurm_account": "def-bengioy",
            },
            "remote": {
                "env_command": "source /path/to/remote/venv/bin/activate",
                "slurm_account": "rrg-account_name",
                "hostname": "machine",
            },
        },
        "default_machine": "local",
    }
    with open(config_path, "w") as file:
        json.dump(config, file)

    monkeypatch.setattr("sys.argv", ["autoslurm-configuration"])
    main(["--set-default", "remote"])
    capsys.readouterr()

    updated = json.loads(config_path.read_text())
    assert updated["default_machine"] == "remote"


def test_autoslurm_configuration_interactive_creates_config(
    tmp_path,
    monkeypatch,
):
    from autoslurm.storage import set_storage_root

    storage = tmp_path / "storage"
    set_storage_root(storage)

    answers = iter(
        [
            "source /path/to/venv/bin/activate",
            "def-bengioy",
            "n",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MagicMock(returncode=0, stderr=""))

    main(["--interactive"])

    assert config_file_path().exists()
