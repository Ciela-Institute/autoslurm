from autoslurm.context import agent_context, agent_context_paths


def test_agent_context_includes_key_docs():
    context = agent_context()
    assert "01_context_overview.md" in context
    assert "01_simple_job.sh" in context


def test_agent_context_paths_include_examples():
    paths = agent_context_paths()
    assert any("01_simple_job.sh" in str(path) for path in paths)


def test_agent_context_sections_filter():
    context = agent_context(sections=["09_task_inspect.md"])
    assert "Task: Inspect Experiments" in context
    assert "Task: Plan & Schedule Jobs" not in context


def test_agent_context_sections_keyword():
    context = agent_context(sections=["Schedule"])
    assert "Task: Plan & Schedule Jobs" in context
    assert "Task: Inspect Experiments" not in context


def test_schedule_context_contains_expected_sections():
    context = agent_context(sections=["10_task_schedule.md", "12_task_acp_reference.md"])
    assert "Task: Plan & Schedule Jobs" in context
    assert "ACP Reference" in context
    assert "Task: Inspect Experiments" not in context


def test_schedule_context_keywords_only():
    context = agent_context(sections=["10_task_schedule", "acp_reference"])
    assert "Task: Plan & Schedule Jobs" in context
    assert "ACP Reference" in context
    assert "Task: Inspect Experiments" not in context
