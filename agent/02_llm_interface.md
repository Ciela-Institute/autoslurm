# Agent Interface

This doc describes how LLM-based agents consume context produced by AutoSlurm and which tools should be built first so agents can drive the package.

## Context sources

1. **Agent documentation (`agent/`)** – `04_project_map.md` lays out the Python APIs, CLI entry points, directory layout, and metadata hooks; `03_experiment_context.md` explains the concatenated snapshot for a bundle; `06_resource_rules.md` and `schema.json` describe policy expectations and bundle format, while `05_cli_reference.md` and `examples/` provide concrete commands that agents can mimic or parse.
2. **`autoslurm-experiment-context` output** – both the CLI and the `experiment_context(bundle_name, desired_date=None)` helper produce a single string containing the bundle JSON, generated SLURM scripts, and `.out` logs (local plus fetched remote logs). This string is designed to be ingested verbatim by an LLM so it has a complete picture of a completed or pending experiment.
3. **Bundles/logs on disk (`jobs/`, `slurm/`, `out/`)** – agents can read the JSON files and logs directly if they have filesystem access; the context helper and docs describe the naming (`bundle_timestamp`) and how to pick a bundle based on name/date.
4. **Configuration metadata** – the `~/.autoslurmconfig` layout and machine definitions (described in docs) help agents understand where to submit jobs and how to SSH into remote machines.

These pieces combine to give an LLM a human-readable narrative (docs) plus machine-state snapshots (bundles + experiment context) so decisions can be made in a single turn.

## Tooling roadmap for agents

Agents currently only consume context. The next step is to expose tools that allow them to drive AutoSlurm via a minimal Agent Communication Protocol (ACP) layer:

1. **`execute_acp` wrapper** – the new `autoslurm.acp.execute_acp(...)` function parses an ACP payload (see below) and routes requests to `experiment_context`, `list_bundles`, or `schedule_job`. Wrapping it in a tool gives agents one entry point for observation and staging.
2. **`experiment_context(bundle[, date])` tool** – the ACP already returns the concatenated bundle/SLURM/scripts/logs string, so this tool can simply call `execute_acp({"action": "context", ...})`.
3. **`agent_context()` helper** – the new `autoslurm-agent-context` CLI (and Python `agent_context()` API) emit the entire `agent/` folder in one string. Agents can keep this handy reference when they need structural guidance or want to import docs into their context window.
4. **`agent_docs` action** – `{"action": "agent_docs"}` hits the same helper as `autoslurm-agent-context`, so tools that already talk to the ACP can grab the agent docs without a separate CLI call.
5. **`list_bundles(name)` tool** – provided by the ACP (`{"action": "list"}`), it enumerates available bundle timestamps and job names so agents can choose what to inspect or resubmit.
6. **`schedule_job` tool** – backstops scheduling through the ACP's `{"action": "schedule"}` request, taking a structured job dict (script, args, slurm, bundle, append flag) and returning the bundle file written.
7. **Future tools** – `submit_jobs`, log fetching, or cancellation can be added later by extending the ACP dispatch table.

The ACP already codifies the minimal protocol—`action`, `bundle`, `date`, etc.—so tools simply translate LLM requests into ACP payloads and return the `result` object. Building tools in this order lets agents first observe (context/list) before acting (schedule) with a stable, extendable interface.
