# Cooperative workflow

```text
peer_a ─┐
        ├→ integration owner → combined verification
peer_b ─┘
```

Each peer owns a separate workspace. Their `PATCH_READY.md` handoffs are discovered into a shared co-domain contract. The integration owner receives the shared boundary, runs the extracted verification commands, and cannot finish while the contract remains unverified.

Use this shape for CooperBench-style tasks.
