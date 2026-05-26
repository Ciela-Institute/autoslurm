from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..storage import ensure_storage_dirs, storage_root

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for older runtimes
    tomllib = None


CATALOG_FILENAME = "apps_catalog.json"


def _catalog_path() -> Path:
    ensure_storage_dirs()
    return storage_root() / CATALOG_FILENAME


def _load_catalog() -> dict[str, Any]:
    path = _catalog_path()
    if not path.exists():
        return {"repos": []}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"repos": []}


def _save_catalog(payload: dict[str, Any]) -> None:
    _catalog_path().write_text(json.dumps(payload, indent=2, sort_keys=True))


def _scan_pyproject(repo: Path) -> list[dict[str, str]]:
    pyproject = repo / "pyproject.toml"
    if not pyproject.exists():
        return []
    if tomllib is None:
        raise RuntimeError("TOML parser unavailable. Use Python 3.11+ for `asl apps scan`.")
    parsed = tomllib.loads(pyproject.read_text())
    scripts = parsed.get("project", {}).get("scripts", {}) or {}
    entries: list[dict[str, str]] = []
    for name, target in sorted(scripts.items()):
        entries.append(
            {
                "name": str(name),
                "target": str(target),
                "source": "pyproject.project.scripts",
            }
        )
    return entries


def _infer_purpose(app_name: str, target: str) -> str:
    text = f"{app_name} {target}".lower()
    if any(token in text for token in ("status", "inspect", "context", "log", "scan", "list")):
        return "inspection"
    if any(token in text for token in ("submit", "schedule", "slurm", "train", "run")):
        return "job execution"
    if any(token in text for token in ("config", "init", "setup")):
        return "configuration"
    return "general utility"


def _module_file_candidates(repo: Path, module: str) -> list[Path]:
    rel = Path(*module.split(".")).with_suffix(".py")
    return [
        repo / rel,
        repo / "src" / rel,
    ]


def _doc_summary_from_target(repo: Path, target: str) -> str:
    module_name, _, callable_name = target.partition(":")
    if not module_name:
        return ""
    for candidate in _module_file_candidates(repo, module_name):
        if not candidate.exists():
            continue
        try:
            source = candidate.read_text()
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue

        if callable_name:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name:
                    doc = ast.get_docstring(node)
                    if doc:
                        return doc.strip().splitlines()[0]
        module_doc = ast.get_docstring(tree)
        if module_doc:
            return module_doc.strip().splitlines()[0]
    return ""


def _upsert_repo_entry(catalog: dict[str, Any], repo_entry: dict[str, Any]) -> dict[str, Any]:
    repos = catalog.setdefault("repos", [])
    key = repo_entry["repo"]
    for idx, existing in enumerate(repos):
        if existing.get("repo") == key:
            repos[idx] = repo_entry
            return catalog
    repos.append(repo_entry)
    return catalog


def _render_scan_table(repo: Path, apps: list[dict[str, str]]) -> str:
    if not apps:
        return f"repo={repo}\nNo apps found."
    rows: list[dict[str, str]] = []
    for app in apps:
        name = str(app.get("name", ""))
        target = str(app.get("target", ""))
        summary = _doc_summary_from_target(repo, target) or _infer_purpose(name, target)
        rows.append(
            {
                "app": name,
                "purpose": _infer_purpose(name, target),
                "summary": summary,
            }
        )
    headers = ["app", "purpose", "summary"]
    widths = {h: max(len(h), max(len(r[h]) for r in rows)) for h in headers}
    lines = [f"repo={repo}"]
    lines.append("  ".join(h.center(widths[h]) for h in headers))
    lines.extend("  ".join(row[h].ljust(widths[h]) for h in headers) for row in rows)
    return "\n".join(lines)


def _scan_repo(repo_path: str) -> str:
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise FileNotFoundError(f"Repository path not found: {repo}")
    apps = _scan_pyproject(repo)
    now = datetime.now().isoformat(timespec="seconds")
    repo_entry = {
        "repo": str(repo),
        "scanned_at": now,
        "apps": apps,
    }
    catalog = _load_catalog()
    catalog = _upsert_repo_entry(catalog, repo_entry)
    _save_catalog(catalog)
    return _render_scan_table(repo, apps)


def _render_list(catalog: dict[str, Any]) -> str:
    rows: list[dict[str, str]] = []
    for repo_entry in catalog.get("repos", []):
        repo = repo_entry.get("repo", "")
        scanned_at = repo_entry.get("scanned_at", "")
        for app in repo_entry.get("apps", []):
            rows.append(
                {
                    "app": str(app.get("name", "")),
                    "target": str(app.get("target", "")),
                    "repo": repo,
                    "scanned": scanned_at,
                }
            )
    if not rows:
        return "No app catalog entries found. Run `asl apps scan <repo-path>`."

    headers = ["app", "target", "repo", "scanned"]
    widths = {h: max(len(h), max(len(r[h]) for r in rows)) for h in headers}
    lines = ["  ".join(h.center(widths[h]) for h in headers)]
    for row in rows:
        lines.append("  ".join(row[h].ljust(widths[h]) for h in headers))
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan a repo for app entrypoints.")
    parser.add_argument("repo", help="Path to repository root.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    print(_scan_repo(args.repo))
