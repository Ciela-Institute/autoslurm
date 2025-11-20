# Task: Inspect Experiments

Agents that need to understand what a job bundle contains should focus on these sources:

- `03_experiment_context.md` explains `autoslurm-experiment-context` / `autoslurm.experiment_context.experiment_context(...)`, which emit (1) the saved bundle JSON, (2) the rendered SLURM scripts, and (3) the `.out` logs tied to each job. Running this tool with `--date` or passing `desired_date` lets you target a specific timestamped bundle.
- In `04_project_map.md` the Python function is listed under “Python surface area,” and the generated scripts/logs are described near the section that covers `$AUTOSLURM/jobs`, `/slurm`, and `/out`. Use this to track where files live.
- Reference `07_acp_actions.md` plus `acp_action.y` to find the `inspect_experiments` action, which requires `bundle` and optional `date`, and returns the same concatenated text.
- When you need remote logs that may live on another machine, rely on the agent context helper for the ACP: `execute_acp({"action":"inspect_experiments", ...})` triggers the same fetch logic that the CLI uses.

Quick summary:

1. Prefetch docs with `autoslurm-agent-context` (or the `gather_context` ACP) so you know the bucket names and CLI semantics.
2. Use `inspect_experiments` to read `jobs/<bundle>_YYYYMMDDHHMMSS.json`, the associated SLURM script, and `.out` logs all in one shot.
3. If the job ran remotely, the ACP reruns `autoslurm-experiment-context` on the remote host via SSH and pulls the logs into `out/`, so rerunning the same `inspect_experiments` action later will reflect new outputs.
4. Use `autoslurm-agent-context --sections 09_task_inspect.md 12_task_acp_reference.md` (or `execute_acp({"action":"gather_context","sections":["09_task_inspect.md","12_task_acp_reference.md"]})`) when you only need the inspect-relevant docs in your prompt; alternatively, pass `task: "inspect_experiments"` to `gather_context` so it selects the relevant sections automatically.
