#!/usr/bin/env python3
"""Run one CooperBench feature pair through an OpenClaw coordinator.

CooperBench remains the dataset/image/evaluator owner. This adapter only
replaces the agent execution step and emits the standard coop patch layout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

DEFAULT_CB = Path.home() / "cooperbench-run" / "CooperBench"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
PLUGIN_ID = "multi-agent-contract-protocol"


def run(cmd: list[str], cwd: Path, timeout: int = 900, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if check and proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr or proc.stdout}")
    return proc


def extract_repo(image: str, destination: Path) -> None:
    container = run(["docker", "create", image, "sleep", "1"], destination.parent).stdout.strip()
    try:
        destination.mkdir(parents=True)
        run(["docker", "cp", f"{container}:/workspace/repo/.", str(destination)], destination.parent, 300)
        base_sha = run(["git", "rev-parse", "HEAD"], destination).stdout.strip()
        (destination / ".cooperbench_base_sha").write_text(base_sha + "\n")
    finally:
        run(["docker", "rm", "-f", container], destination.parent, 60, False)


def feature_text(cb_root: Path, repo: str, task: int, feature: int) -> str:
    path = cb_root / "dataset" / repo / f"task{task}" / f"feature{feature}" / "feature.md"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text()


def prompt(repo: str, task: int, f1: int, f2: int, spec1: str, spec2: str, workspace: Path) -> str:
    return f"""Run one CooperBench cooperative task with exactly two native OpenClaw child Agents.
They are peer feature owners, not planner/implementer/reviewer. Spawn both with mode=run.
Do not invent product code in the coordinator. The coordinator owns only the
integration workspace: it must apply both producer patches there, test their
composition, and ask the responsible producer to repair a failing patch.

[Project cooperbench-{repo}-{task}-features-{f1}-{f2}]
[Assignment feature-{f1}-owner]
Workspace: peer_feature{f1}
Artifact: peer_feature{f1}/PATCH_READY.md
Shared base repository; implement only Feature {f1}. The product file may overlap Feature {f2}.
Specification:\n{spec1}

[Assignment feature-{f2}-owner]
Workspace: peer_feature{f2}
Artifact: peer_feature{f2}/PATCH_READY.md
Shared base repository; implement only Feature {f2}. The product file may overlap Feature {f1}.
Specification:\n{spec2}

Each child task must reproduce the complete Project and both Assignment blocks. Each owner must:
- work only in its assigned directory under {workspace};
- inspect the existing implementation before editing;
- implement its own feature without reading golden patches;
- preserve compatibility with the other assignment and explicitly describe the shared API contract;
- run relevant executable tests after its final edit;
- write PATCH_READY.md containing changed files/API, exact test command, exit status/result, and compatibility commitment.

Wait with bounded exec checks until both PATCH_READY.md files exist. Inspect both packets. If their
shared contract conflicts, resume the responsible owner for repair and fresh verification. Then use the
clean repository at {workspace}/integration: generate each peer diff from its recorded base commit,
apply both diffs to integration (resolving overlap without dropping either feature), and run every exact
test command declared in both PATCH_READY.md packets from the integration tree. Add a focused joint test
when both features change one API. A passing test in peer_feature{f1} or peer_feature{f2} is producer
evidence only and cannot prove composition. Finish only after both repositories contain non-empty product
diffs and every producer test passes against the same integration tree with current executable evidence.
"""


def configure_plugin(openclaw: str, cwd: Path, enabled: bool) -> None:
    value = "true" if enabled else "false"
    run([openclaw, "config", "set", f"plugins.entries.{PLUGIN_ID}.enabled", value, "--strict-json"], cwd, 120)
    run([openclaw, "gateway", "restart"], cwd, 60, False)
    time.sleep(4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("condition", choices=["without_plugin", "with_plugin"])
    ap.add_argument("--name", required=True)
    ap.add_argument("--repo", default="llama_index_task")
    ap.add_argument("--task", type=int, default=17070)
    ap.add_argument("--features", default="1,2")
    ap.add_argument("--model", default=os.environ.get("BENCHMARK_MODEL", DEFAULT_MODEL))
    ap.add_argument("--cooperbench-root", type=Path, default=DEFAULT_CB)
    ap.add_argument("--openclaw", default=shutil.which("openclaw") or "openclaw")
    args = ap.parse_args()
    features = [int(x) for x in args.features.split(",")]
    if len(features) != 2 or features[0] == features[1]:
        ap.error("--features must contain two distinct numeric IDs")
    f1, f2 = sorted(features)
    cb = args.cooperbench_root.expanduser().resolve()
    adapter_root = Path(__file__).resolve().parent
    workspace = adapter_root / "runs" / args.name / f"{args.repo}_{args.task}_f{f1}_f{f2}"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    image = f"akhatua/cooperbench-{args.repo.removesuffix('_task').replace('_', '-')}:task{args.task}"
    for feature in (f1, f2):
        extract_repo(image, workspace / f"peer_feature{feature}")
    # A third clean checkout is the only workspace from which composition
    # verification is accepted. It is intentionally not used for patch output.
    extract_repo(image, workspace / "integration")
    spec1, spec2 = (feature_text(cb, args.repo, args.task, f) for f in (f1, f2))
    task_prompt = prompt(args.repo, args.task, f1, f2, spec1, spec2, workspace)
    (workspace / "TASK.md").write_text(task_prompt)
    (workspace / "AGENTS.md").write_text(
        "Work only inside this workspace. Never inspect CooperBench feature.patch or tests.patch files.\n"
    )
    enabled = args.condition == "with_plugin"
    configure_plugin(args.openclaw, workspace, enabled)
    agent_id = f"cb-macp-{args.condition[:4]}-{uuid.uuid4().hex[:8]}"
    run([args.openclaw, "agents", "add", agent_id, "--non-interactive", "--workspace", str(workspace),
         "--model", args.model, "--json"], workspace, 120)
    for _ in range(30):
        listed = run([args.openclaw, "agents", "list", "--json"], workspace, 60, False)
        try:
            if listed.returncode == 0 and any(item.get("id") == agent_id for item in json.loads(listed.stdout)):
                time.sleep(5)
                break
        except json.JSONDecodeError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError(f"OpenClaw agent was not discoverable after registration: {agent_id}")
    # The gateway caches the agent registry at startup. Reload it after adding
    # this run-scoped coordinator, then allow the listener to become ready.
    run([args.openclaw, "gateway", "restart"], workspace, 60, False)
    time.sleep(5)
    session = f"{args.name}-{int(time.time())}"
    started = time.time()
    proc = run([args.openclaw, "agent", "--agent", agent_id, "--session-id", session,
                "--model", args.model, "--thinking", "off", "--timeout", "1200", "--json",
                "--message", task_prompt], workspace, 1500, False)
    (workspace / "root.stdout.json").write_text(proc.stdout)
    (workspace / "root.stderr").write_text(proc.stderr)
    log_dir = cb / "logs" / args.name / "coop" / args.repo / str(args.task) / f"f{f1}_f{f2}"
    log_dir.mkdir(parents=True, exist_ok=True)
    agents: dict[str, dict] = {}
    producer_diffs: dict[int, str] = {}
    for feature in (f1, f2):
        peer = workspace / f"peer_feature{feature}"
        base_sha = (peer / ".cooperbench_base_sha").read_text().strip()
        committed = run(["git", "diff", "--binary", base_sha, "HEAD", "--", "."], peer, 120).stdout
        uncommitted = run(["git", "diff", "--binary", "HEAD", "--", "."], peer, 120).stdout
        diff = committed + uncommitted
        producer_diffs[feature] = diff
        # Preserve the raw owner contribution for trace diagnosis. Official
        # CooperBench consumes agentN.patch below, which represents the final
        # mutually accepted integrated artifact.
        (log_dir / f"agent{feature}.producer.patch").write_text(diff)
        ready = peer / "PATCH_READY.md"
        agents[f"agent{feature}"] = {
            "feature_id": feature,
            "status": "Submitted" if diff.strip() and ready.is_file() else "Error",
            "patch_lines": len(diff.splitlines()),
            "error": None if diff.strip() and ready.is_file() else "missing patch or PATCH_READY.md",
        }
    integration = workspace / "integration"
    integration_base = (integration / ".cooperbench_base_sha").read_text().strip()
    integrated = (run(["git", "diff", "--binary", integration_base, "HEAD", "--", "."], integration, 120).stdout
                  + run(["git", "diff", "--binary", "HEAD", "--", "."], integration, 120).stdout)
    # CooperBench's cooperative evaluator treats identical patches as the two
    # peers agreeing on one normalized integrated artifact. Export that final
    # artifact for both agents; retain *.producer.patch for attribution.
    if integrated.strip():
        for feature in (f1, f2):
            (log_dir / f"agent{feature}.patch").write_text(integrated)
    else:
        for feature in (f1, f2):
            (log_dir / f"agent{feature}.patch").write_text(producer_diffs[feature])
    result = {
        "repo": args.repo, "task_id": args.task, "features": [f1, f2], "setting": "coop",
        "run_name": args.name, "agent_framework": "openclaw_macp", "model": args.model,
        "condition": args.condition, "plugin_enabled": enabled, "root_exit": proc.returncode,
        "integration_patch_lines": len(integrated.splitlines()),
        "duration_seconds": time.time() - started, "agents": agents,
        "prompt_sha256": hashlib.sha256(task_prompt.encode()).hexdigest(),
        "workspace": str(workspace),
    }
    (log_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    (cb / "logs" / args.name / "config.json").write_text(json.dumps({
        "run_name": args.name, "setting": "coop", "agent_framework": "openclaw_macp",
        "model": args.model, "condition": args.condition, "plugin_enabled": enabled,
    }, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if proc.returncode or any(a["status"] == "Error" for a in agents.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
