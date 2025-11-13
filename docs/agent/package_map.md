# Package Map

Use this document when an autonomous agent needs to answer questions such as
“Where do bundle files live?”, “Which module actually calls `sbatch`?”, or
“Which function should I import to submit a job programmatically?”. It captures
the concrete entry points and the data flowing through AutoSlurm.

## Architectural Overview

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

Everything hinges on three folders inside the configured `$AUTOSLURM` path:

- `jobs/` – persisted JSON bundles (input + metadata).
- `slurm/` – rendered bash scripts (one per job).
- `results/` (plus `data/`, `models/`) – user-owned assets that jobs often read/write.

## CLI Entry Points

| Command | Module | Intent | Notes |
| --- | --- | --- | --- |
| `autoslurm-configuration` | `autoslurm.apps.configuration` | Create or edit `~/.autoslurmconfig`, materialize folders locally/remotely. | Also sets `AUTOSLURM` env vars via `.bashrc`. |
| `autoslurm-initialize <name>` | `autoslurm.apps.initialize` | Create an empty bundle JSON so later jobs can append. | Calls `save_bundle({}, name)`. |
| `autoslurm-schedule <script>` | `autoslurm.apps.schedule` | Validate script arguments (via `<script>-cli`), persist job(s), optionally submit immediately. | Accepts SLURM args, machine overrides, dependencies, pre-commands. |
| `autoslurm-submit <bundle>` | `autoslurm.apps.submit` | Load the latest bundle matching `<bundle>_*` and call `submit_jobs`. | Can point at remote machines via `--machine` or inline SSH params. |

When automating through a shell, these commands are deterministic and emit the
paths they touch, which is useful for log parsing.

## Python Surface Area

| Function | Location | Description |
| --- | --- | --- |
| `schedule_job(job, bundle_name=None, append=False)` | `autoslurm.save_load_jobs` | Persist a single job dict. Creates or appends to `<bundle>_YYYYMMDDhhmmss.json`. |
| `save_bundle(bundle_dict, name, append=False)` | `autoslurm.save_load_jobs` | Persist multiple jobs at once. |
| `load_bundle(name)` | `autoslurm.save_load_jobs` | Returns `jobs`, `dependencies`, `date` for the latest bundle. |
| `submit_jobs(name, machine_config=None, date=None)` | `autoslurm.job_runner` | Converts bundle → SLURM scripts → `sbatch` (local or remote). |
| `create_slurm_script(job, date, machine_config)` | `autoslurm.job_to_slurm` | Renders the `#!/bin/bash` file with headers, env export, pre-commands, and CLI args. |
| `run_slurm_locally(slurm_name)` / `run_slurm_remotely(slurm_name, machine_config)` | `autoslurm.run_slurm` | Execute `sbatch` and capture the job ID. |
| `update_slurm_with_dependencies(slurm_name, job_ids)` | `autoslurm.job_dependency` | Inject `#SBATCH --dependency=afterok:` entries after upstream jobs complete. |

Agents can import these helpers directly (everything is exposed via
`autoslurm.__init__`) when they need tighter control than the CLI provides.

## Configuration & State

- **Global config** – `~/.autoslurmconfig` (see `autoslurm.definitions.CONFIG_FILE_PATH`).
  Contains machine entries keyed by human-friendly names plus the mandatory
  `local` section. Each entry should include `path`, `env_command`, and
  `slurm_account`; remote entries may also set `hostname`, `hosturl`,
  `username`, and `key_path`.
- **Runtime environment** – each configured path hosts subdirectories
  (`data/`, `models/`, `results/`, `slurm/`, `jobs/`). The configuration CLI
  ensures they exist locally and remotely.
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
- **SLURM scripts** – stored under `$AUTOSLURM/slurm/<job_name_timestamp>.sh`
  and reference the same `script_args` so they can be regenerated or amended.

## Typical Agent Tasks

1. **Inspect queued work** – list `jobs/<bundle>_*.json`, parse with Python’s
   `json` module, or call `load_bundle`.
2. **Modify & re-submit** – edit the JSON (or call `schedule_job` with `append=True`)
   and run `submit_jobs`.
3. **Register a new CLI target** – add entry points to `pyproject.toml` under
   `[project.scripts]` so `autoslurm-schedule` can discover `<script>-cli`.
4. **Add a machine** – run `autoslurm-configuration`, edit the JSON, and let the
   helper create remote directories/`AUTOSLURM` exports.

## Extension Points

- **Custom validation**: wrap `autoslurm.apps.schedule.parse_script_args` or call
  a project-specific CLI to validate/serialize arguments.
- **Alternative submission backends**: new modules can replicate the contract of
  `run_slurm_locally` / `run_slurm_remotely` if additional schedulers are needed.
- **Metadata hooks**: use `autoslurm.utils.update_job_info_with_id` to attach
  extra keys (loss, dataset, comments) to bundle files after submission.

Keep this map updated whenever new modules, directories, or workflows are
introduced so downstream agents can make correct inferences about the system.
