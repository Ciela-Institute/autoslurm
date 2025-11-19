from __future__ import annotations

import argparse
from datetime import datetime
from typing import Optional

from ..experiment_context import experiment_context


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dump the job, script, and log context for a bundle."
    )
    parser.add_argument(
        "bundle",
        help="Bundle name to inspect (e.g., the name passed to autoslurm-schedule).",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        help="Optional timestamp to target the bundle closest to the provided date.",
    )
    args = parser.parse_args()

    context = experiment_context(args.bundle, args.date)
    print(context)
