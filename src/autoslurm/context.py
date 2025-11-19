from pathlib import Path
from textwrap import dedent
from typing import Iterable


AGENT_FOLDER = Path(__file__).resolve().parent.parent / "agent"


def _read_files(pattern: str) -> Iterable[str]:
    for path in AGENT_FOLDER.glob(pattern):
        if path.is_file():
            yield path.read_text()


def agent_context() -> str:
    """
    Load the agent helpers (project map, examples, etc.) as a single chunk of text.
    """
    parts = []
    for section_name in ("project_map.md", "examples.md"):
        contents = AGENT_FOLDER / section_name
        if contents.exists():
            parts.append(f"## {section_name}\n{contents.read_text()}")
    for dynamic in _read_files("*.md"):
        if dynamic.strip():
            parts.append(dynamic)
    return dedent("\n\n".join(parts)).strip()
