from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb

from evolution.schemas import EvolutionRun, ExperienceEntry, FailureEvent


def initialize_experience_tables(db: duckdb.DuckDBPyConnection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS evolution_runs (
            run_id TEXT PRIMARY KEY,
            objective TEXT NOT NULL,
            strategy_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            metadata_json TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS experience_entries (
            experience_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            strategy_type TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            bias_check_json TEXT,
            artifacts_json TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ,
            FOREIGN KEY(run_id) REFERENCES evolution_runs(run_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS failure_events (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            experience_id TEXT,
            stage TEXT NOT NULL,
            failure_type TEXT NOT NULL,
            message TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TIMESTAMPTZ,
            FOREIGN KEY(run_id) REFERENCES evolution_runs(run_id),
            FOREIGN KEY(experience_id) REFERENCES experience_entries(experience_id)
        )
        """
    )


def create_evolution_run(db: duckdb.DuckDBPyConnection, run: EvolutionRun) -> None:
    db.execute(
        """
        INSERT INTO evolution_runs (
            run_id,
            objective,
            strategy_type,
            status,
            created_at,
            completed_at,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run.run_id,
            run.objective,
            run.strategy_type,
            run.status,
            run.created_at,
            run.completed_at,
            json.dumps(run.metadata),
        ],
    )


def update_evolution_run(db: duckdb.DuckDBPyConnection, run: EvolutionRun) -> None:
    db.execute(
        """
        UPDATE evolution_runs
        SET
            objective = ?,
            strategy_type = ?,
            status = ?,
            created_at = ?,
            completed_at = ?,
            metadata_json = ?
        WHERE run_id = ?
        """,
        [
            run.objective,
            run.strategy_type,
            run.status,
            run.created_at,
            run.completed_at,
            json.dumps(run.metadata),
            run.run_id,
        ],
    )


def insert_experience_entry(db: duckdb.DuckDBPyConnection, entry: ExperienceEntry) -> None:
    db.execute(
        """
        INSERT INTO experience_entries (
            experience_id,
            run_id,
            strategy_type,
            candidate_name,
            hypothesis,
            metrics_json,
            bias_check_json,
            artifacts_json,
            notes,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            entry.experience_id,
            entry.run_id,
            entry.strategy_type,
            entry.candidate_name,
            entry.hypothesis,
            json.dumps(entry.metrics),
            json.dumps(entry.bias_check.model_dump(mode="json")) if entry.bias_check is not None else None,
            json.dumps(entry.artifacts),
            entry.notes,
            entry.created_at,
        ],
    )


def insert_failure_event(db: duckdb.DuckDBPyConnection, event: FailureEvent) -> None:
    db.execute(
        """
        INSERT INTO failure_events (
            event_id,
            run_id,
            experience_id,
            stage,
            failure_type,
            message,
            details_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            event.event_id,
            event.run_id,
            event.experience_id,
            event.stage,
            event.failure_type,
            event.message,
            json.dumps(event.details),
            event.created_at,
        ],
    )


def get_experience_by_id(db: duckdb.DuckDBPyConnection, experience_id: str) -> ExperienceEntry | None:
    row = db.execute(
        """
        SELECT
            experience_id,
            run_id,
            strategy_type,
            candidate_name,
            hypothesis,
            metrics_json,
            bias_check_json,
            artifacts_json,
            notes,
            created_at
        FROM experience_entries
        WHERE experience_id = ?
        """,
        [experience_id],
    ).fetchone()
    if row is None:
        return None
    return _experience_from_row(row)


def list_run_experiences(db: duckdb.DuckDBPyConnection, run_id: str) -> list[ExperienceEntry]:
    rows = db.execute(
        """
        SELECT
            experience_id,
            run_id,
            strategy_type,
            candidate_name,
            hypothesis,
            metrics_json,
            bias_check_json,
            artifacts_json,
            notes,
            created_at
        FROM experience_entries
        WHERE run_id = ?
        ORDER BY created_at ASC, experience_id ASC
        """,
        [run_id],
    ).fetchall()
    return [_experience_from_row(row) for row in rows]


def _experience_from_row(row: tuple[object, ...]) -> ExperienceEntry:
    bias_check_json = row[6]
    created_at = row[9]
    payload = {
        "experience_id": row[0],
        "run_id": row[1],
        "strategy_type": row[2],
        "candidate_name": row[3],
        "hypothesis": row[4],
        "metrics": _load_json_object(row[5]),
        "bias_check": _load_json_object(bias_check_json) if bias_check_json is not None else None,
        "artifacts": _load_json_object(row[7]),
        "notes": row[8],
        "created_at": _normalize_datetime(created_at),
    }
    return ExperienceEntry.model_validate(payload)


def _load_json_object(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        raise TypeError(f"Unsupported JSON value: {value!r}")
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise TypeError(f"Expected JSON object, got: {loaded!r}")
    return loaded


def _normalize_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise TypeError(f"Unsupported datetime value: {value!r}")
