import os
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

    assert f"Job or bundle '{bundle_name}'" in context
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


def test_context_latest_log_prints_newest_out_file(tmp_path, capsys):
    from autoslurm.storage import ensure_storage_dirs, set_storage_root

    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle_name = "latest_log_experiment"
    bundle = {
        "analysis": {
            "name": "analysis",
            "script": "python train.py",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        },
        "cleanup": {
            "name": "cleanup",
            "script": "python cleanup.py",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        },
    }

    save_bundle(bundle, bundle_name)
    capsys.readouterr()

    first_log = out_dir() / "analysis-1.out"
    second_log = out_dir() / "cleanup-2.out"
    first_log.write_text("older log")
    second_log.write_text("newer log")
    older = 1_700_000_000
    newer = older + 10
    os.utime(first_log, (older, older))
    os.utime(second_log, (newer, newer))

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main(["--latest-log"])
    output = capsys.readouterr().out.strip()

    assert output == "newer log"
