#!/usr/bin/env python3
import argparse, hashlib, json, os, re, shutil, subprocess, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPENCLAW = os.environ.get("OPENCLAW_BIN") or shutil.which("openclaw")
if not OPENCLAW:
    local_openclaw = Path.home() / ".local/bin/openclaw"
    OPENCLAW = str(local_openclaw) if local_openclaw.is_file() else "openclaw"
MODEL = os.environ.get("BENCHMARK_JUDGE_MODEL", os.environ.get("BENCHMARK_MODEL", "deepseek/deepseek-v4-flash"))
JUDGE_TEMPLATE = """
[Context]
**Task Description:**
{task_description}

**Implementation Requirements:**
{requirements}

**Current Solution:**
{solution}

[System]
This evaluation requires strict scoring and deduction. The scores should not be generous, and deductions should be applied for every issue found.

### **Evaluation Criteria**
1. **Instruction-Following:** Does the code fulfill all the requirements of the task? Deduct points for unmet or partially met requirement from the task instructions.
2. **Executability:** Is the code syntactically correct and executable? Deduct points for any syntax errors, missing imports, or runtime errors.
3. **Consistency:** Is the code consistent in variable naming, formatting, and logic? Deduct points for inconsistent variable naming, formatting issues, or contradictory logic.
4. **Quality:** Is the code well-documented, clear, and modular? Deduct points for poor documentation, unclear logic, or lack of modular design.

### **Scoring**
- **1 point:** Below Average - Significant issues that need addressing.
- **2 points:** Average - Noticeable areas for improvement.
- **3 points:** Good - Minor issues or improvements needed.
- **4 points:** Excellent - Almost or fully satisfies the criterion.
- **5 points:** Legendary - Flawless, perfectly satisfies the criterion, and exceeds expectations.

**Do not give the same scores for different criteria, such as 3 for instruction-following, 3 for executability, 3 for consistency, and 3 for quality.**
If you give the same scores for the 4 criteria, you have to add or deduct 1 point randomly for one or two criteria.

### **Question**
Based on the criteria, evaluate the code and output the scores for each criterion in the following JSON format:
{{
    "instruction_following": score,
    "executability": score,
    "consistency": score,
    "quality": score
}}
""".strip()
OUT, SUMMARY = HERE / "scores.jsonl", HERE / "score_comparison.json"

def call(cmd, cwd=HERE, timeout=720):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)

def plugin_enabled():
    result = call([OPENCLAW, "config", "get",
                   "plugins.entries.multi-agent-contract-protocol.enabled"],
                  timeout=20)
    return result.returncode == 0 and result.stdout.strip().lower() == "true"

def toggle(enabled):
    value = "true" if enabled else "false"
    print(f"judge setup: plugin enabled={value}", flush=True)
    result = call([OPENCLAW, "config", "set", "plugins.entries.multi-agent-contract-protocol.enabled", value, "--strict-json"], timeout=20)
    try:
        call([OPENCLAW, "gateway", "restart"], timeout=60)
    except subprocess.TimeoutExpired:
        print("judge setup: gateway restart timed out; continuing after bounded wait", flush=True)
    time.sleep(3)
    return result.returncode

def visible(envelope):
    result = envelope.get("result", envelope)
    payloads = result.get("payloads", []) if isinstance(result, dict) else []
    texts = []
    for payload in payloads:
        if isinstance(payload, dict):
            for key in ("text", "content", "message"):
                if isinstance(payload.get(key), str): texts.append(payload[key])
    return "\n".join(texts) or json.dumps(envelope)

def prior_scores():
    rows = {}
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            try:
                row = json.loads(line)
                if row.get("valid"): rows[(row["condition"], int(row["task_id"]))] = row
            except Exception: pass
    return rows

def judge(condition, task_id):
    ws = HERE / condition / f"task_{task_id:02d}"
    manifest = json.loads((ws / "run_manifest.json").read_text())
    task = (ws / "TASK.md").read_text()
    start = "1. Implementation requirements:\n"
    end = "\n\n2. Project structure:"
    a, b = task.find(start), task.find(end)
    requirements = task[a + len(start):b].strip() if a >= 0 and b > a else task
    solution_path = ws / "solution.py"
    solution = solution_path.read_text() if solution_path.exists() else ""
    judge_prompt = JUDGE_TEMPLATE.format(task_description=task, requirements=requirements, solution=solution)
    attempts = 0
    while True:
        attempts += 1
        session = f"fair20-score-{condition}-t{task_id:02d}-{int(time.time())}"
        try:
            proc = call([OPENCLAW, "agent", "--agent", manifest["agent"], "--session-id", session, "--model", MODEL, "--thinking", "off", "--timeout", "600", "--json", "--message", judge_prompt], cwd=ws, timeout=660)
        except subprocess.TimeoutExpired:
            time.sleep(min(180, 30 * attempts)); continue
        stderr = (proc.stderr or "").lower()
        if any(x in stderr for x in ("llm request timed out", "failovererror", "unknown agent id")):
            time.sleep(min(180, 30 * attempts)); continue
        try:
            envelope = json.loads(proc.stdout)
            match = re.search(r"\{[^{}]*\}", visible(envelope), re.S)
            scores = json.loads(match.group(0)) if match else {}
            valid = set(scores) == {"instruction_following", "executability", "consistency", "quality"} and all(isinstance(v, int) and 1 <= v <= 5 for v in scores.values())
        except Exception: scores, valid = {}, False
        row = {"condition": condition, "task_id": task_id, "judge_model": MODEL, "judge_template_sha256": hashlib.sha256(JUDGE_TEMPLATE.encode()).hexdigest(), "judge_prompt_sha256": hashlib.sha256(judge_prompt.encode()).hexdigest(), "solution_present": solution_path.exists(), "run_root_exit": manifest.get("root_exit"), "scores": scores, "mean": sum(scores.values()) / 4 if valid else None, "valid": valid, "attempts": attempts, "judge_exit": proc.returncode}
        (ws / "score.stdout.json").write_text(proc.stdout)
        (ws / "score.stderr").write_text(proc.stderr)
        if valid: return row
        time.sleep(min(120, 20 * attempts))

def summarize(rows, task_ids):
    result, dims = {}, ("instruction_following", "executability", "consistency", "quality")
    for condition in ("without_plugin", "with_plugin"):
        selected = [rows[(condition, i)] for i in task_ids]
        count = len(selected)
        mean = sum(r["mean"] for r in selected) / count
        result[condition] = {"tasks": count, "dimension_means": {d: sum(r["scores"][d] for r in selected) / count for d in dims}, "mean_task_score": mean, "score_out_of_100": mean * 20, "root_exit_zero": sum(r["run_root_exit"] == 0 for r in selected)}
    result["delta"] = {"dimension_means": {d: result["with_plugin"]["dimension_means"][d] - result["without_plugin"]["dimension_means"][d] for d in dims}, "mean_task_score": result["with_plugin"]["mean_task_score"] - result["without_plugin"]["mean_task_score"], "score_out_of_100": result["with_plugin"]["score_out_of_100"] - result["without_plugin"]["score_out_of_100"]}
    SUMMARY.write_text(json.dumps(result, indent=2) + "\n")
    return result

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--tasks", default="1-20"); args = parser.parse_args()
    task_ids = []
    for part in args.tasks.split(","):
        if "-" in part:
            first, last = map(int, part.split("-", 1)); task_ids.extend(range(first, last + 1))
        else: task_ids.append(int(part))
    rows = prior_scores()
    original_state = plugin_enabled()
    try:
        toggle(False)
        for task_id in task_ids:
            for condition in ("without_plugin", "with_plugin"):
                key = (condition, task_id)
                if key in rows: continue
                row = judge(condition, task_id)
                with OUT.open("a") as f: f.write(json.dumps(row) + "\n")
                rows[key] = row
                print(json.dumps({"condition": condition, "task": task_id, "mean": row["mean"]}), flush=True)
        print(json.dumps(summarize(rows, task_ids), indent=2), flush=True)
    finally:
        toggle(original_state)

if __name__ == "__main__": main()
