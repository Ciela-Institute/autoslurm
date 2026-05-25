import argparse
import sys
from pathlib import Path
from ..utils import machine_config
from ..save_load_jobs import latest_bundle_summaries
from ..job_runner import submit_jobs


def parse_args(argv=None):
    """
    Parses command line arguments.

    Returns:
    argparse.Namespace: The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description="Run scripts on a SLURM cluster.")
    parser.add_argument("name", nargs="?", help="Name of the job")
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
        "--venv_path",
        required=False,
        help="Path to the virtualenv root; autoslurm renders source <venv>/bin/activate.",
    )
    parser.add_argument(
        "--env_command",
        required=False,
        help="Legacy command to activate environment (deprecated; prefer --venv_path).",
    )
    parser.add_argument(
        "--slurm_account",
        required=False,
        help="SLURM account to use for job submission",
    )
    parser.add_argument(
        "--bundle-file",
        required=False,
        type=Path,
        help="Explicit path to a JSON bundle file to submit instead of loading from AutoSlurm storage.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Submit the latest scheduled bundle from AutoSlurm storage.",
    )

    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser = argparse.ArgumentParser(description="Run scripts on a SLURM cluster.")
        parser.add_argument("name", help="Name of the job")
        parser.add_argument("--machine", required=False, help="Machine name to run the jobs (e.g., local, remote_1)")
        parser.add_argument("--hostname", required=False, help="Hostname of the remote machine")
        parser.add_argument("--hosturl", required=False, help="The url of the machine")
        parser.add_argument("--username", required=False, help="Username for SSH login")
        parser.add_argument("--key_path", required=False, help="Path to the SSH private key")
        parser.add_argument("--venv_path", required=False, help="Path to the virtualenv root; autoslurm renders source <venv>/bin/activate.")
        parser.add_argument("--env_command", required=False, help="Legacy command to activate environment (deprecated; prefer --venv_path).")
        parser.add_argument("--slurm_account", required=False, help="SLURM account to use for job submission")
        parser.add_argument("--bundle-file", required=False, type=Path, help="Explicit path to a JSON bundle file to submit instead of loading from AutoSlurm storage.")
        parser.add_argument("--latest", action="store_true", help="Submit the latest scheduled bundle from AutoSlurm storage.")
        parser.print_help()
        return
    args = parse_args(argv)
    if args.latest and args.bundle_file is not None:
        raise SystemExit("--latest cannot be combined with --bundle-file.")
    if args.latest and args.name is not None:
        raise SystemExit("--latest does not take a bundle name.")
    if not args.latest and args.name is None:
        raise SystemExit("Submit requires a bundle name unless --latest is used.")

    if args.latest:
        summaries = latest_bundle_summaries()
        if not summaries:
            raise SystemExit("No saved bundles found.")
        args.name = max(summaries, key=lambda entry: entry["date"])["bundle"]

    machine_name, config = machine_config(args)
    submit_jobs(
        args.name,
        machine=machine_name,
        machine_overrides=config,
        bundle_path=args.bundle_file,
    )
