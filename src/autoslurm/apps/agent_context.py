from __future__ import annotations

import argparse

from ..context import agent_context


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dump the agent documentation context as a single string."
    )
    args = parser.parse_args()

    context = agent_context()
    print(context)
