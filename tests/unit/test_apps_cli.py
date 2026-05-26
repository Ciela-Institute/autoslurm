from __future__ import annotations

from autoslurm.apps import scan as apps
from autoslurm.storage import ensure_storage_dirs, set_storage_root


def test_apps_scan_and_list(tmp_path, capsys):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "sample"',
                "[project.scripts]",
                'train-cli = "sample.train:main"',
                'inspect-cli = "sample.inspect:main"',
            ]
        )
    )
    pkg = repo / "src" / "sample"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "train.py").write_text(
        "\n".join(
            [
                '"""Training app module."""',
                "def main():",
                '    """Run training jobs on cluster."""',
                "    pass",
            ]
        )
    )
    (pkg / "inspect.py").write_text(
        "\n".join(
            [
                "def main():",
                '    """Inspect experiment artifacts and outputs."""',
                "    pass",
            ]
        )
    )

    apps.main([str(repo)])
    scan_output = capsys.readouterr().out
    assert "app" in scan_output
    assert "purpose" in scan_output
    assert "summary" in scan_output
    assert "train-cli" in scan_output
    assert "inspect-cli" in scan_output
    assert "Run training jobs on cluster." in scan_output
    assert "Inspect experiment artifacts and outputs." in scan_output


def test_apps_catalog_is_written(tmp_path):
    set_storage_root(tmp_path / "storage")
    ensure_storage_dirs()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "sample"',
                "[project.scripts]",
                'train-cli = "sample.train:main"',
            ]
        )
    )
    pkg = repo / "src" / "sample"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "train.py").write_text("def main():\n    pass\n")

    apps.main([str(repo)])
    catalog_path = (tmp_path / "storage" / "apps_catalog.json")
    assert catalog_path.exists()
    text = catalog_path.read_text()
    assert "train-cli" in text
