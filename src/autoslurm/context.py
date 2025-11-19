from pathlib import Path
from textwrap import dedent
from typing import List


AGENT_FOLDER = Path(__file__).resolve().parent.parent.parent / "agent"


def _ordered_agent_files() -> List[Path]:
    files = [path for path in AGENT_FOLDER.rglob("*") if path.is_file()]

    def sort_key(path: Path) -> tuple[int, str]:
        name = path.name
        order = 999
        if "_" in name:
            prefix = name.split("_", 1)[0]
            if prefix.isdigit():
                order = int(prefix)
        return order, str(path)

    return sorted(files, key=sort_key)


def _render_file(path: Path) -> str:
    relative = path.relative_to(AGENT_FOLDER)
    if path.suffix.lower() == ".md":
        return f"## {relative}\n{path.read_text()}"
    lang = path.suffix.lstrip(".")
    fence = lang if lang else ""
    return f"## {relative}\n```{fence}\n{path.read_text()}```"


def agent_context() -> str:
    """
    Load the agent helpers (project map, examples, etc.) as a single chunk of text.
    """
    parts = [_render_file(path) for path in _ordered_agent_files()]
    return dedent("\n\n".join(parts)).strip()


def agent_context_paths() -> List[Path]:
    """
    Return a list of agent files that contribute to the context dump.
    """
    return _ordered_agent_files()
