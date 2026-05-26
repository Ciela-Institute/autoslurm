from __future__ import annotations

import argparse
import sys
from typing import Callable

from . import (
    agent_context,
    configuration,
    experiment_context,
    initialize,
    logs,
    schedule,
    status,
    submit,
    sync,
)


ACTION_HELP = {
    "configuration": "Configure machines and storage.",
    "schedule": "Schedule a job or append it to a bundle.",
    "submit": "Submit an existing bundle.",
    "sync": "Pull remote AutoSlurm storage into the local mirror.",
    "initialize": "Create an empty bundle.",
    "status": "Show bundles with saved timestamp and job count.",
    "logs": "Inspect bundle JSON, SLURM scripts, and logs.",
    "agent": "Print the agent documentation context.",
}

ACTION_HANDLERS: dict[str, Callable[[list[str] | None], None]] = {
    "configuration": configuration.main,
    "schedule": schedule.main,
    "submit": submit.main,
    "sync": sync.main,
    "initialize": initialize.main,
    "status": status.main,
    "logs": logs.main,
    "agent": agent_context.main,
}

ACTION_ALIASES = {
    "config": "configuration",
    "stat": "status",
    "context": "logs",
    "experiment-context": "logs",
    "agent-context": "agent",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoslurm",
        description="AutoSlurm command dispatcher.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Available actions:\n"
            + "\n".join(
                f"  {name:<20} {ACTION_HELP[name]}" for name in sorted(ACTION_HELP)
            )
        ),
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=sorted({*ACTION_HANDLERS, *ACTION_ALIASES}),
        help="Action to run.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else list(argv)
    parser = _build_parser()

    if not args:
        parser.print_help()
        return
    if args[0] in {"-h", "--help"}:
        parser.print_help()
        return

    action = ACTION_ALIASES.get(args[0], args[0])
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        parser.error(f"Unknown action '{action}'.")
    handler(args[1:])
