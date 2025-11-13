# Project Brain — `autoslurm`

## 🧭 Purpose

`autoslurm` automates and streamlines **SLURM job management** on high-performance computing (HPC) systems.
It abstracts away the manual writing of shell scripts and command-line invocations required to submit jobs on clusters.

The goal is to let users (or other software) request computational resources through a **Python or CLI interface**, while the system:
- generates the appropriate `#!/bin/bash` submission script with correct `#SBATCH` headers,
- handles dependencies between multiple jobs,
- submits the scripts either locally or over SSH,
- and tracks job IDs automatically.

This makes job scheduling **portable**, **reproducible**, and **version-controlled**.

---

## ⚙️ Core Concepts

| Concept | Description |
|----------|--------------|
| **Job** | A dictionary describing a unit of work: script path, command-line args, and resource requirements (time, memory, CPUs, GPUs, etc.). |
| **Bundle** | A collection of jobs forming a workflow. Dependencies between jobs are declared by name; the system computes the execution order automatically. |
| **Configuration** | A user-specific YAML/JSON file storing SLURM account, default paths, and remote SSH credentials. Keeps code user-agnostic. |
| **SLURM Script Generator** | Converts a job specification into a valid SLURM submission file. Handles resource headers and dependency flags. |
| **Scheduler** | Core logic that writes, submits, and monitors jobs locally or on remote clusters via SSH. |
| **CLI Interface** | Provides commands to configure the environment, schedule jobs, submit bundles, and view status. |
| **Dependency Graph** | Jobs reference others by name; the scheduler computes a topological sort and fills `--dependency=afterok:<job_ids>` automatically. |

---

## 🧰 Typical Workflow

1. **Initialize** the environment and write a config file:
```bash
autoslurm init
```

2. Create a new job or bundle:
```bash
autoslurm schedule train_model.py --time 04:00:00 --gpus 1
```

3. Submit jobs (local or remote)
```bash
autoslurm submit --remote
```


## 🧩 Integration With Other Projects

Other Python projects or agents can treat autoslurm as a job-submission service:

from autoslurm import submit_job

submit_job(
    script="train.py",
    resources=dict(time="2:00:00", gpus=1, mem="16G"),
    dependencies=["preprocess"]
)


or use the CLI for batched jobs:

autoslurm schedule my_experiment.py --bundle exp_1 --depends preprocess


This allows automated pipelines, experiment managers, and agent systems to use autoslurm as a low-level backend for HPC execution.

## 🧠 Design Principles

User-agnostic — account and file-path differences handled by config.

Declarative — jobs described in structured data, not ad-hoc shell scripts.

Composable — jobs can depend on others; workflows become graphs, not flat lists.

Portable — same interface works locally or over SSH.

Transparent — JSON bundles record what was run, when, and with which resources.

## 🧩 Future Roadmap

Richer schema validation for job definitions.

Better error handling and retry logic for SSH and submission failures.

Unified configuration schema for multi-cluster setups.

Templated SLURM headers for specific partitions or GPU types.

Improved CLI feedback and logging dashboard.

Integration with agent systems for fully autonomous experiment orchestration.
