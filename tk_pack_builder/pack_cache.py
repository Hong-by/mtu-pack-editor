from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 27


class PackCache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get_open_payload(
        self,
        pack_path: Path,
        include_vanilla: bool,
        reference_paths: list[Path] | None = None,
    ) -> dict[str, Any] | None:
        fingerprint = _fingerprint(pack_path)
        reference_key = _reference_key(reference_paths or [])
        with self._connect() as connection:
            row = connection.execute(
                """
                select analysis_json, characters_json
                from pack_open_cache
                where input_path = ?
                  and mtime_ns = ?
                  and size_bytes = ?
                  and include_vanilla = ?
                  and reference_key = ?
                  and cache_version = ?
                """,
                (
                    str(pack_path.resolve()),
                    fingerprint["mtime_ns"],
                    fingerprint["size_bytes"],
                    int(include_vanilla),
                    reference_key,
                    SCHEMA_VERSION,
                ),
            ).fetchone()
        if row is None:
            return None
        return {
            "ok": True,
            "analysis": json.loads(row["analysis_json"]),
            "characters": json.loads(row["characters_json"]),
            "cache": {
                "hit": True,
                "path": str(self.db_path),
            },
        }

    def put_open_payload(
        self,
        pack_path: Path,
        include_vanilla: bool,
        analysis: dict[str, Any],
        characters: dict[str, Any],
        reference_paths: list[Path] | None = None,
    ) -> None:
        fingerprint = _fingerprint(pack_path)
        reference_key = _reference_key(reference_paths or [])
        with self._connect() as connection:
            connection.execute(
                """
                insert or replace into pack_open_cache (
                    input_path,
                    mtime_ns,
                    size_bytes,
                    include_vanilla,
                    reference_key,
                    cache_version,
                    analysis_json,
                    characters_json,
                    updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(pack_path.resolve()),
                    fingerprint["mtime_ns"],
                    fingerprint["size_bytes"],
                    int(include_vanilla),
                    reference_key,
                    SCHEMA_VERSION,
                    json.dumps(analysis, ensure_ascii=False),
                    json.dumps(characters, ensure_ascii=False),
                    time.time(),
                ),
            )

    def get_asset(
        self,
        pack_path: Path,
        packed_path: str,
    ) -> tuple[str, bytes] | None:
        fingerprint = _fingerprint(pack_path)
        with self._connect() as connection:
            row = connection.execute(
                """
                select content_type, data
                from pack_asset_cache
                where input_path = ?
                  and mtime_ns = ?
                  and size_bytes = ?
                  and packed_path = ?
                """,
                (
                    str(pack_path.resolve()),
                    fingerprint["mtime_ns"],
                    fingerprint["size_bytes"],
                    packed_path,
                ),
            ).fetchone()
        if row is None:
            return None
        return row["content_type"], bytes(row["data"])

    def put_asset(
        self,
        pack_path: Path,
        packed_path: str,
        content_type: str,
        data: bytes,
    ) -> None:
        fingerprint = _fingerprint(pack_path)
        with self._connect() as connection:
            connection.execute(
                """
                insert or replace into pack_asset_cache (
                    input_path,
                    mtime_ns,
                    size_bytes,
                    packed_path,
                    content_type,
                    data,
                    updated_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(pack_path.resolve()),
                    fingerprint["mtime_ns"],
                    fingerprint["size_bytes"],
                    packed_path,
                    content_type,
                    sqlite3.Binary(data),
                    time.time(),
                ),
            )

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(f"pragma user_version = {SCHEMA_VERSION}")
            connection.execute(
                """
                create table if not exists pack_open_cache (
                    input_path text not null,
                    mtime_ns integer not null,
                    size_bytes integer not null,
                    include_vanilla integer not null,
                    reference_key text not null default '',
                    cache_version integer not null default 1,
                    analysis_json text not null,
                    characters_json text not null,
                    updated_at real not null,
                    primary key (input_path, mtime_ns, size_bytes, include_vanilla, reference_key, cache_version)
                )
                """
            )
            _ensure_column(connection, "pack_open_cache", "cache_version", "integer not null default 1")
            _ensure_column(connection, "pack_open_cache", "reference_key", "text not null default ''")
            connection.execute(
                """
                create table if not exists pack_asset_cache (
                    input_path text not null,
                    mtime_ns integer not null,
                    size_bytes integer not null,
                    packed_path text not null,
                    content_type text not null,
                    data blob not null,
                    updated_at real not null,
                    primary key (input_path, mtime_ns, size_bytes, packed_path)
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_pack_asset_cache_path
                on pack_asset_cache (packed_path)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _fingerprint(pack_path: Path) -> dict[str, int]:
    stat = pack_path.stat()
    return {
        "mtime_ns": stat.st_mtime_ns,
        "size_bytes": stat.st_size,
    }


def _reference_key(reference_paths: list[Path]) -> str:
    parts = []
    for path in reference_paths:
        if not path.exists():
            parts.append({"path": str(path.resolve()), "missing": True})
            continue
        stat = path.stat()
        parts.append({
            "path": str(path.resolve()),
            "mtime_ns": stat.st_mtime_ns,
            "size_bytes": stat.st_size,
        })
    return json.dumps(parts, ensure_ascii=False, sort_keys=True)


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"pragma table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"alter table {table_name} add column {column_name} {definition}")
