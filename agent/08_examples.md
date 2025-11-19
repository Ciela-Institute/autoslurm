# Agent Submission Examples

This file collects CLI sequences the agent can use to schedule and submit jobs without modifier of configuration state. Each example uses commands that operate on the stored `jobs/` and `slurm/` directories automatically.

## 1. Schedule a single job

```bash
autoslurm-schedule train-model \
  --time 02:00:00 \
  --gres gpu:1 \
  --cpus_per_task 4 \
  --mem 12G \
  --epochs 50 \
  --lr 1e-4
```

Result: AutoSlurm saves `train-model` job metadata into a new bundle JSON and generates a SLURM script under `slurm/`.

## 2. Schedule multiple jobs into a bundle

```bash
autoslurm-schedule preprocess-data \
  --bundle sweep-demo \
  --time 00:30:00 \
  --mem 8G

for seed in 1 2 3; do
  autoslurm-schedule train-model \
    --bundle sweep-demo \
    --append \
    --dependencies preprocess-data \
    --gres gpu:1 \
    --cpus_per_task 8 \
    --seed "$seed" \
    --epochs 80
done
```

The resulting bundle JSON contains one preprocessing job and three training jobs, each scheduled with consistent resources and dependency references.

## 3. Submit a bundle locally

```bash
autoslurm-submit sweep-demo --machine local
```

AutoSlurm reads the bundle from `jobs/sweep-demo_*.json`, transfers the linked SLURM scripts to the local scheduler, runs `sbatch`, and records SLURM job IDs inside the JSON file.

## 4. Remote submission

```bash
autoslurm-submit nightly-inference --machine research-gpu
```

Assuming `research-gpu` has SSH credentials configured in `~/.autoslurmconfig`, AutoSlurm copies the SLURM scripts to that machine’s `~/.autoslurm/slurm`, runs `sbatch` over SSH, and updates the bundle with the remote job IDs.

## 5. Schedule dependent jobs

```bash
autoslurm-schedule build-training-data \
  --bundle prep-train \
  --time 01:00:00 \
  --cpus_per_task 4 \
  --mem 32G \
  --output_path /shared/data/train_dataset.json

autoslurm-schedule train-model \
  --append --bundle prep-train \
  --dependencies build-training-data \
  --time 08:00:00 \
  --gres gpu:1 \
  --cpus_per_task 16 \
  --mem 64G \
  --epochs 100 --lr 3e-4

autoslurm-submit prep-train --machine research-gpu
```

The agent does not need to resolve job IDs—AutoSlurm writes the dependency lines (`#SBATCH --dependency=afterok:...`) when each job is submitted.
