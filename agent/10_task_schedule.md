# Task: Plan & Schedule Jobs

To plan a new workload, gather the relevant CLI usage, resource guidance, and ACP action:

- `04_project_map.md` and `05_cli_reference.md` describe `autoslurm-schedule`, the `--bundle`, `--append`, `--dependencies`, and SLURM resource flags. The Python API `autoslurm.schedule_job` takes the same fields plus `script_args`, `pre_commands`, and `slurm` directives.
- `06_resource_rules.md` explains preferred CPU/GPU/memory/walltime ratios, array/job constraints, and accounting practices—the rules you should obey when generating the SLURM payload.
- `07_acp_actions.md` and `acp_action.y` define the `schedule` action (expecting `bundle`, `job`, optional `append`). Crafting an ACP payload with those keys mirrors calling the CLI/Python helper.
- `01_context_overview.md` reminds you that bundles live under `$AUTOSLURM/jobs` and that duplicate job names are renamed (`_001`, `_002`, …).

Prompt tip: give the LLM the excerpts above plus the descriptions of the `slurm` dict fields from `04_project_map.md` so it knows which flags to request (time, mem, cpus_per_task, gres, tasks, array). Call `autoslurm-agent-context --sections 10_task_schedule.md 12_task_acp_reference.md` (or the `gather_context` action with those sections or `task:"schedule"`) to keep the prompt concise before scheduling, then use `execute_acp({"action":"schedule", ...})`. 
