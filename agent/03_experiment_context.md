# Experiment Context

`autoslurm-experiment-context` is the go-to helper for agents that need to reason
about completed or ongoing experiments. Run it via the CLI or import
`autoslurm.experiment_context.experiment_context(...)` to get a single string
payload with:

1. The bundle JSON that AutoSlurm persisted under `$AUTOSLURM/jobs`.
2. Every rendered SLURM script from `$AUTOSLURM/slurm`.
3. All `.out` logs inside `$AUTOSLURM/out`. When a job ran remotely, the command
   SSHs into that machine, activates the configured environment (`env_command`),
   runs the same CLI remotely (with `--date` pointing at the bundle timestamp),
   and pulls the logs back into `out/` so they appear in the dump.

### CLI usage

```bash
autoslurm-experiment-context my-bundle               # latest bundle
autoslurm-experiment-context my-bundle --date 20250101T120000
```

The command prints the concatenated payload to stdout, so agents can capture it
directly or pipe it through other processors. When no `.out` files exist yet,
the dump clearly indicates whether the job never submitted or lacks logs even
though it has a job ID.

### Python API

```python
from autoslurm.experiment_context import experiment_context

payload = experiment_context("my-bundle")
```

The helper returns the same string the CLI prints. Agents can parse it, store it
for downstream reasoning, or reformat it for structured storage, while still
relying on AutoSlurm’s own view of the experiment state.
