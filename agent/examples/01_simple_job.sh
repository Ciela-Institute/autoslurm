#!/bin/bash
autoslurm-schedule examples/simple_train.py \
  --job-name simple_job \
  --time=01:00:00 \
  --cpus_per_task=2 \
  --mem=4G \
  --epochs 5 \
  --data-path /data/input.fits
