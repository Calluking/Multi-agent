# Independent Mechanism Switches

The single starting-prompt activation remains unchanged:

```text
Use $multi-agent-memory to complete this task.
```

The experimental condition is selected outside the prompt with
`MAM_MECHANISMS`, a comma-separated set containing `dependency`, `codomain`,
and/or `testing`:

```bash
MAM_MECHANISMS=dependency
MAM_MECHANISMS=codomain
MAM_MECHANISMS=testing
MAM_MECHANISMS=dependency,codomain
MAM_MECHANISMS=all
MAM_MECHANISMS=none        # protocol shell, all mechanisms off
```

This separation preserves exact prompt equality across ablations. Every run
must record its resolved switches, model, harness, task revision, prompt hash,
and mechanism implementation revision.

## Required comparison matrix

| Condition | Dependency | Co-Domain | Testing |
|---|---:|---:|---:|
| shell-only control | off | off | off |
| dependency only | on | off | off |
| co-domain only | off | on | off |
| testing only | off | off | on |
| all mechanisms | on | on | on |

Pairwise combinations may be added for interaction analysis, but the five
conditions above are the minimum useful ablation.

The switch disables mechanism behavior, state updates, projections, and gates.
The activation skill must not imitate a disabled mechanism through prompting.
Every operational tool must check the resolved switch before reading even an
existing state file. This prevents stale state from a prior condition leaking
into an ablation run that reuses a workspace.

Dependency Memory, Co-Domain Memory, and Testing-Practice Memory now have
harness-neutral backends and independent OpenCode adapters. A run must still
load only the adapter(s) appropriate to its selected experimental condition.
