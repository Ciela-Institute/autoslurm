from typing import Optional
from datetime import datetime
from .job_to_slurm import create_slurm_script
from .job_dependency import update_slurm_with_dependencies
from .run_slurm import run_slurm_remotely, run_slurm_locally
from .save_load_jobs import load_bundle, transfer_slurm_to_remote
from .utils import load_config

__all__ = ["submit_jobs"]


def submit_jobs(
    name: str, machine_config: Optional[dict] = None, date: Optional[datetime] = None
):
    """
    Run a job with SLURM either locally or on a remote machine. This is the main function of the scheduler module.
    It assumes the job configuration is stored in a JSON file. The logic to save jobs to a JSON file is implemented in the "save_load_jobs" module.

    Parameters:
        - name (str): The name of the job bundle to be scheduled.
        - machine_config (Optional[dict]): The configuration details for the remote machine. If not provided, the default configuration will be used.
        - date (Optional[datetime]): The date and time to schedule the job. If not provided, the current date and time will be used.

    Raises:
        - EnvironmentError: If no configuration is found for the specified machine.

    """
    if machine_config is None:
        machine_config = load_config()["local"]

    # Check for presence of hostname or hosturl
    if "hostname" not in machine_config and "hosturl" not in machine_config:
        machine = "local"
        host = "localhost"
    else:
        machine = "remote"
        host = machine_config.get("hostname", machine_config.get("hosturl"))

    # Create SLURM script for each job
    jobs, dependencies, date = load_bundle(name)
    slurm_names = {}
    for job in jobs:
        if job.get("script", None) is None:
            raise ValueError(
                "'script' entry is missing from one of the jobs in the configuration file {job_name}"
            )
        elif job.get("name", None) is None:
            raise ValueError(
                "'name' entry is missing from one of the jobs in the configuration file {job_name}"
            )
        slurm_name = create_slurm_script(job, date, machine_config)
        slurm_names[job["name"]] = slurm_name

    # Submit each job in topological order and capture dependencies in SLURM script
    for job in jobs:
        slurm_name = slurm_names[job["name"]]
        if machine == "remote":
            transfer_slurm_to_remote(slurm_name, machine_config=machine_config)
            job_id = run_slurm_remotely(slurm_name, machine_config=machine_config)
            print(f"Submitted job {job['name']} with ID {job_id} at {host}")
        else:
            job_id = run_slurm_locally(slurm_name)
            print(f"Submitted job {job['name']} with ID {job_id} locally")

        # Update dependent job scripts with the current job ID
        for dependent_job_name in dependencies.get(job["name"], []):
            update_slurm_with_dependencies(slurm_names[dependent_job_name], job_id)
