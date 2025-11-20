import json

import pytest

from autoslurm.acp import execute_acp
from autoslurm.save_load_jobs import schedule_job
from autoslurm.storage import jobs_dir, out_dir


@pytest.fixture(autouse=True)
def mock_save_load_config(monkeypatch, isolate_storage):
    config = {
        "machines": {
            "local": {
                "path": str(isolate_storage),
            }
        },
        "default_machine": "local",
    }
    monkeypatch.setattr("autoslurm.save_load_jobs.load_config", lambda: config)
    yield


def _create_job(bundle_name, job_name="acp-job"):
    job = {
        "name": job_name,
        "script": "python train.py",
        "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
    }
    schedule_job(job, bundle_name=bundle_name)
    return job


def test_execute_acp_schedule_creates_bundle():
    bundle = "acp_schedule"
    request = {
        "action": "schedule",
        "bundle": bundle,
        "job": {
            "name": "scheduled",
            "script": "python script.py",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        },
    }

    response = execute_acp(request)

    assert response["status"] == "success"
    result = response["result"]
    assert result["bundle"] == bundle
    assert result["file"].startswith(str(jobs_dir()))
    assert json.loads(open(result["file"]).read())


def test_execute_acp_list_returns_metadata():
    bundle = "acp_list"
    _create_job(bundle, job_name="first")
    _create_job(bundle, job_name="second")

    response = execute_acp({"action": "list_experiments", "bundle": bundle})

    assert response["status"] == "success"
    result = response["result"]
    assert result
    assert result[0]["bundle"] == bundle
    assert "first" in result[0]["jobs"] or "second" in result[0]["jobs"]


def test_execute_acp_context_includes_out_log():
    bundle = "acp_context"
    job = _create_job(bundle)
    log_path = out_dir() / f"{job['name']}-42.out"
    log_path.write_text("done")

    response = execute_acp({"action": "inspect_experiments", "bundle": bundle})

    assert response["status"] == "success"
    assert job["name"] in response["result"]
    assert "done" in response["result"]


def test_execute_acp_agent_docs_action():
    response = execute_acp(
        {"action": "gather_context", "sections": ["09_task_inspect.md"]}
    )

    assert response["status"] == "success"
    assert "Task: Inspect Experiments" in response["result"]


def test_execute_acp_gather_context_task():
    response = execute_acp({"action": "gather_context", "task": "schedule"})

    assert response["status"] == "success"
    assert "Task: Plan & Schedule Jobs" in response["result"]
