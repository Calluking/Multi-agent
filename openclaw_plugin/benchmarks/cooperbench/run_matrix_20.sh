#!/usr/bin/env bash
set -u

condition=${1:?usage: run_matrix_20.sh without_plugin|with_plugin}
prefix=${2:-matrix20-current}
repo=llama_index_task
runner=$(dirname "$0")/run_openclaw_macp.py
cb=${COOPERBENCH_ROOT:-$HOME/cooperbench-run/CooperBench}

cases=(
  '17070 1,2' '17070 1,3' '17070 2,3'
  '17244 1,2' '17244 1,3' '17244 1,4' '17244 1,5'
  '17244 1,6' '17244 1,7' '17244 2,3' '17244 2,4'
  '17244 2,5' '17244 2,6' '17244 2,7' '17244 3,4'
  '17244 3,5' '17244 3,6' '17244 3,7' '17244 4,5'
  '17244 4,6'
)

for entry in "${cases[@]}"; do
  read -r task features <<<"$entry"
  compact=${features/,/}
  feature_dir=f${features/,/_f}
  name="${prefix}-${condition}-${task}-f${compact}"
  status_dir="$cb/logs/$name"
  result="$cb/logs/$name/coop/$repo/$task/$feature_dir/result.json"
  summary="$cb/logs/$name/eval_summary.json"
  if [[ -s "$result" && -s "$summary" ]]; then
    echo "cached $name"
    continue
  fi
  echo "START $name"
  mkdir -p "$status_dir"
  printf '{"state":"running","started_at":"%s"}\n' "$(date --iso-8601=seconds)" > "$status_dir/matrix_status.json"
  python3 "$runner" "$condition" --name "$name" --repo "$repo" \
    --task "$task" --features "$features"
  run_rc=$?
  if [[ -s "$result" ]]; then
    rm -f "$cb/logs/$name/coop/$repo/$task/$feature_dir/eval.json" "$summary"
    (cd "$cb" && source .venv/bin/activate && \
      cooperbench eval -n "$name" -r "$repo" -t "$task" -f "$features" --backend docker) || true
  fi
  if [[ -s "$result" && -s "$summary" ]]; then
    state=complete
  elif [[ -s "$result" ]]; then
    state=eval_failed
  else
    state=run_failed
  fi
  printf '{"state":"%s","run_exit":%d,"finished_at":"%s"}\n' \
    "$state" "$run_rc" "$(date --iso-8601=seconds)" > "$status_dir/matrix_status.json"
  echo "END $name"
done
