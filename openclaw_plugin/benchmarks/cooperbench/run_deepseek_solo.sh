#!/usr/bin/env bash
set -eo pipefail

COOPERBENCH_ROOT="${COOPERBENCH_ROOT:-$HOME/cooperbench-run/CooperBench}"
RUN_NAME="${RUN_NAME:-deepseek-one}"
REPO_NAME="${REPO_NAME:-llama_index_task}"
TASK_ID="${TASK_ID:-17070}"
MODEL="${MODEL:-deepseek/deepseek-chat}"
AGENT="${AGENT:-mini_swe_agent_v2}"
CONCURRENCY="${CONCURRENCY:-1}"

case "$TASK_ID" in
  ''|*[!0-9]*) printf 'TASK_ID must be numeric, got: %s\n' "$TASK_ID" >&2; exit 2 ;;
esac

cd "$COOPERBENCH_ROOT"
source .venv/bin/activate
export PATH="$HOME/.local/bin:$PATH"

command -v cooperbench >/dev/null
command -v uv >/dev/null
docker info >/dev/null
docker ps | grep -q redis
test -n "${DEEPSEEK_API_KEY:-}"
test -n "${DEEPSEEK_BASE_URL:-}"
uv pip install 'httpx[socks]'

cooperbench run \
  -n "$RUN_NAME" \
  -r "$REPO_NAME" \
  -t "$TASK_ID" \
  -m "$MODEL" \
  -a "$AGENT" \
  --setting solo \
  -c "$CONCURRENCY" \
  --backend docker \
  --no-auto-eval \
  --force

cooperbench eval \
  -n "$RUN_NAME" \
  -r "$REPO_NAME" \
  -t "$TASK_ID" \
  --backend docker

printf 'Results: %s/logs/%s/solo/\n' "$COOPERBENCH_ROOT" "$RUN_NAME"
