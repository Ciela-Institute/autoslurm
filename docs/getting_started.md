# Getting started

## Installation

### Install the `autoslurm` package

```bash
git clone git@github.com:Ciela-Institute/autoslurm.git
cd autoslurm
pip install -e .
```

### Configure `autoslurm` for your environment

```bash
autoslurm-configuration
```

This command will allow you to configure paths and user-specific details for
your local and remote SLURM machines. More details can be found in the
[Configuration](configuration.md) section.

### Register your application in the `pyproject.toml` file of your package

```toml
[project.scripts]
my-script = "my_package.module:main"
my-script-cli = "my_package.module:cli"
```

More details can be found in the [Register a script](register_a_script.md)
section.

## Basic Usage

### Schedule a job

```bash
autoslurm-schedule my-script \
    # Application args
    --my_job_arg1=arg1 \
    # SLURM args
    --time=00-01:00 \
    --cpus_per_task=1 \
    --gres=gpu:1 \
    --mem=16G
```

This command schedules `my-script` to run for 1 hour, using 1 CPU, 1 GPU, and
16GB of memory.

### Submit a job

Once the job is scheduled, you can submit it at any time just by using the name
of the application.

```bash
autoslurm-submit my-script --machine=machine
```

This command submits `my-script` on the `machine` name specified in your
configuration (see [AutoSlurm Configuration](#AutoSlurm-Configuration)). You can also
schedule and submit a job at the same time to skip a step.

```bash
autoslurm-schedule my-script --submit --machine=machine\
    # Application and SLURM args
    ...
```

### Schedule multiple jobs

Use the `--append` keyword to combine multiple jobs in a bundle. Use the
`--bundle` keyword to specify the name of the bundle.

```bash
autoslurm-schedule job1 --bundle=my-bundle
autoslurm-schedule job2 --append --bundle=my-bundle
autoslurm-submit my-bundle
```

An empty bundle can be initialized as follows
```bash
autoslurm-initialize my-bundle
```
Jobs can then be appended to this bundle using `autoslurm-schedule --append --bundle=my-bundle`.
This is useful when you want to schedule jobs in a loop.

**Warning**: In case `--append` is not used, two bundles (each with a single job) are
created with unique timestamps. Only the last bundle created is submitted.


### Schedule jobs with dependencies

Dependencies can be set by specifying the job names in the `--dependencies`
argument.

```bash
autoslurm-schedule job1 --bundle=my-bundle
autoslurm-schedule job2 --append --bundle=my-bundle --dependencies job1
```

Multiple dependencies can be set by separating the job names with a space.

```bash
autoslurm-schedule job3 --append --bundle=my-bundle \
    --dependencies job1 job2
```

<!--The `--dependency_type` argument specifies the type of dependency. The default-->
<!--is `afterany`.-->

**Notes**:

- Any dependency loop will be detected and raise an error (e.g. if job1 depends
  on job2 and vice versa).
- Order in which jobs are appended is not important. Jobs are sorted in
  topological order before submission.
  <!--- `--dependency_type` can be a list of same length as `--dependencies` or a-->
    <!--single value to be broadcasted.-->


### Pre-commands

Commands like copying files or creating directories can be
executed before the python script by using the `--pre-command` argument when scheduling a job.

```bash
autoslurm-schedule my-script \
    --pre-command "mkdir -p /path/to/my/directory"
    ...
```
Multiple pre-commands are provided by separating them with a semicolon

```bash
autoslurm-schedule my-script \
    --pre-command "mkdir -p /path/to/my/directory; cp /path/to/my/file /path/to/my/directory"
    ...
```

Or separating them with a space

```bash
autoslurm-schedule my-script \
    --pre-command \
    "mkdir -p /path/to/my/directory" \
    "cp /path/to/my/file /path/to/my/directory"\
    ...
```

## Worked Examples

### Example 1 — Parameter sweeps with bundles

```bash
# Prepare an empty bundle
autoslurm-initialize sweep-demo

# Append variants (here preprocessing and three seeds)
autoslurm-schedule preprocess-data \
    --append --bundle sweep-demo \
    --time 00-30:00 --mem 8G

for seed in 1 2 3; do
  autoslurm-schedule train-model \
      --append --bundle sweep-demo \
      --dependencies preprocess-data \
      --time 04:00:00 --gres gpu:1 --cpus_per_task 8 \
      --seed "$seed" --epochs 50
done

autoslurm-submit sweep-demo --machine local
```

This pattern stores every variant inside a single JSON bundle. Inspect the file
under `$AUTOSLURM/jobs/sweep-demo_<timestamp>.json` to reproduce, edit, or copy
the workload later.

### Example 2 — Remote submission with environment activation

```bash
autoslurm-schedule inference \
    --bundle nightly-inference \
    --submit \
    --machine research-gpu \
    --pre-command "source /shared/miniconda3/etc/profile.d/conda.sh; conda activate ldm" \
    --time 02:00:00 --mem 32G --gres gpu:1 \
    --checkpoint /models/ldm.ckpt --input_path /data/batch.json
```

If `research-gpu` is defined in `autoslurm-configuration`, the job is copied to
the remote `$path/slurm/` directory, `sbatch` is executed over SSH, and the
stack keeps track of the returned job ID.

### Example 3 — Programmatic scheduling from Python

```python
from autoslurm.save_load_jobs import schedule_job
from autoslurm.job_runner import submit_jobs

job = {
    "name": "analysis",
    "script": "stats-pipeline",
    "script_args": {"input": "results.csv", "alpha": 0.05},
    "slurm": {"time": "00:45:00", "mem": "4G", "cpus_per_task": 2},
}

schedule_job(job, bundle_name="analytics", append=True)
submit_jobs("analytics")  # Uses default machine config unless overridden
```

Use this API when another service (for example, an LLM agent) needs to stage
jobs without invoking the CLI. The saved bundle mirrors the CLI format, so you
can mix and match tooling safely.
