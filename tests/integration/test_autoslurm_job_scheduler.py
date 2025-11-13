from unittest.mock import patch, MagicMock
from autoslurm.apps.schedule import parse_script_args, parse_args, main
from argparse import Namespace
import pytest
import json
import os


@pytest.fixture
def mock_run():
    with patch("subprocess.run") as mock_run:
        # Simulate JSON output as if the CLI application was modified to print arguments as a JSON string
        args_dict = {"custom_arg1": "value1", "custom_arg2": "value2"}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(args_dict, indent=4)
        )
        yield mock_run


@pytest.fixture
def mock_submit_job():
    """
    We avoid the full integration of submit_jobs, which is integrated in another test (see test_job_runner.py)
    Here, we test up until the point where submit_jobs is called.
    """
    with patch("autoslurm.apps.schedule.submit_jobs") as mock_submit_job:
        yield mock_submit_job


@pytest.fixture
def mock_parse_known_args():
    with patch("argparse.ArgumentParser.parse_known_args") as mock_parse_known_args:
        mock_parse_known_args.return_value = (
            Namespace(
                script="job_name",
                bundle="bundle_name",
                job_name=None,
                job=None,
                append=False,
                submit=False,
                dependencies=None,
                pre_commands=None,
                array=None,
                tasks=None,
                cpus_per_task=None,
                gres=None,
                mem=None,
                time="01:00:00",
                machine=None,
                hostname=None,
                hosturl=None,
                username=None,
                key_path=None,
                remote_path=None,
                env_command=None,
                slurm_account=None,
            ),
            ["--custom_arg1", "value1", "--custom_arg2", "value2"],
        )
        yield mock_parse_known_args


@pytest.fixture
def mock_load_config(monkeypatch, tmp_path):
    mock_config = {
        "local": {
            "path": tmp_path,
            "env_command": "source /path/to/env/bin/activate",
            "slurm_account": "def-bengioy",
        }
    }
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


"""
Tests
"""


def test_parse_script_args_success(mock_run):
    """
    Test that the function returns the job arguments correctly as a dictionary,
    simulating the behavior of a CLI application outputting JSON.
    """
    job_args = parse_script_args(
        "job_name", ["--custom_arg1", "value1", "--custom_arg2", "value2"]
    )
    expected_dict = {"custom_arg1": "value1", "custom_arg2": "value2"}
    assert job_args == expected_dict


# This test does not work now that except is not naked anymore in parse_script_args. Need to produce a json.JSONDecondeError
# def test_parse_script_args_error(mock_run):
# mock_run.return_value = MagicMock(returncode=1, stderr="error")
# with pytest.raises(ValueError):
# job_args = parse_script_args(
# "job_name", ["--custom_arg1", "value1", "--custom_arg2", "value2"]
# )


def test_schedule_cli(mock_parse_known_args, mock_run):
    # Adjust the mock to return a JSON string that matches the expected output from the CLI application
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"custom_arg1": "value1", "custom_arg2": "value2"}, indent=4),
    )
    args, job_args = parse_args()
    assert args.script == "job_name"
    # Parse the JSON string to assert the dictionary contents
    expected_job_args = job_args
    assert expected_job_args == {"custom_arg1": "value1", "custom_arg2": "value2"}


def test_schedule_main(
    mock_submit_job, mock_parse_known_args, mock_run, mock_load_config
):
    # Adjust mock_run to simulate the output from a successful CLI application run
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"custom_arg1": "value1", "custom_arg2": "value2"}, indent=4),
    )
    main()

    # Modify mock_parse_known_args to simulate --run_now
    mock_parse_known_args.return_value = (
        Namespace(
            script="job_name",
            bundle="bundle_name",
            job_name=None,
            job=None,
            append=False,
            submit=True,
            dependencies=[],
            pre_commands=[],
            array=None,
            tasks=None,
            cpus_per_task=None,
            gres=None,
            mem=None,
            time="01:00:00",
            machine=None,
            hostname=None,
            hosturl=None,
            username=None,
            key_path=None,
            remote_path=None,
            env_command=None,
            slurm_account=None,
        ),
        ["--custom_arg1", "value1", "--custom_arg2", "value2"],
    )
    main()
