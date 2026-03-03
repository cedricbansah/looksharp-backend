#!/usr/bin/env python3
"""Infer Firestore field schema from sampled documents."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Firestore schema inventory by sampling documents."
    )
    parser.add_argument(
        "--service-account",
        default=os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", ""),
        help=(
            "Path to Firebase service account JSON. "
            "Defaults to FIREBASE_SERVICE_ACCOUNT_KEY_PATH env var."
        ),
    )
    parser.add_argument(
        "--project-id",
        default="",
        help="Optional Firebase project ID override.",
    )
    parser.add_argument(
        "--max-docs-per-collection",
        type=int,
        default=200,
        help="Max number of docs sampled in each collection/subcollection.",
    )
    parser.add_argument(
        "--output",
        default="firestore_schema_inventory.json",
        help="Output file path.",
    )
    return parser.parse_args()


def initialize_firestore(service_account_path: str, project_id: str) -> firestore.Client:
    options: dict[str, str] = {}
    if project_id:
        options["projectId"] = project_id

    if service_account_path:
        app_cred = credentials.Certificate(service_account_path)
    else:
        app_cred = credentials.ApplicationDefault()

    app = firebase_admin.initialize_app(app_cred, options=options or None)
    return firestore.client(app=app)


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if hasattr(value, "path"):
        return "reference"
    if hasattr(value, "latitude") and hasattr(value, "longitude"):
        return "geopoint"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def walk_map(
    group: str,
    payload: dict[str, Any],
    schema: dict[str, dict[str, set[str]]],
    prefix: str = "",
) -> None:
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        schema[group][path].add(value_type(value))
        if isinstance(value, dict):
            walk_map(group, value, schema, path)


def walk_collection(
    collection_ref: firestore.CollectionReference,
    max_docs_per_collection: int,
    schema: dict[str, dict[str, set[str]]],
    sampled_docs: dict[str, int],
) -> None:
    group_name = collection_ref.id
    for document in collection_ref.limit(max_docs_per_collection).stream():
        sampled_docs[group_name] += 1
        payload = document.to_dict() or {}
        walk_map(group_name, payload, schema)
        for child_collection in document.reference.collections():
            walk_collection(child_collection, max_docs_per_collection, schema, sampled_docs)


def main() -> int:
    args = parse_args()
    if args.max_docs_per_collection <= 0:
        raise ValueError("--max-docs-per-collection must be greater than zero.")

    db = initialize_firestore(args.service_account, args.project_id)
    schema: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    sampled_docs: dict[str, int] = defaultdict(int)

    for root_collection in db.collections():
        walk_collection(root_collection, args.max_docs_per_collection, schema, sampled_docs)

    output: dict[str, Any] = {}
    for collection_group, field_meta in sorted(schema.items()):
        output[collection_group] = {
            "sampled_docs": sampled_docs[collection_group],
            "fields": {
                field_path: sorted(list(type_set))
                for field_path, type_set in sorted(field_meta.items())
            },
        }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote schema inventory to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
