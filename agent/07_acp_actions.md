# ACP Actions Reference

AutoSlurm exposes a small Agent Communication Protocol (ACP) whose actions are documented in `src/autoslurm/acp_action.y`. Each payload follows the shape `{"action": "...", ...}` and returns `{"status": "...", "result": ...}`. The available actions are:

1. **context**: returns the `autoslurm.agent_context` dump (bundle + scripts + `.out` logs) for a given bundle and optional date.
2. **list**: lists the available bundle JSON files (`jobs/<bundle>_*.json`) so an agent knows which timestamps are available and which jobs they contain.
3. **schedule**: persists a job dict into storage (new bundle or appended bundle), mirroring what `autoslurm.schedule_job(...)` does.

Tools should call `autoslurm.acp.execute_acp(...)` with one of the above actions. Use `autoslurm.acp.action_definitions()` to discover the allowed payload structure programmatically if needed. The new `autoslurm-agent-context` CLI/`agent_context()` API can serve as a companion reference tool for the agent documentation that underpins the ACP.
