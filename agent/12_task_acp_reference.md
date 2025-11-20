# Task: ACP Reference

For any tool that speaks ACP, rely on this distilled reference:

| Action | Purpose | Required Parameters |
| --- | --- | --- |
| `inspect_experiments` | Dump bundle JSON + SLURM scripts + `.out` logs (same as `autoslurm-experiment-context`). | `bundle`, optional `date`. |
| `list_experiments` | Enumerate `jobs/<bundle>_*.json` files so you can pick the right timestamp. | `bundle`. |
| `schedule` | Persist a job dict (script + args + SLURM resources) into a bundle. | `bundle` (or job-provided bundle), `job`, optional `append`. |
| `gather_context` | Return the entire `agent/` folder (docs, schema, examples) as one string. | None. |

See `src/autoslurm/acp_action.y` for the authoritative metadata (copy it but keep the JSON valid). `agent_context()`/`autoslurm-agent-context` print a sorted version of these docs, and `07_acp_actions.md` describes how to use `action_definitions()` to introspect this table programmatically before emitting ACPs. To gather only this reference via the CLI: `autoslurm-agent-context --sections 12_task_acp_reference.md`; via ACP: `{"action":"gather_context","sections":["12_task_acp_reference.md"]}`.
