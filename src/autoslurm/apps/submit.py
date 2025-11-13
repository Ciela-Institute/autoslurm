import argparse
from ..utils import machine_config
from ..job_runner import submit_jobs


def parse_args():
    """
    Parses command line arguments.

    Returns:
    argparse.Namespace: The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description="Run scripts on a SLURM cluster.")
    parser.add_argument("name", help="Name of the job")
    # parser.add_argument('date', required=False, help='If provided, will look for job closest to this date. Otherwise, latest job is ran.'
    # 'Provide in the format [Y]YYYY-[M]MM-[D]DD-[H]HH-[m]mm-[s]ss.'
    # 'E.g., Y2021 will yield the latest job of 2021. M09 will yield the latest job of last September.'
    # 'D15 will yield the latest job of the 15th of the month. Y2021-M09 will yield the latest job of September 2021. etc.')

    # Optional argument for machine configuration
    parser.add_argument(
        "--machine",
        required=False,
        help="Machine name to run the jobs (e.g., local, remote_1)",
    )

    # Optional arguments for custom machine configuration
    parser.add_argument(
        "--hostname", required=False, help="Hostname of the remote machine"
    )
    parser.add_argument("--hosturl", required=False, help="The url of the machine")
    parser.add_argument("--username", required=False, help="Username for SSH login")
    parser.add_argument(
        "--key_path", required=False, help="Path to the SSH private key"
    )
    parser.add_argument(
        "--remote_path",
        required=False,
        help="Path to the remote directory where scripts will be run",
    )
    parser.add_argument(
        "--env_command",
        required=False,
        help="Command to activate the environment on the remote machine",
    )
    parser.add_argument(
        "--slurm_account",
        required=False,
        help="SLURM account to use for job submission",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    config = machine_config(args)
    submit_jobs(args.name, machine_config=config)
