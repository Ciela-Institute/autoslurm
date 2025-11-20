This folder contains curated guidance for agent use:

- `04_project_map.md` describes how the Python API + CLI interact with job definitions.
- `schema.json` captures the JSON format of bundles for validation/reference.
- `agent/examples/` holds reusable shell scripts illustrating common submission patterns.
- `05_cli_reference.md` lists CLI commands and flags relevant to agents.
- `06_resource_rules.md` documents SLURM resource expectations.
- `07_acp_actions.md` summarizes the ACP actions and references `acp_action.y`.
- `02_llm_interface.md` summarizes LLM context tooling and outlines the ACP/tools roadmap.
- `09_task_inspect.md`, `10_task_schedule.md`, `11_task_submit_monitor.md`, and `12_task_acp_reference.md` distill the relevant pieces for specific agent tasks.
- The new `autoslurm-agent-context` CLI (and `agent_context()` API) print the
  entire agent folder as a single payload.
