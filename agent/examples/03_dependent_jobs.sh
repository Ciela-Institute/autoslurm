#!/bin/bash
# Schedule a data-preparation job (default name = build-datasets)
autoslurm-schedule build-datasets \
  --bundle pipeline \
  --time=00:20:00 \
  --cpus_per_task=4 \
  --mem=8G \
  --pre-commands "mkdir -p /scratch/build"

# Schedule the first analysis job. Name defaults to "analyze".
autoslurm-schedule analyze \
  --bundle pipeline \
  --append \
  --dependencies build-datasets \
  --time=02:00:00 \
  --gres gpu:1 \
  --cpus_per_task=8 \
  --mem=32G

# Schedule a second analysis (same script name). AutoSlurm will rename it to "analyze_001".
# We express dependencies explicitly, including the new suffix.
autoslurm-schedule analyze \
  --bundle pipeline \
  --append \
  --dependencies analyze analyze_001 \
  --time=01:00:00 \
  --gres gpu:1 \
  --cpus_per_task=4 \
  --mem=16G
