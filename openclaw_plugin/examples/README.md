# Examples

These examples describe the two target workflow shapes.

## Sequential workflow

```text
planner → implementer → reviewer
```

Dependency memory carries artifact ownership and readiness. The implementer cannot finish with an acknowledgment while its artifact obligation is unresolved.

## Cooperative workflow

```text
peer_a ─┐
        ├→ integration owner → combined verification
peer_b ─┘
```

Co-domain memory records the shared boundary and requires executable evidence before completion.

## Memory toggles

The adapter accepts independent `dependencyEnabled`, `codomainEnabled`, and `testingEnabled` settings. Use these toggles to reproduce ablations and isolate a mechanism during evaluation.
