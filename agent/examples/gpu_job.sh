#!/bin/bash
autoslurm-schedule train_diffusion.py \
  --job-name gpu_task \
  --bundle gpu-training \
  --time=04:00:00 \
  --gres gpu:1 \
  --cpus_per_task=8 \
  --mem=32G \
  --model edm \
  --batch-size 64 \
  --epochs 100
