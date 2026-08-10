# Sequential workflow

```text
planner → implementer → reviewer
```

The planner declares the implementer's artifacts and verification command. The implementer receives a dependency packet, writes the artifact, and must pass its producer checkpoint. The reviewer is blocked until the artifact is observed and its evidence is current.

Use this shape for MultiAgentBench-style tasks. Toggle all three mechanisms on for the full control plane, or disable two mechanisms to reproduce an ablation.
