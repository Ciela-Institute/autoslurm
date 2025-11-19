from autoslurm.context import agent_context, agent_context_paths


def test_agent_context_includes_key_docs():
    context = agent_context()
    assert "01_context_overview.md" in context
    assert "01_simple_job.sh" in context


def test_agent_context_paths_include_examples():
    paths = agent_context_paths()
    assert any("01_simple_job.sh" in str(path) for path in paths)
