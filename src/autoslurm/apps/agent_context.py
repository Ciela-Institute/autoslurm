from __future__ import annotations

import argparse

from ..context import agent_context


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dump the agent documentation context as a single string."
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        help="Optional list of agent filenames or substrings to include.",
    )
    args = parser.parse_args()

    context = agent_context(sections=args.sections)
    print(context)
