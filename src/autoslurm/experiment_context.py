from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from textwrap import dedent
from typing import Iterable, Optional

from .definitions import DATE_FORMAT
from .save_load_jobs import latest_bundle_summaries, load_bundle, nearest_bundle_filename
from .storage import jobs_dir, slurm_dir, out_dir
from .utils import load_config, name_slurm_script, ssh_host_from_config


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
        return _fetch_statuses_locally(job_ids)

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
        return _fetch_statuses_locally(job_ids)

    machine_config = config["machines"].get(machine_name) or config.get(machine_name)
    if machine_config is None:
        return _fetch_statuses_locally(job_ids)

    if not machine_config.get("hostname") and not machine_config.get("hosturl"):
        return _fetch_statuses_locally(job_ids)

    return _fetch_statuses_remotely(job_ids, machine_name, machine_config)


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


def _bundle_summary_lines(desired_date: Optional[datetime] = None) -> list[str]:
    summaries = latest_bundle_summaries(desired_date=desired_date)
    if not summaries:
        return ["No saved bundles found."]
    bundle_width = max(len("bundle"), max(len(entry["bundle"]) for entry in summaries))
    saved_values = [entry["date"].strftime("%Y-%m-%d %H:%M") for entry in summaries]
    saved_width = max(len("saved"), max(len(value) for value in saved_values))
    jobs_width = max(
        len("jobs"),
        max(len(str(entry.get("job_count", len(entry.get("jobs", []))))) for entry in summaries),
    )
    header = (
        f"{'bundle'.center(bundle_width)}  "
        f"{'saved'.center(saved_width)}  "
        f"{'jobs'.center(jobs_width)}"
    )
    lines = [header]
    for entry, saved_value in zip(summaries, saved_values):
        bundle = entry["bundle"].ljust(bundle_width)
        saved = saved_value.ljust(saved_width)
        jobs = str(entry.get("job_count", len(entry.get("jobs", [])))).ljust(jobs_width)
        lines.append(f"{bundle}  {saved}  {jobs}")
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
    jobs, _, bundle_date = load_bundle(bundle_name, desired_date)
    statuses = _job_status_texts(jobs)
    lines = [f"{bundle_name} {bundle_date.isoformat()}"]
    lines.append("Use --job <number|name> to inspect a job.")
    for index, job in enumerate(jobs, start=1):
        job_name = job["name"]
        status = statuses.get(job_name)
        if status is None:
            status = _job_status_text(job)
        job_id = job.get("id")
        job_bits = [f"{index})", job_name, f"status={status}"]
        if job_id is not None:
            job_bits.append(f"id={job_id}")
        lines.append(" ".join(job_bits))
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

    env_command = machine_config.get("env_command", "")
    remote_path = machine_config.get("path", "~/.autoslurm")
    date_arg = bundle_date.strftime(DATE_FORMAT)
    bundle_arg = shlex.quote(bundle_name)
    commands = []
    if env_command:
        commands.append(env_command)
    commands.append(f"cd $(eval echo {shlex.quote(remote_path)})")
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
