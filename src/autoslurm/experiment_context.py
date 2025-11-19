from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Iterable, Optional

from .definitions import DATE_FORMAT
from .save_load_jobs import nearest_bundle_filename
from .storage import jobs_dir, slurm_dir, out_dir
from .utils import load_config, name_slurm_script, ssh_host_from_config


__all__ = ["experiment_context"]


def _job_entries(bundle: dict) -> Iterable[tuple[str, dict]]:
    for job_key, job_value in bundle.items():
        job = dict(job_value)
        job.setdefault("name", job_key)
        yield job["name"], job


def _read_text(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    text = path.read_text()
    return text.rstrip()


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
        ["ssh", hostname, remote_command], capture_output=True, text=True
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
        f"## Bundle '{bundle_name}'",
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
