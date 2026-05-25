import pytest
from io import StringIO
from autoslurm.job_to_slurm import write_slurm_content
from unittest.mock import patch
import os


@pytest.fixture
def mock_load_config(tmp_path):
    mock_config = {"local": {"path": tmp_path}}
    os.makedirs(tmp_path / "jobs", exist_ok=True)
    with patch("autoslurm.load_config", return_value=mock_config) as mock_load_config:
        yield mock_load_config


def test_write_slurm_content(mock_load_config):
    job = {
        "name": "test_job",
        "slurm": {"time": "01:00:00", "partition": "test-partition", "array": "1-10%6"},
        "script_args": {"arg1": "value1", "arg2": [1, 2, 3]},
        "script": "test-application",
    }
    file = StringIO()

    user_settings = mock_load_config.return_value
    machine_config = user_settings["local"]
    write_slurm_content(file, job, machine_config)

    content = file.getvalue()
    assert "#SBATCH --time=01:00:00" in content
    assert "#SBATCH --partition=test-partition" in content
    assert "#SBATCH --array=1-10%6" in content
    assert "test-application" in content
    assert "--arg1=value1" in content
    assert "--arg2 1 2 3" in content


@pytest.mark.parametrize(
    "conditional_flag, expected_line",
    [
        (True, "  --conditional"),  # Test for boolean True
        (False, ""),  # Test for boolean False, should result in no line
    ],
)
def test_write_slurm_boolean_flag(conditional_flag, expected_line, mock_load_config):
    job = {
        "name": "boolean_flag_test",
        "slurm": {},
        "script_args": {"conditional": conditional_flag},
        "script": "test-boolean-application",
    }
    file = StringIO()

    user_settings = mock_load_config.return_value
    machine_config = user_settings["local"]
    write_slurm_content(file, job, machine_config)

    content = file.getvalue()
    print(content)
    assert (
        expected_line in content
    ), f"Conditional flag handling failed for {conditional_flag}"


def test_write_slurm_with_none_value(mock_load_config):
    job = {
        "name": "none_value_test",
        "slurm": {},
        "script_args": {"arg_with_none": None},  # Test handling None value
        "script": "test-none-application",
    }
    file = StringIO()

    user_settings = mock_load_config.return_value
    machine_config = user_settings["local"]
    write_slurm_content(file, job, machine_config)

    content = file.getvalue()
    print(content)
    assert (
        "--arg_with_none=None" not in content
    ), "None value should not be included in the script"


def test_write_slurm_writes_activation_and_main_command(mock_load_config):
    job = {
        "name": "activation_test",
        "slurm": {},
        "script_args": {},
        "script": "test-activation-application",
    }
    file = StringIO()

    user_settings = mock_load_config.return_value
    machine_config = user_settings["local"]
    machine_config["venv_path"] = "/tmp/venv"
    write_slurm_content(file, job, machine_config)

    content = file.getvalue()
    assert "source /tmp/venv/bin/activate" in content
    assert "test-activation-application" in content


def test_write_slurm_output_dir_customization(mock_load_config):
    job = {
        "name": "output_dir_test",
        "slurm": {"output": "custom-output-%j.txt"},
        "script_args": {},
        "script": "test-output-dir-application",
    }
    file = StringIO()

    user_settings = mock_load_config.return_value
    machine_config = user_settings["local"]
    write_slurm_content(file, job, machine_config)

    content = file.getvalue()
    assert (
        "#SBATCH --output=custom-output-%j.txt" in content
    ), "Custom output directory setting failed"


def test_write_slurm_uses_remote_storage_root_when_path_missing(monkeypatch):
    from unittest.mock import MagicMock

    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if cmd[0] == "ssh":
            return MagicMock(returncode=0, stdout="/remote/autoslurm\n", stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("subprocess.run", fake_run)

    job = {
        "name": "default_output_dir_test",
        "slurm": {},
        "script_args": {},
        "script": "test-default-output-dir-application",
    }
    file = StringIO()
    machine_config = {
        "hostname": "testhost",
        "username": "testuser",
        "env_command": "source activate test-env",
        "slurm_account": "test-account",
    }

    write_slurm_content(file, job, machine_config)

    content = file.getvalue()
    assert "#SBATCH --output=/remote/autoslurm/out/%x-%j.out" in content
    assert any(cmd[0] == "ssh" for cmd in calls)


def test_write_slurm_resolves_relative_output_dir_with_results_root():
    job = {
        "name": "relative_output_dir_job",
        "slurm": {},
        "script_args": {"output_dir": "substructure_lens/results/run_001"},
        "script": "test-app",
    }
    file = StringIO()
    machine_config = {
        "path": "/remote/autoslurm",
        "env_command": "source activate test-env",
        "slurm_account": "test-account",
        "results_root": "/lustre10/scratch/aadam",
    }

    write_slurm_content(file, job, machine_config)
    content = file.getvalue()
    assert (
        "--output-dir=/lustre10/scratch/aadam/substructure_lens/results/run_001"
        in content
    )


def test_write_slurm_resolves_relative_output_dir_with_default_results_root():
    job = {
        "name": "relative_output_dir_default_root_job",
        "slurm": {},
        "script_args": {"output_dir": "substructure_lens/results/run_002"},
        "script": "test-app",
    }
    file = StringIO()
    machine_config = {
        "path": "/remote/autoslurm",
        "env_command": "source activate test-env",
        "slurm_account": "test-account",
    }

    write_slurm_content(file, job, machine_config)
    content = file.getvalue()
    assert (
        "--output-dir=/remote/autoslurm/results/substructure_lens/results/run_002"
        in content
    )


def test_write_slurm_keeps_absolute_output_dir_unchanged():
    job = {
        "name": "absolute_output_dir_job",
        "slurm": {},
        "script_args": {"output_dir": "/lustre10/scratch/aadam/substructure_lens/results/run_003"},
        "script": "test-app",
    }
    file = StringIO()
    machine_config = {
        "path": "/remote/autoslurm",
        "env_command": "source activate test-env",
        "slurm_account": "test-account",
        "results_root": "/should/not/be/used",
    }

    write_slurm_content(file, job, machine_config)
    content = file.getvalue()
    assert (
        "--output-dir=/lustre10/scratch/aadam/substructure_lens/results/run_003"
        in content
    )
