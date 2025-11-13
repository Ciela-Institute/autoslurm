import os
from typing import Union
from collections import defaultdict
from .utils import load_config

__all__ = ["dependency_graph", "update_slurm_with_dependencies"]


def dependency_graph(jobs):
    """
    Build a dependency graph from a dictionary of jobs.

    Example:
        jobs = {
            "JobA": {},
            "JobB": {"dependencies": ["JobA"]},
            "JobC": {"dependencies": ["JobA", "JobB"]},
        }
        dependency_graph(jobs) = {
                "JobA": ["JobB", JobC"],
                "JobB": ["JobC"],
                "JobC": []
            }
    """
    dependency_graph = defaultdict(list)
    names = set()
    for job_name, job in jobs.items():
        if job_name in names:
            raise ValueError("Duplicate job: {}".format(job_name))
        names.add(job_name)
        dependency_graph[job_name] = []
        if job.get("dependencies") is not None:  # avoid case where dependencies is None
            for dep in job.get("dependencies", []):
                dependency_graph[dep].append(job_name)
    return dependency_graph


def update_slurm_with_dependencies(
    slurm_name, dependency_job_ids: Union[list, tuple, int]
):  # , dependency_type: Union[list, str]='afterok'):
    if not isinstance(dependency_job_ids, (list, tuple)):
        dependency_job_ids = [dependency_job_ids]
    # if not isinstance(dependency_type, list):
    # dependency_type = [dependency_type] * len(dependency_job_ids)
    user_config = load_config()
    file_path = os.path.join(user_config["local"]["path"], "slurm", slurm_name)

    with open(file_path, "r") as file:
        lines = file.readlines()

    dependency_line_index = None
    for i, line in enumerate(lines):
        if line.startswith("#SBATCH --dependency"):
            dependency_line_index = i
            existing_deps = line.strip().split("afterok:")[-1]
            new_deps = ":".join(dependency_job_ids)
            if existing_deps:
                new_deps = existing_deps + ":" + new_deps
            lines[i] = f"#SBATCH --dependency=afterok:{new_deps}\n"
            break

    if dependency_line_index is None:
        # Insert the dependency directive after the shebang line
        dependency_directive = (
            f"#SBATCH --dependency=afterok:{':'.join(dependency_job_ids)}\n"
        )
        for i, line in enumerate(lines):
            if line.startswith("#!/bin/bash"):
                lines.insert(i + 1, dependency_directive)
                break

    with open(file_path, "w") as file:
        file.writelines(lines)
