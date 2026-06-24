from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .adapters import RpfmPackSession, _encode_rpfm_cell
from .character_clone import CHARACTER_TABLE_ALIASES, resolve_character_table_name
from .recipe import CharacterClone, CharacterPatch, Recipe
from .stat_tables import resolve_stat_target
from .validation import has_errors, validate


def build_delta_pack(
    session: RpfmPackSession,
    recipe: Recipe,
    output_path: Path,
) -> list[dict[str, object]]:
    output_path = output_path.resolve()
    messages = validate(session, recipe, str(output_path))
    if has_errors(messages):
        return [
            {"level": message.level, "code": message.code, "message": message.message}
            for message in messages
        ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_dbs: dict[str, dict[str, Any]] = {}
    rows_by_table: dict[str, list[dict[str, Any]]] = {}

    changed_stats = _collect_stat_patch_rows(session, recipe, source_dbs, rows_by_table)
    changed_character_fields = _collect_character_patch_rows(session, recipe.character_patches, source_dbs, rows_by_table)
    cloned_characters = _collect_character_clone_rows(session, recipe.character_clones, source_dbs, rows_by_table)

    target_key = _new_delta_pack(session)
    try:
        for table_path, rows in rows_by_table.items():
            source_db = source_dbs[table_path]
            delta_db = _db_with_rows(source_db, rows)
            table = delta_db["table"]
            _raise_rpfm_error(session.client.send({
                "NewPackedFile": [
                    target_key,
                    table_path,
                    {"DB": [table_path, table["table_name"], table["definition"]["version"]]},
                ]
            }))
            _raise_rpfm_error(session.client.send({
                "SavePackedFileFromView": [target_key, table_path, {"DB": delta_db}]
            }))

        _raise_rpfm_error(session.client.send({"SavePackAs": [target_key, str(output_path)]}))
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise

    return [
        {"level": message.level, "code": message.code, "message": message.message}
        for message in messages
    ] + [
        {
            "level": "success",
            "code": "delta_pack_written",
            "message": (
                f"Wrote delta patch pack {output_path} ({output_path.stat().st_size} bytes) "
                f"with {len(rows_by_table)} DB table(s), {changed_stats} edited equipment stat value(s), "
                f"{changed_character_fields} edited character field(s), and {cloned_characters} cloned character(s)."
            ),
        }
    ]


def _collect_stat_patch_rows(
    session: RpfmPackSession,
    recipe: Recipe,
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
) -> int:
    changed = 0
    for patch in recipe.equipment_stat_patches:
        target = resolve_stat_target(
            session,
            patch.equipment_key,
            patch.stat_table,
            patch.column,
            patch.value,
            patch.game_mode,
        )
        rows = _read_rows(session, target.table_name, source_dbs)
        row = _find_required(rows, "key", target.row_key)
        patched = {**row, target.column: target.value}
        _upsert_delta_row(rows_by_table, target.table_name, "key", patched)
        changed += 1
    return changed


def _collect_character_patch_rows(
    session: RpfmPackSession,
    patches: list[CharacterPatch],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
) -> int:
    if not patches:
        return 0
    table_names = {
        alias: resolve_character_table_name(session, alias)
        for alias in (
            "character_generation_templates",
            "character_generation_template_game_mode_details",
        )
    }
    templates = _read_rows(session, table_names["character_generation_templates"], source_dbs)
    details = _read_rows(session, table_names["character_generation_template_game_mode_details"], source_dbs)

    changed = 0
    for patch in patches:
        template = dict(_find_required(templates, "key", patch.template_key))
        for column, value in patch.template_overrides.items():
            if template.get(column) != value:
                template[column] = value
                changed += 1
        _upsert_delta_row(rows_by_table, table_names["character_generation_templates"], "key", template)

        for detail in [
            row for row in details
            if row.get("character_generation_template") == patch.template_key
        ]:
            overrides = patch.detail_overrides.get(detail.get("game_mode", ""), {})
            if not overrides:
                continue
            patched = dict(detail)
            for column, value in overrides.items():
                if patched.get(column) != value:
                    patched[column] = value
                    changed += 1
            _upsert_delta_row(
                rows_by_table,
                table_names["character_generation_template_game_mode_details"],
                _detail_key,
                patched,
            )
    return changed


def _collect_character_clone_rows(
    session: RpfmPackSession,
    clones: list[CharacterClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
) -> int:
    if not clones:
        return 0

    table_names = {
        alias: resolve_character_table_name(session, alias)
        for alias in CHARACTER_TABLE_ALIASES
    }
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }

    created = 0
    for clone in clones:
        source_template = dict(_find_required(
            tables["character_generation_templates"],
            "key",
            clone.source_template_key,
        ))
        new_template = {
            **source_template,
            "key": clone.new_template_key,
            **clone.template_overrides,
        }

        if clone.new_art_set_id:
            new_template["art_set_override"] = clone.new_art_set_id
            source_art_set = clone.art_set_source_id or source_template["art_set_override"]
            _clone_art_set_delta(tables, table_names, rows_by_table, source_art_set, clone)

        if clone.new_age_range_key:
            new_template["spawn_age_range"] = clone.new_age_range_key
            source_age = clone.age_range_source_key or source_template["spawn_age_range"]
            _clone_keyed_delta(
                tables["character_generation_spawn_age_ranges"],
                rows_by_table,
                table_names["character_generation_spawn_age_ranges"],
                "key",
                source_age,
                clone.new_age_range_key,
                clone.age_range_overrides,
            )

        _upsert_delta_row(
            rows_by_table,
            table_names["character_generation_templates"],
            "key",
            new_template,
        )
        created += 1

        source_details = [
            row for row in tables["character_generation_template_game_mode_details"]
            if row.get("character_generation_template") == clone.detail_source_template_key
        ]
        if clone.new_initial_ceo_key:
            source_ceo = clone.initial_ceo_source_key or source_details[0]["initial_ceos"]
            _clone_keyed_delta(
                tables["ceo_initial_datas"],
                rows_by_table,
                table_names["ceo_initial_datas"],
                "key",
                source_ceo,
                clone.new_initial_ceo_key,
                {},
            )

        for source_detail in source_details:
            game_mode = source_detail.get("game_mode", "")
            overrides = clone.detail_overrides.get(game_mode, {})
            new_detail = {
                **source_detail,
                "character_generation_template": clone.new_template_key,
                **overrides,
            }
            if clone.new_initial_ceo_key:
                new_detail["initial_ceos"] = clone.new_initial_ceo_key
            _upsert_delta_row(
                rows_by_table,
                table_names["character_generation_template_game_mode_details"],
                _detail_key,
                new_detail,
            )
    return created


def _clone_art_set_delta(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    source_art_set: str,
    clone: CharacterClone,
) -> None:
    _clone_keyed_delta(
        tables["campaign_character_art_sets"],
        rows_by_table,
        table_names["campaign_character_art_sets"],
        "art_set_id",
        source_art_set,
        clone.new_art_set_id or source_art_set,
        clone.art_set_overrides,
    )
    for art_row in [
        row for row in tables["campaign_character_arts"]
        if row.get("art_set_id") == source_art_set
    ]:
        _upsert_delta_row(
            rows_by_table,
            table_names["campaign_character_arts"],
            _art_key,
            {
                **art_row,
                "art_set_id": clone.new_art_set_id,
                **clone.art_overrides,
            },
        )


def _clone_keyed_delta(
    rows: list[dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_name: str,
    key_field: str,
    source_key: str,
    new_key: str,
    overrides: dict[str, Any],
) -> None:
    source = _find_required(rows, key_field, source_key)
    _upsert_delta_row(
        rows_by_table,
        table_name,
        key_field,
        {**source, key_field: new_key, **overrides},
    )


def _read_rows(
    session: RpfmPackSession,
    table_name: str,
    source_dbs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = session.read_table(table_name)
    path = session._resolve_table_path(table_name)
    source_dbs[path] = copy.deepcopy(session.decoded_db_by_path[path])
    return rows


def _db_with_rows(source_db: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    db = copy.deepcopy(source_db)
    table = db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    template_row = table["table_data"][0]
    table["table_data"] = [
        [
            _encode_rpfm_cell(template_cell, row.get(field_name))
            for field_name, template_cell in zip(fields, template_row, strict=True)
        ]
        for row in rows
    ]
    return db


def _new_delta_pack(session: RpfmPackSession) -> str:
    response = session.client.send("NewPack")
    _raise_rpfm_error(response)
    target_key = response["data"]["String"]
    _raise_rpfm_error(session.client.send({"SetPackFileType": [target_key, "Mod"]}))
    return target_key


def _upsert_delta_row(
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_name: str,
    key_field: str | Any,
    row: dict[str, Any],
) -> None:
    rows = rows_by_table.setdefault(table_name, [])
    row_key = key_field(row) if callable(key_field) else row.get(key_field)
    for index, existing in enumerate(rows):
        existing_key = key_field(existing) if callable(key_field) else existing.get(key_field)
        if existing_key == row_key:
            rows[index] = row
            return
    rows.append(row)


def _find_required(rows: list[dict[str, Any]], key_field: str, key: str) -> dict[str, Any]:
    for row in rows:
        if row.get(key_field) == key:
            return row
    raise ValueError(f"Row not found: {key_field}={key}")


def _detail_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("character_generation_template"), row.get("game_mode")


def _art_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("art_set_id"),
        row.get("age"),
        row.get("is_female"),
        row.get("has_come_of_age"),
    )


def _raise_rpfm_error(response: dict[str, Any]) -> None:
    data = response.get("data")
    if isinstance(data, dict) and "Error" in data:
        raise ValueError(data["Error"])
