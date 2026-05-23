"""
Utility functions to save/load bundle of jobs to/from a JSON file in the jobs directory
"""

from .utils import (
    load_config,
    scp_host_and_keypath_from_config,
    remote_storage_root_from_config,
    ssh_host_from_config,
)
from .definitions import DATE_FORMAT
from .job_dependency import dependency_graph
from typing import Optional
from graphlib import TopologicalSorter
from datetime import datetime, timedelta
import warnings
import subprocess
import json
import os
import shlex
from pathlib import Path
from .storage import ensure_storage_dirs, jobs_dir, slurm_dir, storage_root
from .utils import ssh_host_from_config

__all__ = [
    "schedule_job",
    "save_bundle",
    "load_bundle",
    "load_bundle_from_path",
    "list_saved_bundles",
    "latest_bundle_summaries",
    "transfer_slurm_to_remote",
    "transfer_bundle_to_remote",
    "nearest_bundle_filename",
]


def _is_placeholder_file(path: Path) -> bool:
    return path.name.startswith(".")


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
                "Each job in the bundle must be a dictionary. If you want to save a single job, use schedule_job() instead."
            )
        if "script" not in job:
            raise KeyError(
                "Each job in the bundle must minimally contain the 'script' entry to run an application"
            )

    if append:
        for job_name, job in bundle.items():
            if "name" not in job:
                job["name"] = job_name
            _, file_path = schedule_job(job, name, append=True)
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
                    "use the flags --append and --bundle=name_of_bundle."
                )
                date += timedelta(seconds=1)
        except FileNotFoundError:
            pass
        ensure_storage_dirs()
        date = date.strftime(DATE_FORMAT)
        file_path = jobs_dir() / f"{name}_{date}.json"
        # Make sure every job has a name
        for job_name, job in bundle.items():
            if job.get("name", None) is None:
                job["name"] = job_name
        with open(file_path, "w") as file:
            json.dump(bundle, file, indent=4)
    print(f"Saved bundle {name} to {file_path}")


def schedule_job(
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
    ensure_storage_dirs()
    job_dir = jobs_dir()
    if "script" not in job:
        raise KeyError(
            "Job configuration must minimally contain the 'script' entry to run an application"
        )

    if "name" not in job:  # If job does not have a name, use the script name
        script_value = job["script"]
        tokens = script_value.split()
        candidate = tokens[-1]
        if candidate.endswith(".py"):
            job["name"] = Path(candidate).stem
        elif Path(script_value).suffix:
            job["name"] = Path(script_value).stem
        else:
            job["name"] = script_value
    # Normalize python script paths without invocation
    if len(job["script"].split()) == 1 and job["script"].endswith(".py"):
        job["script"] = f"python {job['script']}"
    job_name = job["name"]

    if bundle_name is None:
        bundle_name = job_name

    if append:
        try:  # Save the job in existing bundle file
            # Load the job file
            filename, date = nearest_bundle_filename(bundle_name)
            file_path = job_dir / filename
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
            file_path = job_dir / f"{bundle_name}_{date}.json"
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
        file_path = job_dir / f"{bundle_name}_{date}.json"
        bundle = {job_name: job}

    with open(file_path, "w") as file:
        json.dump(bundle, file, indent=4)
    print(f"Saved job {job_name} to {file_path}")
    return job, file_path


def _resolve_machine_config(
    machine_name: Optional[str], machine_config: Optional[dict]
) -> tuple[Optional[str], dict]:
    if machine_name is not None:
        user_config = load_config()
        machine_config = user_config.get(machine_name)
        if not machine_config:
            raise EnvironmentError(
                f"No configuration found for machine: {machine_name}"
            )
    if machine_config is None:
        raise ValueError("Either machine_name or machine_config must be specified")
    return machine_name, machine_config


def _remote_root_for_machine(machine_name: Optional[str], machine_config: dict) -> str:
    if machine_config.get("path"):
        return machine_config["path"]
    return remote_storage_root_from_config(machine_config, machine_name)


def _scp_to_remote(local_path: Path, remote_path: str, machine_name: Optional[str], machine_config: dict) -> None:
    hostname, key_path = scp_host_and_keypath_from_config(machine_config, machine_name)
    ssh_command = ["scp"]
    if key_path:
        ssh_command.extend(shlex.split(key_path))
    ssh_command.extend([str(local_path), f"{hostname}:{remote_path}"])
    result = subprocess.run(ssh_command, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"Error running scp command: {result.stderr}")


def _ensure_remote_directory(machine_name: Optional[str], machine_config: dict, remote_dir: str) -> None:
    hostname = ssh_host_from_config(machine_config, machine_name)
    result = subprocess.run(
        ["ssh", *shlex.split(hostname), f"mkdir -p {shlex.quote(remote_dir)}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Unable to create remote directory '{remote_dir}' for machine '{machine_name or ''}': {message}"
        )


def transfer_slurm_to_remote(
    slurm_name,
    machine_name: Optional[str] = None,
    machine_config: Optional[dict] = None,
) -> None:
    """
    Transfers a script from the local machine to a remote machine.
    """
    ensure_storage_dirs()
    local_script_path = slurm_dir() / slurm_name
    machine_name, machine_config = _resolve_machine_config(machine_name, machine_config)
    remote_path = _remote_root_for_machine(machine_name, machine_config)
    remote_script_path = os.path.join(remote_path, "slurm", slurm_name)
    _ensure_remote_directory(machine_name, machine_config, os.path.join(remote_path, "slurm"))
    _scp_to_remote(local_script_path, remote_script_path, machine_name, machine_config)


def transfer_bundle_to_remote(
    bundle_name: str,
    date: datetime,
    machine_name: Optional[str] = None,
    machine_config: Optional[dict] = None,
) -> None:
    """
    Transfers the bundle JSON file to the remote machine jobs directory.
    """
    ensure_storage_dirs()
    local_bundle_path = jobs_dir() / f"{bundle_name}_{date.strftime(DATE_FORMAT)}.json"
    machine_name, machine_config = _resolve_machine_config(machine_name, machine_config)
    remote_path = _remote_root_for_machine(machine_name, machine_config)
    remote_bundle_path = os.path.join(remote_path, "jobs", local_bundle_path.name)
    _ensure_remote_directory(machine_name, machine_config, os.path.join(remote_path, "jobs"))
    _scp_to_remote(local_bundle_path, remote_bundle_path, machine_name, machine_config)


def order_jobs(jobs, sorted_names):
    jobs_list = []
    for name in sorted_names:
        job = jobs[name]
        if job.get("name") is None:
            job["name"] = name
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
    ensure_storage_dirs()
    job_file, date = nearest_bundle_filename(name, desired_date)
    file_path = jobs_dir() / job_file

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


def load_bundle_from_path(
    bundle_path: str | Path,
) -> tuple[list, dict, datetime]:
    """
    Load a bundle from an explicit JSON file path.

    This is the path-based counterpart to :func:`load_bundle`, which looks up
    bundles by name under the AutoSlurm storage root.
    """
    ensure_storage_dirs()
    file_path = Path(bundle_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Bundle file not found: {file_path}")

    with open(file_path, "r") as file:
        try:
            jobs = json.load(file)
        except json.JSONDecodeError:
            raise OSError(
                f"Error decoding the job bundle file {file_path}. Make sure it is a valid JSON file."
            )

    dependencies = dependency_graph(jobs)
    sorted_job_names = tuple(TopologicalSorter(dependencies).static_order())[::-1]
    jobs = order_jobs(jobs, sorted_job_names)
    return jobs, dependencies, datetime.fromtimestamp(file_path.stat().st_mtime)


def list_saved_bundles(
    desired_date: Optional[datetime] = None,
    bundle_name: Optional[str] = None,
) -> list[dict]:
    """
    List saved bundle files ordered by proximity to a reference date.

    If ``bundle_name`` is provided, only versions of that bundle are returned.
    Otherwise every bundle under the jobs directory is included.
    """
    ensure_storage_dirs()
    if desired_date is None:
        desired_date = datetime.now()

    entries: list[dict] = []
    for filename in jobs_dir().glob("*.json"):
        if _is_placeholder_file(filename):
            continue
        stem = filename.stem
        if "_" not in stem:
            continue
        name_part, date_text = stem.rsplit("_", 1)
        if bundle_name is not None and name_part != bundle_name:
            continue
        try:
            saved_date = datetime.strptime(date_text, DATE_FORMAT)
        except ValueError:
            continue
        try:
            with open(filename, "r") as file:
                jobs = list(json.load(file).keys())
        except (json.JSONDecodeError, OSError):
            jobs = []
        entries.append(
            {
                "bundle": name_part,
                "date": saved_date,
                "path": filename,
                "jobs": jobs,
                "distance": abs(saved_date - desired_date),
            }
        )

    entries.sort(key=lambda entry: (entry["distance"], entry["date"]), reverse=False)
    return entries


def latest_bundle_summaries(desired_date: Optional[datetime] = None) -> list[dict]:
    """
    Return the newest saved bundle for each bundle name.

    The entries are sorted by proximity to ``desired_date`` (default: now).
    """
    ensure_storage_dirs()
    if desired_date is None:
        desired_date = datetime.now()

    latest_by_name: dict[str, dict] = {}
    for filename in jobs_dir().glob("*.json"):
        if _is_placeholder_file(filename):
            continue
        stem = filename.stem
        if "_" not in stem:
            continue
        bundle_name, date_text = stem.rsplit("_", 1)
        try:
            saved_date = datetime.strptime(date_text, DATE_FORMAT)
        except ValueError:
            continue

        current = latest_by_name.get(bundle_name)
        if current is not None and saved_date <= current["date"]:
            continue

        try:
            with open(filename, "r") as file:
                jobs = json.load(file)
        except (json.JSONDecodeError, OSError):
            jobs = {}

        latest_by_name[bundle_name] = {
            "bundle": bundle_name,
            "date": saved_date,
            "path": filename,
            "job_count": len(jobs),
        }

    entries = list(latest_by_name.values())
    entries.sort(key=lambda entry: (abs(entry["date"] - desired_date), entry["bundle"]))
    return entries


def nearest_bundle_filename(
    name: str, desired_date: Optional[datetime] = None
) -> tuple[str, datetime]:
    """
    Get the filename of a job bundle nearest in time to desired date from the jobs directory.
    """
    user_config = load_config()
    ensure_storage_dirs()
    directory = jobs_dir()
    files = [
        f[:-5]
        for f in os.listdir(directory)
        if not f.startswith(".") and f.startswith(name) and f.endswith(".json")
    ]
    if not files:
        raise FileNotFoundError(
            f"No files found with name '{name}' in directory {directory}"
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
