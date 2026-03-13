"""Firestore to PostgreSQL migration helpers."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import firebase_admin
import psycopg2
from firebase_admin import credentials, firestore
from psycopg2 import Binary, sql
from psycopg2.extras import Json, execute_values

LOGGER = logging.getLogger("firestore_to_postgres")
FIRESTORE_APP_NAME = "firestore-migration"


def default_config_path() -> Path:
    return Path(__file__).resolve().parent / "migration" / "firestore_to_postgres.mapping.json"


def load_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    mappings = payload.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise ValueError("Config must include a non-empty 'mappings' list.")

    return payload


def parse_service_account_json(service_account_json: str) -> dict[str, Any]:
    payload = service_account_json.strip()
    if not payload:
        raise ValueError("Empty service account JSON payload.")

    if payload.startswith("{"):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid raw JSON in service account payload.") from exc

    try:
        decoded = base64.b64decode(payload).decode("utf-8")
        return json.loads(decoded)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "Invalid service account payload. Provide raw JSON or base64-encoded JSON."
        ) from exc


def initialize_firestore(
    service_account_path: str,
    service_account_json: str,
    project_id: str,
) -> firestore.Client:
    options: dict[str, str] = {}
    if project_id:
        options["projectId"] = project_id

    if service_account_json:
        credential = credentials.Certificate(parse_service_account_json(service_account_json))
    elif service_account_path:
        credential = credentials.Certificate(service_account_path)
    else:
        credential = credentials.ApplicationDefault()

    try:
        app = firebase_admin.get_app(FIRESTORE_APP_NAME)
    except ValueError:
        app = firebase_admin.initialize_app(
            credential,
            options=options or None,
            name=FIRESTORE_APP_NAME,
        )

    return firestore.client(app=app)


def connect_postgres(database_url: str) -> psycopg2.extensions.connection:
    if not database_url:
        raise ValueError("Missing Postgres connection string. Set --database-url or DATABASE_URL.")
    return psycopg2.connect(database_url)


def deep_get(data: dict[str, Any], dotted_path: str) -> Any:
    if not dotted_path:
        return None

    current: Any = data
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def extract_mapped_value(document: dict[str, Any], field_spec: Any) -> Any:
    if isinstance(field_spec, str):
        return deep_get(document, field_spec)
    if isinstance(field_spec, list):
        for candidate in field_spec:
            if not isinstance(candidate, str):
                continue
            value = deep_get(document, candidate)
            if value is not None:
                return value
        return None
    return None


def resolve_document_id(snapshot: firestore.DocumentSnapshot, mapping: dict[str, Any]) -> str:
    strategy = mapping.get("document_id_strategy", "raw")
    raw_id = snapshot.id
    if strategy == "raw":
        return raw_id
    if strategy == "uuid5":
        return str(uuid.uuid5(uuid.NAMESPACE_URL, snapshot.reference.path))
    if strategy == "uuid5_if_invalid":
        try:
            uuid.UUID(str(raw_id))
            return str(raw_id)
        except (TypeError, ValueError):
            return str(uuid.uuid5(uuid.NAMESPACE_URL, snapshot.reference.path))
    raise ValueError(
        f"Invalid document_id_strategy '{strategy}'. "
        "Use one of: raw, uuid5, uuid5_if_invalid."
    )


def normalize_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): normalize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_json(item) for item in value]
    if hasattr(value, "path"):  # Firestore DocumentReference
        return getattr(value, "path")
    if hasattr(value, "latitude") and hasattr(value, "longitude"):  # GeoPoint
        return {"latitude": value.latitude, "longitude": value.longitude}
    return str(value)


def to_db_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool, datetime, date)):
        return value
    if isinstance(value, bytes):
        return Binary(value)
    if hasattr(value, "path"):  # Firestore DocumentReference
        return getattr(value, "path")
    if hasattr(value, "latitude") and hasattr(value, "longitude"):  # GeoPoint
        return Json({"latitude": value.latitude, "longitude": value.longitude})
    if isinstance(value, (dict, list, tuple, set)):
        return Json(normalize_json(value))
    return str(value)


def resolve_columns(mapping: dict[str, Any]) -> list[str]:
    columns: list[str] = []

    def add(col: str | None) -> None:
        if col and col not in columns:
            columns.append(col)

    for col in mapping.get("static_values", {}).keys():
        add(col)
    add(mapping.get("document_id_column"))
    add(mapping.get("document_path_column"))
    add(mapping.get("parent_document_id_column"))
    add(mapping.get("parent_document_path_column"))
    for col in mapping.get("field_map", {}).keys():
        add(col)
    for col in mapping.get("defaults", {}).keys():
        add(col)
    add(mapping.get("raw_json_column"))
    return columns


def iter_documents(
    db: firestore.Client, source: dict[str, Any]
) -> Iterator[firestore.DocumentSnapshot]:
    source_type = source.get("type", "collection")
    name = source.get("name")
    limit = source.get("limit")
    path_starts_with = source.get("path_starts_with")
    yielded = 0

    if source_type == "collection":
        if not name:
            raise ValueError("source.name is required for source.type='collection'.")
        stream = db.collection(name).stream()
        for snapshot in stream:
            if path_starts_with and not snapshot.reference.path.startswith(path_starts_with):
                continue
            yield snapshot
            yielded += 1
            if limit and yielded >= int(limit):
                return
        return

    if source_type == "collection_group":
        if not name:
            raise ValueError("source.name is required for source.type='collection_group'.")
        stream = db.collection_group(name).stream()
        for snapshot in stream:
            if path_starts_with and not snapshot.reference.path.startswith(path_starts_with):
                continue
            yield snapshot
            yielded += 1
            if limit and yielded >= int(limit):
                return
        return

    if source_type == "subcollection":
        parent_collection = source.get("parent_collection")
        if not parent_collection or not name:
            raise ValueError(
                "source.parent_collection and source.name are required for source.type='subcollection'."
            )
        for parent_doc in db.collection(parent_collection).stream():
            for snapshot in parent_doc.reference.collection(name).stream():
                if path_starts_with and not snapshot.reference.path.startswith(path_starts_with):
                    continue
                yield snapshot
                yielded += 1
                if limit and yielded >= int(limit):
                    return
        return

    raise ValueError(f"Unsupported source.type: {source_type}")


def build_row(
    snapshot: firestore.DocumentSnapshot,
    mapping: dict[str, Any],
    columns: list[str],
) -> tuple[tuple[Any, ...] | None, str | None]:
    document = snapshot.to_dict() or {}
    row: dict[str, Any] = {col: None for col in columns}

    row.update(mapping.get("static_values", {}))

    document_id_column = mapping.get("document_id_column")
    if document_id_column:
        row[document_id_column] = resolve_document_id(snapshot, mapping)

    document_path_column = mapping.get("document_path_column")
    if document_path_column:
        row[document_path_column] = snapshot.reference.path

    parent_doc = snapshot.reference.parent.parent
    if parent_doc is not None:
        parent_document_id_column = mapping.get("parent_document_id_column")
        if parent_document_id_column:
            row[parent_document_id_column] = parent_doc.id
        parent_document_path_column = mapping.get("parent_document_path_column")
        if parent_document_path_column:
            row[parent_document_path_column] = parent_doc.path

    for db_column, field_spec in mapping.get("field_map", {}).items():
        raw_value = extract_mapped_value(document, field_spec)
        if raw_value is None:
            continue
        row[db_column] = to_db_value(raw_value)

    for db_column, default_value in mapping.get("defaults", {}).items():
        if row.get(db_column) is None:
            row[db_column] = default_value

    raw_json_column = mapping.get("raw_json_column")
    if raw_json_column:
        row[raw_json_column] = Json(normalize_json(document))

    for column in mapping.get("required_columns", []):
        value = row.get(column)
        if value is None or value == "":
            return None, f"missing required column '{column}'"

    return tuple(row[col] for col in columns), None


def build_insert_sql(
    table: str,
    columns: list[str],
    conflict_columns: list[str],
    conflict_action: str,
) -> sql.Composed:
    table_sql = sql.SQL(".").join(sql.Identifier(part) for part in table.split("."))
    columns_sql = sql.SQL(", ").join(sql.Identifier(col) for col in columns)
    on_conflict_sql = sql.SQL("")

    if conflict_columns:
        conflict_sql = sql.SQL(", ").join(sql.Identifier(col) for col in conflict_columns)
        action = conflict_action.lower()
        if action == "nothing":
            on_conflict_sql = sql.SQL(" ON CONFLICT ({}) DO NOTHING").format(conflict_sql)
        elif action == "update":
            update_columns = [col for col in columns if col not in set(conflict_columns)]
            if update_columns:
                assignments = sql.SQL(", ").join(
                    sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
                    for col in update_columns
                )
                on_conflict_sql = sql.SQL(" ON CONFLICT ({}) DO UPDATE SET {}").format(
                    conflict_sql, assignments
                )
            else:
                on_conflict_sql = sql.SQL(" ON CONFLICT ({}) DO NOTHING").format(conflict_sql)
        else:
            raise ValueError(
                f"Invalid conflict_action '{conflict_action}'. Use 'update' or 'nothing'."
            )

    return sql.SQL("INSERT INTO {} ({}) VALUES %s{}").format(
        table_sql,
        columns_sql,
        on_conflict_sql,
    )


def build_table_sql(table: str) -> sql.Composed:
    return sql.SQL(".").join(sql.Identifier(part) for part in table.split("."))


def table_exists(conn: psycopg2.extensions.connection, table: str) -> bool:
    with conn.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s)", (table,))
        return cursor.fetchone()[0] is not None


def split_table_name(table: str) -> tuple[str, str]:
    if "." in table:
        schema, name = table.split(".", 1)
        return schema, name
    return "public", table


def get_table_columns(
    conn: psycopg2.extensions.connection, table: str
) -> set[str]:
    schema, name = split_table_name(table)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (schema, name),
        )
        rows = cursor.fetchall()
    return {column for (column,) in rows}


def get_varchar_limits(
    conn: psycopg2.extensions.connection, table: str
) -> dict[str, int]:
    schema, name = split_table_name(table)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND data_type IN ('character varying', 'character')
              AND character_maximum_length IS NOT NULL
            """,
            (schema, name),
        )
        rows = cursor.fetchall()
    return {column: int(length) for column, length in rows}


def load_existing_values(
    conn: psycopg2.extensions.connection, table: str, table_column: str
) -> set[str]:
    table_sql = build_table_sql(table)
    query = sql.SQL("SELECT {} FROM {}").format(sql.Identifier(table_column), table_sql)
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}


def build_require_existing_checks(
    conn: psycopg2.extensions.connection,
    mapping_name: str,
    columns: list[str],
    require_existing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for rule in require_existing:
        row_column = rule.get("row_column")
        table = rule.get("table")
        table_column = rule.get("table_column", "id")
        if not row_column or not table:
            raise ValueError(
                f"Invalid require_existing rule in mapping '{mapping_name}': {rule}"
            )
        if row_column not in columns:
            raise ValueError(
                f"Invalid require_existing row_column '{row_column}' in mapping '{mapping_name}'."
            )
        values = load_existing_values(conn, table, table_column)
        LOGGER.info(
            "Mapping '%s': loaded %s reference values from %s.%s",
            mapping_name,
            len(values),
            table,
            table_column,
        )
        checks.append(
            {
                "row_column": row_column,
                "row_index": columns.index(row_column),
                "table": table,
                "table_column": table_column,
                "values": values,
            }
        )
    return checks


def validate_row_references(
    row: tuple[Any, ...], checks: list[dict[str, Any]]
) -> str | None:
    for check in checks:
        value = row[check["row_index"]]
        if value is None:
            continue
        if str(value) not in check["values"]:
            return (
                f"missing referenced value '{check['row_column']}'='{value}' "
                f"in {check['table']}.{check['table_column']}"
            )
    return None


def format_insert_error(
    *,
    mapping_name: str,
    doc_path: str,
    exception: Exception,
    columns: list[str],
    row: tuple[Any, ...],
    varchar_limits: dict[str, int],
) -> str:
    details: list[str] = []
    for column, value in zip(columns, row):
        if not isinstance(value, str):
            continue
        max_length = varchar_limits.get(column)
        if max_length and len(value) > max_length:
            details.append(f"{column}={len(value)}>{max_length}")

    base = str(exception).replace("\n", " ").strip()
    if details:
        base = f"{base} | likely overflow columns: {', '.join(details)}"
    return f"mapping='{mapping_name}' doc='{doc_path}' error='{base}'"


def flush_batch(
    conn: psycopg2.extensions.connection,
    statement: sql.Composed,
    rows: list[tuple[str, tuple[Any, ...]]],
    columns: list[str],
    varchar_limits: dict[str, int],
    mapping_name: str,
    page_size: int,
    dry_run: bool,
) -> int:
    if not rows:
        return 0
    if dry_run:
        return len(rows)

    values = [entry[1] for entry in rows]
    sql_text = statement.as_string(conn)

    try:
        with conn.cursor() as cursor:
            execute_values(cursor, sql_text, values, page_size=page_size)
        conn.commit()
        return len(rows)
    except Exception as batch_exc:  # noqa: BLE001
        conn.rollback()
        recovered = 0
        for doc_path, row in rows:
            try:
                with conn.cursor() as cursor:
                    execute_values(cursor, sql_text, [row], page_size=1)
                conn.commit()
                recovered += 1
            except Exception as row_exc:  # noqa: BLE001
                conn.rollback()
                raise ValueError(
                    format_insert_error(
                        mapping_name=mapping_name,
                        doc_path=doc_path,
                        exception=row_exc,
                        columns=columns,
                        row=row,
                        varchar_limits=varchar_limits,
                    )
                ) from batch_exc
        return recovered


def migrate_mapping(
    conn: psycopg2.extensions.connection,
    db: firestore.Client,
    mapping: dict[str, Any],
    batch_size: int,
    dry_run: bool,
) -> dict[str, Any]:
    target = mapping.get("target", {})
    source = mapping.get("source", {})
    table = target.get("table")
    if not table:
        raise ValueError("Each mapping must include target.table.")

    if not table_exists(conn, table):
        raise ValueError(f"Target table does not exist: {table}")

    columns = resolve_columns(mapping)
    if not columns:
        raise ValueError(f"No target columns resolved for table {table}.")

    conflict_columns = target.get("conflict_columns", [])
    table_columns = get_table_columns(conn, table)
    missing_columns = sorted(set(columns) - table_columns)
    if missing_columns:
        raise ValueError(
            f"Mapping '{mapping.get('name', table)}' references columns not found in {table}: "
            f"{missing_columns}"
        )
    missing_conflict_columns = sorted(set(conflict_columns) - table_columns)
    if missing_conflict_columns:
        raise ValueError(
            f"Mapping '{mapping.get('name', table)}' conflict_columns not found in {table}: "
            f"{missing_conflict_columns}"
        )

    conflict_action = target.get("conflict_action", "update")
    statement = build_insert_sql(table, columns, conflict_columns, conflict_action)
    varchar_limits = get_varchar_limits(conn, table)
    reference_checks = build_require_existing_checks(
        conn=conn,
        mapping_name=mapping.get("name", table),
        columns=columns,
        require_existing=mapping.get("require_existing", []),
    )

    if target.get("truncate_before_load", False):
        if dry_run:
            LOGGER.info("Dry-run: skipping truncate on %s", table)
        else:
            LOGGER.warning("Truncating table %s before loading", table)
            with conn.cursor() as cursor:
                cursor.execute(sql.SQL("TRUNCATE TABLE {}").format(build_table_sql(table)))
            conn.commit()

    mapping_name = mapping.get("name", table)
    LOGGER.info("Starting mapping '%s' -> %s", mapping_name, table)

    processed = 0
    skipped = 0
    loaded = 0
    skip_reason_counts: dict[str, int] = defaultdict(int)
    batch: list[tuple[str, tuple[Any, ...]]] = []

    for snapshot in iter_documents(db, source):
        processed += 1
        try:
            row, skip_reason = build_row(snapshot, mapping, columns)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            reason = f"build_row_error: {exc}"
            skip_reason_counts[reason] += 1
            LOGGER.warning(
                "Skipping mapping '%s' doc='%s': %s",
                mapping_name,
                snapshot.reference.path,
                reason,
            )
            continue

        if row is None:
            skipped += 1
            reason = skip_reason or "row_filtered"
            skip_reason_counts[reason] += 1
            LOGGER.warning(
                "Skipping mapping '%s' doc='%s': %s",
                mapping_name,
                snapshot.reference.path,
                reason,
            )
            continue

        reference_error = validate_row_references(row, reference_checks)
        if reference_error:
            skipped += 1
            skip_reason_counts[reference_error] += 1
            LOGGER.warning(
                "Skipping mapping '%s' doc='%s': %s",
                mapping_name,
                snapshot.reference.path,
                reference_error,
            )
            continue

        batch.append((snapshot.reference.path, row))
        if len(batch) >= batch_size:
            loaded += flush_batch(
                conn=conn,
                statement=statement,
                rows=batch,
                columns=columns,
                varchar_limits=varchar_limits,
                mapping_name=mapping_name,
                page_size=batch_size,
                dry_run=dry_run,
            )
            LOGGER.info(
                "Mapping '%s': processed=%s loaded=%s skipped=%s",
                mapping_name,
                processed,
                loaded,
                skipped,
            )
            batch.clear()

    if batch:
        loaded += flush_batch(
            conn=conn,
            statement=statement,
            rows=batch,
            columns=columns,
            varchar_limits=varchar_limits,
            mapping_name=mapping_name,
            page_size=batch_size,
            dry_run=dry_run,
        )

    LOGGER.info(
        "Completed mapping '%s': processed=%s loaded=%s skipped=%s",
        mapping_name,
        processed,
        loaded,
        skipped,
    )
    if skip_reason_counts:
        LOGGER.info(
            "Mapping '%s' skip reasons: %s",
            mapping_name,
            dict(sorted(skip_reason_counts.items())),
        )

    return {
        "mapping": mapping_name,
        "table": table,
        "processed": processed,
        "loaded": loaded,
        "skipped": skipped,
        "skip_reasons": dict(sorted(skip_reason_counts.items())),
    }


def run_migration(
    *,
    config_path: str,
    database_url: str,
    service_account_path: str,
    service_account_json: str,
    project_id: str,
    batch_size_override: int | None,
    dry_run: bool,
) -> dict[str, Any]:
    config = load_config(config_path)
    batch_size = int(batch_size_override or config.get("batch_size", 500))
    if batch_size <= 0:
        raise ValueError("Batch size must be > 0.")

    firestore_client = initialize_firestore(
        service_account_path=service_account_path,
        service_account_json=service_account_json,
        project_id=project_id,
    )
    conn = connect_postgres(database_url)
    start = time.time()

    try:
        results: list[dict[str, Any]] = []
        for mapping in config["mappings"]:
            results.append(
                migrate_mapping(
                    conn=conn,
                    db=firestore_client,
                    mapping=mapping,
                    batch_size=batch_size,
                    dry_run=dry_run,
                )
            )
    finally:
        conn.close()

    elapsed = round(time.time() - start, 2)
    total_processed = sum(item["processed"] for item in results)
    total_loaded = sum(item["loaded"] for item in results)
    total_skipped = sum(item["skipped"] for item in results)

    LOGGER.info("Migration completed in %ss", elapsed)
    LOGGER.info(
        "Totals: processed=%s loaded=%s skipped=%s dry_run=%s",
        total_processed,
        total_loaded,
        total_skipped,
        dry_run,
    )

    return {
        "elapsed": elapsed,
        "batch_size": batch_size,
        "dry_run": dry_run,
        "results": results,
        "totals": {
            "processed": total_processed,
            "loaded": total_loaded,
            "skipped": total_skipped,
        },
    }


def env_default(name: str) -> str:
    return os.getenv(name, "")
