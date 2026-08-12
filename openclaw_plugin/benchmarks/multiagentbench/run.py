#!/usr/bin/env python3
import argparse, hashlib, json, shutil, subprocess, time, uuid
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASET = Path(os.environ.get("MAB_DATASET", "../MARBLE/multiagentbench/coding/coding_main.jsonl")).expanduser().resolve()
MEMORY_ROOT = Path(os.environ.get("MACP_STORE_ROOT", "~/.openclaw/multiagent-memory")).expanduser()
MODEL = os.environ.get("BENCHMARK_MODEL", "deepseek/deepseek-v4-flash")
OPENCLAW = os.environ.get("OPENCLAW_BIN", shutil.which("openclaw") or "openclaw")
PROMPT = """Complete TASK.md through exactly three native OpenClaw child Agents.

- Spawn a planner responsible only for plan.md.
- After plan.md exists, spawn an implementer responsible only for solution.py and implementation.md.
- After solution.py and implementation.md exist, spawn a reviewer responsible only for executable verification and review.md.

Do not implement the task in the coordinator. Do not start a later child before the preceding artifacts exist. After each spawn, use one bounded exec wait of at most 180 seconds that checks only the expected artifact; do not use sessions_yield. Inspect each artifact before continuing.

Finally run the solution's primary executable verification independently. Do not finish until plan.md, solution.py, implementation.md, and review.md all exist and review.md records the exact verification command, exit status, and result.
"""
AGENTS = """# Controlled MultiAgentBench comparison

Work only in this directory. Treat TASK.md as the sole product specification.
Use native sessions_spawn for child Agents. Do not create Agents through shell commands.
Do not read or copy artifacts from any other experiment directory.
Do not use MARBLE profiles or previous benchmark results.
Do not run git commands.
"""

def run(cmd, cwd, timeout=700):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)

def add_agent(agent, workspace):
    proc = run([OPENCLAW, "agents", "add", agent, "--non-interactive", "--workspace",
                str(workspace), "--model", MODEL, "--json"], workspace, 120)
    (workspace / "agent_add.stdout").write_text(proc.stdout)
    (workspace / "agent_add.stderr").write_text(proc.stderr)
    if proc.returncode: raise RuntimeError(proc.stderr or proc.stdout)
    for _ in range(30):
        listed = run([OPENCLAW, "agents", "list", "--json"], workspace, 60)
        try:
            if listed.returncode == 0 and any(x.get("id") == agent for x in json.loads(listed.stdout)):
                time.sleep(5); return
        except json.JSONDecodeError: pass
        time.sleep(1)
    raise RuntimeError("agent not discoverable")

def empty_memory():
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    for kind in ("dependency", "codomain", "testing"):
        (MEMORY_ROOT / f"{kind}.json").write_text(json.dumps({"schemaVersion":"0.1","items":[]}, indent=2)+"\n")

def toggle_plugin(enabled):
    value = "true" if enabled else "false"
    proc = run([OPENCLAW, "config", "set", "plugins.entries.multi-agent-contract-protocol.enabled", value, "--strict-json"], HERE, 120)
    if proc.returncode: raise RuntimeError(proc.stderr or proc.stdout)
    try: run([OPENCLAW, "gateway", "restart"], HERE, 60)
    except subprocess.TimeoutExpired: pass
    time.sleep(4)

def run_one(condition, item):
    task_id = int(item["task_id"])
    workspace = HERE / condition / f"task_{task_id:02d}"
    if (workspace / "run_manifest.json").exists():
        previous = json.loads((workspace / "run_manifest.json").read_text())
        if previous.get("root_exit") == 0:
            return previous
        archived = workspace.with_name(workspace.name + f"_failed_root_{int(time.time())}")
        workspace.rename(archived)
    if workspace.exists(): shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    task = "# Official coding task\n\n" + item["task"]["content"] + "\n"
    (workspace / "TASK.md").write_text(task)
    (workspace / "AGENTS.md").write_text(AGENTS)
    (workspace / "official_task.json").write_text(json.dumps(item, indent=2)+"\n")
    if condition == "with_plugin": empty_memory()
    agent = f"fair20-{condition}-t{task_id:02d}-{uuid.uuid4().hex[:6]}"
    add_agent(agent, workspace)
    session = f"fair20-{condition}-t{task_id:02d}-{int(time.time())}"
    started = time.time()
    proc = None
    provider_timeouts = 0
    attempt = 0
    while True:
        attempt += 1
        try:
            proc = run([OPENCLAW, "agent", "--agent", agent, "--session-id", session,
                        "--model", MODEL, "--thinking", "off", "--timeout", "600", "--json",
                        "--message", PROMPT], workspace)
        except subprocess.TimeoutExpired as exc:
            provider_timeouts += 1
            marker = f"Outer runner timeout after {exc.timeout}s; retrying same task as infrastructure failure.\n"
            (workspace / f"root.attempt_{attempt}.stderr").write_text(marker)
            time.sleep(min(300, 60 * provider_timeouts))
            continue
        (workspace / f"root.attempt_{attempt}.stderr").write_text(proc.stderr)
        error = (proc.stderr or "").lower()
        if "unknown agent id" in error:
            time.sleep(min(30, 5 * attempt))
            continue
        if "llm request timed out" in error or "failovererror" in error:
            provider_timeouts += 1
            # Upstream outages are not benchmark outcomes. Cool down and retry
            # the exact same prompt, Agent, model, session, and workspace.
            time.sleep(min(300, 60 * provider_timeouts))
            continue
        break
    assert proc is not None
    elapsed = time.time() - started
    (workspace / "root.stdout.json").write_text(proc.stdout)
    (workspace / "root.stderr").write_text(proc.stderr)
    if condition == "with_plugin":
        snapshot = workspace / "memory_snapshot"; snapshot.mkdir()
        for kind in ("dependency", "codomain", "testing"):
            source = MEMORY_ROOT / f"{kind}.json"
            if source.exists(): shutil.copyfile(source, snapshot / source.name)
    manifest = {
        "condition": condition, "task_id": task_id, "model": MODEL,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "task_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "agents_sha256": hashlib.sha256(AGENTS.encode()).hexdigest(),
        "agent": agent, "session": session, "root_exit": proc.returncode,
        "elapsed_seconds": elapsed,
        "artifacts": {name: (workspace/name).is_file() for name in ("plan.md","solution.py","implementation.md","review.md")},
    }
    (workspace / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("condition", choices=["without_plugin","with_plugin"]); ap.add_argument("--tasks",default="1-20"); ap.add_argument("--dataset", type=Path, default=DATASET)
    args=ap.parse_args()
    toggle_plugin(args.condition == "with_plugin")
    wanted=[]
    for part in args.tasks.split(","):
        if "-" in part:
            a,b=map(int,part.split("-",1)); wanted.extend(range(a,b+1))
        else: wanted.append(int(part))
    if not args.dataset.is_file(): ap.error(f"MultiAgentBench dataset not found: {args.dataset}; set --dataset or MAB_DATASET")
    tasks={int(x["task_id"]):x for x in (json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip())}
    progress=HERE/f"progress_{args.condition}.jsonl"
    for task_id in wanted:
        try:
            result=run_one(args.condition,tasks[task_id]); status="ok"
        except Exception as exc:
            result={"condition":args.condition,"task_id":task_id,"error":repr(exc)}; status="error"
        with progress.open("a") as f: f.write(json.dumps(result)+"\n")
        print(f"{args.condition} task={task_id:02d} {status} artifacts={result.get('artifacts')}",flush=True)

if __name__=="__main__": main()
