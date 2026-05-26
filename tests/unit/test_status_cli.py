from __future__ import annotations

from datetime import datetime

from autoslurm.apps import status


def test_status_prints_numbered_summary_rows(monkeypatch, capsys):
    monkeypatch.setattr(
        status,
        "latest_bundle_summaries",
        lambda desired_date=None: [
            {"bundle": "older", "date": datetime(2025, 1, 1, 0, 0, 0), "job_count": 1},
            {"bundle": "newer", "date": datetime(2025, 1, 2, 0, 0, 0), "job_count": 2},
        ],
    )
    monkeypatch.setattr(status, "load_bundle", lambda bundle_name, desired_date=None: ([], {}, desired_date))
    monkeypatch.setattr(status, "_job_status_texts", lambda jobs: {})

    status.main([])
    output = capsys.readouterr().out.splitlines()

    assert "idx" in output[0]
    assert output[1].startswith("1")
    assert "newer" in output[1]
    assert output[2].startswith("2")
    assert "older" in output[2]


def test_status_index_selects_bundle_detail(monkeypatch, capsys):
    monkeypatch.setattr(
        status,
        "latest_bundle_summaries",
        lambda desired_date=None: [
            {"bundle": "older", "date": datetime(2025, 1, 1, 0, 0, 0), "job_count": 1},
            {"bundle": "newer", "date": datetime(2025, 1, 2, 0, 0, 0), "job_count": 2},
        ],
    )
    monkeypatch.setattr(status, "bundle_jobs_context", lambda bundle_name, desired_date=None: f"detail:{bundle_name}")

    status.main(["1"])
    output = capsys.readouterr().out.strip()

    assert output == "detail:newer"


def test_status_forwards_reference_date(monkeypatch, capsys):
    seen = {"value": None}
    monkeypatch.setattr(status, "load_bundle", lambda bundle_name, desired_date=None: ([], {}, desired_date))
    monkeypatch.setattr(status, "_job_status_texts", lambda jobs: {})

    def fake_latest_bundle_summaries(desired_date=None):
        seen["value"] = desired_date
        return [{"bundle": "experiment", "date": datetime(2025, 1, 1, 0, 0, 0), "job_count": 1}]

    monkeypatch.setattr(status, "latest_bundle_summaries", fake_latest_bundle_summaries)
    status.main(["--year", "2025", "--month", "1"])
    capsys.readouterr()

    assert seen["value"] is not None
    assert seen["value"].year == 2025
    assert seen["value"].month == 1
