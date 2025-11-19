import importlib
import pytest

from autoslurm.experiment_context import experiment_context
from autoslurm.save_load_jobs import nearest_bundle_filename, save_bundle
from autoslurm.storage import out_dir, slurm_dir
from autoslurm.utils import name_slurm_script


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


def test_experiment_context_includes_bundle_and_logs():
    bundle_name = "experiment"
    job = {
        "name": "analysis",
        "script": "python train.py",
        "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
    }

    save_bundle({job["name"]: job}, bundle_name)
    _, bundle_date = nearest_bundle_filename(bundle_name)
    slurm_name = name_slurm_script(job, bundle_date)
    slurm_path = slurm_dir() / slurm_name
    slurm_path.write_text("#!/bin/bash\necho analysis")

    log_path = out_dir() / f"{job['name']}-42.out"
    log_path.write_text("analysis completed")

    context = experiment_context(bundle_name)

    assert f"Bundle '{bundle_name}'" in context
    assert "#!/bin/bash" in context
    assert "analysis completed" in context


def test_experiment_context_fetches_remote_logs(monkeypatch):
    bundle_name = "remote_experiment"
    job = {
        "name": "remote_task",
        "script": "python train.py",
        "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        "machine": "remote_machine",
    }

    save_bundle({job["name"]: job}, bundle_name)

    def fake_fetch(bundle_arg, bundle_date, job_arg, machine_arg):
        assert bundle_arg == bundle_name
        assert job_arg == job["name"]
        assert machine_arg == job["machine"]
        path = out_dir() / f"{job['name']}-fetched.out"
        path.write_text("fetched remote log")
        return [(path, "fetched remote log")], None

    module = importlib.import_module("autoslurm.experiment_context")
    monkeypatch.setattr(module, "_fetch_remote_logs_for_job", fake_fetch)

    context = experiment_context(bundle_name)

    assert "fetched remote log" in context


def test_experiment_context_reports_unstarted_job():
    bundle_name = "pending_experiment"
    job = {
        "name": "pending_task",
        "script": "python train.py",
        "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
    }

    save_bundle({job["name"]: job}, bundle_name)

    context = experiment_context(bundle_name)

    assert "job 'pending_task' has not been submitted yet" in context
