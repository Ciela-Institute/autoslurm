from pathlib import Path
import sys

from autoslurm import save_bundle, submit_jobs
from autoslurm.apps.schedule import parse_script_args
from tests.integration.mocks import (
    mock_machine_config_local,
    mock_load_config,
    slurm_emulator,
)


def test_cli_submission(mock_load_config, slurm_emulator):
    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "example_python_script.py"
    )
    args = [
        "--dataset",
        "/tmp/galaxies",
        "--epochs",
        "5",
        "--learning-rate",
        "1e-3",
        "--conditional",
    ]
    job_args = parse_script_args(str(script_path), args)
    job_name = "galaxy_training_cli"
    job = {
        "name": job_name,
        "script": f"{sys.executable} {script_path}",
        "script_args": job_args,
        "dependencies": [],
        "slurm": {"tasks": 1, "cpus_per_task": 1, "mem": "1G", "time": "00:01:00"},
    }

    save_bundle({job_name: job}, job_name)
    submit_jobs(job_name, machine="local", machine_overrides=mock_machine_config_local)

    assert slurm_emulator, "No SLURM executions were recorded"
    assert any(
        "/tmp/galaxies" in call["stdout"] for call in slurm_emulator
    )
    assert any("epochs=5" in call["stdout"] for call in slurm_emulator)
    assert any("conditional=True" in call["stdout"] for call in slurm_emulator)
