from __future__ import annotations

import argparse
import shutil
import sys
import subprocess
from datetime import datetime
from typing import Optional

from ..experiment_context import (
    bundle_index_context,
    bundle_jobs_context,
    experiment_context,
    latest_bundle_status_context,
    latest_log_context,
    job_context,
)
from ..save_load_jobs import latest_bundle_summaries
from ..sync import sync_machine


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


def _copy_to_clipboard(text: str) -> None:
    if shutil.which("pbcopy") is not None:
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        return
    if shutil.which("wl-copy") is not None:
        subprocess.run(["wl-copy"], input=text, text=True, check=True)
        return
    if shutil.which("xclip") is not None:
        subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=True)
        return
    if shutil.which("xsel") is not None:
        subprocess.run(["xsel", "--clipboard", "--input"], input=text, text=True, check=True)
        return
    raise RuntimeError(
        "No clipboard utility found. Install pbcopy, wl-copy, xclip, or xsel to use --clipboard."
    )


def _emit(text: str, copy_to_clipboard: bool = False) -> None:
    print(text)
    if copy_to_clipboard:
        _copy_to_clipboard(text)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "bundle",
        nargs="?",
        help="Bundle name to inspect (e.g., the name passed to autoslurm-schedule).",
    )
    parser.add_argument(
        "--view",
        "-v",
        action="store_true",
        help="List the latest saved bundle per name.",
    )
    parser.add_argument(
        "--latest",
        "-l",
        action="store_true",
        help="Use the latest saved bundle.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Sync the configured default machine before printing logs.",
    )
    parser.add_argument(
        "--clipboard",
        "--clip",
        action="store_true",
        help="Copy the printed output to the clipboard.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List jobs in the selected bundle.",
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
        help="Print the full bundle log and context dump.",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Print the latest .out file for the selected bundle or latest bundle.",
    )
    _add_date_arguments(parser)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect logs for a job or bundle."
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
        parser.print_help()
        return
    args = parser.parse_args(argv)

    reference_date = _resolve_reference_date(args)

    if args.full and not args.bundle:
        parser.error("--full requires a bundle name.")
    if args.job and not (args.bundle or args.latest):
        parser.error("--job requires a bundle name or --latest.")
    if (args.script or args.logs or args.status) and not args.job:
        parser.error("--script, --logs, and --status require --job.")
    if args.latest and any((args.view, args.list, args.full)):
        parser.error("--latest cannot be combined with other logs output flags.")
    if args.log and any((args.view, args.list, args.script, args.logs, args.status, args.full)):
        parser.error("--log cannot be combined with other logs output flags.")
    if args.log and not (args.bundle or args.latest):
        parser.error("--log requires a bundle name or --latest.")

    if args.refresh:
        sync_machine()

    if args.latest:
        latest = latest_bundle_summaries(reference_date)
        if not latest:
            message = "No saved bundles found."
            if args.log or args.job is not None:
                message += " Try `asl sync` or `asl logs --refresh`."
            _emit(message, args.clipboard)
            return
        bundle_name = latest[0]["bundle"]
        if args.job is not None:
            if args.script or args.logs or args.status or args.full:
                include_status = args.status or not (args.script or args.logs)
                _emit(
                    job_context(
                        bundle_name,
                        args.job,
                        reference_date,
                        include_script=args.script,
                        include_logs=args.logs,
                        include_status=include_status,
                    ),
                    args.clipboard,
                )
                return
            _emit(
                latest_log_context(bundle_name, reference_date, args.job),
                args.clipboard,
            )
            return
        if args.log:
            _emit(
                latest_log_context(bundle_name, reference_date, args.job),
                args.clipboard,
            )
            return
        _emit(bundle_jobs_context(latest[0]["bundle"], reference_date), args.clipboard)
        return
    if args.view or (args.list and not args.bundle):
        _emit(bundle_index_context(reference_date), args.clipboard)
        return

    if args.list:
        _emit(bundle_jobs_context(args.bundle, reference_date), args.clipboard)
        return

    if args.log:
        _emit(latest_log_context(args.bundle, reference_date, args.job), args.clipboard)
        return

    if args.full:
        _emit(experiment_context(args.bundle, reference_date), args.clipboard)
        return

    if args.job:
        include_status = args.status or not (args.script or args.logs)
        _emit(
            job_context(
                args.bundle,
                args.job,
                reference_date,
                include_script=args.script,
                include_logs=args.logs,
                include_status=include_status,
            ),
            args.clipboard,
        )
        return

    if args.script or args.logs or args.status:
        parser.error("--script, --logs, and --status require --job.")

    if args.bundle is None:
        _emit(bundle_index_context(reference_date), args.clipboard)
        return

    _emit(bundle_jobs_context(args.bundle, reference_date), args.clipboard)
