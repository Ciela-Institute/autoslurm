import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Sequence

from ..job_runner import submit_jobs
from ..save_load_jobs import schedule_job
from ..utils import machine_config

OPTION_PATTERN = re.compile(r"--[a-zA-Z0-9_-]+")
VALUE_PATTERN = re.compile(r"\s+([A-Z0-9_\[\]<>-]+)")
DEFAULT_PATTERN = re.compile(r"default:\s*([^,)]+)", re.IGNORECASE)


def _prepare_script_command(script: str) -> List[str]:
    path = Path(script)
    if path.is_file():
        return [sys.executable, str(path)]
    return [script]


def _run_help_command(script: str) -> str:
    command = _prepare_script_command(script) + ["--help"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(
            f"Unable to read the help message for {script}. Exit code {result.returncode}."
        )
    return result.stdout or result.stderr


def _normalize_flag(flag: str) -> str:
    return flag.lstrip("-").replace("-", "_")


def _parse_help_options(help_text: str) -> Dict[str, Dict[str, bool]]:
    options: Dict[str, Dict[str, bool]] = {}
    for line in help_text.splitlines():
        match = OPTION_PATTERN.search(line)
        if not match:
            continue
        option = match.group(0)
        key = _normalize_flag(option)
        if key in options:
            continue
        rest = line[match.end() :]
        takes_value = bool(VALUE_PATTERN.match(rest))
        options[key] = {
            "takes_value": takes_value,
            "default": DEFAULT_PATTERN.search(line).group(1)
            if DEFAULT_PATTERN.search(line)
            else None,
        }
    return options


def _parse_unknown_args(
    options: Dict[str, Dict[str, bool]], unknown_args: Sequence[str]
) -> Dict[str, bool | str | List[str]]:
    result: Dict[str, bool | str | List[str]] = {}
    i = 0
    length = len(unknown_args)
    while i < length:
        token = unknown_args[i]
        if token == "--":
            result.setdefault("__positionals__", []).extend(unknown_args[i + 1 :])
            break
        if not token.startswith("--"):
            result.setdefault("__positionals__", []).append(token)
            i += 1
            continue
        if "=" in token:
            name, value = token.split("=", 1)
            key = _normalize_flag(name)
            result[key] = value
            i += 1
            continue
        key = _normalize_flag(token)
        meta = options.get(key)
        if meta and not meta["takes_value"]:
            result[key] = True
            i += 1
            continue
        next_arg = unknown_args[i + 1] if i + 1 < length else None
        if next_arg is None or next_arg.startswith("--"):
            result[key] = True
            i += 1
            continue
        result[key] = next_arg
        i += 2
    return result


def parse_script_args(script, unknown_args) -> dict:
    help_output = _run_help_command(script)
    options = _parse_help_options(help_output)
    return _parse_unknown_args(options, unknown_args)


def parse_args():
    # fmt: off
    parser = argparse.ArgumentParser(description='Schedule a job for a SLURM cluster.')

    parser.add_argument('script',                        help='Name of the script to schedule.')
    parser.add_argument('--bundle', default=None,        help='Name of the job bundle (JSON file containing multiple jobs/scripts to be scheduled). '
                                                              'If not provided, the script name is used as the bundle name.')
    parser.add_argument('--job_name', default=None,      help='Name of the job to schedule. If not provided, the script name is used as the job name.')
    parser.add_argument('--append', action='store_true', help='Append the job to an existing bundle. '
                                                              'If not provided, a new unique bundle is created using current timestamp.')
    parser.add_argument('--submit', action='store_true', help='Submit the job immediately after scheduling it.')
    parser.add_argument('--dependencies', required=False, nargs='+', help='List of jobs that this job depends on to run.')
    # parser.add_argument('--dependency_type', nargs="+", default='afterany', choices=['afterany', 'afterok', 'afternotok', 'singleton'],
                            # help='Type of dependency to use for SLURM job submission.')
    parser.add_argument('--pre-commands', required=False, nargs="+", help='List of bash commands to run before the script.')

    # SLURM configuration options
    slurm = parser.add_argument_group('slurm', 'SLURM configuration options.')
    slurm.add_argument('--array', required=False, help='Array job configuration (e.g., 1-10).')
    slurm.add_argument('--tasks', required=False, type=int, help='Number of tasks to run.')
    slurm.add_argument('--cpus_per_task', required=False, type=int, help='Number of CPUs per task.')
    slurm.add_argument('--gres', required=False, help='Generic resource specification (e.g., gpu:1).')
    slurm.add_argument('--mem', required=False, help='Memory per node.')
    slurm.add_argument('--time', required=True, help='Maximum time for the job to run (e.g., 01:00:00).')

    # Optional arguments for custom machine configuration
    machine_config = parser.add_argument_group('machine_config', 'Custom machine configuration options.')
    machine_config.add_argument('--machine', required=False, help='Machine name to run the jobs (e.g., local, remote_1).')
    machine_config.add_argument('--hostname', required=False, help='Hostname of the remote machine. This requires ssh config to be set.')
    machine_config.add_argument('--hosturl', required=False, help='The url of the machine. When provided, consider providing username and key_path also.')
    machine_config.add_argument('--username', required=False, help='Username for SSH login')
    machine_config.add_argument('--key_path', required=False, help='Path to the SSH private key.')
    machine_config.add_argument('--remote_path', required=False, help='Path to the remote directory where scripts will be run.')
    machine_config.add_argument('--env_command', required=False, help='Command to activate the environment on the remote machine.')
    machine_config.add_argument('--slurm_account', required=False, help='SLURM account to use for job submission.')
    machine_config.add_argument('--path', required=False, help='Path to the directory where scripts will be run.')
    # fmt: on

    args, unknown_args = parser.parse_known_args()
    script_args = parse_script_args(args.script, unknown_args)
    return args, script_args


def main():
    args, script_args = parse_args()
    job = {
        "name": args.script if args.job_name is None else args.job_name,
        "script": args.script,
        "script_args": script_args,
        "dependencies": args.dependencies,
        "pre-commands": args.pre_commands,
        "slurm": {
            "array": args.array,
            "tasks": args.tasks,
            "cpus_per_task": args.cpus_per_task,
            "gres": args.gres,
            "mem": args.mem,
            "time": args.time,
        },
    }

    bundle = args.bundle if args.bundle is not None else args.script
    schedule_job(job, bundle_name=bundle, append=args.append)

    if args.submit:
        config = machine_config(args)
        submit_jobs(bundle, machine_config=config)
