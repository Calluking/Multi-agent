# Benchmarks

Benchmark integrations live outside the production OpenClaw plugin package. They are reproducibility tools, not runtime dependencies.

- `multiagentbench/` contains the working coding-task orchestration and judge workflow.
- `cooperbench/` contains a verified native DeepSeek solo runner (66.7% on the documented smoke task) and the gates for a future MACP-capable multi-agent adapter.

Run each integration from its own directory and keep the model, task subset, limits, and evaluator identical between `without_plugin` and `with_plugin` conditions.
