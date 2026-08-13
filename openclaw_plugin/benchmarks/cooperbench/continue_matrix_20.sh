#!/usr/bin/env bash
set -u

prefix=${1:-matrix20-f94661d}
root=$(cd "$(dirname "$0")/../.." && pwd)
cb=${COOPERBENCH_ROOT:-$HOME/cooperbench-run/CooperBench}

# Do not overlap conditions because the OpenClaw plugin toggle is global.
while pgrep -f "run_matrix_20.sh without_plugin $prefix" >/dev/null; do
  sleep 20
done

# These five plugin-on runs used the same benchmark prompt, model, plugin
# implementation and official evaluator. Later commits only changed the
# resumable harness, so preserve and reuse their full native log directories.
for spec in \
  '17070-f12' '17070-f13' '17070-f23' '17244-f12' '17244-f13'
do
  source="$cb/logs/macp-fixed-$spec"
  target="$cb/logs/$prefix-with_plugin-$spec"
  if [[ -s "$source/eval_summary.json" && ! -e "$target" ]]; then
    cp -a "$source" "$target"
  fi
done

cd "$root"
exec bash benchmarks/cooperbench/run_matrix_20.sh with_plugin "$prefix"
