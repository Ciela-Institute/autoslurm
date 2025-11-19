#!/bin/bash
autoslurm-schedule run_seed.py \
  --job-name array_seed \
  --bundle array-training \
  --array 1-10%2 \
  --cpus_per_task=4 \
  --mem=16G \
  --epochs 60 \
  --out results/seed_${SLURM_ARRAY_TASK_ID}.pt \
  --seed "${SLURM_ARRAY_TASK_ID}"
