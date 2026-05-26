from __future__ import annotations

import json
import shlex
import subprocess
import re
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from textwrap import dedent
from typing import Iterable, Optional

from .definitions import DATE_FORMAT
from .save_load_jobs import latest_bundle_summaries, load_bundle, nearest_bundle_filename
from .storage import jobs_dir, slurm_dir, out_dir
from .utils import (
    activation_command_from_config,
    load_config,
    name_slurm_script,
    ssh_host_from_config,
)


__all__ = [
    "experiment_context",
    "bundle_index_context",
    "bundle_jobs_context",
    "latest_log_context",
    "job_context",
]


def _job_entries(bundle: dict) -> Iterable[tuple[str, dict]]:
    for job_key, job_value in bundle.items():
        job = dict(job_value)
        job.setdefault("name", job_key)
        yield job["name"], job


def _resolve_job_selector(jobs: list[dict], selector: str) -> dict:
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(jobs):
            return jobs[index - 1]
        raise KeyError(f"Job index '{selector}' is out of range.")
    job = next((item for item in jobs if item["name"] == selector), None)
    if job is None:
        raise KeyError(f"Job '{selector}' not found.")
    return job


def _read_text(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    text = path.read_text()
    return text.rstrip()


def _parse_status_lines(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        job_id, state = line.split("|", 1)
        job_id = job_id.strip()
        state = state.strip()
        if not job_id or not state:
            continue
        statuses[job_id] = state.split()[0]
    return statuses


def _parse_job_field_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        job_id, value = line.split("|", 1)
        job_id = job_id.strip()
        value = value.strip()
        if not job_id or not value:
            continue
        values[job_id] = value
    return values


def _fetch_statuses_locally(job_ids: list[str]) -> dict[str, str]:
    if not job_ids:
        return {}

    query = ",".join(job_ids)
    statuses: dict[str, str] = {}
    commands = (
        ["squeue", "-h", "-j", query, "-o", "%i|%T"],
        ["sacct", "-n", "-X", "-P", "-j", query, "-o", "JobIDRaw,State"],
    )
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            continue
        statuses.update(_parse_status_lines(result.stdout or result.stderr or ""))
    return statuses


def _fetch_statuses_remotely(
    job_ids: list[str], machine_name: str, machine_config: dict
) -> dict[str, str]:
    if not job_ids:
        return {}

    query = ",".join(job_ids)
    try:
        hostname = ssh_host_from_config(machine_config, machine_name)
    except AttributeError:
        return {}

    remote_script = "\n".join(
        [
            f"squeue -h -j {shlex.quote(query)} -o '%i|%T' 2>/dev/null || true",
            "printf '__AUTOSLURM_SPLIT__\\n'",
            f"sacct -n -X -P -j {shlex.quote(query)} -o JobIDRaw,State 2>/dev/null || true",
        ]
    )
    result = subprocess.run(
        ["ssh", *shlex.split(hostname), f"bash -lc {shlex.quote(remote_script)}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}

    status_lines = (result.stdout or result.stderr or "").split("__AUTOSLURM_SPLIT__")
    statuses: dict[str, str] = {}
    for text in status_lines:
        statuses.update(_parse_status_lines(text))
    return statuses


def _fetch_statuses_for_job_ids(
    job_ids: list[str], machine_name: Optional[str]
) -> dict[str, str]:
    if not job_ids:
        return {}

    if machine_name is None:
        return _fetch_statuses_locally(job_ids)

    try:
        config = load_config()
    except EnvironmentError:
        return {}

    machine_config = config["machines"].get(machine_name) or config.get(machine_name)
    if machine_config is None:
        return {}

    return _fetch_statuses_remotely(job_ids, machine_name, machine_config)


def _fetch_time_left_locally(job_ids: list[str]) -> dict[str, str]:
    if not job_ids:
        return {}
    query = ",".join(job_ids)
    result = subprocess.run(
        ["squeue", "-h", "-j", query, "-o", "%i|%L"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}
    return _parse_job_field_lines(result.stdout or result.stderr or "")


def _fetch_time_left_remotely(
    job_ids: list[str], machine_name: str, machine_config: dict
) -> dict[str, str]:
    if not job_ids:
        return {}
    query = ",".join(job_ids)
    try:
        hostname = ssh_host_from_config(machine_config, machine_name)
    except AttributeError:
        return {}

    remote_script = f"squeue -h -j {shlex.quote(query)} -o '%i|%L' 2>/dev/null || true"
    result = subprocess.run(
        ["ssh", *shlex.split(hostname), f"bash -lc {shlex.quote(remote_script)}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}
    return _parse_job_field_lines(result.stdout or result.stderr or "")


def _fetch_time_left_for_job_ids(
    job_ids: list[str], machine_name: Optional[str]
) -> dict[str, str]:
    if not job_ids:
        return {}
    if machine_name is None:
        return _fetch_time_left_locally(job_ids)
    try:
        config = load_config()
    except EnvironmentError:
        return {}

    machine_config = config["machines"].get(machine_name) or config.get(machine_name)
    if machine_config is None:
        return {}
    return _fetch_time_left_remotely(job_ids, machine_name, machine_config)


def _job_status_text(job: dict) -> str:
    job_id = job.get("id")
    if job_id is None:
        return "not_submitted"
    statuses = _fetch_statuses_for_job_ids([str(job_id)], job.get("machine"))
    return statuses.get(str(job_id), "UNKNOWN")


def _job_status_texts(jobs: list[dict]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    by_machine: dict[Optional[str], list[dict]] = defaultdict(list)
    for job in jobs:
        by_machine[job.get("machine")].append(job)

    for machine_name, machine_jobs in by_machine.items():
        job_ids = [str(job["id"]) for job in machine_jobs if job.get("id") is not None]
        machine_statuses = _fetch_statuses_for_job_ids(job_ids, machine_name)
        for job in machine_jobs:
            job_id = job.get("id")
            if job_id is None:
                statuses[job["name"]] = "not_submitted"
            else:
                statuses[job["name"]] = machine_statuses.get(str(job_id), "UNKNOWN")
    return statuses


def _job_remaining_times(jobs: list[dict], statuses: dict[str, str]) -> dict[str, str]:
    remaining: dict[str, str] = {job["name"]: "-" for job in jobs}
    by_machine: dict[Optional[str], list[dict]] = defaultdict(list)
    for job in jobs:
        by_machine[job.get("machine")].append(job)

    for machine_name, machine_jobs in by_machine.items():
        running = [
            job
            for job in machine_jobs
            if job.get("id") is not None and statuses.get(job["name"], "UNKNOWN").upper() == "RUNNING"
        ]
        if not running:
            continue
        job_ids = [str(job["id"]) for job in running]
        left = _fetch_time_left_for_job_ids(job_ids, machine_name)
        for job in running:
            remaining[job["name"]] = left.get(str(job["id"]), "UNKNOWN")
    return remaining


def _bundle_summary_lines(desired_date: Optional[datetime] = None) -> list[str]:
    summaries = latest_bundle_summaries(desired_date=desired_date)
    if not summaries:
        return ["No saved bundles found."]
    rows: list[dict[str, str]] = []
    for entry in summaries:
        bundle_name = entry["bundle"]
        saved_value = entry["date"].strftime("%Y-%m-%d %H:%M")

        try:
            jobs, _, _ = load_bundle(bundle_name, entry["date"])
        except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError):
            job_count = entry.get("job_count", 0)
            row = {
                "bundle": bundle_name,
                "saved": saved_value,
                "jobs": str(job_count),
                "submitted": "-",
                "running": "-",
                "completed": "-",
                "pending": "-",
                "failed": "-",
            }
            rows.append(row)
            continue

        statuses = _job_status_texts(jobs)
        submitted = sum(1 for job in jobs if job.get("id") is not None)

        completed = 0
        running = 0
        pending = 0
        failed = 0
        for job in jobs:
            state = statuses.get(job["name"], "UNKNOWN").upper()
            if state == "COMPLETED":
                completed += 1
            elif state == "RUNNING":
                running += 1
            elif state in {"PENDING", "CONFIGURING"}:
                pending += 1
            elif state in {
                "FAILED",
                "CANCELLED",
                "TIMEOUT",
                "NODE_FAIL",
                "OUT_OF_MEMORY",
                "PREEMPTED",
                "BOOT_FAIL",
                "DEADLINE",
                "REVOKED",
            }:
                failed += 1

        row = {
            "bundle": bundle_name,
            "saved": saved_value,
            "jobs": str(len(jobs)),
            "submitted": str(submitted),
            "running": str(running),
            "completed": str(completed),
            "pending": str(pending),
            "failed": str(failed),
        }
        rows.append(row)

    headers = ["bundle", "saved", "jobs", "submitted", "running", "completed", "pending", "failed"]
    widths = {
        key: max(len(key), max(len(row[key]) for row in rows))
        for key in headers
    }
    header = "  ".join(key.center(widths[key]) for key in headers)
    lines = [header]
    for row in rows:
        lines.append("  ".join(row[key].ljust(widths[key]) for key in headers))
    return lines


def bundle_index_context(desired_date: Optional[datetime] = None) -> str:
    return "\n".join(_bundle_summary_lines(desired_date=desired_date))


def _load_bundle_snapshot(
    bundle_name: str, desired_date: Optional[datetime] = None
) -> tuple[dict, datetime, Path]:
    job_file, bundle_date = nearest_bundle_filename(bundle_name, desired_date)
    bundle_path = jobs_dir() / job_file
    bundle_text = bundle_path.read_text()
    bundle_data = json.loads(bundle_text)
    return bundle_data, bundle_date, bundle_path


def bundle_jobs_context(bundle_name: str, desired_date: Optional[datetime] = None) -> str:
    def _requested_time(job: dict) -> str:
        slurm = job.get("slurm") or {}
        value = slurm.get("time")
        return str(value) if value else "-"

    def _requested_gpus(job: dict) -> str:
        slurm = job.get("slurm") or {}
        gres = slurm.get("gres")
        if not gres:
            return "0"
        text = str(gres)
        match = re.search(r"gpu(?::[^:,]+)?:(\d+)", text)
        if match:
            return match.group(1)
        if "gpu" in text.lower():
            return "1"
        return "0"

    def _dependencies_text(job: dict) -> str:
        deps = job.get("dependencies")
        if not deps:
            return "-"
        if isinstance(deps, (list, tuple)):
            return ",".join(str(dep) for dep in deps)
        return str(deps)

    jobs, _, bundle_date = load_bundle(bundle_name, desired_date)
    statuses = _job_status_texts(jobs)
    remaining = _job_remaining_times(jobs, statuses)
    lines = [f"{bundle_name} {bundle_date.isoformat()}"]
    lines.append("Use --job <number|name> to inspect a job.")
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for job in jobs:
        job_name = job["name"]
        status = statuses.get(job_name)
        if status is None:
            status = _job_status_text(job)
        job_id = job.get("id")
        rows.append(
            (
                str(job_id) if job_id is not None else "-",
                job_name,
                _requested_time(job),
                _requested_gpus(job),
                _dependencies_text(job),
                remaining.get(job_name, "-"),
                status,
            )
        )

    id_width = max(len("id"), max(len(row[0]) for row in rows))
    name_width = max(len("name"), max(len(row[1]) for row in rows))
    time_width = max(len("time"), max(len(row[2]) for row in rows))
    gpus_width = max(len("gpus"), max(len(row[3]) for row in rows))
    deps_width = max(len("dependencies"), max(len(row[4]) for row in rows))
    remaining_width = max(len("remaining"), max(len(row[5]) for row in rows))
    status_width = max(len("status"), max(len(row[6]) for row in rows))
    lines.append(
        f"{'id'.center(id_width)}  "
        f"{'name'.center(name_width)}  "
        f"{'time'.center(time_width)}  "
        f"{'gpus'.center(gpus_width)}  "
        f"{'dependencies'.center(deps_width)}  "
        f"{'remaining'.center(remaining_width)}  "
        f"{'status'.center(status_width)}"
    )
    for job_id, job_name, time_text, gpus_text, deps_text, remaining_text, status in rows:
        deps_rendered = deps_text.center(deps_width) if deps_text == "-" else deps_text.ljust(deps_width)
        lines.append(
            f"{job_id.ljust(id_width)}  "
            f"{job_name.ljust(name_width)}  "
            f"{time_text.ljust(time_width)}  "
            f"{gpus_text.ljust(gpus_width)}  "
            f"{deps_rendered}  "
            f"{remaining_text.ljust(remaining_width)}  "
            f"{status.ljust(status_width)}"
        )
    return "\n".join(lines)


def job_context(
    bundle_name: str,
    job_name: str,
    desired_date: Optional[datetime] = None,
    include_script: bool = False,
    include_logs: bool = False,
    include_status: bool = True,
) -> str:
    jobs, _, bundle_date = load_bundle(bundle_name, desired_date)
    job = _resolve_job_selector(jobs, job_name)

    lines = [f"{bundle_name} {bundle_date.isoformat()}", f"{job['name']}"]
    if include_status:
        status = _job_status_text(job)
        job_id = job.get("id")
        status_line = f"status={status}"
        if job_id is not None:
            status_line += f" id={job_id}"
        lines.append(status_line)

    if include_script:
        slurm_name = name_slurm_script(job, bundle_date)
        script_path = slurm_dir() / slurm_name
        if script_path.exists():
            lines.append("script:")
            lines.append(_read_text(script_path) or "")
        else:
            lines.append(f"script missing: {slurm_name}")

    if include_logs:
        logs, error = _collect_out_logs(job_name, bundle_name, bundle_date, job.get("machine"))
        if logs:
            for log_path, content in logs:
                lines.append(f"log {log_path.name}:")
                lines.append(content)
        elif error:
            lines.append(f"log error: {error}")
        else:
            lines.append("logs: none")

    return "\n".join(line for line in lines if line is not None)


def _parse_remote_logs(text: str, job_name: str) -> list[tuple[str, str]]:
    logs = []
    current_job: Optional[str] = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("### Job '"):
            pieces = line.split("'")
            if len(pieces) >= 2:
                current_job = pieces[1]
            i += 1
            continue
        if (
            current_job == job_name
            and line.startswith("#### Out log")
            and "`" in line
            and line.count("`") >= 2
        ):
            start = line.find("`") + 1
            end = line.rfind("`")
            filename = line[start:end]
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and lines[i].strip() == "```":
                i += 1
                content_lines = []
                while i < len(lines) and lines[i].strip() != "```":
                    content_lines.append(lines[i])
                    i += 1
                logs.append((filename, "\n".join(content_lines).rstrip()))
            continue
        i += 1
    return logs


def _fetch_remote_logs_for_job(
    bundle_name: str, bundle_date: datetime, job_name: str, machine_name: str
) -> tuple[list[tuple[Path, str]], Optional[str]]:
    try:
        config = load_config()
    except EnvironmentError as exc:
        return [], str(exc)

    machine_config = config["machines"].get(machine_name)
    if machine_config is None:
        return [], f"Machine '{machine_name}' not found in configuration."

    if not machine_config.get("hostname") and not machine_config.get("hosturl"):
        return [], None

    env_command = activation_command_from_config(machine_config)
    remote_path = machine_config.get("path", "~/.autoslurm")
    date_arg = bundle_date.strftime(DATE_FORMAT)
    bundle_arg = shlex.quote(bundle_name)
    commands = []
    if env_command:
        commands.append(env_command)
    if remote_path == "~":
        cd_target = "$HOME"
    elif isinstance(remote_path, str) and remote_path.startswith("~/"):
        cd_target = "$HOME/" + shlex.quote(remote_path[2:])
    else:
        cd_target = shlex.quote(remote_path)
    commands.append(f"cd {cd_target}")
    commands.append(
        f"autoslurm-experiment-context {bundle_arg} --date {shlex.quote(date_arg)}"
    )
    remote_command = " && ".join(commands)

    try:
        hostname = ssh_host_from_config(machine_config, machine_name)
    except AttributeError as exc:
        return [], str(exc)

    result = subprocess.run(
        ["ssh", *shlex.split(hostname), remote_command], capture_output=True, text=True
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        return [], f"Remote command failed: {message}"

    parsed_logs = _parse_remote_logs(result.stdout, job_name)
    stored = []
    for filename, content in parsed_logs:
        log_path = out_dir() / filename
        log_path.write_text(content)
        stored.append((log_path, content))
    return stored, None


def _collect_out_logs(
    job_name: str,
    bundle_name: str,
    bundle_date: datetime,
    job_machine: Optional[str],
) -> tuple[list[tuple[Path, str]], Optional[str]]:
    logs = []
    for log_path in sorted(out_dir().glob(f"{job_name}-*.out")):
        content = _read_text(log_path)
        if content is None:
            continue
        logs.append((log_path, content))
    if logs:
        return logs, None
    if job_machine is None:
        return [], None
    fetched_logs, error = _fetch_remote_logs_for_job(
        bundle_name, bundle_date, job_name, job_machine
    )
    return fetched_logs, error


def _latest_out_log_for_bundle(
    bundle_name: str, desired_date: Optional[datetime] = None
) -> tuple[Optional[str], Optional[str]]:
    jobs, _, bundle_date = load_bundle(bundle_name, desired_date)
    latest: Optional[tuple[float, str, str, str]] = None
    errors: list[str] = []

    for job in jobs:
        job_name = job["name"]
        logs, error = _collect_out_logs(
            job_name, bundle_name, bundle_date, job.get("machine")
        )
        if error:
            errors.append(error)
            continue
        for log_path, content in logs:
            try:
                timestamp = log_path.stat().st_mtime
            except OSError:
                timestamp = bundle_date.timestamp()
            candidate = (timestamp, job_name, log_path.name, content)
            if latest is None or candidate > latest:
                latest = candidate

    if latest is None:
        if errors:
            return None, errors[0]
        return None, None
    return latest[3], None


def _latest_out_log_for_job(
    bundle_name: str,
    job_name: str,
    desired_date: Optional[datetime] = None,
) -> tuple[Optional[str], Optional[str]]:
    jobs, _, bundle_date = load_bundle(bundle_name, desired_date)
    try:
        job = _resolve_job_selector(jobs, job_name)
    except KeyError as exc:
        return None, f"{exc}. Try `asl sync` or `asl logs --refresh`."

    job_name = job["name"]
    logs, error = _collect_out_logs(job_name, bundle_name, bundle_date, job.get("machine"))
    if not logs:
        if error is not None:
            return None, error
        return None, None

    latest_log = max(
        logs,
        key=lambda item: item[0].stat().st_mtime if item[0].exists() else 0.0,
    )
    return latest_log[1], None


def _latest_out_log_in_storage() -> tuple[Optional[str], Optional[str]]:
    latest: Optional[tuple[float, Path]] = None
    for log_path in out_dir().glob("*.out"):
        try:
            timestamp = log_path.stat().st_mtime
        except OSError:
            continue
        if latest is None or timestamp > latest[0]:
            latest = (timestamp, log_path)

    if latest is None:
        return None, None

    content = _read_text(latest[1])
    if content is None:
        return None, f"Unable to read latest log file '{latest[1].name}'."
    return content, None


def _latest_bundle_jobs_context(desired_date: Optional[datetime] = None) -> str:
    summaries = latest_bundle_summaries(desired_date=desired_date)
    if not summaries:
        return "No saved bundles found."
    bundle_name = summaries[0]["bundle"]
    return bundle_jobs_context(bundle_name, desired_date)


def latest_log_context(
    bundle_name: Optional[str] = None,
    desired_date: Optional[datetime] = None,
    job_name: Optional[str] = None,
) -> str:
    if bundle_name is None:
        content, error = _latest_out_log_in_storage()
        if content is not None:
            return content
        if error is not None:
            return f"{error}. Try `asl sync` or `asl logs --refresh`."
        return "No logs found. Try `asl sync` or `asl logs --refresh`."

    if job_name is not None:
        content, error = _latest_out_log_for_job(bundle_name, job_name, desired_date)
    else:
        content, error = _latest_out_log_for_bundle(bundle_name, desired_date)
    if content is not None:
        return content
    if error is not None:
        if job_name is not None:
            return (
                f"No logs found for job '{job_name}' in bundle '{bundle_name}': {error}. "
                f"Try `asl sync` or `asl logs --refresh`."
            )
        return (
            f"No logs found for bundle '{bundle_name}': {error}. "
            f"Try `asl sync` or `asl logs --refresh`."
        )
    return (
        (
            f"No logs found for job '{job_name}' in bundle '{bundle_name}'. "
            if job_name is not None
            else f"No logs found for bundle '{bundle_name}'. "
        )
        + "Try `asl sync` or `asl logs --refresh`."
    )


def latest_bundle_status_context(desired_date: Optional[datetime] = None) -> str:
    return _latest_bundle_jobs_context(desired_date)


def experiment_context(bundle_name: str, desired_date: Optional[datetime] = None) -> str:
    """
    Dump a bundle's job definition, slurm scripts, and output logs for agent consumption.

    Args:
        bundle_name: The name of the bundle to inspect.
        desired_date: Optional datetime to target the bundle closest to that date.
    """
    job_file, bundle_date = nearest_bundle_filename(bundle_name, desired_date)
    bundle_path = jobs_dir() / job_file
    bundle_text = bundle_path.read_text()
    bundle_data = json.loads(bundle_text)

    parts = []
    header_lines = [
        f"## Job or bundle '{bundle_name}'",
        f"- path: {bundle_path}",
        f"- saved: {bundle_date.isoformat()}",
        "### Jobs JSON",
        "```json",
        bundle_text.rstrip(),
        "```",
    ]
    parts.append("\n".join(header_lines))

    for job_name, job in _job_entries(bundle_data):
        slurm_name = name_slurm_script(job, bundle_date)
        script_path = slurm_dir() / slurm_name
        parts.append(f"### Job '{job_name}'")
        if script_path.exists():
            parts.append(f"#### SLURM script `{slurm_name}`")
            parts.append("```bash")
            parts.append(_read_text(script_path) or "")
            parts.append("```")
        else:
            parts.append(
                f"#### SLURM script `{slurm_name}` (missing at {script_path})"
            )

        logs, error = _collect_out_logs(
            job_name, bundle_name, bundle_date, job.get("machine")
        )
        if logs:
            for log_path, content in logs:
                parts.append(f"#### Out log `{log_path.name}`")
                parts.append("```")
                parts.append(content)
                parts.append("```")
        elif error:
            parts.append(
                f"#### Out logs (unable to fetch logs for job '{job_name}': {error})"
            )
        else:
            if job.get("id") is None:
                parts.append(
                    f"#### Out logs (job '{job_name}' has not been submitted yet)"
                )
            else:
                parts.append(
                    f"#### Out logs (no files found for job '{job_name}' despite job ID {job['id']})"
                )

    return dedent("\n\n".join(parts)).strip()
