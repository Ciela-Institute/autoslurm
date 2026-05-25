import os
import subprocess
from typing import Callable

import pytest
from unittest.mock import MagicMock

mock_job_name = "Test_Job"
mock_jobs = {
    "JobA": {
        "name": "JobA",
        "script": "run-job-a",
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
    "JobB": {
        "name": "JobB",
        "script": "run-job-b",
        "dependencies": ["JobA"],
        "slurm": {"tasks": 1, "cpus_per_task": 2, "mem": "8G", "time": "02:00:00"},
        "script_args": {"param1": "value3", "param2": "value4"},
    },
    "JobC": {
        "name": "JobC",
        "script": "run-job-c",
        "dependencies": ["JobA", "JobB"],
        "slurm": {"tasks": 1, "cpus_per_task": 4, "mem": "16G", "time": "03:00:00"},
        "script_args": {"param1": "value5", "param2": "value6"},
    },
}

mock_job_ids = {"JobA": "12345", "JobB": "67890", "JobC": "54321"}

expected_bundle_content = {
    "JobA": [
        "#!/bin/bash\n",
        "#SBATCH --account=def-bengioy\n",
        "#SBATCH --output=/path/to/remote/out/%x-%j.out\n",
        "#SBATCH --job-name=JobA\n",
        "#SBATCH --tasks=1\n",
        "#SBATCH --cpus-per-task=1\n",
        "#SBATCH --gres=gpu:1\n",
        "#SBATCH --mem=4G\n",
        "#SBATCH --time=01:00:00\n",
        "source /path/to/remote/venv/bin/activate\n",
        "run-job-a \\\n",
        "  --param1=value1 \\\n",
        "  --param2=value2\n",
    ],
    "JobB": [
        "#!/bin/bash\n",
        f"#SBATCH --dependency=afterok:{mock_job_ids['JobA']}\n",
        "#SBATCH --account=def-bengioy\n",
        "#SBATCH --output=/path/to/remote/out/%x-%j.out\n",
        "#SBATCH --job-name=JobB\n",
        "#SBATCH --tasks=1\n",
        "#SBATCH --cpus-per-task=2\n",
        "#SBATCH --mem=8G\n",
        "#SBATCH --time=02:00:00\n",
        "source /path/to/remote/venv/bin/activate\n",
        "run-job-b \\\n",
        "  --param1=value3 \\\n",
        "  --param2=value4\n",
    ],
    "JobC": [
        "#!/bin/bash\n",
        f"#SBATCH --dependency=afterok:{mock_job_ids['JobA']}:{mock_job_ids['JobB']}\n",
        "#SBATCH --account=def-bengioy\n",
        "#SBATCH --output=/path/to/remote/out/%x-%j.out\n",
        "#SBATCH --job-name=JobC\n",
        "#SBATCH --tasks=1\n",
        "#SBATCH --cpus-per-task=4\n",
        "#SBATCH --mem=16G\n",
        "#SBATCH --time=03:00:00\n",
        "source /path/to/remote/venv/bin/activate\n",
        "run-job-c \\\n",
        "  --param1=value5 \\\n",
        "  --param2=value6\n",
    ],
}

mock_machine_config_local = {
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}

mock_machine_config1 = {
    "hostname": "remote",
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}

mock_machine_config2 = {
    "hosturl": "remote.host.com",
    "username": "user",
    "key_path": "/path/to/key",
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}

mock_machine_config3 = {
    "hosturl": "remote.host.com",
    "username": "user",
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}


def setup_mock_subprocess_run() -> Callable:
    """Return a callable suitable for patching `subprocess.run` in the classic integration test."""
    mock_run_instance = MagicMock()

    def mock_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd:
            if cmd[0] == "scp":
                mock_run_instance.return_value.stdout = ""
                mock_run_instance.return_value.returncode = 0
                return mock_run_instance.return_value
            if cmd[0] == "ssh" and cmd[-1].startswith("mkdir -p "):
                mock_run_instance.return_value.stdout = ""
                mock_run_instance.return_value.returncode = 0
                return mock_run_instance.return_value
            if cmd[0] == "ssh" and ("-MNf" in cmd or "-O" in cmd):
                mock_run_instance.return_value.stdout = ""
                mock_run_instance.return_value.returncode = 0
                return mock_run_instance.return_value
        job = os.path.split(cmd[-1])[-1]
        job_name = job.split("_")[-2].split(".")[0]
        job_id = mock_job_ids[job_name]
        mock_run_instance.return_value.stdout = f"Submitted batch job {job_id}\n"
        mock_run_instance.return_value.returncode = 0
        return mock_run_instance.return_value

    mock_run_instance.side_effect = mock_run
    return mock_run_instance


@pytest.fixture
def mock_load_config(monkeypatch, tmp_path):
    mock_config = {
        "machines": {
            "local": {
                "path": tmp_path,
                "env_command": "source /path/to/env/bin/activate",
                "slurm_account": "def-bengioy",
            }
        },
        "default_machine": "local",
    }
    os.makedirs(tmp_path / "jobs", exist_ok=True)
    os.makedirs(tmp_path / "slurm", exist_ok=True)

    monkeypatch.setattr("autoslurm.save_load_jobs.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.run_slurm.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.utils.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.load_config", lambda: mock_config)
    from autoslurm.storage import ensure_storage_dirs, set_storage_root
    set_storage_root(tmp_path)
    ensure_storage_dirs()

    yield mock_config


@pytest.fixture
def slurm_emulator(monkeypatch):
    """Emulate SLURM job submission by running the generated script locally."""
    real_run = subprocess.run
    recorded = []
    counter = {"value": 0}

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] == "sbatch":
            counter["value"] += 1
            script_path = cmd[1]
            script_result = real_run(
                ["bash", script_path], capture_output=True, text=True
            )
            recorded.append(
                {
                    "script": script_path,
                    "stdout": script_result.stdout,
                    "stderr": script_result.stderr,
                }
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"Submitted batch job {1000 + counter['value']}\n"
            mock_result.stderr = ""
            return mock_result
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", fake_run)
    yield recorded
