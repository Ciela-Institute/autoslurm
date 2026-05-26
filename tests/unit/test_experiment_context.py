import os
import importlib
import json
import pytest

from autoslurm.experiment_context import experiment_context
from autoslurm.save_load_jobs import nearest_bundle_filename, save_bundle
from autoslurm.storage import ensure_storage_dirs, jobs_dir, out_dir, set_storage_root, slurm_dir
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


def test_context_log_prints_newest_out_file_for_bundle(tmp_path, capsys):
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

    experiment_context_app.main([bundle_name, "--log"])
    output = capsys.readouterr().out.strip()

    assert output == "newer log"


def test_context_latest_bundle_log_prints_newest_out_file(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle_name = "latest_bundle_experiment"
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
    second_log.write_text("newest log")
    older = 1_700_000_000
    newer = older + 10
    os.utime(first_log, (older, older))
    os.utime(second_log, (newer, newer))

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main(["--latest", "--log"])
    output = capsys.readouterr().out.strip()

    assert output == "newest log"


def test_context_latest_bundle_log_accepts_numeric_job_selector(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle_name = "latest_bundle_numeric_job"
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
    second_log.write_text("newest log")
    older = 1_700_000_000
    newer = older + 10
    os.utime(first_log, (older, older))
    os.utime(second_log, (newer, newer))

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main(["--latest", "--job", "1", "--log"])
    output = capsys.readouterr().out.strip()

    assert output == "newest log"


def test_context_latest_bundle_job_defaults_to_log(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle_name = "latest_bundle_default_log"
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
    second_log.write_text("default latest log")
    older = 1_700_000_000
    newer = older + 10
    os.utime(first_log, (older, older))
    os.utime(second_log, (newer, newer))

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main(["--latest", "--job", "1"])
    output = capsys.readouterr().out.strip()

    assert output == "default latest log"


def test_context_latest_bundle_job_script_view(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle_name = "latest_bundle_script_view"
    bundle = {
        "analysis": {
            "name": "analysis",
            "script": "python train.py",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        }
    }

    save_bundle(bundle, bundle_name)
    capsys.readouterr()

    _, bundle_date = nearest_bundle_filename(bundle_name)
    slurm_name = name_slurm_script(bundle["analysis"], bundle_date)
    (slurm_dir() / slurm_name).write_text("#!/bin/bash\necho analysis")

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main(["--latest", "--job", "1", "--script"])
    output = capsys.readouterr().out.strip()

    assert "#!/bin/bash" in output
    assert "echo analysis" in output
    assert "status=" not in output


def test_context_log_reports_missing_logs_with_hint(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle_name = "empty_bundle"
    bundle = {
        "analysis": {
            "name": "analysis",
            "script": "python train.py",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        }
    }
    save_bundle(bundle, bundle_name)
    capsys.readouterr()

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main([bundle_name, "--log"])
    output = capsys.readouterr().out.strip()

    assert "No logs found for bundle 'empty_bundle'" in output
    assert "Try `asl sync` or `asl logs --refresh`." in output


def test_context_log_copies_to_clipboard(tmp_path, monkeypatch, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    bundle_name = "clipboard_bundle"
    bundle = {
        "analysis": {
            "name": "analysis",
            "script": "python train.py",
            "slurm": {"time": "00:05:00", "mem": "1G", "cpus_per_task": 1},
        }
    }
    save_bundle(bundle, bundle_name)
    capsys.readouterr()

    log_path = out_dir() / "analysis-1.out"
    log_path.write_text("clipboard log")

    clipboard = {}

    def fake_which(name):
        return "/usr/bin/pbcopy" if name == "pbcopy" else None

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "pbcopy":
            clipboard["text"] = kwargs.get("input", "")
            return type("Result", (), {"returncode": 0})()
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("autoslurm.apps.experiment_context.shutil.which", fake_which)
    monkeypatch.setattr("autoslurm.apps.experiment_context.subprocess.run", fake_run)

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main([bundle_name, "--log", "--clip"])
    output = capsys.readouterr().out.strip()

    assert output == "clipboard log"
    assert clipboard["text"] == "clipboard log"


def test_context_latest_prints_latest_bundle_status(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    (jobs_dir() / "job_a_20250102000000.json").write_text(
        json.dumps({"job_a": {"script": "run-a"}})
    )
    (jobs_dir() / "job_b_20250103000000.json").write_text(
        json.dumps({"job_b": {"script": "run-b"}})
    )

    from autoslurm.apps import experiment_context as experiment_context_app

    experiment_context_app.main(["--latest"])
    output = capsys.readouterr().out.splitlines()

    assert output[0].startswith("job_b ")
    assert output[1].startswith("Use --job <number|name>")
    assert any("name" in line and "status" in line for line in output)
    assert any("job_b" in line and "not_submitted" in line for line in output)


def test_context_refresh_syncs_before_printing(monkeypatch, capsys):
    from autoslurm.apps import experiment_context as experiment_context_app

    seen = {"sync": 0}

    def fake_sync_machine(machine_name=None):
        seen["sync"] += 1
        assert machine_name is None

    monkeypatch.setattr(experiment_context_app, "sync_machine", fake_sync_machine)
    monkeypatch.setattr(experiment_context_app, "bundle_index_context", lambda reference_date=None: "refreshed context")

    experiment_context_app.main(["--refresh"])

    assert seen["sync"] == 1
    assert capsys.readouterr().out.strip() == "refreshed context"
