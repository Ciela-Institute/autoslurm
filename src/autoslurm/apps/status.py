from __future__ import annotations

import argparse
from datetime import datetime
from typing import Optional

from ..experiment_context import _job_status_texts, bundle_jobs_context
from ..save_load_jobs import latest_bundle_summaries, load_bundle


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
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Date must be ISO formatted (e.g. 2023-09-01T12:00:00) or use YYYYMMDDHHMMSS."
        ) from exc


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show bundle status summary and inspect a bundle by index."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Optional bundle index (1-based, latest first) or bundle name to inspect.",
    )
    parser.add_argument(
        "--date",
        help="Optional timestamp to target bundles closest to the provided date.",
    )
    parser.add_argument("--year", type=int, help="Reference year, e.g. 2025.")
    parser.add_argument("--month", type=int, help="Reference month, e.g. 1 or 01.")
    parser.add_argument("--day", type=int, help="Reference day of month.")
    parser.add_argument("--hour", type=int, help="Reference hour.")
    parser.add_argument("--minute", type=int, help="Reference minute.")
    parser.add_argument("--second", type=int, help="Reference second.")
    return parser


def _status_rows(reference_date: Optional[datetime]) -> list[dict[str, object]]:
    rows = list(latest_bundle_summaries(reference_date))
    rows.sort(key=lambda entry: entry["date"], reverse=True)
    return rows


def _status_summary_text(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No saved bundles found."

    rendered_rows: list[dict[str, str]] = []
    for index, entry in enumerate(rows, start=1):
        bundle_name = str(entry["bundle"])
        saved_date = entry["date"]
        assert isinstance(saved_date, datetime)
        saved_value = saved_date.strftime("%Y-%m-%d %H:%M")

        try:
            jobs, _, _ = load_bundle(bundle_name, saved_date)
            statuses = _job_status_texts(jobs)
            submitted = sum(1 for job in jobs if job.get("id") is not None)
            completed = sum(1 for job in jobs if statuses.get(job["name"], "UNKNOWN").upper() == "COMPLETED")
            pending = sum(
                1
                for job in jobs
                if statuses.get(job["name"], "UNKNOWN").upper() in {"PENDING", "CONFIGURING"}
            )
            failed = sum(
                1
                for job in jobs
                if statuses.get(job["name"], "UNKNOWN").upper()
                in {
                    "FAILED",
                    "CANCELLED",
                    "TIMEOUT",
                    "NODE_FAIL",
                    "OUT_OF_MEMORY",
                    "PREEMPTED",
                    "BOOT_FAIL",
                    "DEADLINE",
                    "REVOKED",
                }
            )
            job_count = len(jobs)
        except Exception:
            job_count = int(entry.get("job_count", 0))
            submitted = completed = pending = failed = 0

        rendered_rows.append(
            {
                "idx": str(index),
                "bundle": bundle_name,
                "saved": saved_value,
                "jobs": str(job_count),
                "submitted": str(submitted),
                "completed": str(completed),
                "pending": str(pending),
                "failed": str(failed),
            }
        )

    headers = ["idx", "bundle", "saved", "jobs", "submitted", "completed", "pending", "failed"]
    widths = {key: max(len(key), max(len(row[key]) for row in rendered_rows)) for key in headers}
    lines = ["  ".join(key.center(widths[key]) for key in headers)]
    lines.extend("  ".join(row[key].ljust(widths[key]) for key in headers) for row in rendered_rows)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    reference_date = _build_reference_date(
        args.date,
        args.year,
        args.month,
        args.day,
        args.hour,
        args.minute,
        args.second,
    )
    rows = _status_rows(reference_date)

    if args.target is None:
        print(_status_summary_text(rows))
        return

    if args.target.isdigit():
        selected = int(args.target)
        if selected < 1 or selected > len(rows):
            parser.error(f"Bundle index '{args.target}' is out of range.")
        row = rows[selected - 1]
        bundle_name = str(row["bundle"])
        bundle_date = row["date"]
        assert isinstance(bundle_date, datetime)
        print(bundle_jobs_context(bundle_name, bundle_date))
        return

    print(bundle_jobs_context(args.target, reference_date))
