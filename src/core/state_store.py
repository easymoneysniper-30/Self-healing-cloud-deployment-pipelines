"""State store and cryptographic tamper-evident audit log.

Implements SQLite persistence with WAL mode and SHA-256 block-hash chaining
per PRD DR-1, DR-2, DR-3, EI-7, OBJ-5.
"""

from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from src.core.models import (
    AuditEvent,
    ChaosExperiment,
    Incident,
    IncidentStatus,
    RollbackCheckpoint,
    utc_now,
)


class StateStore:
    """Thread-safe SQLite-backed state store with cryptographic audit trail."""

    def __init__(self, db_path: str = "self_healing_state.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # Incidents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    correlation_id TEXT UNIQUE NOT NULL,
                    service_name TEXT NOT NULL,
                    incident_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    detection_timestamp TEXT NOT NULL,
                    resolution_timestamp TEXT,
                    recovery_duration_seconds REAL,
                    is_chaos_injected INTEGER NOT NULL DEFAULT 0,
                    chaos_experiment_id TEXT,
                    human_approved INTEGER,
                    operator_comment TEXT,
                    raw_data TEXT NOT NULL
                );
            """)

            # Configuration Snapshots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS config_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL, -- 'REFERENCE', 'LIVE', 'ROLLBACK_CHECKPOINT'
                    version TEXT,
                    config_json TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                );
            """)

            # Chaos Experiments table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chaos_experiments (
                    experiment_id TEXT PRIMARY KEY,
                    correlation_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    fault_type TEXT NOT NULL,
                    target_service TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    detected_by_system INTEGER DEFAULT 0,
                    detection_latency_seconds REAL,
                    repaired_by_system INTEGER DEFAULT 0,
                    recovery_time_seconds REAL,
                    raw_data TEXT NOT NULL
                );
            """)

            # Tamper-Evident Immutable Audit Log (Hash-chained block structure)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    correlation_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action_name TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL
                );
            """)

            # Circuit breaker state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_state (
                    service_name TEXT PRIMARY KEY,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    last_failure_time TEXT,
                    is_tripped INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.commit()

    # --- Audit Log (Tamper-Evident SHA-256 Chaining) ---

    def append_audit_event(
        self,
        correlation_id: str,
        actor: str,
        action_name: str,
        details: Dict[str, Any],
    ) -> AuditEvent:
        """Appends an event to the audit trail with SHA-256 cryptographic chaining."""
        with self._get_connection() as conn:
            # Fetch the last event's current_hash
            cursor = conn.execute(
                "SELECT current_hash FROM audit_log ORDER BY sequence_id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            prev_hash = row["current_hash"] if row else ("0" * 64)

            now_dt = utc_now()
            now_str = now_dt.isoformat()
            details_serialized = json.dumps(details, sort_keys=True)

            # Compute current hash over (prev_hash + timestamp + actor + action_name + details)
            hash_input = f"{prev_hash}|{correlation_id}|{now_str}|{actor}|{action_name}|{details_serialized}"
            current_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            event = AuditEvent(
                correlation_id=correlation_id,
                timestamp=now_dt,
                actor=actor,
                action_name=action_name,
                details=details,
                prev_hash=prev_hash,
                current_hash=current_hash,
            )

            conn.execute(
                """
                INSERT INTO audit_log (
                    event_id, correlation_id, timestamp, actor, action_name, details_json, prev_hash, current_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.correlation_id,
                    now_str,
                    event.actor,
                    event.action_name,
                    details_serialized,
                    prev_hash,
                    current_hash,
                ),
            )
            conn.commit()
            return event

    def verify_audit_log_integrity(self) -> Tuple[bool, Optional[str]]:
        """Verifies full cryptographic integrity of the entire audit trail."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT sequence_id, event_id, correlation_id, timestamp, actor, action_name, details_json, prev_hash, current_hash FROM audit_log ORDER BY sequence_id ASC"
            )
            rows = cursor.fetchall()

            expected_prev_hash = "0" * 64
            for row in rows:
                if row["prev_hash"] != expected_prev_hash:
                    return (
                        False,
                        f"Integrity check failed at sequence {row['sequence_id']}: prev_hash mismatch.",
                    )

                hash_input = f"{row['prev_hash']}|{row['correlation_id']}|{row['timestamp']}|{row['actor']}|{row['action_name']}|{row['details_json']}"
                computed_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

                if computed_hash != row["current_hash"]:
                    return (
                        False,
                        f"Integrity check failed at sequence {row['sequence_id']}: current_hash tampered!",
                    )

                expected_prev_hash = row["current_hash"]

            return True, None

    def list_audit_events(
        self, correlation_id: Optional[str] = None, limit: int = 200
    ) -> List[AuditEvent]:
        with self._get_connection() as conn:
            if correlation_id:
                cursor = conn.execute(
                    """
                    SELECT event_id, correlation_id, timestamp, actor, action_name, details_json, prev_hash, current_hash
                    FROM audit_log WHERE correlation_id = ? ORDER BY sequence_id ASC LIMIT ?
                    """,
                    (correlation_id, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT event_id, correlation_id, timestamp, actor, action_name, details_json, prev_hash, current_hash
                    FROM audit_log ORDER BY sequence_id DESC LIMIT ?
                    """,
                    (limit,),
                )
            results = []
            for row in cursor.fetchall():
                results.append(
                    AuditEvent(
                        event_id=row["event_id"],
                        correlation_id=row["correlation_id"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        actor=row["actor"],
                        action_name=row["action_name"],
                        details=json.loads(row["details_json"]),
                        prev_hash=row["prev_hash"],
                        current_hash=row["current_hash"],
                    )
                )
            return results

    # --- Incidents ---

    def save_incident(self, incident: Incident) -> None:
        raw_data = incident.model_dump_json()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO incidents (
                    incident_id, correlation_id, service_name, incident_type, status,
                    summary, detection_timestamp, resolution_timestamp,
                    recovery_duration_seconds, is_chaos_injected, chaos_experiment_id,
                    human_approved, operator_comment, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    status=excluded.status,
                    summary=excluded.summary,
                    resolution_timestamp=excluded.resolution_timestamp,
                    recovery_duration_seconds=excluded.recovery_duration_seconds,
                    human_approved=excluded.human_approved,
                    operator_comment=excluded.operator_comment,
                    raw_data=excluded.raw_data
                """,
                (
                    incident.incident_id,
                    incident.correlation_id,
                    incident.service_name,
                    incident.incident_type.value,
                    incident.status.value,
                    incident.summary,
                    incident.detection_timestamp.isoformat(),
                    incident.resolution_timestamp.isoformat()
                    if incident.resolution_timestamp
                    else None,
                    incident.recovery_duration_seconds,
                    1 if incident.is_chaos_injected else 0,
                    incident.chaos_experiment_id,
                    1
                    if incident.human_approved is True
                    else (0 if incident.human_approved is False else None),
                    incident.operator_comment,
                    raw_data,
                ),
            )
            conn.commit()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT raw_data FROM incidents WHERE incident_id = ?",
                (incident_id,),
            )
            row = cursor.fetchone()
            if row:
                return Incident.model_validate_json(row["raw_data"])
            return None

    def get_incident_by_correlation_id(self, correlation_id: str) -> Optional[Incident]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT raw_data FROM incidents WHERE correlation_id = ?",
                (correlation_id,),
            )
            row = cursor.fetchone()
            if row:
                return Incident.model_validate_json(row["raw_data"])
            return None

    def list_incidents(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Incident]:
        with self._get_connection() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT raw_data FROM incidents WHERE status = ? ORDER BY detection_timestamp DESC LIMIT ?",
                    (status, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT raw_data FROM incidents ORDER BY detection_timestamp DESC LIMIT ?",
                    (limit,),
                )
            return [Incident.model_validate_json(row["raw_data"]) for row in cursor.fetchall()]

    # --- Configuration Snapshots & Checkpoints ---

    def save_config_snapshot(
        self,
        service_name: str,
        config_data: Dict[str, Any],
        snapshot_type: str = "LIVE",
        version: Optional[str] = None,
    ) -> int:
        now_str = utc_now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO config_snapshots (service_name, snapshot_type, version, config_json, captured_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    service_name,
                    snapshot_type,
                    version,
                    json.dumps(config_data),
                    now_str,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_latest_config_snapshot(
        self, service_name: str, snapshot_type: str = "REFERENCE"
    ) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT config_json FROM config_snapshots
                WHERE service_name = ? AND snapshot_type = ?
                ORDER BY snapshot_id DESC LIMIT 1
                """,
                (service_name, snapshot_type),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["config_json"])
            return None

    # --- Chaos Experiments ---

    def save_chaos_experiment(self, experiment: ChaosExperiment) -> None:
        raw_data = experiment.model_dump_json()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO chaos_experiments (
                    experiment_id, correlation_id, name, fault_type, target_service,
                    duration_seconds, status, started_at, ended_at, detected_by_system,
                    detection_latency_seconds, repaired_by_system, recovery_time_seconds, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    status=excluded.status,
                    ended_at=excluded.ended_at,
                    detected_by_system=excluded.detected_by_system,
                    detection_latency_seconds=excluded.detection_latency_seconds,
                    repaired_by_system=excluded.repaired_by_system,
                    recovery_time_seconds=excluded.recovery_time_seconds,
                    raw_data=excluded.raw_data
                """,
                (
                    experiment.experiment_id,
                    experiment.correlation_id,
                    experiment.name,
                    experiment.fault_type,
                    experiment.target_service,
                    experiment.duration_seconds,
                    experiment.status,
                    experiment.started_at.isoformat()
                    if experiment.started_at
                    else None,
                    experiment.ended_at.isoformat()
                    if experiment.ended_at
                    else None,
                    1 if experiment.detected_by_system else 0,
                    experiment.detection_latency_seconds,
                    1 if experiment.repaired_by_system else 0,
                    experiment.recovery_time_seconds,
                    raw_data,
                ),
            )
            conn.commit()

    def get_chaos_experiment(self, experiment_id: str) -> Optional[ChaosExperiment]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT raw_data FROM chaos_experiments WHERE experiment_id = ?",
                (experiment_id,),
            )
            row = cursor.fetchone()
            if row:
                return ChaosExperiment.model_validate_json(row["raw_data"])
            return None

    def list_chaos_experiments(self, limit: int = 50) -> List[ChaosExperiment]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT raw_data FROM chaos_experiments ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
            return [
                ChaosExperiment.model_validate_json(row["raw_data"])
                for row in cursor.fetchall()
            ]

    # --- Circuit Breaker State ---

    def get_circuit_breaker(self, service_name: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT consecutive_failures, last_failure_time, is_tripped FROM circuit_breaker_state WHERE service_name = ?",
                (service_name,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "consecutive_failures": row["consecutive_failures"],
                    "last_failure_time": row["last_failure_time"],
                    "is_tripped": bool(row["is_tripped"]),
                }
            return {
                "consecutive_failures": 0,
                "last_failure_time": None,
                "is_tripped": False,
            }

    def record_repair_failure(self, service_name: str, max_threshold: int = 3) -> bool:
        """Increments repair failure counter and trips circuit breaker if threshold exceeded."""
        now_str = utc_now().isoformat()
        with self._get_connection() as conn:
            current = self.get_circuit_breaker(service_name)
            new_failures = current["consecutive_failures"] + 1
            is_tripped = 1 if new_failures >= max_threshold else 0

            conn.execute(
                """
                INSERT INTO circuit_breaker_state (service_name, consecutive_failures, last_failure_time, is_tripped)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(service_name) DO UPDATE SET
                    consecutive_failures = excluded.consecutive_failures,
                    last_failure_time = excluded.last_failure_time,
                    is_tripped = excluded.is_tripped
                """,
                (service_name, new_failures, now_str, is_tripped),
            )
            conn.commit()
            return bool(is_tripped)

    def reset_circuit_breaker(self, service_name: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO circuit_breaker_state (service_name, consecutive_failures, last_failure_time, is_tripped)
                VALUES (?, 0, NULL, 0)
                ON CONFLICT(service_name) DO UPDATE SET
                    consecutive_failures = 0,
                    last_failure_time = NULL,
                    is_tripped = 0
                """,
                (service_name,),
            )
            conn.commit()

    def clear_all_records(self) -> None:
        """Purges all incidents, snapshots, chaos experiments, and audit logs."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM incidents;")
            conn.execute("DELETE FROM config_snapshots;")
            conn.execute("DELETE FROM chaos_experiments;")
            conn.execute("DELETE FROM audit_log;")
            conn.execute("DELETE FROM circuit_breaker_state;")
            conn.commit()
