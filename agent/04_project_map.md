# Agent Project Map

This document collects the canonical entry points, data flows, and workflows
that autonomous agents need when they orchestrate AutoSlurm.  It assumes the
reader has little tribal knowledge about SLURM clusters but still needs to
reason about scheduling, submission, and post-run inspection.

## What Agents Can Do With AutoSlurm

- **Schedule and submit compute jobs** through either the CLI or the Python API.
- **Inspect bundle JSONs** inside `$AUTOSLURM/jobs` to understand what work is
  pending or has already run.
- **Update machine configuration** when credentials, accounts, or virtual
  environments change.
- **Assemble pipelines** by wiring dependencies between jobs within a bundle.
- **Trace experiments end-to-end** by running `autoslurm-experiment-context`,
  which brings back the bundle, SLURM scripts, and `.out` logs (local or remote).

## Python API usage

### Scheduling jobs

Use `autoslurm.schedule_job(job, bundle_name, append=False)` to write job
definitions into the internal storage. A job dict includes:

- `name`: unique identifier for the job.
- `script`: the application entry point or script name to run.
- `script_args`: dict of CLI arguments parsed from the target script (`--arg=value` style).
- `slurm`: dict of SBATCH directives (`time`, `mem`, `cpus_per_task`, `gres`, etc.).
- `dependencies`: optional list of job names this job depends on.
- `pre_commands`: optional list of shell commands to run before the job.

Example job:

```python
from autoslurm.save_load_jobs import schedule_job

job = {
    "name": "analysis",
    "script": "stats-pipeline",
    "script_args": {
        "input": "results.csv",
        "alpha": 0.05,
        "output_dir": "my_project/results/analysis/run_001",
    },
    "slurm": {"time": "00:45:00", "mem": "4G", "cpus_per_task": 2},
}

schedule_job(job, bundle_name="analytics", append=True)
```

`append=True` adds the job to an existing bundle (module writes to `jobs/<bundle>_*.json`). Omitting append creates a new bundle file.

If `job["script"]` is a path ending in `.py`, AutoSlurm treats it as `python path` and derives the name from the stem, mimicking the CLI path handling. You may still override via `job["name"]`; duplicates get `_001`, `_002` suffixes.

### Naming jobs

When you call `schedule_job`, the `job` dict can include a `name`. If you omit it, AutoSlurm defaults to the value of `script`. When you append to a bundle, it detects duplicates and renames the job (e.g., `job`, `job_001`, `job_002`) so every entry stays unique. If you need a particular identity for retries or extra metadata, set `job["name"]` explicitly before scheduling and AutoSlurm will keep it as-is unless it conflicts with an existing entry in that bundle.

### Submitting jobs

Call `autoslurm.submit_jobs(bundle_name, machine=<machine_name>, machine_overrides=...)` once all jobs are staged. Pass the machine name stored in `~/.autoslurmconfig` (defaults to the configured default), and optionally override the env/SLURM details or SSH info via `machine_overrides`.

Dependencies are embedded in the job structure (via the `dependencies` key). AutoSlurm rewrites the generated SLURM scripts with proper `#SBATCH --dependency` lines before submission.

## CLI usage

### Scheduling via `autoslurm-schedule`

- `autoslurm-schedule <script>` schedules a job or appends it to a bundle. It introspects `<script>` (or a registered entry point) by running `--help` and parsing the available CLI arguments.
- Application arguments follow the SLURM options; AutoSlurm collects everything it doesn't recognize and stores it in the job definition.
- Use `--bundle <name>` to group multiple jobs, `--append` to add to an existing bundle, `--dependencies <job1> <job2>` to declare prerequisites, and `--pre-commands` to execute shell commands before the main script.
- SLURM flags (e.g., `--time`, `--mem`, `--gres`, `--cpus_per_task`) specify resource requests.
- Use `--submit` to schedule and immediately submit the bundle, optionally with `--machine` to target a named machine from the config.
- AutoSlurm derives the job name from the script name unless you pass `--job-name`. When you append multiple jobs that share the same name, AutoSlurm renames the duplicates by appending `_001`, `_002`, etc., so every entry in the bundle remains unique without manual ID tracking.
- If you pass a `.py` filename (relative or absolute) instead of a registered entry point, AutoSlurm automatically prefixes the invocation with `python ` and derives the job name from the script basename, matching the Python API behavior.

### Path policy for result directories

- For arguments like `output_dir`, agents should emit a **project-relative path** that includes the project root folder (for example `substructure_lens/results/...`).
- Do not hard-code machine-specific absolute prefixes (for example `/lustre...`, `/scratch...`) in job payloads.
- AutoSlurm should resolve relative output paths against the target machine's configured results base (for example `results_root`) at script rendering time.
- Absolute output paths are allowed only when a user explicitly requests a fixed location.

Example command:

```bash
autoslurm-schedule train-model \
  --bundle nightly-training \
  --time 06:00:00 --gres gpu:1 --cpus_per_task 2 --mem 16G \
  --data-path /shared/datasets/train.json \
  --epochs 40 --lr 5e-4 --seed 42
```

### Submitting via `autoslurm-submit`

- After scheduling (possibly jobs), run `autoslurm-submit <bundle>` to dispatch the jobs either locally or remotely.
- You can override machine parameters (hostname/hosturl/username/key_path/env_command/slurm_account) via CLI flags when the stored configuration is insufficient.
- The CLI uploads the generated SLURM scripts, runs `sbatch`, and tracks the returned job IDs inside the bundle JSON.

### Handling dependencies & bundles

- Each job has a unique name; you specify the dependencies via the job unique names; AutoSlurm automatically rewrites the SLURM script with `--dependency=afterok:<parent_ids>` so you don’t need to manage job IDs yourself.
- Bundles are JSON files in the internal storage. Add jobs with `--append` or the Python `schedule_job` helper, then submit once all dependencies are captured.

## Architectural overview

```
┌──────────────────────┐    ┌─────────────────────────────┐
│ autoslurm.apps.* CLI │    │ autoslurm.save_load_jobs    │
│ schedule/submit/...  │──▶ │ schedule_job / load_bundle  │
└──────────┬───────────┘    └──────────────┬──────────────┘
           │                               │
           │ job JSON bundles              │ (jobs/<name>_*.json)
           ▼                               ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│ autoslurm.job_runner │    │ autoslurm.job_to_slurm      │
│ submit_jobs          │──▶ │ create_slurm_script         │
└──────────┬───────────┘    └──────────────┬──────────────┘
           │ updates dependencies          │ writes *.sh under slurm/
           ▼                               ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│ autoslurm.job_dep    │    │ autoslurm.run_slurm         │
│ update_slurm_with…   │◀── │ run_slurm_local/remote      │
└──────────────────────┘    └─────────────────────────────┘
```

Everything hinges on these directories inside the configured `$AUTOSLURM` path:

- `jobs/` – persisted JSON bundles (input + metadata).
- `slurm/` – rendered bash scripts (one per job).
- `out/` – `.out` logs generated by the scheduler (pulled remotely when needed).
- `results/`, `data/`, `models/` – user-owned assets that jobs often read/write.

## CLI entry points

| Command | Module | Intent | Notes |
| --- | --- | --- | --- |
| `autoslurm-configuration` | `autoslurm.apps.configuration` | Create or edit `~/.autoslurmconfig`, materialize folders locally/remotely. | Also sets `AUTOSLURM` env vars via `.bashrc`. |
| `autoslurm-initialize <name>` | `autoslurm.apps.initialize` | Create an empty bundle JSON so later jobs can append. | Calls `save_bundle({}, name)`. |
| `autoslurm-schedule <script>` | `autoslurm.apps.schedule` | Validate script arguments (via `<script>-cli`), persist job(s), optionally submit immediately. | Accepts SLURM args, machine overrides, dependencies, pre-commands. |
| `autoslurm-submit <bundle>` | `autoslurm.apps.submit` | Load the latest bundle matching `<bundle>_*` and call `submit_jobs`. | Can point at remote machines via `--machine` or inline SSH params. |
| `autoslurm-experiment-context <bundle>` | `autoslurm.apps.experiment_context` | Dump the bundle JSON, rendered SLURM scripts, and matching `.out` logs (optional `--date`). | Designed for agents to reason about experiments (remotely fetches logs). |
| `autoslurm-agent-context` | `autoslurm.apps.agent_context` | Print every agent doc/script as one string so downstream tools can consume the guidance, examples, and schema in a single call. |

## Python surface area

| Function | Location | Description |
| --- | --- | --- |
| `schedule_job(job, bundle_name=None, append=False)` | `autoslurm.save_load_jobs` | Persist a single job dict. Creates or appends to `<bundle>_YYYYMMDDhhmmss.json`. |
| `save_bundle(bundle_dict, name, append=False)` | `autoslurm.save_load_jobs` | Persist multiple jobs at once. |
| `load_bundle(name)` | `autoslurm.save_load_jobs` | Returns `jobs`, `dependencies`, `date` for the latest bundle. |
| `submit_jobs(name, machine=None, machine_overrides=None, date=None)` | `autoslurm.job_runner` | Converts bundle → SLURM scripts → `sbatch` (local or remote). Specify a named machine from the config (`machine`) and/or overrides for env/slurm credentials. |
| `create_slurm_script(job, date, machine_config)` | `autoslurm.job_to_slurm` | Renders the `#!/bin/bash` file with headers, env export, pre-commands, and CLI args. |
| `run_slurm_locally(slurm_name)` / `run_slurm_remotely(slurm_name, machine_config)` | `autoslurm.run_slurm` | Execute `sbatch` and capture the job ID. |
| `update_slurm_with_dependencies(slurm_name, job_ids)` | `autoslurm.job_dependency` | Inject `#SBATCH --dependency=afterok:` entries after upstream jobs complete. |
| `experiment_context(bundle_name, desired_date=None)` | `autoslurm.experiment_context` | Returns a single concatenated string (bundle JSON + SLURM scripts + logs, fetching remote `.out` files if needed) that agents can ingest directly. |
| `execute_acp(payload)` | `autoslurm.acp` | Parse a minimal ACP payload (`action`, `bundle`, `job`, etc.) and route requests to context/list/scheduling helpers so tools have one entry point. |

Agents can import these helpers directly (`import autoslurm`) when they need tighter control than the CLI provides.

## Configuration & state

- **Global config** – `~/.autoslurmconfig` (see `autoslurm.definitions.CONFIG_FILE_PATH`). Contains machine entries keyed by human-friendly names plus the mandatory `local` section. Each entry includes `path`, `env_command`, and `slurm_account`; remote entries may also set `hostname`, `hosturl`, `username`, and `key_path`.
- **Result root mapping** – machine configs may define a results base (for example `results_root`) used to convert relative `script_args["output_dir"]` values into absolute remote paths during SLURM script generation.
- **Runtime environment** – each configured path hosts subdirectories (`data/`, `models/`, `results/`, `slurm/`, `jobs/`, `out/`). The configuration CLI ensures they exist locally and remotely.
- **Bundles** – JSON schema roughly equals:

```json
{
  "job_name": {
    "name": "job_name",
    "script": "train-model",
    "script_args": {...},
    "dependencies": ["preprocess"],
    "pre-commands": ["mkdir -p /scratch/tmp"],
    "slurm": {"time": "02:00:00", "gres": "gpu:1"}
  }
}
```
- **SLURM scripts** – stored under `$AUTOSLURM/slurm/<job_name_timestamp>.sh` and reference the same `script_args` so they can be regenerated or amended.

## Typical agent tasks

1. **Inspect queued work** – list `jobs/<bundle>_*.json`, parse with Python’s `json` module, or call `load_bundle`.
2. **Modify & re-submit** – edit the JSON (or call `schedule_job` with `append=True`) and run `submit_jobs`.
3. **Register a new CLI target** – add entry points to `pyproject.toml` under `[project.scripts]` so `autoslurm-schedule` can discover `<script>-cli`.
4. **Add a machine** – run `autoslurm-configuration`, edit the JSON, and let the helper create remote directories / `AUTOSLURM` exports.

## Extension points

- **Custom validation**: wrap `autoslurm.apps.schedule.parse_script_args` or call a project-specific CLI to validate/serialize arguments.
- **Alternative submission backends**: new modules can replicate the contract of `run_slurm_locally` / `run_slurm_remotely` if additional schedulers are needed.
- **Metadata hooks**: use `autoslurm.utils.update_job_info_with_id` to attach extra keys (loss, dataset, comments) to bundle files after submission.
