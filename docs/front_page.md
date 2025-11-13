# AutoSlurm

`autoslurm` turns repetitive SLURM scripting into a repeatable workflow service.
You describe *what* to run (Python module, CLI entry point, shell pre-commands)
alongside the SLURM resources you need, and the toolkit writes, stores, and
submits the correct `sbatch` payload locally or over SSH. Everything lives in
structured JSON bundles so humans, CI jobs, or autonomous agents can reason
about past and future runs.

## Why AutoSlurm?

- **Consistent infrastructure hand‑offs** – user-specific paths, accounts, and SSH details stay in config, not in your scripts.
- **Bundle-level provenance** – every scheduled job is serialized with timestamps, dependencies, and CLI args for later inspection or reruns.
- **Graph-aware scheduling** – jobs reference each other by name; AutoSlurm resolves the dependency graph and injects the right `--dependency` flags.
- **Agent-friendly surface area** – the CLI (`autoslurm-schedule`, `autoslurm-submit`, …) mirrors the Python API (`save_job`, `submit_jobs`) so automation can pick the right layer.

## Reference Workflow

1. **Configure once** with `autoslurm-configuration` so the tool knows where your local/remote workspaces live.
2. **Register CLI entry points** in your project’s `pyproject.toml` so `autoslurm-schedule my-script` can discover arguments.
3. **Schedule jobs** with resource flags (`--time`, `--gres`, `--mem`, …) plus optional bundles/dependencies.
4. **Submit later or immediately** (`autoslurm-submit` or `autoslurm-schedule --submit`) to run locally or on named SSH machines.
5. **Inspect saved bundles** in `$AUTOSLURM/jobs/` or rehydrate them through the Python API for auditing or replays.

## How The Docs Are Organized

- **Getting Started** – installation, configuration, and CLI basics with executable examples.
- **Configuration & Registration** – details on machine profiles and script discovery.
- **Agent Guide** – a package map and automation patterns so LLM-powered agents can reason about the codebase.

```{tableofcontents}

```
