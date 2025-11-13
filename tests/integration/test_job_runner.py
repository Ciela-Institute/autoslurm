import os
import pytest
from unittest.mock import patch, MagicMock
from autoslurm import save_bundle, submit_jobs
from glob import glob

# Mock Data for Job Configurations
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
        "pre_commands": ["echo 'Starting Job C'"],
    },
}

# Mock of submitting jobs to SLURM
mock_job_ids = {"JobA": "12345", "JobB": "67890", "JobC": "54321"}

expected_bundle_content = {
    "JobA": [
        "#!/bin/bash\n",
        "#SBATCH --output=/path/to/remote/slurm/%x-%j.out\n",
        "#SBATCH --job-name=JobA\n",
        "#SBATCH --tasks=1\n",
        "#SBATCH --cpus-per-task=1\n",
        "#SBATCH --gres=gpu:1\n",
        "#SBATCH --mem=4G\n",
        "#SBATCH --time=01:00:00\n",
        'export AUTOSLURM="/path/to/remote"\n',
        "source /path/to/remote/venv/bin/activate\n",  # Environment activation command is added if provided
        "run-job-a \\\n",
        "  --param1=value1 \\\n",
        "  --param2=value2\n",
    ],
    "JobB": [
        "#!/bin/bash\n",
        f"#SBATCH --dependency=afterok:{mock_job_ids['JobA']}\n",
        "#SBATCH --output=/path/to/remote/slurm/%x-%j.out\n",
        "#SBATCH --job-name=JobB\n",
        "#SBATCH --tasks=1\n",
        "#SBATCH --cpus-per-task=2\n",
        "#SBATCH --mem=8G\n",
        "#SBATCH --time=02:00:00\n",
        'export AUTOSLURM="/path/to/remote"\n',
        "source /path/to/remote/venv/bin/activate\n",  # Environment activation command is added if provided
        "run-job-b \\\n",
        "  --param1=value3 \\\n",
        "  --param2=value4\n",
    ],
    "JobC": [
        "#!/bin/bash\n",
        f"#SBATCH --dependency=afterok:{mock_job_ids['JobA']}:{mock_job_ids['JobB']}\n",
        "#SBATCH --output=/path/to/remote/slurm/%x-%j.out\n",
        "#SBATCH --job-name=JobC\n",
        "#SBATCH --tasks=1\n",
        "#SBATCH --cpus-per-task=4\n",
        "#SBATCH --mem=16G\n",
        "#SBATCH --time=03:00:00\n",
        'export AUTOSLURM="/path/to/remote"\n',  # Added automatically in every script
        "source /path/to/remote/venv/bin/activate\n",  # Environment activation command is added if provided
        "echo 'Starting Job C'\n",  # Pre-commands are added between the environment activation and the main command
        "run-job-c \\\n",
        "  --param1=value5 \\\n",
        "  --param2=value6\n",
    ],
}


# Mock local Machine Config
mock_machine_config_local = {
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}

# Mock Machine Config using config
mock_machine_config1 = {
    "hostname": "remote",
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}

# Mock Machine Config w key path
mock_machine_config2 = {
    "hosturl": "remote.host.com",
    "username": "user",
    "key_path": "/path/to/key",
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}

# Mock Machine Config w/o key_path
mock_machine_config3 = {
    "hosturl": "remote.host.com",
    "username": "user",
    "env_command": "source /path/to/remote/venv/bin/activate",
    "path": "/path/to/remote",
}


@pytest.fixture
def mock_load_config(monkeypatch, tmp_path):
    mock_config = {"local": {"path": tmp_path}}
    os.makedirs(tmp_path / "jobs", exist_ok=True)
    os.makedirs(tmp_path / "slurm", exist_ok=True)

    # Patch all the instances of load_config to save and load jobs from the tmp_path
    monkeypatch.setattr("autoslurm.save_load_jobs.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.job_to_slurm.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.job_dependency.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.job_runner.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.run_slurm.load_config", lambda: mock_config)
    monkeypatch.setattr("autoslurm.utils.load_config", lambda: mock_config)

    with patch("autoslurm.load_config", return_value=mock_config) as mock_load_config:
        yield mock_load_config


def setup_mock_subprocess_run() -> MagicMock:
    """Sets up a mock for subprocess.run for testing purposes."""
    mock_run_instance = MagicMock()

    # Define the behavior of subprocess.run to simulate sbatch job submission
    def mock_run(cmd, *args, **kwargs):
        job = os.path.split(cmd[-1])[-1]
        job_name = job.split("_")[-2].split(".")[0]  # Extract job name
        job_id = mock_job_ids[job_name]
        mock_run_instance.return_value.stdout = f"Submitted batch job {job_id}\n"
        mock_run_instance.return_value.returncode = 0
        return mock_run_instance.return_value

    mock_run_instance.side_effect = mock_run
    return mock_run_instance


# Mocking File I/O and Remote SSH interactions
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
    mock_run_script_remotely, mock_ssh_client, mock_machine_config, mock_load_config
):
    # Save the mock jobs to a JSON file
    save_bundle(mock_jobs, mock_job_name)
    submit_jobs(mock_job_name, machine_config=mock_machine_config)

    # Now check the content of the SLURM scripts  generated
    user_config = mock_load_config()
    autoslurm_path = user_config["local"]["path"]
    slurm_dir = os.path.join(autoslurm_path, "slurm")

    print(os.listdir(autoslurm_path))
    print(os.listdir(slurm_dir))

    files_created = glob(os.path.join(slurm_dir, "*.sh"))
    assert len(files_created) == 3, "Expected 3 SLURM scripts to be created"

    for file in files_created:
        with open(file, "r") as f:
            script_content = f.readlines()
        # extract job name from file name (see make_script_name in scheduler/utils.py, job_name is saved as the second to last element)
        job_name = os.path.split(file)[-1].split("_")[-2].split(".")[0]
        # Check if the content of the script matches the expected content
        expected_content_lines = expected_bundle_content[job_name]
        for i, (line, expected_line) in enumerate(
            zip(script_content, expected_content_lines)
        ):
            print(line, expected_line)
            assert (
                line == expected_line
            ), f"Mismatch for job {job_name} script at line {i}"


mock_jobs_error = {
    "JobA": {
        "name": "JobA",
        # "script": "run_job_a",
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


# Mocking File I/O and Remote SSH interactions
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
        # Save the mock jobs to a JSON file
        save_bundle(mock_jobs_error, mock_job_name)
        submit_jobs(mock_job_name, machine_config=mock_machine_config)
        # Missing script name should raise an error
