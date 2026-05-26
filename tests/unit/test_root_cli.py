from __future__ import annotations

from autoslurm.apps import root


def test_root_dispatches_action_arguments(monkeypatch):
    calls = []

    def fake_schedule(argv=None):
        calls.append(argv)

    monkeypatch.setitem(root.ACTION_HANDLERS, "schedule", fake_schedule)

    root.main(["schedule", "--time", "00:05:00", "--mem", "1G"])

    assert calls == [["--time", "00:05:00", "--mem", "1G"]]


def test_root_accepts_action_aliases(monkeypatch):
    calls = []

    def fake_inspect(argv=None):
        calls.append(("inspect", argv))

    def fake_agent(argv=None):
        calls.append(("agent", argv))

    def fake_configuration(argv=None):
        calls.append(("configuration", argv))

    def fake_status(argv=None):
        calls.append(("status", argv))

    def fake_scan(argv=None):
        calls.append(("scan", argv))

    monkeypatch.setitem(root.ACTION_HANDLERS, "inspect", fake_inspect)
    monkeypatch.setitem(root.ACTION_HANDLERS, "agent", fake_agent)
    monkeypatch.setitem(root.ACTION_HANDLERS, "configuration", fake_configuration)
    monkeypatch.setitem(root.ACTION_HANDLERS, "status", fake_status)
    monkeypatch.setitem(root.ACTION_HANDLERS, "scan", fake_scan)

    root.main(["experiment-context", "--date", "20250101"])
    root.main(["context", "--latest"])
    root.main(["agent-context", "--sections", "10_task_schedule.md"])
    root.main(["config", "--summary"])
    root.main(["stat", "--date", "20250101"])
    root.main(["scan", "/tmp/repo"])

    assert calls == [
        ("inspect", ["--date", "20250101"]),
        ("inspect", ["--latest"]),
        ("agent", ["--sections", "10_task_schedule.md"]),
        ("configuration", ["--summary"]),
        ("status", ["--date", "20250101"]),
        ("scan", ["/tmp/repo"]),
    ]


def test_root_help_lists_actions(capsys):
    root.main(["--help"])
    captured = capsys.readouterr()

    assert "autoslurm" in captured.out
    assert "schedule" in captured.out
    assert "submit" in captured.out
    assert "configuration" in captured.out
    assert "inspect" in captured.out
    assert "status" in captured.out
    assert "scan" in captured.out
    assert "agent" in captured.out
