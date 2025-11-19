from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .definitions import DATE_FORMAT
from .context import agent_context
from .experiment_context import experiment_context
from .save_load_jobs import schedule_job
from .storage import ensure_storage_dirs, jobs_dir

ACTION_FILE = Path(__file__).resolve().parent / "acp_action.y"


def _load_action_definitions() -> Dict[str, Dict[str, Any]]:
    try:
        with open(ACTION_FILE, "r") as f:
            actions = json.load(f)
    except Exception:  # pragma: no cover - config should be valid
        return {}
    return {action["name"]: action for action in actions}


ACTION_DEFINITIONS = _load_action_definitions()


__all__ = ["execute_acp", "list_bundles", "action_definitions"]


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, DATE_FORMAT)
        except ValueError:
            raise ValueError(
                f"Date '{value}' is not ISO-8601 or '{DATE_FORMAT}' formatted"
            )


def list_bundles(bundle_name: str) -> List[Dict[str, Any]]:
    ensure_storage_dirs()
    entries = []
    for filename in sorted(jobs_dir().glob(f"{bundle_name}_*.json")):
        try:
            date_text = filename.stem.split("_")[-1]
            date = datetime.strptime(date_text, DATE_FORMAT)
        except ValueError:
            continue
        jobs = []
        try:
            with open(filename, "r") as file:
                jobs = list(json.load(file).keys())
        except (json.JSONDecodeError, OSError):
            jobs = []
        entries.append(
            {
                "bundle": bundle_name,
                "date": date.isoformat(),
                "path": str(filename),
                "jobs": jobs,
            }
        )
    return entries


def execute_acp(acl: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an Agent Communication Protocol request.

    The `acl` dict must include an `"action"` key (one of `context`, `list`,
    `schedule`). Each action defines its own parameters. The return value is a
    dict with keys `status` and either `result` or `message`.
    """
    action = acl.get("action")
    if not action:
        return {"status": "error", "message": "Missing action"}

    try:
        if action == "context":
            bundle = acl["bundle"]
            date = _parse_date(acl.get("date"))
            payload = experiment_context(bundle, date)
            return {"status": "success", "result": payload}
        if action == "agent_docs":
            payload = agent_context()
            return {"status": "success", "result": payload}
        if action == "list":
            bundle = acl["bundle"]
            result = list_bundles(bundle)
            return {"status": "success", "result": result}
        if action == "schedule":
            job = acl["job"]
            bundle = acl.get("bundle") or job.get("bundle")
            if bundle is None:
                raise ValueError("bundle must be specified when scheduling a job")
            append = bool(acl.get("append"))
            _, file_path = schedule_job(job, bundle_name=bundle, append=append)
            return {
                "status": "success",
                "result": {
                    "bundle": bundle,
                    "file": str(file_path),
                },
            }
        return {"status": "error", "message": f"Unknown action '{action}'"}
    except Exception as exc:  # pragma: no cover - bubble up errors
        return {"status": "error", "message": str(exc)}


def action_definitions() -> Dict[str, Dict[str, Any]]:
    """Return the ACP action metadata."""
    return ACTION_DEFINITIONS
