"""
Utility functions to save/load bundle of jobs to/from a JSON file in the jobs directory
"""

from .utils import load_config, scp_host_and_keypath_from_config
from .definitions import DATE_FORMAT
from .job_dependency import dependency_graph
from typing import Optional
from graphlib import TopologicalSorter
from datetime import datetime, timedelta
import warnings
import subprocess
import json
import os

__all__ = [
    "save_job",
    "save_bundle",
    "load_bundle",
    "transfer_slurm_to_remote",
    "nearest_bundle_filename",
]


def save_bundle(
    bundle: dict,
    name: str,
    append: bool = False,
) -> None:
    """
    Save job bundle configuration to a JSON file.

    Args:
        name (str): The name of the job bundle to save.
        bundle (dict): A dict of jobs (dict).
        append (bool): Flag indicating whether to append the job configurations to an existing file. Defaults to False.

    Behavior:
        - If append=False, a new job file is created.
        - If append=True, the jobs are saved to the last modified bundle with pattern 'name_*'. If no bundle file exists, a new one is created.
        - If job does not have key 'name', one is provided based on the key in the bundle.
    """
    if not isinstance(bundle, dict):
        raise TypeError("bundle must be a dictionary")
    for _, job in bundle.items():
        if not isinstance(job, dict):
            raise TypeError(
                "Each job in the bundle must be a dictionary. If you want to save a single job, use save_job() instead."
            )
        if "script" not in job:
            raise KeyError(
                "Each job in the bundle must minimally contain the 'script' entry to run an application"
            )

    if append:
        for job_name, job in bundle.items():
            if "name" not in job:
                job["name"] = job_name
            _, file_path = save_job(job, name, append=True)
    else:
        user_config = load_config()
        # Make sure a file with the same date does not exists, otherwise add 1 second to timestamp
        try:
            date = datetime.now()
            _, nearest_date = nearest_bundle_filename(name)
            if date - nearest_date < timedelta(seconds=1):
                warnings.warn(
                    "Found a job saved at the same time. "
                    "If you wanted the job to be appended to a bundle instead, "
                    "use the flags --append and --name=name_of_bundle."
                )
                date += timedelta(seconds=1)
        except FileNotFoundError:
            pass
        date = date.strftime(DATE_FORMAT)
        file_path = os.path.join(
            user_config["local"]["path"], "jobs", f"{name}_{date}.json"
        )
        # Make sure every job has a name
        for job_name, job in bundle.items():
            if job.get("name", None) is None:
                job["name"] = job_name
        with open(file_path, "w") as file:
            json.dump(bundle, file, indent=4)
    print(f"Saved bundle {name} to {file_path}")


def save_job(
    job: dict,
    bundle_name: Optional[str] = None,
    append: bool = False,
) -> None:
    """
    Save job configurations to a JSON file.

    Args:
        job (dict): A dict of job configurations.
        bundle_name (Optional[str]): The name of the job bundle file to save to a JSON file. If None, the job name is used. Defaults to None.
        append (bool): Flag indicating whether to append the job configuration to an existing bundle. Defaults to False.

    Behavior:
        - If append=False and bundle_name=None, a new job file is created.
        - If append=False and bundle_name is specified, a new job file is created.
        - If append=True and bundle_name=None, the job is saved to the last modified bundle with pattern 'job['name']_*'.
            If no bundle file exists, a new one is created.
        - If append=True and bundle_name is specified, the job is saved to the latest bundle with the specified name.
            If no bundle file exists, a new one is created.
        - If job does not have key 'name', one is provided based on the script name. Note that name must be unique in the bundle,
            so the scheduler reserves the right to modify it.
    Returns:
        dict: The saved job configuration
    """
    user_config = load_config()
    job_dir = os.path.join(user_config["local"]["path"], "jobs")
    if "script" not in job:
        raise KeyError(
            "Job configuration must minimally contain the 'script' entry to run an application"
        )

    if "name" not in job:  # If job does not have a name, use the script name
        job["name"] = job["script"]
    job_name = job["name"]

    if bundle_name is None:
        bundle_name = job_name

    if append:
        try:  # Save the job in existing bundle file
            # Load the job file
            filename, date = nearest_bundle_filename(bundle_name)
            file_path = os.path.join(job_dir, filename)
            with open(file_path, "r") as file:
                bundle = json.load(file)
            # Create a unique name in case of name conflict
            if job_name in bundle:
                i = 1
                job_name = f"{job_name}_{i:03d}"
                while job_name in bundle:
                    i += 1
                    job_name = f"{job_name[:-4]}_{i:03d}"
            job["name"] = job_name  # Update name of the job
            bundle[job_name] = job  # Save it in bundle
        except (
            FileNotFoundError
        ):  # Create a new empty bundle file and save the job inside it
            date = datetime.now().strftime(DATE_FORMAT)
            print(
                f"Did not find a file with the pattern '{bundle_name}_*' in the directory {job_dir}. "
                f"Creating a new bundle file '{bundle_name}_{date}.json'"
            )
            file_path = os.path.join(job_dir, f"{bundle_name}_{date}.json")
            bundle = {job_name: job}
    else:  # Create a new job file
        date = datetime.now()
        try:
            # Make sure a file with the same date does not exists, otherwise add 1 second to timestamp
            _, nearest_date = nearest_bundle_filename(bundle_name)
            if date - nearest_date < timedelta(seconds=1):
                date += timedelta(seconds=1)
        except FileNotFoundError:
            pass
        date = date.strftime(DATE_FORMAT)
        file_path = os.path.join(job_dir, f"{bundle_name}_{date}.json")
        bundle = {job_name: job}

    with open(file_path, "w") as file:
        json.dump(bundle, file, indent=4)
    print(f"Saved job {job_name} to {file_path}")
    return job, file_path


def transfer_slurm_to_remote(
    slurm_name,
    machine_name: Optional[str] = None,
    machine_config: Optional[dict] = None,
) -> None:
    """
    Transfers a script from the local machine to a remote machine.
    """
    user_config = load_config()
    local_script_path = os.path.join(user_config["local"]["path"], "slurm", slurm_name)

    if machine_name is not None:
        machine_config = user_config.get(machine_name)
        if not machine_config:
            raise EnvironmentError(
                f"No configuration found for machine: {machine_name}"
            )
    if machine_config is None:
        raise ValueError("Either machine_name or machine_config must be specified")
    if machine_config.get("path", None) is None:
        raise ValueError(
            f"Machine {machine_config['hostname']} configuration must contain a path to the autoslurm directory"
        )

    # Transfer the script to the remote machine
    remote_script_path = os.path.join(machine_config["path"], "slurm", slurm_name)
    hostname, key_path = scp_host_and_keypath_from_config(machine_config, machine_name)
    ssh_command = [
        "scp",
        key_path,
        local_script_path,
        f"{hostname}:{remote_script_path}",
    ]
    result = subprocess.run(ssh_command, capture_output=True, text=True)

    # Check for errors
    if result.returncode != 0:
        raise ValueError(f"Error running scp command: {result.stderr}")


def order_jobs(jobs, sorted_names):
    jobs_list = []
    for name in sorted_names:
        job = jobs[name]
        jobs_list.append(job)
    return jobs_list


def load_bundle(
    name: str, desired_date: Optional[datetime] = None
) -> tuple[list, dict, datetime]:
    """
    Read the job bundle JSON file and extract the dependency graph.

    Parameters:
    name (str): The name of the job bundle to load.
    topological_sort (bool): Flag indicating whether to perform a topological sort on the dependency graph.
                             Defaults to True.

    Returns:
    tuple: A tuple containing the loaded jobs and the dependency graph.

    Raises:
    FileNotFoundError: If the specified job file does not exist.
    JSONDecodeError: If the job file is not a valid JSON file.
    """

    # Load user configuration and job file path
    user_config = load_config()
    job_file, date = nearest_bundle_filename(name, desired_date)
    file_path = os.path.join(user_config["local"]["path"], "jobs", job_file)

    with open(file_path, "r") as file:
        try:
            jobs = json.load(file)
        except json.JSONDecodeError:
            raise OSError(
                f"Error decoding the job file {name}.json (located in jobs folder). Make sure it is a valid JSON file."
            )

    dependencies = dependency_graph(jobs)

    # Depth-first search topological sorting of a graph (raises error if a cycle is detected)
    sorted_job_names = tuple(TopologicalSorter(dependencies).static_order())[::-1]
    jobs = order_jobs(jobs, sorted_job_names)

    return jobs, dependencies, date


def nearest_bundle_filename(
    name: str, desired_date: Optional[datetime] = None
) -> tuple[str, datetime]:
    """
    Get the filename of a job bundle nearest in time to desired date from the jobs directory.
    """
    user_config = load_config()
    jobs_dir = os.path.join(user_config["local"]["path"], "jobs")
    files = [
        f[:-5]
        for f in os.listdir(jobs_dir)
        if f.startswith(name) and f.endswith(".json")
    ]
    if not files:
        raise FileNotFoundError(
            f"No files found with name '{name}' in directory {jobs_dir}"
        )
    dates = []
    for file in files:
        try:
            dates.append(datetime.strptime(file.split("_")[-1], DATE_FORMAT))
        except ValueError:
            print(
                f"Could not parse date from file {file}. Name of file expected to have the format 'name_{DATE_FORMAT}.json' this file will not be considered."
            )
    if desired_date is None:
        desired_date = datetime.now()
    nearest_date = min(dates, key=lambda x: abs(x - desired_date))
    file_name = f"{name}_{nearest_date.strftime(DATE_FORMAT)}.json"
    return file_name, nearest_date
