# Task: Submit & Monitor

When it’s time to execute scheduled jobs and watch their logs, these references help:

- `04_project_map.md` and `03_experiment_context.md` note the submission flow: `autoslurm-submit <bundle>` invokes `submit_jobs`, which renders scripts, transfers them if remote, calls `sbatch`, and updates the bundle with job IDs.
- Track dependencies using `autoslurm.job_dependency.update_slurm_with_dependencies` (discussed in the project map) so downstream jobs wait for upstream IDs before sbatch.
- After submission, `inspect_experiments` (ACP) or rerunning `autoslurm-experiment-context` returns the `.out` logs that the scheduler writes under `$AUTOSLURM/out` (and the remote fetch logic brings remote logs back into that directory).
- `07_acp_actions.md` plus `acp_action.y` explain `list_experiments` (enumerate bundle files), so you can detect the latest bundle of a given name before submitting or monitoring.
- The agent context summary (`gather_context`) is handy for reminding the agent which directories exist and which helper to call for submission.

LLM prompt tip: include `submit_jobs` into the prompt by referencing the `autoslurm.job_runner` section in `04_project_map.md`, describe what `autoslurm-submit` prints, and have it emit `{"action":"list_experiments","bundle":...}` followed by `{"action":"inspect_experiments", ...}` to monitor outputs. Use `autoslurm-agent-context --sections 11_task_submit_monitor.md 12_task_acp_reference.md` (or `{"action":"gather_context","task":"schedule"}`/`"list_experiments"`) to load just the submit guidance and ACP reference into the prompt before issuing these calls.
