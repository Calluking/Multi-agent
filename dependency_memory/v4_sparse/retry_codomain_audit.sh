#!/usr/bin/env bash
set -euo pipefail
export PATH="/home/luzh/.local/bin:$PATH"
cd /home/luzh/Multi-agent
python3 dependency_memory/v4_sparse/run_four_fault_audit.py \
  --condition codomain_prework_v2 \
  --roots /home/luzh/Multi-agent/experiments/prework_v2_dynamic_20tasks_20260803 \
  --output /home/luzh/Multi-agent/experiments/four_fault_reaudit_20260803/codomain_prework_v2_four_faults.json \
  > /home/luzh/Multi-agent/experiments/four_fault_reaudit_20260803/codomain_task10_retry.log 2>&1
