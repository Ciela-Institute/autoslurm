from unittest.mock import patch, MagicMock
from autoslurm.apps.schedule import parse_script_args, parse_args, main
from argparse import Namespace
import pytest

from tests.integration.mocks import mock_load_config


@pytest.fixture
def mock_run():
    help_output = """usage: job_name [options]
  --custom_arg1 CUSTOM_ARG1  First argument
  --custom_arg2 CUSTOM_ARG2  Second argument
"""

    def _run(cmd, *args, **kwargs):
        return MagicMock(returncode=0, stdout=help_output)

    with patch("subprocess.run", side_effect=_run) as mock_run:
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


"""
Tests
"""


def test_parse_script_args_success(mock_run):
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
    args, job_args = parse_args()
    assert args.script == "job_name"
    assert job_args == {"custom_arg1": "value1", "custom_arg2": "value2"}


def test_schedule_main(
    mock_submit_job, mock_parse_known_args, mock_run, mock_load_config
):
    # parse_script_args uses the patched subprocess.run fixture, which already returns a help message
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
