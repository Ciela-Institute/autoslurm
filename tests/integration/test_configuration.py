import json
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
        assert cmd[-1].startswith(f"mkdir -p {storage_root()}/")
        return MagicMock(returncode=0, stderr="")

    return mock_subprocess_run


def test_autoslurm_configuration(tmp_path, monkeypatch):
    from autoslurm.storage import set_storage_root, ensure_storage_dirs
    storage_root = tmp_path / "storage"
    set_storage_root(storage_root)
    ensure_storage_dirs()

    with patch("builtins.input", return_value="6"), patch("subprocess.run") as mock_run:

        config_path = config_file_path()
        with open(config_path, "w") as f:
            json.dump(EXAMPLE_CONFIG, f)

        monkeypatch.setattr("sys.argv", ["autoslurm-configuration"])
        main(["--interactive"])

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


def test_autoslurm_configuration_summary(
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

    main(["--summary"])
    output = capsys.readouterr().out.strip().splitlines()

    assert "local local def-bengioy" in output
    assert "remote remote rrg-account_name" in output


def test_autoslurm_configuration_rename_machine(
    tmp_path,
    monkeypatch,
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

    answers = iter(["3", "2", "cluster", "6"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MagicMock(returncode=0, stderr=""))

    main(["--interactive"])

    updated = json.loads(config_path.read_text())
    assert "cluster" in updated["machines"]
    assert "remote" not in updated["machines"]
    assert updated["default_machine"] == "local"


def test_autoslurm_configuration_validate_remote_machine(
    tmp_path,
    monkeypatch,
):
    from autoslurm.storage import set_storage_root, ensure_storage_dirs

    storage = tmp_path / "storage"
    set_storage_root(storage)
    ensure_storage_dirs()

    config_path = config_file_path()
    config = {
        "machines": {
            "remote": {
                "env_command": "source /path/to/remote/venv/bin/activate",
                "slurm_account": "rrg-account_name",
                "hostname": "rorqual",
            }
        },
        "default_machine": "remote",
    }
    with open(config_path, "w") as file:
        json.dump(config, file)

    def mock_subprocess_run(cmd, *args, **kwargs):
        assert cmd[0] == "ssh"
        if cmd[-1] == "true":
            return MagicMock(returncode=0, stdout="", stderr="")
        if cmd[-1].startswith("bash -lc "):
            return MagicMock(returncode=0, stdout="/path/to/autoslurm/__init__.py\n", stderr="")
        if cmd[-1].startswith(f"mkdir -p {storage_root()}/"):
            return MagicMock(returncode=0, stdout="", stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    answers = iter(["5", "1", "6"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    main(["--interactive"])


def test_autoslurm_configuration_interactive_creates_config(
    tmp_path,
    monkeypatch,
):
    from autoslurm.storage import set_storage_root

    storage = tmp_path / "storage"
    set_storage_root(storage)

    answers = iter(
        [
            "rorqual",
            "source /path/to/venv/bin/activate",
            "def-bengioy",
            "n",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MagicMock(returncode=0, stderr=""))

    main(["--interactive"])

    assert config_file_path().exists()


def test_autoslurm_configuration_short_interactive_flag(
    tmp_path,
    monkeypatch,
):
    from autoslurm.storage import set_storage_root

    storage = tmp_path / "storage"
    set_storage_root(storage)

    answers = iter(
        [
            "rorqual",
            "source /path/to/venv/bin/activate",
            "def-bengioy",
            "n",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MagicMock(returncode=0, stderr=""))

    main(["-i"])

    assert config_file_path().exists()
