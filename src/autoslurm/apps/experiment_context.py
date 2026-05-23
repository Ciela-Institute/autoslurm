from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from ..experiment_context import (
    bundle_index_context,
    bundle_jobs_context,
    experiment_context,
    latest_log_context,
    job_context,
)


DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%Y%m%d%H%M%S",
    "%Y%m%d",
)


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Date must be ISO formatted (e.g. 2023-09-01T12:00:00) or use YYYYMMDDHHMMSS."
        )


def _build_reference_date(
    date: Optional[str],
    year: Optional[int],
    month: Optional[int],
    day: Optional[int],
    hour: Optional[int],
    minute: Optional[int],
    second: Optional[int],
) -> Optional[datetime]:
    if date is not None:
        return _parse_date(date)

    if any(value is not None for value in (year, month, day, hour, minute, second)):
        now = datetime.now()
        return datetime(
            year=year if year is not None else now.year,
            month=month if month is not None else 1,
            day=day if day is not None else 1,
            hour=hour if hour is not None else 0,
            minute=minute if minute is not None else 0,
            second=second if second is not None else 0,
        )

    return None


def _add_date_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--date",
        help="Optional timestamp to target the bundle closest to the provided date.",
    )
    parser.add_argument("--year", type=int, help="Reference year, e.g. 2025.")
    parser.add_argument("--month", type=int, help="Reference month, e.g. 1 or 01.")
    parser.add_argument("--day", type=int, help="Reference day of month.")
    parser.add_argument("--hour", type=int, help="Reference hour.")
    parser.add_argument("--minute", type=int, help="Reference minute.")
    parser.add_argument("--second", type=int, help="Reference second.")


def _resolve_reference_date(args: argparse.Namespace) -> Optional[datetime]:
    return _build_reference_date(
        args.date,
        args.year,
        args.month,
        args.day,
        args.hour,
        args.minute,
        args.second,
    )


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "bundle",
        nargs="?",
        help="Bundle name to inspect (e.g., the name passed to autoslurm-schedule).",
    )
    _add_date_arguments(parser)
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the latest saved bundle per name.",
    )
    parser.add_argument(
        "--job",
        help="Select a specific job inside the chosen bundle.",
    )
    parser.add_argument(
        "--script",
        action="store_true",
        help="Include the rendered SLURM script for the selected job.",
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="Include output logs for the selected job.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Include the SLURM status for the selected job.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print the full bundle context dump.",
    )
    parser.add_argument(
        "--latest-log",
        action="store_true",
        help="Print the newest .out file for the selected bundle, or the newest bundle overall if no bundle is given.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dump the context for a job or bundle."
    )
    _add_common_arguments(parser)
    return parser


def main(argv=None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    if argv in (["-h"], ["--help"]):
        parser.print_help()
        return
    if not argv:
        print(bundle_index_context())
        return
    args = parser.parse_args(argv)

    reference_date = _resolve_reference_date(args)

    if args.full and not args.bundle:
        parser.error("--full requires a bundle name.")
    if args.job and not args.bundle:
        parser.error("--job requires a bundle name.")
    if (args.script or args.logs or args.status) and not args.job:
        parser.error("--script, --logs, and --status require --job.")
    if args.latest_log and any(
        (args.list, args.job, args.script, args.logs, args.status, args.full)
    ):
        parser.error("--latest-log cannot be combined with other context output flags.")

    if args.latest_log:
        print(latest_log_context(args.bundle, reference_date))
        return
    if args.list or not args.bundle:
        print(bundle_index_context(reference_date))
        return

    if args.full:
        print(experiment_context(args.bundle, reference_date))
        return

    if args.job:
        include_status = args.status or not (args.script or args.logs)
        print(
            job_context(
                args.bundle,
                args.job,
                reference_date,
                include_script=args.script,
                include_logs=args.logs,
                include_status=include_status,
            )
        )
        return

    if args.script or args.logs or args.status:
        parser.error("--script, --logs, and --status require --job.")

    print(bundle_jobs_context(args.bundle, reference_date))
