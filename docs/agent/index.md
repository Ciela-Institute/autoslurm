# Agent Guide

This section is tailored for autonomous agents (LLMs, workflow engines, CI
robots) that need to reason about the AutoSlurm codebase without having the
full tribal knowledge of its maintainers. It complements the user-facing docs
with system maps, module responsibilities, and actionable playbooks.

## What Agents Can Do With AutoSlurm

- Schedule and submit compute jobs through the CLI or Python API.
- Inspect bundle JSON files to understand pending or past workloads.
- Update machine configuration when new clusters or credentials appear.
- Assemble pipelines by wiring dependencies between jobs inside a bundle.

## Navigation

- **Package Map** – end-to-end dataflow, module summaries, and extension points.
- **Worked Examples** – see `docs/getting_started.md` for CLI/Python flows that
  can be scripted verbatim.

Whenever you extend AutoSlurm (new CLI command, custom scheduler), update the
map so future agents inherit the context they need.
