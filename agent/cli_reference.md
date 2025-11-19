## CLI Reference for Agents

- `autoslurm-schedule <script>`: schedules or appends jobs. Recognizes SLURM flags (`--time`, `--mem`, `--gres`, etc.), dependencies (`--dependencies`), bundles (`--bundle`/`--append`), pre-commands (`--pre-commands`), and machine overrides (`--machine`, remote host info). Use `--job-name` to override the job identity stored inside the bundle; without it the script name is reused, and AutoSlurm appends `_001`, `_002`, etc., when duplicate job names appear in the same bundle.
- `autoslurm-submit <bundle>`: submits the most recent bundle matching the name. Add `--machine` or SSH overrides if you need a non-default endpoint.
- `autoslurm-configuration`: runs the interactive menu (or `--view`) to manage machine definitions. Agents can supply SSH details as either hostname aliases or host+user pairs.
