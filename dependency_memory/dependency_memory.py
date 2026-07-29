#!/usr/bin/env python3
"""Generic YAML-backed dependency memory for a single workflow run."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


UNRESOLVED = {"unknown", "pending", "blocking", "missing", "failed", "stale"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DependencyMemoryStore:
    """Maintain complete records, select blockers, and render compact projections."""

    def __init__(self, workspace: Path, store_path: Path):
        self.workspace = workspace
        self.store_path = store_path
        self.data: dict[str, Any] = {
            "schema_version": "0.2",
            "generated_at": now(),
            "records": [],
            "event_log": [],
        }

    def load(self) -> None:
        if self.store_path.exists():
            self.data = yaml.safe_load(self.store_path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.data["updated_at"] = now()
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def compile_contracts(
        self,
        *,
        system_id: str,
        task_id: str,
        run_id: str,
        workflow_id: str,
        producer_role: str | None,
        consumer_role: str | None,
        artifacts: list[dict[str, Any]],
        extraction_provenance: dict[str, Any] | None = None,
    ) -> None:
        for spec in artifacts:
            dep_id = spec["dependency_id"]
            path = spec.get("location")
            spec_producer_role = spec.get("producer_role", producer_role)
            if not spec_producer_role:
                raise ValueError(f"Dependency {dep_id} has no producer role")
            raw_consumers = spec.get("consumers")
            if raw_consumers:
                consumers = [
                    item if isinstance(item, dict) else {"role": item}
                    for item in raw_consumers
                ]
            elif consumer_role:
                consumers = [{"role": consumer_role}]
            else:
                consumers = []
            reader_roles = list(dict.fromkeys([
                spec_producer_role,
                *(item.get("role") for item in consumers if item.get("role")),
            ]))
            primary_consumer_role = consumers[0].get("role") if consumers else spec_producer_role
            resource_type = spec.get("resource_type", "file" if path else spec.get("type", "artifact"))
            source_provenance = extraction_provenance or {
                "extraction_method": "contract_compilation",
                "source_agent_id": "orchestrator",
                "source_events": [],
                "evidence_refs": ["workflow configuration"],
                "confidence": 1.0,
                "inferred_fields": [],
                "verified_fields": [],
            }
            record = {
                "identity": {
                    "memory_id": f"dep:{run_id}:{dep_id}:1",
                    "dependency_id": dep_id,
                    "memory_type": "dependency",
                    "record_type": "contract_state",
                    "version": 1,
                },
                "scope": {
                    "system_id": system_id,
                    "task_id": str(task_id),
                    "run_id": run_id,
                    "workflow_id": workflow_id,
                    "stage_id": spec_producer_role,
                    "episode_id": None,
                },
                "privacy": {
                    "visibility": "recipient_private",
                    "owner_agent_id": None,
                    "owner_role": spec_producer_role,
                    "permitted_readers": reader_roles,
                    "transferable": True,
                    "transfer_policy": "fact_projection_only",
                },
                "dependency": {
                    "type": spec.get("type", "artifact"),
                    "scope": spec.get("dependency_scope", "workflow"),
                    "subject": {
                        "id": dep_id,
                        "name": spec.get("name", path or dep_id),
                        "description": spec["description"],
                        "resource_type": resource_type,
                        "location": path,
                    },
                    "producer": {"agent_id": None, "role": spec_producer_role, "stage_id": spec_producer_role},
                    "consumers": [{
                        "agent_id": item.get("agent_id"),
                        "role": item.get("role"),
                        "stage_id": item.get("stage_id", item.get("role")),
                        "intended_action": item.get("intended_action", spec.get("consumer_action", "consume")),
                    } for item in consumers],
                    "prerequisites": spec.get("prerequisites", []),
                    "dependents": spec.get("dependents", []),
                },
                "contract": {
                    "required": spec.get("required", True),
                    "expected_state": spec.get("expected_state", "produced"),
                    "acceptance_criteria": spec.get("acceptance_criteria", [{
                        "criterion_id": "artifact_exists",
                        "type": "existence",
                        "specification": f"{path} exists",
                    }]),
                    "verification": spec.get("verification"),
                    "deadline": {
                        "boundary": spec.get("deadline", "before_consumer_completion"),
                        "stage_id": spec.get("deadline_stage", primary_consumer_role),
                    },
                },
                "state": {
                    "status": "unknown",
                    "readiness": False,
                    "observed_state": "not_observed",
                    "missing_prerequisites": [],
                    "blocker": None,
                    "artifact": {
                        "exists": False,
                        "version": None,
                        "content_hash": None,
                        "last_modified": None,
                    },
                    "verification": {
                        "status": "not_required" if not spec.get("verification") else "not_run",
                        "last_attempt_id": None,
                        "last_result": None,
                    },
                },
                "ownership": {
                    "responsible_agent_id": None,
                    "responsible_role": spec_producer_role,
                    "recovery_agent_id": None,
                    "recovery_role": spec.get("recovery_role", primary_consumer_role),
                    "responsibility_status": "active",
                    "handoff_status": "not_ready",
                },
                "recovery": {
                    "required": False,
                    "strategy_id": spec.get("strategy_id", "produce_required_artifact"),
                    "next_action": {
                        "action_type": "create",
                        "target": path,
                        "description": spec.get("next_action", f"Create required artifact {path}"),
                    },
                    "alternative_actions": [],
                    "attempts": 0,
                    "last_attempt": None,
                    "avoid_repeating": [],
                },
                "selection": {
                    "semantic_text": spec.get("semantic_text", spec["description"]),
                    "keywords": spec.get("keywords", [str(value) for value in (path, spec_producer_role, primary_consumer_role) if value]),
                    "entities": spec.get("entities", [path] if path else [dep_id]),
                    "applicable_actions": spec.get("applicable_actions", ["create", "consume", "handoff"]),
                    "applicable_stages": spec.get("applicable_stages", reader_roles),
                    "priority": spec.get("priority", "critical"),
                    "injection_policy": spec.get("injection_policy", "proactive"),
                },
                "lifecycle": {
                    "created_at": now(),
                    "updated_at": now(),
                    "expires_at": None,
                    "persistent_across_runs": False,
                    "supersedes": None,
                    "superseded_by": None,
                    "resolution_conditions": spec.get("resolution_conditions", ["artifact_exists"]),
                    "retention_policy": "retain_until_run_completion",
                },
                "provenance": deepcopy(source_provenance),
            }
            self.data["records"].append(record)
        self.save()

    def observe_files(self, *, stage: str, event_id: str) -> None:
        """Deterministically reconcile file-backed dependency records."""
        timestamp = now()
        for record in self.data["records"]:
            subject = record["dependency"]["subject"]
            if subject.get("resource_type") != "file":
                continue
            path = self.workspace / subject["location"]
            exists = path.is_file()
            artifact = record["state"]["artifact"]
            old_hash = artifact.get("content_hash")
            current_hash = file_hash(path)
            changed = exists and old_hash is not None and old_hash != current_hash
            verification = record["state"]["verification"]
            if changed and verification["status"] == "passed":
                verification["status"] = "stale"
            artifact.update({
                "exists": exists,
                "version": current_hash[:12] if current_hash else None,
                "content_hash": current_hash,
                "last_modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat() if exists else None,
            })
            expected = record["contract"]["expected_state"]
            content_valid, content_failures = self._validate_content(record, path)
            prerequisites_ready = self._prerequisites_ready(record)
            if not exists:
                record["state"].update({
                    "status": "missing",
                    "readiness": False,
                    "observed_state": "missing",
                    "blocker": {
                        "type": "artifact_missing",
                        "description": f"Required artifact {subject['location']} does not exist",
                        "retryable": True,
                    },
                })
                record["recovery"]["required"] = True
                record["ownership"]["handoff_status"] = "not_ready"
            elif not content_valid:
                record["state"].update({
                    "status": "failed",
                    "readiness": False,
                    "observed_state": "present_invalid",
                    "blocker": {
                        "type": "acceptance_criteria_failed",
                        "description": "; ".join(content_failures),
                        "retryable": True,
                    },
                })
                record["recovery"]["required"] = True
                record["ownership"]["handoff_status"] = "not_ready"
            elif not prerequisites_ready:
                record["state"].update({
                    "status": "blocking",
                    "readiness": False,
                    "observed_state": "present_prerequisites_unresolved",
                    "blocker": {
                        "type": "prerequisite_unresolved",
                        "description": "Artifact exists but one or more dependency prerequisites are not ready",
                        "retryable": True,
                    },
                })
                record["recovery"]["required"] = True
                record["ownership"]["handoff_status"] = "not_ready"
            elif expected == "verified" and verification["status"] != "passed":
                record["state"].update({
                    "status": "produced",
                    "readiness": False,
                    "observed_state": "present_unverified",
                    "blocker": {
                        "type": "verification_pending",
                        "description": f"{subject['location']} exists but required verification has not passed",
                        "retryable": True,
                    },
                })
                record["recovery"]["required"] = True
                record["ownership"]["handoff_status"] = "not_ready"
            else:
                record["state"].update({
                    "status": "verified" if expected == "verified" else "produced",
                    "readiness": True,
                    "observed_state": "verified" if expected == "verified" else "present",
                    "blocker": None,
                })
                record["recovery"]["required"] = False
                record["ownership"]["handoff_status"] = "ready"
            record["scope"]["stage_id"] = stage
            record["lifecycle"]["updated_at"] = timestamp
            record["provenance"]["source_events"].append({
                "event_type": "filesystem_snapshot",
                "event_id": event_id,
                "observation": f"{subject['location']}: {'present' if exists else 'missing'}",
                "observed_at": timestamp,
            })
            record["provenance"]["verified_fields"] = [
                "state.artifact.exists", "state.artifact.content_hash"
            ]
        self.data["event_log"].append({
            "event_id": event_id,
            "event_type": "filesystem_snapshot",
            "stage": stage,
            "observed_at": timestamp,
        })
        self.save()

    def record_verification(
        self,
        *,
        dependency_id: str,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        stage: str,
        event_id: str,
    ) -> None:
        record = self._by_id(dependency_id)
        passed = exit_code == 0
        result = {
            "command": command,
            "exit_code": exit_code,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:],
            "observed_at": now(),
        }
        record["state"]["verification"].update({
            "status": "passed" if passed else "failed",
            "last_attempt_id": event_id,
            "last_result": result,
        })
        requires_file = record["dependency"]["subject"].get("resource_type") == "file"
        exists = record["state"]["artifact"]["exists"] if requires_file else True
        record["state"].update({
            "status": "verified" if passed and exists else "failed",
            "readiness": bool(passed and exists),
            "observed_state": "verified" if passed and exists else "verification_failed",
            "blocker": None if passed and exists else {
                "type": "verification_failed",
                "description": f"Verification failed with exit code {exit_code}",
                "retryable": True,
            },
        })
        record["recovery"]["required"] = not (passed and exists)
        record["ownership"]["handoff_status"] = "ready" if passed and exists else "not_ready"
        record["scope"]["stage_id"] = stage
        record["lifecycle"]["updated_at"] = now()
        record["provenance"]["source_events"].append({
            "event_type": "command_result",
            "event_id": event_id,
            "observation": json.dumps(result, ensure_ascii=False),
        })
        record["provenance"]["verified_fields"].extend([
            "state.verification.status", "state.verification.last_result"
        ])
        self.save()

    def record_observation(
        self,
        *,
        dependency_id: str,
        event_type: str,
        passed: bool,
        observed_state: str,
        evidence: dict[str, Any],
        stage: str,
        event_id: str,
    ) -> None:
        """Apply a typed observation to any non-file dependency.

        Environment adapters, approval systems, interface checkers, service probes,
        and semantic evaluators can all submit observations through this method.
        The memory engine stores the result but does not itself execute inferred
        commands or contact external systems.
        """
        allowed_events = {
            "availability_result", "approval_result", "interface_result",
            "service_probe_result", "semantic_evaluation", "decision_result",
            "capability_result", "data_validation_result",
        }
        if event_type not in allowed_events:
            raise ValueError(f"Unsupported observation event type: {event_type}")
        record = self._by_id(dependency_id)
        expected = record["contract"]["expected_state"]
        completed_status = "verified" if expected in {"verified", "available"} else expected
        record["state"].update({
            "status": completed_status if passed else "failed",
            "readiness": passed,
            "observed_state": observed_state,
            "blocker": None if passed else {
                "type": f"{event_type}_failed",
                "description": evidence.get("summary", f"{event_type} did not satisfy the contract"),
                "retryable": evidence.get("retryable", True),
            },
        })
        record["recovery"]["required"] = not passed
        record["ownership"]["handoff_status"] = "ready" if passed else "not_ready"
        record["scope"]["stage_id"] = stage
        record["lifecycle"]["updated_at"] = now()
        record["provenance"]["source_events"].append({
            "event_type": event_type,
            "event_id": event_id,
            "observation": json.dumps(evidence, ensure_ascii=False),
            "observed_at": now(),
        })
        record["provenance"]["verified_fields"].extend([
            "state.status", "state.readiness", "state.observed_state"
        ])
        self.data["event_log"].append({
            "event_id": event_id,
            "event_type": event_type,
            "dependency_id": dependency_id,
            "stage": stage,
            "observed_at": now(),
        })
        self.save()

    def select(
        self,
        *,
        task_id: str,
        run_id: str,
        recipient_role: str,
        stage: str,
        action: str,
        query: str,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Hard-filter current blockers, then apply lightweight hybrid ranking."""
        q_tokens = set(query.lower().replace(".", " ").split())
        candidates = []
        for record in self.data["records"]:
            if record["scope"]["task_id"] != str(task_id):
                continue
            if record["scope"]["run_id"] != run_id:
                continue
            readers = record["privacy"]["permitted_readers"]
            if recipient_role not in readers:
                continue
            if stage not in record["selection"]["applicable_stages"]:
                continue
            if record["state"]["status"] not in UNRESOLVED:
                continue
            exact_action = action in record["selection"]["applicable_actions"]
            text = " ".join([
                record["selection"]["semantic_text"],
                " ".join(record["selection"]["keywords"]),
                " ".join(record["selection"]["entities"]),
                record["dependency"]["subject"]["description"],
                (record["state"].get("blocker") or {}).get("description", ""),
                record["recovery"]["next_action"]["description"],
            ]).lower().replace(".", " ")
            tokens = set(text.split())
            lexical = len(q_tokens & tokens) / max(1, len(q_tokens))
            priority = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}.get(
                record["selection"]["priority"], 0.5
            )
            dependency_depth = len(record["dependency"].get("prerequisites", []))
            root_bonus = 1.0 / (1.0 + dependency_depth)
            score = 0.30 * lexical + 0.20 * float(exact_action) + 0.25 * priority + 0.15 * root_bonus + 0.10
            candidates.append((score, dependency_depth, record))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [deepcopy(record) for _, _, record in candidates[:limit]]

    def projection(self, records: list[dict[str, Any]]) -> str:
        projected = []
        for record in records:
            subject = record["dependency"]["subject"]
            projected.append({
                "dependency_id": record["identity"]["dependency_id"],
                "status": record["state"]["status"],
                "subject": subject["description"],
                "location": subject.get("location"),
                "observed": record["state"]["observed_state"],
                "blocker": (record["state"].get("blocker") or {}).get("description"),
                "required_before": record["contract"]["deadline"]["boundary"],
                "next_action": record["recovery"]["next_action"]["description"],
                "completion_conditions": record["lifecycle"]["resolution_conditions"],
            })
        return yaml.safe_dump({"private_dependency_checkpoint": projected}, sort_keys=False)

    def unresolved(self) -> list[dict[str, Any]]:
        return [deepcopy(r) for r in self.data["records"] if r["state"]["status"] in UNRESOLVED]

    def _by_id(self, dependency_id: str) -> dict[str, Any]:
        for record in self.data["records"]:
            if record["identity"]["dependency_id"] == dependency_id:
                return record
        raise KeyError(dependency_id)

    def _prerequisites_ready(self, record: dict[str, Any]) -> bool:
        for prerequisite in record["dependency"].get("prerequisites", []):
            dep_id = prerequisite.get("dependency_id")
            if not dep_id:
                continue
            try:
                upstream = self._by_id(dep_id)
            except KeyError:
                return False
            required_state = prerequisite.get("required_state", "verified")
            if required_state == "verified" and upstream["state"]["status"] != "verified":
                return False
            if required_state in {"available", "produced"} and not upstream["state"]["artifact"]["exists"]:
                return False
        return True

    @staticmethod
    def _validate_content(record: dict[str, Any], path: Path) -> tuple[bool, list[str]]:
        if not path.is_file():
            return False, [f"{path.name} does not exist"]
        criteria = record["contract"].get("acceptance_criteria", [])
        if not criteria:
            return True, []
        text: str | None = None
        failures: list[str] = []
        for criterion in criteria:
            kind = criterion.get("type")
            if kind == "existence":
                continue
            if kind in {"content_contains_all", "content_contains_any"}:
                if text is None:
                    text = path.read_text(encoding="utf-8", errors="replace")
                values = criterion.get("values", [])
                hits = [value in text for value in values]
                passed = all(hits) if kind == "content_contains_all" else any(hits)
                if not passed:
                    failures.append(criterion.get("specification", f"Content criterion {criterion.get('criterion_id')} failed"))
        return not failures, failures
