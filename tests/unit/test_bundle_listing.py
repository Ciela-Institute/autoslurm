from __future__ import annotations

import importlib
import json
from datetime import datetime

import pytest

from autoslurm.apps import experiment_context
from autoslurm.save_load_jobs import latest_bundle_summaries, list_saved_bundles
from autoslurm.storage import ensure_storage_dirs, jobs_dir, set_storage_root


def _write_bundle(filename: str, jobs: dict) -> None:
    path = jobs_dir() / filename
    path.write_text(json.dumps(jobs))


@pytest.fixture(autouse=True)
def mock_load_config(monkeypatch, tmp_path):
    config = {
        "machines": {
            "local": {
                "path": str(tmp_path / "storage"),
            }
        },
        "default_machine": "local",
    }
    monkeypatch.setattr("autoslurm.save_load_jobs.load_config", lambda: config)
    monkeypatch.setattr("autoslurm.utils.load_config", lambda: config)
    yield config


def test_list_saved_bundles_orders_by_date(tmp_path):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    _write_bundle("job_a_20250102000000.json", {"job_a": {"script": "run-a"}})
    _write_bundle("job_b_20250103000000.json", {"job_b": {"script": "run-b"}})
    _write_bundle("job_c_20250105000000.json", {"job_c": {"script": "run-c"}})

    entries = list_saved_bundles(
        desired_date=datetime(2025, 1, 3, 0, 0, 0),
    )

    assert [entry["bundle"] for entry in entries] == ["job_b", "job_a", "job_c"]


def test_latest_bundle_summaries_keep_only_most_recent_snapshot(tmp_path):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    _write_bundle("job_a_20250102000000.json", {"job_a": {"script": "run-a"}})
    _write_bundle("job_a_20250106000000.json", {"job_a": {"script": "run-a2"}})
    _write_bundle("job_b_20250103000000.json", {"job_b": {"script": "run-b"}})
    _write_bundle("job_c_20250105000000.json", {"job_c": {"script": "run-c"}})

    entries = latest_bundle_summaries(datetime(2025, 1, 3, 0, 0, 0))

    assert [entry["bundle"] for entry in entries] == ["job_b", "job_c", "job_a"]
    assert entries[-1]["date"] == datetime(2025, 1, 6, 0, 0, 0)


def test_context_list_mode_accepts_partial_date_components(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    _write_bundle("job_a_20250102000000.json", {"job_a": {"script": "run-a"}})
    _write_bundle("job_b_20250103000000.json", {"job_b": {"script": "run-b"}})
    _write_bundle("job_c_20250105000000.json", {"job_c": {"script": "run-c"}})

    experiment_context.main(["--view", "--year", "2025", "--month", "1"])
    output = capsys.readouterr().out

    lines = output.splitlines()
    assert lines[0].startswith("bundle")
    assert all("path=" not in line for line in lines)


def test_context_with_no_args_shows_help(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    experiment_context.main([])
    output = capsys.readouterr().out

    assert "usage:" in output
    assert "--view" in output


def test_context_view_lists_saved_bundles(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    _write_bundle("job_a_20250102000000.json", {"job_a": {"script": "run-a"}})
    _write_bundle("job_b_20250103000000.json", {"job_b": {"script": "run-b"}})

    experiment_context.main(["--view"])
    output = capsys.readouterr().out

    lines = output.splitlines()
    assert "bundle" in lines[0]
    assert "saved" in lines[0]
    assert "jobs" in lines[0]
    assert "path=" not in output
    assert "2025-01-02 00:00" in lines[1] or "2025-01-03 00:00" in lines[1]
    assert lines[0].index("jobs") != lines[1].index(lines[1].split()[-1])
    assert "1" in lines[1]


def test_context_job_status_is_compact(tmp_path, monkeypatch, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle = {
        "analysis": {
            "name": "analysis",
            "script": "run-analysis",
            "id": "12345",
            "machine": "local",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        }
    }
    _write_bundle("experiment_20250102000000.json", bundle)

    def fake_run(cmd, *args, **kwargs):
        class Result:
            returncode = 0
            stdout = "12345|RUNNING\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    experiment_context.main(["experiment", "--job", "1"])
    output = capsys.readouterr().out

    assert "analysis" in output
    assert "status=RUNNING" in output
    assert "path=" not in output


def test_context_job_status_batches_remote_queries(tmp_path, monkeypatch, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle = {
        "analysis": {
            "name": "analysis",
            "script": "run-analysis",
            "id": "11111",
            "machine": "remote",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        },
        "cleanup": {
            "name": "cleanup",
            "script": "run-cleanup",
            "id": "22222",
            "machine": "remote",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        },
    }
    _write_bundle("experiment_20250102000000.json", bundle)

    config = {
        "machines": {
            "remote": {
                "hostname": "remote.example.org",
            }
        },
        "default_machine": "remote",
    }
    module = importlib.import_module("autoslurm.experiment_context")
    monkeypatch.setattr(module, "load_config", lambda: config)
    monkeypatch.setattr("autoslurm.utils.load_config", lambda: config)

    seen = {"ssh": 0}

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "ssh":
            seen["ssh"] += 1

            class Result:
                returncode = 0
                stdout = (
                    "11111|RUNNING\n"
                    "22222|PENDING\n"
                    "__AUTOSLURM_SPLIT__\n"
                    "11111|RUNNING\n"
                    "22222|PENDING\n"
                )
                stderr = ""

            return Result()
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("subprocess.run", fake_run)

    experiment_context.main(["experiment", "--list"])
    output = capsys.readouterr().out

    assert seen["ssh"] == 1
    assert "analysis" in output
    assert "cleanup" in output
    assert "status=RUNNING" in output
    assert "status=PENDING" in output


def test_context_job_script_view_is_compact(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle = {
        "analysis": {
            "name": "analysis",
            "script": "run-analysis",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        }
    }
    _write_bundle("experiment_20250102000000.json", bundle)
    (tmp_path / "storage" / "slurm" / "analysis_20250102000000.sh").write_text(
        "#!/bin/bash\necho analysis"
    )

    experiment_context.main(["experiment", "--job", "analysis", "--script"])
    output = capsys.readouterr().out

    assert "analysis" in output
    assert "#!/bin/bash" in output
    assert "path=" not in output
