#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/luzh/.local/bin:$PATH"

cd /home/luzh/Multi-agent
OUT=/home/luzh/Multi-agent/experiments/four_fault_reaudit_20260803
mkdir -p "$OUT"

mark() {
  printf '%s %s\n' "$(date -Is)" "$1" | tee -a "$OUT/stages.log"
}

mark "waiting for codomain_prework_v2 20-task run"
while kill -0 199358 2>/dev/null; do sleep 30; done

mark "auditing codomain_prework_v2"
python3 dependency_memory/v4_sparse/run_four_fault_audit.py \
  --condition codomain_prework_v2 \
  --roots /home/luzh/Multi-agent/experiments/prework_v2_dynamic_20tasks_20260803 \
  --output "$OUT/codomain_prework_v2_four_faults.json" \
  > "$OUT/codomain_prework_v2_audit.log" 2>&1

mark "auditing testing-only"
python3 dependency_memory/v4_sparse/run_four_fault_audit.py \
  --condition testing \
  --roots /home/luzh/Multi-agent/experiments/testing_memory_5tasks_20260803 \
          /home/luzh/Multi-agent/experiments/testing_memory_remaining15_20260803 \
  --output "$OUT/testing_four_faults.json" \
  > "$OUT/testing_audit.log" 2>&1

mark "running current all-three (optimized co-domain prework V2)"
python3 dependency_memory/v4_sparse/run_feature_ablation.py \
  --tasks 1-20 --condition all_three_prework_v2 \
  --root /home/luzh/Multi-agent/experiments/all_three_prework_v2_20tasks_20260803 \
  > "$OUT/all_three_run.log" 2>&1

mark "auditing current all-three"
python3 dependency_memory/v4_sparse/run_four_fault_audit.py \
  --condition all_three_prework_v2 \
  --roots /home/luzh/Multi-agent/experiments/all_three_prework_v2_20tasks_20260803 \
  --output "$OUT/all_three_prework_v2_four_faults.json" \
  > "$OUT/all_three_audit.log" 2>&1

mark "complete"
