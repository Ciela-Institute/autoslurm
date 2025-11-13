import argparse
import subprocess
import shlex
import json
import sys
from ..job_runner import submit_jobs
from ..save_load_jobs import save_job
from ..utils import machine_config


def parse_script_args(script, unknown_args) -> dict:
    # Each argument needs to be properly quoted to handle spaces and special characters
    prepared_args = [shlex.quote(arg) for arg in unknown_args]

    # Run the job specific CLI parser to validate the arguments
    command = [f"{script}-cli"] + prepared_args
    result = subprocess.run(command, capture_output=True, text=True)

    try:  # Try to run the CLI
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        # Capture error and parse it to be more intuitive
        error_message = (
            f"Failed to execute command: {' '.join(command)}\n"
            f"Exit code: {e.returncode}\n"
            f"Error output: {e.stderr}\n"
            "Please check the above command and error output to diagnose the issue."
        )
        print(error_message)
        sys.exit(1)

    try:
        # Load the arguments provided by the CLI parser
        args_dict = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError(
            f"Error parsing the output of the {script}-cli command. "
            f"Please make sure {script}-clip prints its arguments to the command line with the structure of "
            f"a valid JSON object (e.g. use 'print(json.dumps(vars(args), indent=4))')."
        )
    return args_dict


def parse_args():
    # fmt: off
    parser = argparse.ArgumentParser(description='Schedule a job for a SLURM cluster.')

    parser.add_argument('script',                        help='Name of the script to schedule.')
    parser.add_argument('--name',   default=None,        help='Name of the job bundle (JSON file containing multiple jobs/scripts to be scheduled). '
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

    name = args.name if args.name is not None else args.script
    save_job(job, bundle_name=name, append=args.append)

    if args.submit:
        config = machine_config(args)
        submit_jobs(name, machine_config=config)
