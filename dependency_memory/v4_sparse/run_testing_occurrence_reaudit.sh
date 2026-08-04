#!/usr/bin/env bash
set -euo pipefail
export PATH="/home/luzh/.local/bin:$PATH"
cd /home/luzh/Multi-agent
OUT=/home/luzh/Multi-agent/experiments/testing_occurrence_reaudit_20260804
mkdir -p "$OUT"
python3 dependency_memory/v4_sparse/run_occurrence_fault_audit.py \
  --condition testing \
  --roots /home/luzh/Multi-agent/experiments/testing_memory_5tasks_20260803 \
          /home/luzh/Multi-agent/experiments/testing_memory_remaining15_20260803 \
  --output "$OUT/testing_occurrence_four_faults.json" \
  > "$OUT/audit.log" 2>&1
date -Is > "$OUT/complete.marker"
