from pathlib import Path
import os
import json
import sys
import pytest
from unittest.mock import patch, MagicMock
from autoslurm import save_bundle, submit_jobs
from autoslurm.storage import slurm_dir, ensure_storage_dirs, set_storage_root
from glob import glob

from tests.integration.mocks import (
    expected_bundle_content,
    mock_job_name,
    mock_jobs,
    mock_machine_config1,
    mock_machine_config2,
    mock_machine_config3,
    mock_machine_config_local,
    mock_load_config,
    setup_mock_subprocess_run,
    slurm_emulator,
)


@pytest.fixture
def storage_env(monkeypatch, tmp_path):
    path = tmp_path / "storage"
    set_storage_root(path)
    ensure_storage_dirs()
    return path


@pytest.mark.parametrize(
    "mock_machine_config",
    [
        mock_machine_config_local,
        mock_machine_config1,
        mock_machine_config2,
        mock_machine_config3,
    ],
)
@patch("subprocess.run", new_callable=setup_mock_subprocess_run)
@patch("autoslurm.run_slurm.run_slurm_remotely")
def test_integration_schedule_jobs(
    mock_run_script_remotely, mock_ssh_client, mock_machine_config, mock_load_config, storage_env
):
    save_bundle(mock_jobs, mock_job_name)
    submit_jobs(mock_job_name, machine="local", machine_overrides=mock_machine_config)

    files_created = glob(os.path.join(slurm_dir(), "*.sh"))
    assert len(files_created) == 3, "Expected 3 SLURM scripts to be created"

    for file in files_created:
        with open(file, "r") as f:
            script_content = f.readlines()
        job_name = os.path.split(file)[-1].split("_")[-2].split(".")[0]
        expected_content_lines = expected_bundle_content[job_name]
        for i, (line, expected_line) in enumerate(
            zip(script_content, expected_content_lines)
        ):
            assert (
                line == expected_line
            ), f"Mismatch for job {job_name} script at line {i}"


mock_jobs_error = {
    "JobA": {
        "name": "JobA",
        "dependencies": [],
        "slurm": {
            "tasks": 1,
            "cpus_per_task": 1,
            "gres": "gpu:1",
            "mem": "4G",
            "time": "01:00:00",
        },
        "script_args": {"param1": "value1", "param2": "value2"},
    },
}


@pytest.mark.parametrize(
    "mock_machine_config",
    [
        mock_machine_config_local,
        mock_machine_config1,
        mock_machine_config2,
        mock_machine_config3,
    ],
)
@patch("subprocess.run", new_callable=setup_mock_subprocess_run)
@patch("autoslurm.run_slurm.run_slurm_remotely")
def test_integration_schedule_jobs_with_error(
    mock_run_script_remotely, mock_ssh_client, mock_machine_config, mock_load_config
):
    with pytest.raises(KeyError):
        save_bundle(mock_jobs_error, mock_job_name)
        submit_jobs(mock_job_name, machine="local", machine_overrides=mock_machine_config)


def test_unregistered_python_script_executes(tmp_path, mock_load_config, slurm_emulator):
    script_source = """#!/usr/bin/env python3
print(\"Hello from an unregistered script!\")
"""
    script_path = tmp_path / "unregistered_print.py"
    script_path.write_text(script_source)
    script_path.chmod(0o755)

    job_name = "unregistered_script"
    job = {
        "name": job_name,
        "script": str(script_path),
        "script_args": {},
        "dependencies": [],
        "pre_commands": [],
        "slurm": {"tasks": 1, "cpus_per_task": 1, "mem": "1G", "time": "00:01:00"},
    }

    save_bundle({job_name: job}, job_name)
    submit_jobs(job_name, machine="local", machine_overrides=mock_machine_config_local)

    assert slurm_emulator, "The SLURM emulator did not record any executed scripts."
    assert any(
        "Hello from an unregistered script!" in call["stdout"]
        for call in slurm_emulator
    )


def test_submit_jobs_from_bundle_file(
    tmp_path, mock_load_config, slurm_emulator, storage_env
):
    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "example_python_script.py"
    )
    bundle_path = tmp_path / "transfer_alpha_bundle.json"
    job_name = "bundle_file_job"
    bundle = {
        job_name: {
            "name": job_name,
            "script": f"{sys.executable} {script_path}",
            "script_args": {
                "dataset": "/tmp/galaxies",
                "epochs": "5",
                "learning_rate": "1e-3",
            },
            "dependencies": [],
            "pre_commands": [],
            "slurm": {
                "tasks": 1,
                "cpus_per_task": 1,
                "mem": "1G",
                "time": "00:01:00",
            },
        }
    }
    bundle_path.write_text(json.dumps(bundle))

    submit_jobs(
        "transfer-alpha",
        machine="local",
        machine_overrides=mock_machine_config_local,
        bundle_path=bundle_path,
    )

    assert slurm_emulator, "The SLURM emulator did not record any executed scripts."
    assert any("/tmp/galaxies" in call["stdout"] for call in slurm_emulator)
