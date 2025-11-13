from unittest.mock import patch
from autoslurm.job_dependency import (
    update_slurm_with_dependencies,
    dependency_graph,
)
import os


"""
Test dependency graph
"""


def test_dependency_graph_no_dependencies():
    jobs = {"JobA": {}, "JobB": {}}
    graph = dependency_graph(jobs)
    assert graph == {"JobA": [], "JobB": []}


def test_dependency_graph_linear_dependencies():
    jobs = {"JobA": {}, "JobB": {"dependencies": ["JobA"]}}
    graph = dependency_graph(jobs)
    assert graph == {"JobA": ["JobB"], "JobB": []}


def test_dependency_graph_complex_dependencies():
    jobs = {
        "JobA": {},
        "JobB": {"dependencies": ["JobA"]},
        "JobC": {"dependencies": ["JobA", "JobB"]},
    }
    graph = dependency_graph(jobs)
    assert graph == {"JobA": ["JobB", "JobC"], "JobB": ["JobC"], "JobC": []}


def test_dependency_graph_empty_job_list():
    jobs = {}
    graph = dependency_graph(jobs)
    assert graph == {}


"""
Test update_slurm_with_dependencies
"""


# Helper function
def create_temp_slurm_script(tmp_path, script_name, content):
    os.mkdir(tmp_path / "slurm")
    script_path = tmp_path / f"slurm/{script_name}"
    with open(script_path, "w") as f:
        f.write(content)
    return script_path


def test_update_slurm_with_existing_dependency(tmp_path):
    original_script = "#!/bin/bash\n#SBATCH --dependency=afterok:111\n"
    expected_script = "#!/bin/bash\n#SBATCH --dependency=afterok:111:123:456\n"
    script_name = "dummy_job.sh"
    script_path = create_temp_slurm_script(tmp_path, script_name, original_script)

    # Mock load_config to return the path of the temporary directory
    mock_config = {"local": {"path": str(tmp_path)}}
    with patch("autoslurm.job_dependency.load_config", return_value=mock_config):
        update_slurm_with_dependencies(script_name, ["123", "456"])
        with open(script_path, "r") as f:
            content = f.read()
        assert content == expected_script


def test_update_slurm_script_without_dependency(tmp_path):
    original_script = "#!/bin/bash\n#SBATCH --job-name=test_job\n"
    # Dependency directive is inserted after the shebang line
    expected_script = (
        "#!/bin/bash\n"
        + "#SBATCH --dependency=afterok:123:456\n"
        + "#SBATCH --job-name=test_job\n"
    )
    script_name = "dummy_job.sh"
    script_path = create_temp_slurm_script(tmp_path, script_name, original_script)

    # Mock load_config to return the path of the temporary directory
    mock_config = {"local": {"path": str(tmp_path)}}
    with patch("autoslurm.job_dependency.load_config", return_value=mock_config):
        update_slurm_with_dependencies(script_name, ["123", "456"])

        with open(script_path, "r") as f:
            content = f.read()
        assert content == expected_script


def test_update_empty_slurm_script(tmp_path):
    script_name = "dummy_job.sh"
    script_path = create_temp_slurm_script(tmp_path, script_name, "")

    # Mock load_config to return the path of the temporary directory
    mock_config = {"local": {"path": str(tmp_path)}}
    with patch("autoslurm.job_dependency.load_config", return_value=mock_config):
        update_slurm_with_dependencies(script_name, ["123", "456"])

        with open(script_path, "r") as f:
            content = f.read()
        assert content == ""  # Expect no changes as the script is empty


def test_update_non_standard_slurm_script(tmp_path):
    original_script = "Some random content\nAnother line\n"
    script_name = "dummy_job.sh"
    script_path = create_temp_slurm_script(tmp_path, script_name, original_script)

    # Mock load_config to return the path of the temporary directory
    mock_config = {"local": {"path": str(tmp_path)}}
    with patch("autoslurm.job_dependency.load_config", return_value=mock_config):
        update_slurm_with_dependencies(script_name, ["123", "456"])

        with open(script_path, "r") as f:
            content = f.read()
        assert (
            content == original_script
        )  # Expect no changes as the script is non-standard
