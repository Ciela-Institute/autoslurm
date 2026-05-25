# AutoSlurm Workflow Notes

This document tracks the current workflow we have been building, the main pieces that now exist, and the assumptions that are no longer valid.

## Current Workflow

`autoslurm` is the scheduler and control plane.
`substructure_lens` builds the experiment bundles.

The intended flow is:

1. Configure one or more machines with `asl configuration`.
2. Build an experiment bundle in `substructure_lens`.
3. Register the bundle with `autoslurm`.
4. Submit the latest bundle or a named bundle with `autoslurm submit`.
5. Pull remote storage into the local mirror with `asl sync`, or refresh on demand with `asl logs --refresh`.
6. Inspect bundle status, job status, scripts, and logs with `asl logs`.

Preferred operator workflow:

1. `asl config -i`
2. choose whether the machine is local or remote
3. for remote machines, provide:
   - SSH alias or host URL
   - SSH username if needed
   - private key path if needed
   - `env_command` for the virtual environment
   - SLURM account
4. set the default machine explicitly
5. build the bundle in `substructure_lens`
6. submit with `autoslurm submit --latest` or a named bundle
7. inspect with `asl logs`
8. refresh remote state with `asl sync` only when needed

## What Exists Today

### In `autoslurm`

- `asl` root command as the main entry point.
- `asl config` as the short alias for `asl configuration`.
- `asl config -i` as the short interactive configuration entry point.
- `agent` and `logs` as short names, with backward-compatible aliases.
- `autoslurm submit --latest`.
- `autoslurm logs --latest`.
- `autoslurm logs --log`.
- `autoslurm logs --refresh`.
- `autoslurm logs --clipboard` and `--clip`.
- Compact `logs` views for:
  - latest bundle summaries
  - bundle job listings
  - single job status
  - job script output
  - logs
- Remote machine support through SSH aliases and `env_command`.
- Remote storage root discovery from the remote AutoSlurm install.
- Remote submission that:
  - copies SLURM scripts to remote `slurm/`
  - runs `sbatch` remotely
  - mirrors bundle JSON to remote `jobs/`
- Experiment scheduling through installed CLIs so scripts never depend on local paths.
- `asl sync` as a pull-only mirror from remote `jobs/`, `slurm/`, and `out/`.
- Config storage at the AutoSlurm root, not under `src/`.
- `config.json`, `jobs/`, `slurm/`, and `out/` at the AutoSlurm root.
- Validation for remote machine config:
  - SSH reachability
  - venv activation
  - `python -c "import autoslurm"`
- Short machine summary with `asl configuration --summary`.
- Interactive machine rename and default-machine switching.

### In `substructure_lens`

- Bundle builders for:
  - alpha sweep
  - source-resolution sweep
- Shared bundle helper layer to avoid duplicating scheduling and logging code.
- Automatic experiment ledger in `jobs/experiments.jsonl`.
- Bundle scheduling into AutoSlurm by default.
- Configurable bundle names for experiment tracking.
- Quieter production runs:
  - reduced Bessel-root verbosity
  - Hutchinson start/finish timing prints
- Job metadata including:
  - timings
  - CG iteration counts
  - stop codes
  - epsilon/lambda definitions
  - output paths
- Jacobian mode subset computation so jobs only differentiate assigned columns.
- Batch controls separated by purpose:
  - Jacobian construction batch size
  - CG projection batch size
  - Hutchinson probe batch size

## Current Usage Pattern

Recommended day-to-day flow:

- configure machines with `asl config -i`
- set the default machine explicitly
- generate a named bundle from `substructure_lens`
- submit the latest or named bundle with `autoslurm submit`
- use `autoslurm submit --latest` when the bundle builder has already registered the current experiment
- use `asl logs` to inspect status and logs
- use `asl sync` only when you want to refresh the local mirror
- use `asl logs --refresh` when you want fresh logs without calling sync manually

Why the installed package matters:

- scripts are launched from installed console entry points, not from ad hoc filesystem paths
- this removes path drift on the cluster
- it also makes the experiment bundle the stable unit of scheduling
- `--latest` is useful because it lets the CLI use AutoSlurm storage directly instead of requiring a handwritten path

Context and sync:

- `asl logs` is the cheap inspection command
- `asl logs --latest` shows the latest bundle status
- `asl logs --log` prints the latest saved log for the selected bundle or latest bundle
- `asl logs --refresh` pulls fresh remote state before inspection
- `asl sync` is the explicit pull step when you want the whole mirror updated

## Stale Assumptions

The following assumptions should be treated as stale:

- `local` must exist as a configuration entry.
- configuration should create runtime directories.
- machine config must include an explicit local path.
- remote machine discovery can rely on DNS resolution of SSH aliases.
- SLURM output should point at the local workstation path for remote runs.
- `logs` should default to dumping everything.
- logs must be inspected manually in the filesystem.
- submission must always use a named bundle.
- remote AutoSlurm must be installed in a fixed path.
- `autoslurm` should own experiment purpose tracking as scheduler metadata.

## Caution Points

These parts are working, but should still be treated carefully:

- `logs` on large remote logs can be expensive if refreshed too often.
- `sync` is intentionally pull-only and does not clean old files.
- experiment purpose tracking is still a lightweight local record, not a full database.
- the remote `path` override still exists in some places for backward compatibility, but the long-term model is root discovery plus `env_command`.

## Suggested Doc Sections

If this becomes a fuller docs page later, the natural sections are:

- Overview
- Machine Configuration
- CLI Surface
- Bundle Builders
- Submission Workflow
- Context and Logs
- Sync
- Experiment Logging
- Remote Execution Model
- Deprecated Assumptions

## Documentation TODOs

The docs still need a dedicated page that explains:

- the current CLI surface and aliases
- the difference between local and remote machines
- what `env_command`, SSH alias, username, and key path mean
- how to configure the default machine
- how bundles are created, named, and registered
- how `autoslurm submit --latest` works
- how `asl logs` and `asl sync` differ
- how remote storage is discovered and mirrored
- the output-path contract for bundle builders:
  - bundle job payloads should emit project-relative result paths (including project root segment)
  - autoslurm resolves those relative paths to machine-specific absolute roots (for example `results_root`)
  - when absolute output paths are acceptable and when they should be avoided
- a design review of the current output-path chain to reduce hidden assumptions and moving parts:
  - current default flow is `relative output_root` -> `project-prefixed relative output_dir` -> `autoslurm absolute resolution at slurm-render time`
  - verify whether this should remain the general pattern across projects or be replaced by a simpler model with fewer implicit conventions
  - evaluate whether project-prefixing belongs in project code, autoslurm core, or machine profile templates
- why installed console scripts are the preferred experiment entry points
- how the current experiment builders map to the workflow we used for the first successful runs
- a refactored end-to-end CLI usage guide aligned with the new CLI surface and current scheduling/submission patterns
