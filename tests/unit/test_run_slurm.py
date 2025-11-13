import pytest
from unittest.mock import patch, MagicMock, Mock
from autoslurm.run_slurm import get_job_id_from_sbatch_output
from autoslurm.run_slurm import run_slurm_remotely, run_slurm_locally
import os


@pytest.fixture
def mock_ssh():
    """Sets up a mock for subprocess.run for testing purposes."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Submitted batch job 12345\n", stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_load_config(tmp_path):
    mock_config = {"local": {"path": tmp_path}}
    os.makedirs(tmp_path / "jobs", exist_ok=True)
    with patch(
        "autoslurm.run_slurm.load_config", return_value=mock_config
    ) as mock_load_config:
        yield mock_load_config


def test_get_job_id_from_sbatch_output():
    output = "Submitted batch job 12345"  # Simulation of SLURM output
    job_id = get_job_id_from_sbatch_output(output)
    assert job_id == "12345"


def test_get_job_id_from_sbatch_output_failure():
    output = "Error: something went wrong"
    with pytest.raises(ValueError):
        get_job_id_from_sbatch_output(output)


def test_run_slurm_remotely(mock_ssh, mock_load_config):
    # Ensure that read() returns bytes
    mock_machine_config = {
        "hostname": "testhost",
        "username": "testuser",
        "key_path": "testkey",
        "path": "/path/to/remote",
    }

    # Call the function
    job_id = run_slurm_remotely("remote_script.sh", machine_config=mock_machine_config)

    assert job_id == "12345"


@patch("subprocess.run")
def test_run_slurm_locally(mock_run, mock_load_config):
    # Setup mock behavior
    mock_run.return_value = Mock(stdout="Submitted batch job 67890")

    # Call the function
    job_id = run_slurm_locally("local_script.sh")

    assert job_id == "67890"
    # Same as test above
    # mock_run.assert_called_with(['sbatch', 'local_script.sh'], capture_output=True, text=True)
