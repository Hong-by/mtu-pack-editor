from __future__ import annotations

import copy
import json
import os
import struct
from pathlib import Path
from typing import Any
import zlib

from .adapters import RpfmPackSession, _decode_rpfm_cell, _encode_rpfm_cell
from .character_clone import CHARACTER_TABLE_ALIASES, resolve_character_table_name
from .land_units import validate_land_unit_clone
from .recipe import AgeRangeClone, ArmourTypeClone, AttributeSetClone, CharacterClone, CharacterPatch, Recipe, SkillSetClone, recipe_from_dict
from .stat_tables import TABLE_ALIASES, StatTarget, resolve_stat_target, resolve_table_name


LEGACY_TEMPLATE_PACK = Path("work/legacy_template/8King_4P_1.7_up.pack")
ROOT = Path(os.environ.get("TK_PACK_EDITOR_ROOT", Path(__file__).resolve().parents[1])).resolve()
EXTRACTED_ASSET_ROOT = ROOT / "work" / "assets"
CORE_ASSET_SOURCE_ID = "17309a40b912"
IMAGE_ONLY_ASSET_PREFIX = "__image_only_reference__"
TEMP_IMAGE_ASSET_ROOT = ROOT / "work" / "tmp_delta_image_assets"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_COMMENT_KEY = "Comment"
PANEL_COMMENT_FALLBACKS = {
    ("large_panel", "angry"): "[type:angry;x:-80;y:121;z-order:0;pivot_x:0.5001;pivot_y:0.5000;]",
    ("large_panel", "happy"): "[type:happy;x:-33;y:122;z-order:0;pivot_x:0.4995;pivot_y:0.4997;]",
    ("large_panel", "norm"): "[type:norm;x:-10;y:122;z-order:0;pivot_x:0.4999;pivot_y:0.4998;]",
    ("small_panel", "angry"): "[type:angry;x:-55;y:84;z-order:0;pivot_x:0.5008;pivot_y:0.5006;]",
    ("small_panel", "happy"): "[type:happy;x:-23;y:84;z-order:0;pivot_x:0.4993;pivot_y:0.4995;]",
    ("small_panel", "norm"): "[type:norm;x:-7;y:84;z-order:0;pivot_x:0.4997;pivot_y:0.4996;]",
    ("root", "norm"): "[type:norm;x:-10;y:122;z-order:0;pivot_x:0.4999;pivot_y:0.4998;]",
}


def build_delta_pack(
    session: RpfmPackSession,
    recipe: Recipe,
    output_path: Path,
    reference_paths: list[Path] | None = None,
) -> list[dict[str, object]]:
    output_path = output_path.resolve()
    messages: list[Any] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_dbs: dict[str, dict[str, Any]] = {}
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    loc_rows: dict[str, str] = {}
    opened_pack_keys = {str(session.pack_path.resolve()): session.pack_key}
    patched_skill_set_keys: set[str] = set()

    changed_stats = 0
    cloned_armour_types = 0
    cloned_land_units = 0
    attribute_sets = 0
    skill_sets = 0
    age_ranges = 0
    changed_character_fields = 0
    cloned_characters = 0
    copied_dependency_rows = 0
    processed_clones: list[CharacterClone] = []
    processed_patches: list[CharacterPatch] = []

    for work_recipe in _processing_recipes(recipe):
        patched_skill_set_keys.update(clone.new_set_key for clone in work_recipe.skill_set_clones)
        changed_stats += _collect_stat_patch_rows(
            session,
            work_recipe,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        cloned_armour_types += _collect_armour_type_clone_rows(
            session,
            work_recipe.armour_type_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        cloned_land_units += _collect_land_unit_clone_rows(
            session,
            work_recipe,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        attribute_sets += _collect_attribute_set_clone_rows(
            session,
            work_recipe.attribute_set_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        skill_sets += _collect_skill_set_clone_rows(
            session,
            work_recipe.skill_set_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        age_ranges += _collect_age_range_clone_rows(
            session,
            work_recipe.age_range_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        changed_character_fields += _collect_character_patch_rows(
            session,
            work_recipe.character_patches,
            source_dbs,
            rows_by_table,
            loc_rows,
            patched_skill_set_keys,
            reference_paths or [],
            opened_pack_keys,
        )
        cloned_characters += _collect_character_clone_rows(
            session,
            work_recipe.character_clones,
            source_dbs,
            rows_by_table,
            loc_rows,
            reference_paths or [],
            opened_pack_keys,
        )
        copied_dependency_rows += _collect_character_dependency_rows(
            session,
            work_recipe.character_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        processed_clones.extend(work_recipe.character_clones)
        processed_patches.extend(work_recipe.character_patches)

    campaign_script = _campaign_start_spawn_script(processed_clones)
    diagnostic_warnings = [
        *_clone_image_asset_target_warnings(processed_clones),
        *_image_asset_path_warnings([*processed_clones, *processed_patches]),
    ]
    processed_recipe = _recipe_with_processed_characters(recipe, processed_clones, processed_patches)
    _write_delta_diagnostics(
        output_path,
        processed_recipe,
        rows_by_table,
        loc_rows,
        campaign_script,
        diagnostic_warnings,
    )

    target_key = _new_delta_pack(session)
    try:
        for table_path, rows in rows_by_table.items():
            source_db = source_dbs[table_path]
            _write_db_file(session, target_key, table_path, source_db, rows)

        if campaign_script:
            _write_lua_text_file(
                session,
                target_key,
                "script/campaign/mod/hby_mtu_pack_editor_player_spawn.lua",
                campaign_script,
            )

        if loc_rows:
            _write_loc_file(
                session,
                target_key,
                "text/hby_mtu_pack_editor_names.loc",
                loc_rows,
            )

        incident_tables = _write_spawn_incident_tables(session, target_key, processed_clones)
        copied_assets = _copy_image_assets(
            session,
            target_key,
            [*processed_clones, *processed_patches],
            opened_pack_keys,
        )

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
                f"{cloned_armour_types} cloned armour type row(s), "
                f"{cloned_land_units} cloned land unit row(s), "
                f"{attribute_sets} cloned attribute set(s), "
                f"{skill_sets} cloned romance skill set(s), "
                f"{age_ranges} cloned age range row(s), "
                f"{changed_character_fields} edited character field(s), {cloned_characters} cloned character(s), "
                f"{copied_dependency_rows} referenced DB row(s), "
                f"{len(loc_rows)} name loc row(s), {incident_tables} spawn incident table(s), "
                f"{copied_assets} image asset(s), "
                f"and {1 if campaign_script else 0} campaign script(s)."
            ),
        }
    ]


def build_delta_pack_from_materials(
    source_session: Any,
    writer_session: RpfmPackSession,
    recipe: Recipe,
    output_path: Path,
    reference_paths: list[Path] | None = None,
) -> list[dict[str, object]]:
    class MaterialWriterSession:
        client = writer_session.client
        pack_key = writer_session.pack_key
        pack_path = writer_session.pack_path
        decoded_db_by_path = source_session.decoded_db_by_path

        def list_tables(self, source: str = "pack") -> list[str]:
            return source_session.list_tables(source)

        def read_table(self, table_name: str, source: str = "pack") -> list[dict[str, Any]]:
            return source_session.read_table(table_name, source)

        def _resolve_table_path(self, table_name: str, source: str = "pack") -> str:
            return source_session._resolve_table_path(table_name, source)

        def list_files(self) -> list[str]:
            return writer_session.list_files()

        def list_loc_files(self) -> list[str]:
            return writer_session.list_loc_files()

        def metadata(self) -> dict[str, Any]:
            return source_session.metadata()

    return build_delta_pack(
        MaterialWriterSession(),  # type: ignore[arg-type]
        recipe,
        output_path,
        reference_paths or [],
    )


def _processing_recipes(recipe: Recipe) -> list[Recipe]:
    if not recipe.work_items:
        return [recipe]
    recipes: list[Recipe] = []
    for work in recipe.work_items:
        work_recipe = dict(work.get("recipe") or {})
        work_recipe["modName"] = recipe.mod_name
        recipes.append(recipe_from_dict(work_recipe))
    return recipes


def _recipe_with_processed_characters(
    recipe: Recipe,
    clones: list[CharacterClone],
    patches: list[CharacterPatch],
) -> Recipe:
    return Recipe(
        mod_name=recipe.mod_name,
        equipment_stat_patches=recipe.equipment_stat_patches,
        armour_type_clones=recipe.armour_type_clones,
        land_unit_clones=recipe.land_unit_clones,
        skill_set_clones=recipe.skill_set_clones,
        attribute_set_clones=recipe.attribute_set_clones,
        age_range_clones=recipe.age_range_clones,
        character_clones=clones,
        character_patches=patches,
        work_items=recipe.work_items,
        raw=recipe.raw,
    )


def _collect_stat_patch_rows(
    session: RpfmPackSession,
    recipe: Recipe,
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    changed = 0
    tables, table_names = _load_reference_backed_stat_tables(
        session,
        source_dbs,
        reference_paths or [],
        opened_pack_keys,
    )
    for patch in recipe.equipment_stat_patches:
        try:
            target = _resolve_reference_backed_stat_target(
                tables,
                table_names,
                patch.equipment_key,
                patch.stat_table,
                patch.column,
                patch.value,
                patch.game_mode,
            )
        except ValueError as error:
            if str(error).startswith("Equipment stat mapping not found:"):
                continue
            raise
        rows = tables[target.stat_table]
        row = _find_required(rows, "key", target.row_key)
        patched = {**row, target.column: target.value}
        table_path = row.get("_sourceTablePath") or target.table_name
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(patched))
        row[target.column] = target.value
        changed += 1
    return changed


def _load_reference_backed_stat_tables(
    session: RpfmPackSession,
    source_dbs: dict[str, dict[str, Any]],
    reference_paths: list[Path],
    opened_pack_keys: dict[str, str] | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    aliases = {
        alias: TABLE_ALIASES[alias]
        for alias in (
            "equipment_variants_weapons",
            "equipment_variants_armours",
            "melee_weapons",
            "missile_weapons",
            "projectiles",
            "unit_armour_types",
            "land_units",
        )
    }
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths,
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    return tables, table_names


def _resolve_reference_backed_stat_target(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    equipment_key: str,
    stat_table: str,
    column: str,
    value: int | float,
    game_mode: str | None,
) -> StatTarget:
    if stat_table == "land_unit":
        row = _require_stat_row(tables.get("land_units", []), equipment_key, column)
        return StatTarget("land_units", row.get("_sourceTablePath") or table_names["land_units"], equipment_key, column, value)

    if stat_table == "armour":
        variants = tables.get("equipment_variants_armours", [])
        variant = _find_stat_variant_any(
            variants,
            _equipment_key_spellings(equipment_key),
            game_mode,
            "armour",
        )
        row_key = variant["armour"]
        row = _require_stat_row(
            tables.get("unit_armour_types", []),
            row_key,
            column,
            numeric=column != "audio_type",
        )
        return StatTarget("unit_armour_types", row.get("_sourceTablePath") or table_names["unit_armour_types"], row_key, column, value)

    if stat_table == "melee_weapon":
        variant = _find_stat_variant(tables.get("equipment_variants_weapons", []), equipment_key, game_mode, "primary_melee_weapon")
        row_key = variant["primary_melee_weapon"]
        row = _require_stat_row(tables.get("melee_weapons", []), row_key, column)
        return StatTarget("melee_weapons", row.get("_sourceTablePath") or table_names["melee_weapons"], row_key, column, value)

    variant = _find_stat_variant(tables.get("equipment_variants_weapons", []), equipment_key, game_mode, "primary_missile_weapon")
    missile_key = variant["primary_missile_weapon"]
    missile = _require_stat_row(tables.get("missile_weapons", []), missile_key, "default_projectile", numeric=False)
    row_key = missile["default_projectile"]
    row = _require_stat_row(tables.get("projectiles", []), row_key, column)
    return StatTarget("projectiles", row.get("_sourceTablePath") or table_names["projectiles"], row_key, column, value)


def _find_stat_variant(
    rows: list[dict[str, Any]],
    equipment_key: str,
    game_mode: str | None,
    stat_key_field: str,
) -> dict[str, Any]:
    matches = [
        row for row in rows
        if row.get("ceos_key") == equipment_key and row.get(stat_key_field)
    ]
    if game_mode is not None:
        matches = [row for row in matches if row.get("game_mode") == game_mode]
    if not matches:
        suffix = f" for gameMode {game_mode}" if game_mode else ""
        raise ValueError(f"Equipment stat mapping not found: {equipment_key}{suffix}")
    if len(matches) > 1 and game_mode is None:
        raise ValueError(f"Equipment stat mapping is ambiguous; provide gameMode: {equipment_key}")
    return matches[0]


def _find_stat_variant_any(
    rows: list[dict[str, Any]],
    equipment_keys: list[str],
    game_mode: str | None,
    stat_key_field: str,
) -> dict[str, Any]:
    last_error: ValueError | None = None
    for equipment_key in equipment_keys:
        try:
            return _find_stat_variant(rows, equipment_key, game_mode, stat_key_field)
        except ValueError as error:
            last_error = error
    raise last_error or ValueError(f"Equipment stat mapping not found: {equipment_keys[0] if equipment_keys else ''}")


def _equipment_key_spellings(equipment_key: str) -> list[str]:
    candidates = [equipment_key]
    if "_ancillary_" in equipment_key:
        candidates.append(equipment_key.replace("_ancillary_", "_ancilliary_"))
    if "_ancilliary_" in equipment_key:
        candidates.append(equipment_key.replace("_ancilliary_", "_ancillary_"))
    return list(dict.fromkeys(candidates))


def _require_stat_row(
    rows: list[dict[str, Any]],
    row_key: str,
    column: str,
    numeric: bool = True,
) -> dict[str, Any]:
    row = _find_required(rows, "key", row_key)
    if column not in row:
        raise ValueError(f"Column is missing on stat row: {row_key}/{column}")
    if numeric and not isinstance(row[column], (int, float)):
        raise ValueError(f"Column is not numeric on stat row: {row_key}/{column}")
    return row


def _collect_armour_type_clone_rows(
    session: RpfmPackSession,
    clones: list[ArmourTypeClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    aliases = {"unit_armour_types": TABLE_ALIASES["unit_armour_types"]}
    table_names = _optional_table_names(session, aliases)
    if "unit_armour_types" not in table_names:
        table_names["unit_armour_types"] = resolve_table_name(session, "unit_armour_types")
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    rows = tables["unit_armour_types"]
    created = 0
    for clone in clones:
        source = _find_required(rows, "key", clone.source_key)
        _validate_armour_type_clone_from_row(rows, source, clone)
        cloned = {**source, "key": clone.new_key, **clone.overrides}
        table_path = source.get("_sourceTablePath") or table_names["unit_armour_types"]
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(cloned))
        rows.append({**cloned, "_sourceTablePath": table_path})
        created += 1
    return created


def _validate_armour_type_clone_from_row(
    rows: list[dict[str, Any]],
    source: dict[str, Any],
    clone: ArmourTypeClone,
) -> None:
    if _find_row(rows, "key", clone.new_key) is not None:
        raise ValueError(f"New armour type already exists: {clone.new_key}")
    unknown_columns = set(clone.overrides) - {"armour_value", "audio_type"}
    if unknown_columns:
        raise ValueError(f"Unsupported armour type override column: {', '.join(sorted(unknown_columns))}")
    for column, value in clone.overrides.items():
        if column not in source:
            raise ValueError(f"Column is missing on armour type row: {clone.source_key}/{column}")
        if column == "audio_type":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Armour audio_type must be a non-empty string: {clone.new_key}/{column}")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Armour override must be a non-negative number: {clone.new_key}/{column}")


def _collect_land_unit_clone_rows(
    session: RpfmPackSession,
    recipe: Recipe,
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not recipe.land_unit_clones:
        return 0
    aliases = {
        "land_units": TABLE_ALIASES["land_units"],
        "main_units": TABLE_ALIASES["main_units"],
        "retinues": _character_dependency_aliases()["retinues"],
        "retinue_slot_initial_units": _character_dependency_aliases()["retinue_slot_initial_units"],
        "cai_retinues_to_aspects": _character_dependency_aliases()["cai_retinues_to_aspects"],
    }
    table_names = _optional_table_names(session, aliases)
    if "land_units" not in table_names:
        table_names["land_units"] = resolve_table_name(session, "land_units")
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    rows = tables["land_units"]
    created = 0
    for clone in recipe.land_unit_clones:
        source = _find_required(rows, "key", clone.source_key)
        _validate_land_unit_clone_from_row(rows, source, clone)
        cloned = {**source, "key": clone.new_key, **clone.overrides}
        table_path = source.get("_sourceTablePath") or table_names["land_units"]
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(cloned))
        rows.append({**cloned, "_sourceTablePath": table_path})
        main_unit_key = _clone_main_unit_for_land_unit(tables, table_names, rows_by_table, clone)
        _clone_retinue_chain_for_land_unit(tables, table_names, rows_by_table, clone, main_unit_key)
        created += 1
    return created


def _validate_land_unit_clone_from_row(
    rows: list[dict[str, Any]],
    source: dict[str, Any],
    clone: Any,
) -> None:
    if _find_row(rows, "key", clone.new_key) is not None:
        raise ValueError(f"New land unit already exists: {clone.new_key}")
    unknown_columns = set(clone.overrides) - {"charge_bonus", "morale", "primary_ammo", "armour"}
    if unknown_columns:
        raise ValueError(f"Unsupported land unit override column: {', '.join(sorted(unknown_columns))}")
    for column, value in clone.overrides.items():
        if column not in source:
            raise ValueError(f"Column is missing on land unit row: {clone.source_key}/{column}")
        if column == "armour":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Land unit armour override must be a non-empty string: {clone.new_key}/{column}")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Land unit override must be a non-negative number: {clone.new_key}/{column}")


def _clone_retinue_chain_for_land_unit(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    clone: Any,
    main_unit_key: str | None = None,
) -> None:
    source_retinue_key = str(getattr(clone, "source_retinue_key", "") or "")
    new_retinue_key = str(getattr(clone, "new_retinue_key", "") or "")
    if not source_retinue_key or not new_retinue_key:
        return

    source_retinue = _find_row(tables.get("retinues", []), "key", source_retinue_key)
    if source_retinue is None:
        return
    retinue_table = source_retinue.get("_sourceTablePath") or table_names.get("retinues")
    if retinue_table:
        _upsert_delta_row(
            rows_by_table,
            retinue_table,
            "key",
            _clean_source_row({**source_retinue, "key": new_retinue_key}),
        )

    for row in tables.get("retinue_slot_initial_units", []):
        if row.get("retinue") != source_retinue_key:
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("retinue_slot_initial_units")
        if not table_path:
            continue
        initial_unit = (
            main_unit_key or clone.new_key
            if row.get("initial_unit_record") == clone.source_key
            else row.get("initial_unit_record")
        )
        _upsert_delta_row(
            rows_by_table,
            table_path,
            _retinue_slot_key,
            _clean_source_row({**row, "retinue": new_retinue_key, "initial_unit_record": initial_unit}),
        )

    for row in tables.get("cai_retinues_to_aspects", []):
        if row.get("retinue") != source_retinue_key:
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("cai_retinues_to_aspects")
        if table_path:
            _upsert_delta_row(
                rows_by_table,
                table_path,
                _retinue_aspect_key,
                _clean_source_row({**row, "retinue": new_retinue_key}),
            )


def _clone_main_unit_for_land_unit(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    clone: Any,
) -> str | None:
    rows = tables.get("main_units", [])
    if not rows:
        return None
    source = (
        _find_row(rows, "unit", clone.source_key)
        or _find_row(rows, "key", clone.source_key)
        or next((row for row in rows if row.get("land_unit") == clone.source_key), None)
    )
    if source is None:
        return None
    key_field = "unit" if "unit" in source else "key"
    if _find_row(rows, key_field, clone.new_key) is not None:
        raise ValueError(f"New main unit already exists: {clone.new_key}")
    cloned = {**source, key_field: clone.new_key}
    if "land_unit" in cloned:
        cloned["land_unit"] = clone.new_key
    if "unique_index" in cloned:
        cloned["unique_index"] = _unique_numeric_delta_value(
            f"main_units:{clone.new_key}",
            [*rows, *[row for table_rows in rows_by_table.values() for row in table_rows]],
            "unique_index",
        )
    table_path = source.get("_sourceTablePath") or table_names.get("main_units")
    if not table_path:
        return None
    _upsert_delta_row(rows_by_table, table_path, _main_unit_key, _clean_source_row(cloned))
    rows.append({**cloned, "_sourceTablePath": table_path})
    return clone.new_key


def _collect_attribute_set_clone_rows(
    session: RpfmPackSession,
    clones: list[AttributeSetClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
        if alias in {"character_attribute_sets", "character_attributes"}
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )

    created = 0
    for clone in clones:
        source_set = dict(_find_required_by(tables.get("character_attribute_sets", []), _attribute_set_key, clone.source_set_key))
        set_table = source_set.get("_sourceTablePath") or table_names.get("character_attribute_sets")
        if not set_table:
            raise ValueError("Source attribute set table not found.")
        new_set = _with_attribute_set_key(source_set, clone.new_set_key)
        _upsert_delta_row(rows_by_table, set_table, _attribute_set_key, new_set)

        source_attrs = [
            row for row in tables.get("character_attributes", [])
            if _attribute_set_key(row) == clone.source_set_key
        ]
        if not source_attrs:
            raise ValueError(f"Source attribute set has no attributes: {clone.source_set_key}")
        for source_attr in source_attrs:
            attr_key = _attribute_override_key(source_attr)
            value_column = _attribute_value_column(source_attr)
            new_attr = _with_attribute_set_key(source_attr, clone.new_set_key)
            if attr_key in clone.overrides and value_column:
                new_attr[value_column] = clone.overrides[attr_key]
            attr_table = source_attr.get("_sourceTablePath") or table_names.get("character_attributes")
            if attr_table:
                _upsert_delta_row(rows_by_table, attr_table, _attribute_key, _clean_source_row(new_attr))
        tables.setdefault("character_attribute_sets", []).append({**new_set, "_sourceTablePath": set_table})
        tables.setdefault("character_attributes", []).extend(
            _with_attribute_set_key(row, clone.new_set_key)
            for row in source_attrs
        )
        created += 1
    return created


def _collect_skill_set_clone_rows(
    session: RpfmPackSession,
    clones: list[SkillSetClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )

    created = 0
    for clone in clones:
        source_set = dict(_find_required(tables.get("character_skill_node_sets", []), "key", clone.source_set_key))
        new_set = {**source_set, "key": clone.new_set_key}
        _upsert_delta_row(rows_by_table, table_names["character_skill_node_sets"], "key", new_set)

        source_nodes = [
            row for row in tables.get("character_skill_nodes", [])
            if row.get("character_skill_node_set_key") == clone.source_set_key
        ]
        if not source_nodes:
            raise ValueError(f"Source skill node set has no nodes: {clone.source_set_key}")
        node_key_map = {
            str(row.get("key")): _skill_node_clone_key(clone.source_set_key, clone.new_set_key, str(row.get("key")))
            for row in source_nodes
            if row.get("key")
        }
        used_skill_keys: set[str] = set()
        for source_node in source_nodes:
            old_key = str(source_node.get("key") or "")
            new_skill_key = clone.replacements.get(old_key, source_node.get("character_skill_key"))
            if new_skill_key:
                used_skill_keys.add(str(new_skill_key))
            new_node = {
                **source_node,
                "key": node_key_map[old_key],
                "character_skill_node_set_key": clone.new_set_key,
                "character_skill_key": new_skill_key,
            }
            _upsert_delta_row(rows_by_table, table_names["character_skill_nodes"], "key", new_node)

        source_node_keys = set(node_key_map)
        for source_link in tables.get("character_skill_node_links", []):
            parent = str(source_link.get("parent_key") or "")
            child = str(source_link.get("child_key") or "")
            if parent not in source_node_keys and child not in source_node_keys:
                continue
            new_link = {
                **source_link,
                "parent_key": node_key_map.get(parent, parent),
                "child_key": node_key_map.get(child, child),
            }
            _upsert_delta_row(rows_by_table, table_names["character_skill_node_links"], _skill_link_key, new_link)

        _copy_skill_effect_dependencies(tables, table_names, rows_by_table, used_skill_keys)
        created += 1
    return created


def _collect_character_patch_rows(
    session: RpfmPackSession,
    patches: list[CharacterPatch],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
    patched_skill_set_keys: set[str] | None = None,
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not patches:
        return 0
    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    for alias in (
        "character_generation_templates",
        "character_generation_template_game_mode_details",
    ):
        if alias not in table_names:
            table_names[alias] = resolve_character_table_name(session, alias)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    templates = tables["character_generation_templates"]
    details = tables["character_generation_template_game_mode_details"]
    patched_skill_set_keys = patched_skill_set_keys or set()

    changed = 0
    for patch in patches:
        source_template = _find_required(templates, "key", patch.template_key)
        source_art_set_id = str(source_template.get("art_set_override") or "")
        template_table = source_template.get("_sourceTablePath") or table_names["character_generation_templates"]
        existing_template = _find_delta_row(rows_by_table, "key", patch.template_key, template_table)
        template = dict(existing_template or source_template)
        for column, value in patch.template_overrides.items():
            if template.get(column) != value:
                template[column] = value
                changed += 1
        if _apply_character_patch_name(session, source_dbs, rows_by_table, template, patch, loc_rows):
            changed += 1
        _upsert_delta_row(
            rows_by_table,
            template_table,
            "key",
            _clean_source_row(template),
        )
        art_set_id = str(template.get("art_set_override") or "")
        if art_set_id:
            if source_art_set_id and art_set_id != source_art_set_id:
                _clone_art_set_patch_delta(
                    tables,
                    table_names,
                    rows_by_table,
                    source_art_set_id,
                    art_set_id,
                    patch.art_set_overrides,
                    patch.art_overrides,
                )
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_art_sets",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                "art_set_id",
            )
            if patch.art_set_overrides:
                _patch_art_set_row(
                    tables,
                    table_names,
                    rows_by_table,
                    art_set_id,
                    patch.art_set_overrides,
                )
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_arts",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                _art_key,
            )
            if patch.art_overrides:
                _patch_art_rows(
                    tables,
                    table_names,
                    rows_by_table,
                    art_set_id,
                    patch.art_overrides,
                )
            if patch.art_set_overrides and "is_male" in patch.art_set_overrides:
                _patch_child_art_rows_for_gender(
                    tables,
                    table_names,
                    rows_by_table,
                    art_set_id,
                    _coerce_bool(patch.art_set_overrides["is_male"]),
                )
        age_range = str(template.get("spawn_age_range") or "")
        if age_range:
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "character_generation_spawn_age_ranges",
                lambda row, key=age_range: row.get("key") == key,
                "key",
            )

        for detail in [
            row for row in details
            if row.get("character_generation_template") == patch.template_key
        ]:
            overrides = patch.detail_overrides.get(detail.get("game_mode", ""), {})
            detail_table = detail.get("_sourceTablePath") or table_names["character_generation_template_game_mode_details"]
            existing_detail = _find_delta_row(rows_by_table, _detail_key, _detail_key(detail), detail_table)
            patched = dict(existing_detail or detail)
            for column, value in overrides.items():
                if patched.get(column) != value:
                    patched[column] = value
                    changed += 1
            _upsert_delta_row(
                rows_by_table,
                detail_table,
                _detail_key,
                _clean_source_row(patched),
            )
            _copy_initial_ceo_dependency(tables, table_names, rows_by_table, patched.get("initial_ceos"))
            _copy_attribute_dependency(tables, table_names, rows_by_table, patched.get("attribute_set"))
            if str(patched.get("skill_set_override") or "") not in patched_skill_set_keys:
                _copy_skill_dependency(tables, table_names, rows_by_table, patched.get("skill_set_override"))
            _copy_retinue_dependency(tables, table_names, rows_by_table, patched.get("retinue"))
    return changed


def _apply_character_patch_name(
    session: RpfmPackSession,
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    template: dict[str, Any],
    patch: CharacterPatch,
    loc_rows: dict[str, str],
) -> bool:
    display_name = str(patch.display_name or "").strip()
    if not display_name:
        return False
    current_forename = str(template.get("forename") or "")
    seed = f"{patch.template_key}:{display_name}".encode("utf-8")
    name_id = 2_000_000_000 + (zlib.crc32(seed) % 100_000_000)
    if str(name_id) == current_forename:
        return False
    try:
        names = _read_rows(session, "names", source_dbs)
        names_table = _source_table_path_for_rows(names, "names")
        source_name = _find_row(names, "id", current_forename) or (names[0] if names else {})
        name_row = {
            **source_name,
            "id": str(name_id),
        }
        _upsert_delta_row(rows_by_table, names_table, "id", name_row)
    except Exception:
        pass
    template["forename"] = name_id
    template["family_name"] = 0
    template["clan_name"] = 0
    template["other_name"] = 0
    loc_rows[f"names_name_{name_id}"] = display_name
    loc_rows[f"names_alt_name_{name_id}"] = display_name
    return True


def _patch_art_rows(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_set_id: str,
    overrides: dict[str, Any],
) -> None:
    clean_overrides = {key: value for key, value in overrides.items() if value not in (None, "")}
    if not clean_overrides:
        return
    art_rows = [
        row for row in tables.get("campaign_character_arts", [])
        if row.get("art_set_id") == art_set_id
    ]
    apply_all = not any(_is_adult_art_row(row) for row in art_rows)
    for row in art_rows:
        if not apply_all and not _is_adult_art_row(row):
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("campaign_character_arts")
        if not table_path:
            continue
        _upsert_delta_row(
            rows_by_table,
            table_path,
            _art_key,
            _clean_source_row({**row, **clean_overrides}),
        )


def _patch_child_art_rows_for_gender(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_set_id: str,
    is_male: bool,
) -> None:
    child_overrides = _child_art_overrides_for_gender(is_male)
    for row in tables.get("campaign_character_arts", []):
        if row.get("art_set_id") != art_set_id or _is_adult_art_row(row):
            continue
        portrait = str(row.get("portrait") or "")
        card = str(row.get("card") or "")
        if "child" not in portrait and "child" not in card:
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("campaign_character_arts")
        if not table_path:
            continue
        _upsert_delta_row(
            rows_by_table,
            table_path,
            _art_key,
            _clean_source_row({**row, **child_overrides}),
        )


def _child_art_overrides_for_gender(is_male: bool) -> dict[str, str]:
    if is_male:
        return {
            "portrait": "child_03_male/",
            "card": "child_03_male",
            "uniform": "3k_main_child_male",
        }
    return {
        "portrait": "child_01_female/",
        "card": "child_01_female",
        "uniform": "3k_main_child_female",
    }


def _patch_art_set_row(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_set_id: str,
    overrides: dict[str, Any],
) -> None:
    clean_overrides = {key: value for key, value in overrides.items() if value not in (None, "")}
    if not clean_overrides:
        return
    row = _find_row(tables.get("campaign_character_art_sets", []), "art_set_id", art_set_id)
    if not row:
        return
    table_path = row.get("_sourceTablePath") or table_names.get("campaign_character_art_sets")
    if not table_path:
        return
    _upsert_delta_row(
        rows_by_table,
        table_path,
        "art_set_id",
        _clean_source_row({**row, **clean_overrides}),
    )


def _collect_age_range_clone_rows(
    session: RpfmPackSession,
    clones: list[AgeRangeClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    table_name = resolve_character_table_name(session, "character_generation_spawn_age_ranges")
    rows = _read_rows(session, table_name, source_dbs)
    aliases = {
        "character_generation_spawn_age_ranges": CHARACTER_TABLE_ALIASES["character_generation_spawn_age_ranges"],
    }
    tables = {"character_generation_spawn_age_ranges": rows}
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, {"character_generation_spawn_age_ranges": table_name}, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        {"character_generation_spawn_age_ranges": table_name},
        tables,
        source_dbs,
        opened_pack_keys,
    )
    rows = tables["character_generation_spawn_age_ranges"]
    created = 0
    for clone in clones:
        if clone.new_key == clone.source_key:
            if clone.overrides:
                raise ValueError(f"Unsafe age range clone would overwrite source row: {clone.source_key}")
            continue
        source = _find_required(rows, "key", clone.source_key)
        new_row = {
            **source,
            "key": clone.new_key,
            **clone.overrides,
        }
        table_path = source.get("_sourceTablePath") or table_name
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(new_row))
        rows.append({**new_row, "_sourceTablePath": table_path})
        created += 1
    return created


def _collect_character_clone_rows(
    session: RpfmPackSession,
    clones: list[CharacterClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0

    table_names = {}
    for alias in CHARACTER_TABLE_ALIASES:
        try:
            table_names[alias] = resolve_character_table_name(session, alias)
        except ValueError:
            if alias != "ceo_initial_datas":
                raise
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    dependency_aliases = _character_dependency_aliases()
    dependency_aliases.update({
        alias: CHARACTER_TABLE_ALIASES[alias]
        for alias in CHARACTER_TABLE_ALIASES
    })
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), dependency_aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, dependency_aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        dependency_aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    names = _read_rows(session, "names", source_dbs)
    names_table = _source_table_path_for_rows(names, "names")

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
        if clone.display_name:
            name_id = _name_id_for_clone(clone, names)
            source_name_id = str(source_template.get("forename") or "")
            source_name = _find_row(names, "id", source_name_id) or (names[0] if names else {})
            name_row = {
                **source_name,
                "id": str(name_id),
                "frequency": 1,
            }
            _upsert_delta_row(rows_by_table, names_table, "id", name_row)
            names.append(name_row)
            new_template["forename"] = name_id
            new_template["family_name"] = 0
            new_template["clan_name"] = 0
            new_template["other_name"] = 0
            loc_rows[f"names_name_{name_id}"] = clone.display_name
            loc_rows[f"names_alt_name_{name_id}"] = clone.display_name

        if clone.new_art_set_id:
            source_art_set = clone.art_set_source_id or source_template["art_set_override"]
            source_art_set_row = _find_row(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
            if source_art_set_row:
                new_template["art_set_override"] = clone.new_art_set_id
                if source_art_set_row.get("is_male") not in (None, ""):
                    is_male = _coerce_bool(source_art_set_row.get("is_male"))
                    new_template["is_male"] = is_male
                    new_template["voiceover_actor"] = _voiceover_actor_for_template_gender(
                        is_male,
                        str(new_template.get("subtype") or source_template.get("subtype") or ""),
                    )
                _clone_art_set_delta(tables, table_names, rows_by_table, source_art_set, clone)
            else:
                new_template["art_set_override"] = source_art_set

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
        if not source_details:
            raise ValueError(f"Row not found: character_generation_template={clone.detail_source_template_key}")
        if clone.new_initial_ceo_key:
            if "ceo_initial_datas" not in tables:
                raise ValueError("Source initial CEO table not found.")
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
    art_rows = [
        row for row in tables["campaign_character_arts"]
        if row.get("art_set_id") == source_art_set
    ]
    apply_all = not any(_is_adult_art_row(row) for row in art_rows)
    for art_row in art_rows:
        overrides = clone.art_overrides if apply_all or _is_adult_art_row(art_row) else {}
        new_row = {
            **art_row,
            "art_set_id": clone.new_art_set_id,
            **overrides,
        }
        if "id" in new_row:
            new_row["id"] = _art_id_for_clone(clone.new_art_set_id or source_art_set, art_row)
        _upsert_delta_row(
            rows_by_table,
            table_names["campaign_character_arts"],
            _art_key,
            new_row,
        )


def _clone_art_set_patch_delta(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    source_art_set: str,
    new_art_set: str,
    art_set_overrides: dict[str, Any],
    art_overrides: dict[str, Any],
) -> None:
    if _find_row(tables.get("campaign_character_art_sets", []), "art_set_id", new_art_set):
        return
    source_set = _find_required(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
    set_table = source_set.get("_sourceTablePath") or table_names["campaign_character_art_sets"]
    new_set = _clean_source_row({
        **source_set,
        "art_set_id": new_art_set,
        **{key: value for key, value in art_set_overrides.items() if value not in (None, "")},
    })
    _upsert_delta_row(rows_by_table, set_table, "art_set_id", new_set)
    tables.setdefault("campaign_character_art_sets", []).append({**new_set, "_sourceTablePath": set_table})

    source_rows = [
        row for row in tables.get("campaign_character_arts", [])
        if row.get("art_set_id") == source_art_set
    ]
    apply_all = not any(_is_adult_art_row(row) for row in source_rows)
    art_table = table_names["campaign_character_arts"]
    for source_row in source_rows:
        overrides = art_overrides if apply_all or _is_adult_art_row(source_row) else {}
        new_row = _clean_source_row({
            **source_row,
            "art_set_id": new_art_set,
            **{key: value for key, value in overrides.items() if value not in (None, "")},
        })
        if "id" in new_row:
            new_row["id"] = _art_id_for_clone(new_art_set, source_row)
        _upsert_delta_row(rows_by_table, art_table, _art_key, new_row)
        tables.setdefault("campaign_character_arts", []).append({**new_row, "_sourceTablePath": art_table})


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


def _is_adult_art_row(row: dict[str, Any]) -> bool:
    if row.get("has_come_of_age") is True:
        return True
    try:
        return int(row.get("age") or 0) >= 16
    except (TypeError, ValueError):
        return False


def _art_id_for_clone(art_set_id: str, source_row: dict[str, Any]) -> int:
    seed = "|".join(
        str(value)
        for value in (
            art_set_id,
            source_row.get("age", ""),
            source_row.get("level", ""),
            source_row.get("season", ""),
            source_row.get("has_come_of_age", ""),
        )
    ).encode("utf-8")
    return 100_000_000 + (zlib.crc32(seed) % 1_900_000_000)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _voiceover_actor_for_template_gender(is_male: bool, subtype: str) -> str:
    lower = subtype.lower()
    if "water" in lower:
        element = "water"
    elif "wood" in lower:
        element = "wood"
    elif "fire" in lower:
        element = "fire"
    elif "earth" in lower:
        element = "earth"
    else:
        element = "metal"
    gender = "male" if is_male else "female"
    return f"vo_actor_group_generic_{gender}_{element}_general"


def _collect_character_dependency_rows(
    session: RpfmPackSession,
    clones: list[CharacterClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path],
    opened_pack_keys: dict[str, str],
) -> int:
    if not clones:
        return 0

    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(session, aliases, reference_paths, table_names, tables, source_dbs, opened_pack_keys)

    before = sum(len(rows) for rows in rows_by_table.values())
    for clone in clones:
        source_template = _find_row(
            tables.get("character_generation_templates", []),
            "key",
            clone.source_template_key,
        ) or {}
        art_set_id = str(
            clone.new_art_set_id
            or clone.template_overrides.get("art_set_override")
            or source_template.get("art_set_override")
            or ""
        )
        age_range = str(
            clone.template_overrides.get("spawn_age_range")
            or clone.new_age_range_key
            or source_template.get("spawn_age_range")
            or ""
        )
        if art_set_id:
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_art_sets",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                "art_set_id",
            )
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_arts",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                _art_key,
            )
        if age_range:
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "character_generation_spawn_age_ranges",
                lambda row, key=age_range: row.get("key") == key,
                "key",
            )

        source_details = [
            row for row in tables.get("character_generation_template_game_mode_details", [])
            if row.get("character_generation_template") == clone.detail_source_template_key
        ]
        merged_details = []
        for source_detail in source_details:
            game_mode = str(source_detail.get("game_mode", ""))
            merged_details.append({
                **source_detail,
                **clone.detail_overrides.get(game_mode, {}),
            })

        for detail in merged_details:
            _copy_initial_ceo_dependency(tables, table_names, rows_by_table, detail.get("initial_ceos"))
            _copy_attribute_dependency(tables, table_names, rows_by_table, detail.get("attribute_set"))
            _copy_skill_dependency(tables, table_names, rows_by_table, detail.get("skill_set_override"))
            _copy_retinue_dependency(tables, table_names, rows_by_table, detail.get("retinue"))

    after = sum(len(rows) for rows in rows_by_table.values())
    return max(0, after - before)


def _character_dependency_aliases() -> dict[str, list[str]]:
    return {
        "character_generation_templates": [
            "character_generation_templates",
            "db/character_generation_templates_tables/_mtu_characters",
            "db/character_generation_templates_tables/data",
            "db/character_generation_templates_tables/data__",
            "db/character_generation_templates_tables/new_hero",
        ],
        "character_generation_template_game_mode_details": [
            "character_generation_template_game_mode_details",
            "db/character_generation_template_game_mode_details_tables/_mtu_characters",
            "db/character_generation_template_game_mode_details_tables/data",
            "db/character_generation_template_game_mode_details_tables/data__",
            "db/character_generation_template_game_mode_details_tables/new_hero",
        ],
        "campaign_character_art_sets": [
            "campaign_character_art_sets",
            "db/campaign_character_art_sets_tables/_mtu_characters",
            "db/campaign_character_art_sets_tables/data",
            "db/campaign_character_art_sets_tables/data__",
            "db/campaign_character_art_sets_tables/new_hero",
        ],
        "campaign_character_arts": [
            "campaign_character_arts",
            "db/campaign_character_arts_tables/_mtu_characters",
            "db/campaign_character_arts_tables/data",
            "db/campaign_character_arts_tables/data__",
            "db/campaign_character_arts_tables/new_hero",
        ],
        "character_generation_spawn_age_ranges": [
            "character_generation_spawn_age_ranges",
            "db/character_generation_spawn_age_ranges_tables/_mtu_characters",
            "db/character_generation_spawn_age_ranges_tables/data",
            "db/character_generation_spawn_age_ranges_tables/data__",
            "db/character_generation_spawn_age_ranges_tables/new_hero",
        ],
        "ceo_initial_datas": [
            "ceo_initial_datas",
            "db/ceo_initial_datas_tables/_mtu_characters_ceo",
            "db/ceo_initial_datas_tables/data",
            "db/ceo_initial_datas_tables/data__",
            "db/ceo_initial_datas_tables/new_hero",
        ],
        "retinues": ["retinues"],
        "retinue_slot_initial_units": ["retinue_slot_initial_units"],
        "cai_retinues_to_aspects": ["cai_retinues_to_aspects"],
        "character_attribute_sets": ["character_attribute_sets"],
        "character_attributes": ["character_attributes"],
        "character_skill_node_sets": [
            "character_skill_node_sets",
            "db/character_skill_node_sets_tables/_mtu_characters_skills",
            "db/character_skill_node_sets_tables/_mtu_characters",
        ],
        "character_skill_nodes": [
            "character_skill_nodes",
            "db/character_skill_nodes_tables/_mtu_characters_skills_nodes_01_earth_commander",
            "db/character_skill_nodes_tables/_mtu_characters",
        ],
        "character_skill_node_links": [
            "character_skill_node_links",
            "db/character_skill_node_links_tables/_mtu_characters_skills",
            "db/character_skill_node_links_tables/_mtu_characters",
        ],
        "character_skill_level_to_effects_junctions": [
            "character_skill_level_to_effects_junctions",
            "db/character_skill_level_to_effects_junctions_tables/_mtu_characters_skills",
        ],
        "effects": [
            "effects",
            "db/effects_tables/_mtu_characters_skills_effects",
        ],
        "land_units": [
            "land_units",
            "db/land_units_tables/_mtu_characters_custom_battles_land_units",
        ],
        "land_units_to_unit_abilites_junctions": ["land_units_to_unit_abilites_junctions"],
    }


def _copy_initial_ceo_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    initial_ceo: Any,
) -> None:
    key = str(initial_ceo or "")
    if not key:
        return
    _copy_matching_rows(tables, table_names, rows_by_table, "ceo_initial_datas", lambda row: row.get("key") == key, "key")


def _copy_attribute_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    attribute_set: Any,
) -> None:
    key = str(attribute_set or "")
    if not key:
        return
    _copy_matching_rows(tables, table_names, rows_by_table, "character_attribute_sets", lambda row: _attribute_set_key(row) == key, _attribute_set_key)
    _copy_matching_rows(tables, table_names, rows_by_table, "character_attributes", lambda row: _attribute_set_key(row) == key, _attribute_key)


def _copy_skill_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    skill_set: Any,
) -> None:
    key = str(skill_set or "")
    if not key:
        return
    _copy_matching_rows(tables, table_names, rows_by_table, "character_skill_node_sets", lambda row: row.get("key") == key, "key")
    skill_nodes = [
        row for row in tables.get("character_skill_nodes", [])
        if row.get("character_skill_node_set_key") == key
    ]
    node_keys = {str(row.get("key")) for row in skill_nodes if row.get("key")}
    for row in skill_nodes:
        table_path = row.get("_sourceTablePath") or table_names.get("character_skill_nodes")
        if table_path:
            clean_row = {key: value for key, value in row.items() if not key.startswith("_source")}
            _upsert_delta_row(rows_by_table, table_path, "key", clean_row)
    if node_keys:
        _copy_matching_rows(
            tables,
            table_names,
            rows_by_table,
            "character_skill_node_links",
            lambda row, keys=node_keys: str(row.get("parent_key")) in keys or str(row.get("child_key")) in keys,
            _skill_link_key,
        )
    skill_keys = {str(row.get("character_skill_key") or "") for row in skill_nodes if row.get("character_skill_key")}
    _copy_skill_effect_dependencies(tables, table_names, rows_by_table, skill_keys)


def _copy_skill_effect_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    skill_keys: set[str],
) -> None:
    if not skill_keys:
        return
    effect_keys: set[str] = set()
    for row in tables.get("character_skill_level_to_effects_junctions", []):
        if str(row.get("character_skill_key") or "") not in skill_keys:
            continue
        effect_key = str(row.get("effect_key") or "")
        if effect_key:
            effect_keys.add(effect_key)
        table_path = row.get("_sourceTablePath") or table_names.get("character_skill_level_to_effects_junctions")
        if table_path:
            clean_row = {key: value for key, value in row.items() if not key.startswith("_source")}
            _upsert_delta_row(rows_by_table, table_path, _skill_effect_key, clean_row)
    if effect_keys:
        _copy_matching_rows(
            tables,
            table_names,
            rows_by_table,
            "effects",
            lambda row, keys=effect_keys: _effect_key(row) in keys,
            _effect_key,
        )


def _skill_node_clone_key(source_set_key: str, new_set_key: str, source_node_key: str) -> str:
    if source_set_key == new_set_key:
        return source_node_key
    suffix = source_node_key
    prefix = f"{source_set_key}_"
    if source_node_key.startswith(prefix):
        suffix = source_node_key[len(prefix):]
    return f"{new_set_key}_{suffix}"


def _copy_retinue_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    retinue: Any,
) -> None:
    key = str(retinue or "")
    if not key:
        return
    _copy_matching_rows(tables, table_names, rows_by_table, "retinues", lambda row: row.get("key") == key, "key")
    _copy_matching_rows(tables, table_names, rows_by_table, "cai_retinues_to_aspects", lambda row: row.get("retinue") == key, _retinue_aspect_key)
    slot_rows = [
        row for row in tables.get("retinue_slot_initial_units", [])
        if row.get("retinue") == key
    ]
    unit_keys = {str(row.get("initial_unit_record")) for row in slot_rows if row.get("initial_unit_record")}
    for row in slot_rows:
        table_path = row.get("_sourceTablePath") or table_names.get("retinue_slot_initial_units")
        if table_path:
            clean_row = {key: value for key, value in row.items() if not key.startswith("_source")}
            _upsert_delta_row(rows_by_table, table_path, _retinue_slot_key, clean_row)
    for unit_key in unit_keys:
        _copy_matching_rows(tables, table_names, rows_by_table, "land_units", lambda row, key=unit_key: row.get("key") == key, "key")
        _copy_matching_rows(
            tables,
            table_names,
            rows_by_table,
            "land_units_to_unit_abilites_junctions",
            lambda row, key=unit_key: row.get("land_unit") == key,
            _land_unit_ability_key,
        )


def _copy_matching_rows(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    alias: str,
    predicate: Any,
    key_field: str | Any,
) -> None:
    if alias not in tables:
        return
    for row in tables[alias]:
        if predicate(row):
            table_path = row.get("_sourceTablePath") or table_names.get(alias)
            if not table_path:
                continue
            clean_row = _clean_source_row(row)
            _upsert_delta_row(rows_by_table, table_path, key_field, clean_row)


def _optional_table_names(session: RpfmPackSession, aliases: dict[str, list[str]]) -> dict[str, str]:
    table_list = session.list_tables()
    tables = set(table_list)
    resolved: dict[str, str] = {}
    for alias, candidates in aliases.items():
        for candidate in candidates:
            if candidate in tables:
                resolved[alias] = candidate
                break
        if alias in resolved:
            continue
        folder = f"{alias}_tables"
        matches = [path for path in table_list if f"/{folder}/" in path]
        if len(matches) == 1:
            resolved[alias] = matches[0]
    return resolved


def _merge_reference_dependency_tables(
    session: RpfmPackSession,
    aliases: dict[str, list[str]],
    reference_paths: list[Path],
    table_names: dict[str, str],
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
    opened_pack_keys: dict[str, str],
) -> None:
    for reference_path in reference_paths:
        resolved = reference_path.expanduser()
        if not resolved.exists():
            continue
        try:
            reference_key = _open_pack_reusing_existing(session, resolved, opened_pack_keys)
            tree = session.client.send({"GetPackFileDataForTreeView": reference_key})
            _raise_rpfm_error(tree)
            file_infos = tree["data"]["ContainerInfoVecRFileInfo"][1]
            reference_tables = sorted(
                info["path"]
                for info in file_infos
                if info.get("path", "").startswith(("db/", "ceo_db/"))
            )
            _merge_dependency_tables_from_pack(session, reference_key, reference_tables, aliases, tables, source_dbs)
            for alias, table_path in _optional_table_names_from_list(reference_tables, aliases).items():
                table_names.setdefault(alias, table_path)
        except Exception:
            continue


def _merge_vanilla_dependency_tables(
    session: RpfmPackSession,
    aliases: dict[str, list[str]],
    table_names: dict[str, str],
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
) -> None:
    try:
        vanilla_tables = session.list_tables("vanilla")
        vanilla_key = session._pack_key_for_source("vanilla")
    except Exception:
        return
    _merge_dependency_tables_from_pack(session, vanilla_key, vanilla_tables, aliases, tables, source_dbs)
    for alias, table_path in _optional_table_names_from_list(vanilla_tables, aliases).items():
        table_names.setdefault(alias, table_path)


def _merge_dependency_tables_from_pack(
    session: RpfmPackSession,
    pack_key: str,
    table_list: list[str],
    aliases: dict[str, list[str]],
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
) -> None:
    is_internal_materials = False
    metadata = getattr(session, "metadata", None)
    if callable(metadata):
        try:
            is_internal_materials = metadata().get("adapter") == "internal-materials"
        except Exception:
            is_internal_materials = False
    if (is_internal_materials or not hasattr(session, "client")) and pack_key == getattr(session, "pack_key", None):
        for alias in aliases:
            for table_path in _matching_table_paths(table_list, alias, aliases[alias]):
                try:
                    rows = _read_rows(session, table_path, source_dbs)
                except Exception:
                    continue
                _append_dependency_rows(tables.setdefault(alias, []), rows, _dependency_key_for_alias(alias))
        return
    for alias in aliases:
        for table_path in _matching_table_paths(table_list, alias, aliases[alias]):
            try:
                rows = _read_rows_from_pack_key(session, pack_key, table_path, source_dbs)
            except Exception:
                continue
            _append_dependency_rows(tables.setdefault(alias, []), rows, _dependency_key_for_alias(alias))


def _matching_table_paths(table_list: list[str], alias: str, candidates: list[str]) -> list[str]:
    matches = []
    tables = set(table_list)
    for candidate in candidates:
        if candidate in tables:
            matches.append(candidate)
    folder = (
        "/ceos_to_equipment_variants_tables/"
        if alias in {"equipment_variants_weapons", "equipment_variants_armours"}
        else f"/{alias}_tables/"
    )
    matches.extend(path for path in table_list if folder in path and path not in matches)
    return sorted(matches)


def _open_pack_reusing_existing(
    session: RpfmPackSession,
    path: Path,
    opened_pack_keys: dict[str, str],
) -> str:
    resolved = path.resolve()
    for key in (str(path), str(resolved)):
        if key in opened_pack_keys:
            return opened_pack_keys[key]

    existing_key = _open_pack_key_for_path(session, resolved)
    if existing_key:
        opened_pack_keys[str(path)] = existing_key
        opened_pack_keys[str(resolved)] = existing_key
        return existing_key

    opened = session.client.send({"OpenPackFiles": [str(resolved)]})
    try:
        _raise_rpfm_error(opened)
    except ValueError:
        existing_key = _open_pack_key_for_path(session, resolved)
        if existing_key:
            opened_pack_keys[str(path)] = existing_key
            opened_pack_keys[str(resolved)] = existing_key
            return existing_key
        raise
    pack_key = opened["data"]["StringContainerInfo"][0]
    opened_pack_keys[str(path)] = pack_key
    opened_pack_keys[str(resolved)] = pack_key
    return pack_key


def _open_pack_key_for_path(session: RpfmPackSession, path: Path) -> str | None:
    response = session.client.send("ListOpenPacks")
    _raise_rpfm_error(response)
    for item in response.get("data", {}).get("VecStringContainerInfo", []):
        if not isinstance(item, list) or len(item) < 2:
            continue
        pack_key, info = item[0], item[1]
        file_path = str((info or {}).get("file_path") or "")
        if not file_path:
            continue
        try:
            if Path(file_path).resolve() == path.resolve():
                return str(pack_key)
        except OSError:
            if file_path.replace("\\", "/").lower() == str(path).replace("\\", "/").lower():
                return str(pack_key)
    return None


def _optional_table_names_from_list(table_list: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    tables = set(table_list)
    resolved: dict[str, str] = {}
    for alias, candidates in aliases.items():
        for candidate in candidates:
            if candidate in tables:
                resolved[alias] = candidate
                break
        if alias in resolved:
            continue
        folder = f"{alias}_tables"
        matches = [path for path in table_list if f"/{folder}/" in path]
        if len(matches) == 1:
            resolved[alias] = matches[0]
    return resolved


def _read_rows_from_pack_key(
    session: RpfmPackSession,
    pack_key: str,
    table_name: str,
    source_dbs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    response = session.client.send({"DecodePackedFile": [pack_key, table_name, "PackFile"]})
    _raise_rpfm_error(response)
    data = response.get("data", {})
    if "DBRFileInfo" not in data:
        return []
    source_dbs.setdefault(table_name, copy.deepcopy(data["DBRFileInfo"][0]))
    table = data["DBRFileInfo"][0]["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    rows = [
        {
            field_name: _decode_rpfm_cell(value)
            for field_name, value in zip(fields, row, strict=False)
        }
        for row in table["table_data"]
    ]
    for row in rows:
        row["_sourceTablePath"] = table_name
    return rows


def _append_dependency_rows(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    key_field: str | Any,
) -> None:
    existing = {
        key_field(row) if callable(key_field) else row.get(key_field)
        for row in target
    }
    for row in source:
        key = key_field(row) if callable(key_field) else row.get(key_field)
        if key in existing:
            continue
        target.append(row)
        existing.add(key)


def _dependency_key_for_alias(alias: str) -> str | Any:
    if alias in {"equipment_variants_weapons", "equipment_variants_armours"}:
        return _equipment_variant_key
    if alias == "character_generation_template_game_mode_details":
        return _detail_key
    if alias == "campaign_character_art_sets":
        return "art_set_id"
    if alias == "campaign_character_arts":
        return _art_key
    if alias == "character_attributes":
        return _attribute_key
    if alias == "character_attribute_sets":
        return _attribute_set_key
    if alias == "character_skill_node_links":
        return _skill_link_key
    if alias == "character_skill_level_to_effects_junctions":
        return _skill_effect_key
    if alias == "retinue_slot_initial_units":
        return _retinue_slot_key
    if alias == "cai_retinues_to_aspects":
        return _retinue_aspect_key
    if alias == "land_units_to_unit_abilites_junctions":
        return _land_unit_ability_key
    if alias == "main_units":
        return _main_unit_key
    if alias == "effects":
        return _effect_key
    return "key"


def _equipment_variant_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any, Any, Any]:
    return (
        row.get("ceos_key"),
        row.get("game_mode"),
        row.get("armour"),
        row.get("primary_melee_weapon"),
        row.get("primary_missile_weapon"),
        row.get("mount"),
    )


def _read_rows(
    session: RpfmPackSession,
    table_name: str,
    source_dbs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = session.read_table(table_name)
    path = session._resolve_table_path(table_name)
    source_dbs[path] = copy.deepcopy(session.decoded_db_by_path[path])
    for row in rows:
        row["_sourceTablePath"] = path
    if hasattr(session, "payload") and path.startswith(("db/", "ceo_db/")):
        folder = path.rsplit("/", 1)[0]
        for sibling_path in session.list_tables():
            if sibling_path == path or not sibling_path.startswith(f"{folder}/"):
                continue
            try:
                sibling_rows = session.read_table(sibling_path)
            except Exception:
                continue
            source_dbs[sibling_path] = copy.deepcopy(session.decoded_db_by_path[sibling_path])
            for row in sibling_rows:
                row["_sourceTablePath"] = sibling_path
            rows.extend(sibling_rows)
    return rows


def _source_table_path_for_rows(rows: list[dict[str, Any]], table_name: str) -> str:
    for row in rows:
        path = row.get("_sourceTablePath")
        if path:
            return str(path)
    raise ValueError(f"RPFM table not found in pack: {table_name}")


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


def _write_lua_text_file(session: RpfmPackSession, target_key: str, path: str, contents: str) -> None:
    file_name = path.rsplit("/", 1)[-1]
    _raise_rpfm_error(session.client.send({
        "NewPackedFile": [target_key, path, {"Text": [file_name, "Lua"]}]
    }))
    _raise_rpfm_error(session.client.send({
        "SavePackedFileFromView": [
            target_key,
            path,
            {
                "Text": {
                    "encoding": "Utf8",
                    "format": "Lua",
                    "contents": contents,
                }
            },
        ]
    }))


def _write_loc_file(session: RpfmPackSession, target_key: str, path: str, rows: dict[str, str]) -> None:
    file_name = path.rsplit("/", 1)[-1].removesuffix(".loc")
    loc_db = _loc_db_with_rows(session, rows)
    _raise_rpfm_error(session.client.send({
        "NewPackedFile": [target_key, path, {"Loc": file_name}]
    }))
    _raise_rpfm_error(session.client.send({
        "SavePackedFileFromView": [target_key, path, {"Loc": loc_db}]
    }))


def _write_spawn_incident_tables(
    session: RpfmPackSession,
    target_key: str,
    clones: list[CharacterClone],
) -> int:
    spawn_clones = [
        clone
        for clone in clones
        if clone.spawn_event in {"campaign_start", "delayed_join"} and clone.template_overrides.get("subtype")
    ]
    if not spawn_clones:
        return 0

    template_path = (Path.cwd() / LEGACY_TEMPLATE_PACK).resolve()
    if not template_path.exists():
        return 0

    template_key = _open_pack_reusing_existing(session, template_path, {})

    source_paths = {
        "incidents": "db/incidents_tables/event",
        "payloads": "db/cdir_events_incident_payloads_tables/event",
        "options": "db/cdir_events_incident_option_junctions_tables/event",
    }
    source_dbs = {
        name: _decode_db_from_pack(session, template_key, path)
        for name, path in source_paths.items()
    }

    incidents_source = _rows_from_db(source_dbs["incidents"])
    payloads_source = _rows_from_db(source_dbs["payloads"])
    options_source = _rows_from_db(source_dbs["options"])

    located_source = _find_row(payloads_source, "payload_key", "LOCATED") or payloads_source[0]

    incident_rows = []
    options = []
    payloads = []
    loc = {}
    for clone in spawn_clones:
        incident_key = _incident_key_for_clone(clone)
        name = str(clone.display_name or "").strip() or clone.new_template_key
        incident_rows.append({
            **incidents_source[0],
            "key": incident_key,
            "generate": False,
            "prioritised": True,
        })

        base_id = 1_820_000_000 + (zlib.crc32(incident_key.encode("utf-8")) % 100_000)
        for index, source_row in enumerate(options_source):
            options.append({
                **source_row,
                "id": base_id + index,
                "incident_key": incident_key,
            })

        payloads.append({
            **located_source,
            "id": base_id + 100,
            "incident_key": incident_key,
            "payload_key": "LOCATED",
            "value": "FACTION",
            "target_key": "default",
        })
        loc[f"incidents_localised_title_{incident_key}"] = "신규 장수 합류"
        loc[f"incidents_localised_description_{incident_key}"] = f"{name} 장수가 플레이어 세력에 합류했습니다."

    _write_db_file(session, target_key, source_paths["incidents"], source_dbs["incidents"], incident_rows)
    _write_db_file(session, target_key, source_paths["options"], source_dbs["options"], options)
    _write_db_file(session, target_key, source_paths["payloads"], source_dbs["payloads"], payloads)
    _write_loc_file(
        session,
        target_key,
        "text/db/hby_mtu_pack_editor_event.loc",
        loc,
    )
    return 3


def _decode_db_from_pack(session: RpfmPackSession, pack_key: str, path: str) -> dict[str, Any]:
    response = session.client.send({"DecodePackedFile": [pack_key, path, "PackFile"]})
    _raise_rpfm_error(response)
    data = response.get("data", {})
    if "DBRFileInfo" not in data:
        raise ValueError(f"RPFM did not decode '{path}' as a DB table.")
    return copy.deepcopy(data["DBRFileInfo"][0])


def _rows_from_db(db: dict[str, Any]) -> list[dict[str, Any]]:
    table = db["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    return [
        {
            field_name: _decode_rpfm_cell(value)
            for field_name, value in zip(fields, row, strict=False)
        }
        for row in table["table_data"]
    ]


def _write_db_file(
    session: RpfmPackSession,
    target_key: str,
    path: str,
    source_db: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    output_path = _delta_table_path(path)
    delta_db = _db_with_rows(source_db, rows)
    table = delta_db["table"]
    _raise_rpfm_error(session.client.send({
        "NewPackedFile": [
            target_key,
            output_path,
            {"DB": [output_path, table["table_name"], table["definition"]["version"]]},
        ]
    }))
    _raise_rpfm_error(session.client.send({
        "SavePackedFileFromView": [target_key, output_path, {"DB": delta_db}]
    }))


def _delta_table_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "/" not in normalized:
        return f"hby_mtu_pack_editor_{_safe_table_leaf(normalized)}"
    folder, leaf = normalized.rsplit("/", 1)
    if leaf.startswith("hby_mtu_pack_editor"):
        return normalized
    return f"{folder}/hby_mtu_pack_editor_{_safe_table_leaf(leaf)}"


def _safe_table_leaf(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in {"_", "-"}:
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "data"


def _incident_key_for_clones(clones: list[CharacterClone]) -> str:
    seed = "|".join(clone.new_template_key for clone in clones)
    return f"hby_mtu_pack_editor_spawn_{zlib.crc32(seed.encode('utf-8')):08x}"


def _incident_key_for_clone(clone: CharacterClone) -> str:
    seed = f"{clone.new_template_key}:{clone.spawn_event or ''}"
    return f"hby_mtu_pack_editor_spawn_{zlib.crc32(seed.encode('utf-8')):08x}"


def _loc_db_with_rows(session: RpfmPackSession, rows: dict[str, str]) -> dict[str, Any]:
    loc_files = session.list_loc_files()
    if not loc_files:
        raise ValueError("Source pack has no loc file to use as a loc table template.")
    source: dict[str, Any] | None = None
    for loc_file in loc_files:
        response = session.client.send({"DecodePackedFile": [session.pack_key, loc_file, "PackFile"]})
        _raise_rpfm_error(response)
        candidate = copy.deepcopy(response["data"]["LocRFileInfo"][0])
        if candidate.get("table", {}).get("table_data"):
            source = candidate
            break
        if source is None:
            source = candidate
    if source is None:
        raise ValueError("Source pack has no loc file to use as a loc table template.")
    table = source["table"]
    fields = [field["name"] for field in table["definition"]["fields"]]
    template_row = table["table_data"][0] if table["table_data"] else [
        _default_loc_template_cell(field_name)
        for field_name in fields
    ]
    table["table_data"] = [
        [
            _encode_rpfm_cell(template_cell, {"key": key, "text": text, "tooltip": True}.get(field_name))
            for field_name, template_cell in zip(fields, template_row, strict=True)
        ]
        for key, text in sorted(rows.items())
    ]
    return source


def _default_loc_template_cell(field_name: str) -> dict[str, Any]:
    if field_name == "tooltip":
        return {"Boolean": False}
    return {"StringU8": ""}


def _copy_image_assets(
    session: RpfmPackSession,
    target_key: str,
    items: list[Any],
    opened_sources: dict[str, str] | None = None,
) -> int:
    assets_by_source: dict[str, set[str]] = {}
    retargeted_assets: list[tuple[str, str, str]] = []
    for item in items:
        for asset in item.image_assets or []:
            packed_path = _normalize_pack_path(asset.get("path", ""))
            if not packed_path:
                continue
            if _is_duplicate_character_folder_path(packed_path):
                continue
            target_path = _normalize_pack_path(asset.get("targetPath", ""))
            if target_path and _is_duplicate_character_folder_path(target_path):
                continue
            source_path = str(asset.get("sourcePath") or session.pack_path)
            if target_path and target_path != packed_path:
                retargeted_assets.append((source_path, packed_path, target_path))
                continue
            assets_by_source.setdefault(source_path, set()).add(packed_path)

    copied = _copy_retargeted_image_assets(session, target_key, retargeted_assets)
    opened_sources = dict(opened_sources or {})
    opened_sources.setdefault(str(session.pack_path), session.pack_key)
    opened_sources.setdefault(str(session.pack_path.resolve()), session.pack_key)
    for source_path, packed_paths in assets_by_source.items():
        source_key = opened_sources.get(source_path)
        if source_key is None:
            resolved = str(Path(source_path).resolve())
            source_key = opened_sources.get(resolved)
        if source_key is None:
            resolved_path = Path(source_path).resolve()
            if resolved_path.is_file():
                source_key = _open_pack_reusing_existing(session, resolved_path, opened_sources)
                opened_sources[source_path] = source_key
                opened_sources[str(resolved_path)] = source_key
            else:
                copied += _copy_extracted_image_assets(session, target_key, sorted(packed_paths))
                continue

        paths = [{"File": path} for path in sorted(packed_paths)]
        if not paths:
            continue
        response = session.client.send({
            "AddPackedFilesFromPackFile": [target_key, source_key, paths]
        })
        try:
            _raise_rpfm_error(response)
        except Exception:
            copied += _copy_extracted_image_assets(session, target_key, sorted(packed_paths))
            continue
        copied += len(paths)
    return copied


def _copy_extracted_image_assets(
    session: RpfmPackSession,
    target_key: str,
    packed_paths: list[str],
) -> int:
    return _copy_extracted_image_asset_pairs(
        session,
        target_key,
        [(packed_path, packed_path) for packed_path in packed_paths],
    )


def _copy_extracted_image_asset_pairs(
    session: RpfmPackSession,
    target_key: str,
    path_pairs: list[tuple[str, str]],
) -> int:
    source_paths: list[str] = []
    dest_paths: list[dict[str, str]] = []
    missing: list[str] = []
    for source_packed_path, target_packed_path in path_pairs:
        source_packed_path = _normalize_pack_path(source_packed_path)
        target_packed_path = _normalize_pack_path(target_packed_path)
        extracted = _find_extracted_asset(source_packed_path)
        if extracted is None:
            missing.append(source_packed_path)
            continue
        source_paths.append(str(_prepare_image_asset_for_pack(session, extracted, target_packed_path)))
        dest_paths.append({"File": target_packed_path})
    if missing:
        raise ValueError(
            "Extracted image asset(s) not found. Refresh/extract reference assets first: "
            + ", ".join(missing[:5])
        )
    if not source_paths:
        return 0
    response = session.client.send({
        "AddPackedFiles": [target_key, source_paths, dest_paths, None]
    })
    _raise_rpfm_error(response)
    data = response.get("data", {})
    added = data.get("VecContainerPathOptionString", [dest_paths, None])[0]
    return len(added)


def _copy_retargeted_image_assets(
    session: RpfmPackSession,
    target_key: str,
    path_triples: list[tuple[str, str, str]],
) -> int:
    source_paths: list[str] = []
    dest_paths: list[dict[str, str]] = []
    missing: list[str] = []
    for source_path, source_packed_path, target_packed_path in path_triples:
        source_packed_path = _normalize_pack_path(source_packed_path)
        target_packed_path = _normalize_pack_path(target_packed_path)
        extracted = _find_extracted_asset(source_packed_path, source_path)
        if extracted is None:
            missing.append(source_packed_path)
            continue
        source_paths.append(str(_prepare_image_asset_for_pack(session, extracted, target_packed_path)))
        dest_paths.append({"File": target_packed_path})
    if missing:
        raise ValueError(
            "Extracted image asset(s) not found. Refresh/extract reference assets first: "
            + ", ".join(missing[:5])
        )
    if not source_paths:
        return 0
    response = session.client.send({
        "AddPackedFiles": [target_key, source_paths, dest_paths, None]
    })
    _raise_rpfm_error(response)
    data = response.get("data", {})
    added = data.get("VecContainerPathOptionString", [dest_paths, None])[0]
    return len(added)


def _copy_available_extracted_image_assets(
    session: RpfmPackSession,
    target_key: str,
    path_pairs: list[tuple[str, str]],
) -> tuple[int, list[str]]:
    source_paths: list[str] = []
    dest_paths: list[dict[str, str]] = []
    missing: list[str] = []
    for source_packed_path, target_packed_path in path_pairs:
        source_packed_path = _normalize_pack_path(source_packed_path)
        target_packed_path = _normalize_pack_path(target_packed_path)
        extracted = _find_extracted_asset(source_packed_path)
        if extracted is None:
            missing.append(source_packed_path)
            continue
        source_paths.append(str(_prepare_image_asset_for_pack(session, extracted, target_packed_path)))
        dest_paths.append({"File": target_packed_path})
    if not source_paths:
        return 0, missing
    response = session.client.send({
        "AddPackedFiles": [target_key, source_paths, dest_paths, None]
    })
    _raise_rpfm_error(response)
    data = response.get("data", {})
    added = data.get("VecContainerPathOptionString", [dest_paths, None])[0]
    return len(added), missing


def _prepare_image_asset_for_pack(
    session: RpfmPackSession,
    extracted: Path,
    target_packed_path: str,
) -> Path:
    comment = _panel_comment_for_pack_path(target_packed_path)
    if comment is None or extracted.suffix.lower() != ".png":
        return extracted
    data = extracted.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        return extracted

    target_comment = _target_pack_png_comment(session, target_packed_path)
    source_comment = _png_text_chunk(data, PNG_COMMENT_KEY)
    final_comment = target_comment or source_comment or comment
    if source_comment == final_comment:
        return extracted

    patched = _png_with_text_comment(data, final_comment)
    TEMP_IMAGE_ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    digest = zlib.crc32((str(extracted) + "|" + target_packed_path + "|" + final_comment).encode("utf-8")) & 0xFFFFFFFF
    patched_path = TEMP_IMAGE_ASSET_ROOT / f"{digest:08x}.png"
    patched_path.write_bytes(patched)
    return patched_path


def _target_pack_png_comment(session: RpfmPackSession, target_packed_path: str) -> str | None:
    try:
        data = session.read_file_bytes(target_packed_path)
    except Exception:
        return None
    return _png_text_chunk(data, PNG_COMMENT_KEY)


def _panel_comment_for_pack_path(packed_path: str) -> str | None:
    parts = [part for part in _normalize_pack_path(packed_path).split("/") if part]
    lower = [part.lower() for part in parts]
    try:
        composite_index = lower.index("composites")
    except ValueError:
        return None
    if composite_index + 1 >= len(lower):
        return None
    panel = lower[composite_index + 1]
    if panel in {"noanim.png", "norm.png", "normal.png"}:
        return PANEL_COMMENT_FALLBACKS[("root", "norm")]
    if panel not in {"large_panel", "small_panel"} or composite_index + 2 >= len(lower):
        return None
    mood = lower[composite_index + 2]
    if mood not in {"angry", "happy", "norm"}:
        return None
    return PANEL_COMMENT_FALLBACKS.get((panel, mood))


def _png_text_chunk(data: bytes, key: str) -> str | None:
    if not data.startswith(PNG_SIGNATURE):
        return None
    position = len(PNG_SIGNATURE)
    key_prefix = key.encode("latin1") + b"\x00"
    while position + 12 <= len(data):
        length = int.from_bytes(data[position:position + 4], "big")
        chunk_type = data[position + 4:position + 8]
        payload_start = position + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            return None
        payload = data[payload_start:payload_end]
        if chunk_type == b"tEXt" and payload.startswith(key_prefix):
            return payload[len(key_prefix):].decode("latin1", errors="replace")
        position = payload_end + 4
    return None


def _png_with_text_comment(data: bytes, comment: str) -> bytes:
    if not data.startswith(PNG_SIGNATURE):
        return data
    text_payload = PNG_COMMENT_KEY.encode("latin1") + b"\x00" + comment.encode("latin1", errors="replace")
    text_chunk = _png_chunk(b"tEXt", text_payload)
    output = bytearray(PNG_SIGNATURE)
    position = len(PNG_SIGNATURE)
    inserted = False
    while position + 12 <= len(data):
        length = int.from_bytes(data[position:position + 4], "big")
        chunk_type = data[position + 4:position + 8]
        chunk_end = position + 12 + length
        if chunk_end > len(data):
            return data
        payload = data[position + 8:position + 8 + length]
        is_comment = chunk_type == b"tEXt" and payload.startswith(PNG_COMMENT_KEY.encode("latin1") + b"\x00")
        if chunk_type == b"IDAT" and not inserted:
            output.extend(text_chunk)
            inserted = True
        if not is_comment:
            output.extend(data[position:chunk_end])
        position = chunk_end
        if chunk_type == b"IEND":
            break
    if not inserted:
        iend_index = output.rfind(b"IEND")
        if iend_index >= 4:
            insert_at = iend_index - 4
            output[insert_at:insert_at] = text_chunk
    return bytes(output)


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def _find_extracted_asset(packed_path: str, source_path: str | None = None) -> Path | None:
    normalized = _normalize_pack_path(packed_path)
    parts = [part for part in normalized.split("/") if part]
    if not parts or not EXTRACTED_ASSET_ROOT.is_dir():
        return None
    if source_path:
        source_root = Path(source_path)
        if source_root.is_dir():
            for candidate_parts in _image_asset_candidate_parts(parts):
                candidate = source_root.joinpath(*candidate_parts)
                if candidate.is_file():
                    return candidate
    core_candidate = EXTRACTED_ASSET_ROOT / CORE_ASSET_SOURCE_ID
    if core_candidate.is_dir():
        for candidate_parts in _image_asset_candidate_parts(parts):
            candidate = core_candidate.joinpath(*candidate_parts)
            if candidate.is_file():
                return candidate
    for pack_dir in EXTRACTED_ASSET_ROOT.iterdir():
        if pack_dir.name == CORE_ASSET_SOURCE_ID:
            continue
        for candidate_parts in _image_asset_candidate_parts(parts):
            candidate = pack_dir.joinpath(*candidate_parts)
            if candidate.is_file():
                return candidate
    return None


def _image_asset_candidate_parts(parts: list[str]) -> list[list[str]]:
    candidates = [parts]
    lower_parts = [part.lower() for part in parts]
    try:
        characters_index = next(
            i for i, part in enumerate(lower_parts)
            if part == "characters" and i > 0 and lower_parts[i - 1] == "ui"
        )
    except StopIteration:
        return candidates
    panel_index = characters_index + 2
    if (
        panel_index < len(parts)
        and lower_parts[panel_index] in {"large_panel", "small_panel"}
        and "composites" not in lower_parts[characters_index + 2:panel_index + 1]
    ):
        candidates.append(parts[:panel_index] + ["composites"] + parts[panel_index:])
    return candidates


def _normalize_pack_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _is_duplicate_character_folder_path(path: str) -> bool:
    parts = [part for part in _normalize_pack_path(path).split("/") if part]
    try:
        index = next(
            i for i, part in enumerate(parts)
            if part == "characters" and i > 0 and parts[i - 1] == "ui"
        )
    except StopIteration:
        return False
    return (
        len(parts) > index + 2
        and parts[index + 1].lower() == parts[index + 2].lower()
    )


def _validate_clone_image_asset_targets(clones: list[CharacterClone]) -> None:
    warnings = _clone_image_asset_target_warnings(clones)
    if warnings:
        raise ValueError(warnings[0])


def _clone_image_asset_target_warnings(clones: list[CharacterClone]) -> list[str]:
    warnings: list[str] = []
    for clone in clones:
        art_tokens = {
            _art_image_token(value)
            for key, value in (clone.art_overrides or {}).items()
            if key in {"portrait", "card"}
            if isinstance(value, str)
        }
        art_tokens.discard("")
        if not art_tokens:
            continue
        for asset in clone.image_assets or []:
            target_path = _normalize_pack_path(asset.get("targetPath") or asset.get("path") or "")
            token = _image_asset_token(target_path)
            if token and token not in art_tokens:
                warnings.append(
                    f"Image asset target does not match art override token: "
                    f"{target_path} not in {sorted(art_tokens)}"
                )
    return warnings


def _image_asset_path_warnings(items: list[Any]) -> list[str]:
    warnings: list[str] = []
    for item in items:
        owner = getattr(item, "new_template_key", None) or getattr(item, "template_key", None) or ""
        for asset in item.image_assets or []:
            source_path = _normalize_pack_path(asset.get("path") or "")
            target_path = _normalize_pack_path(asset.get("targetPath") or asset.get("path") or "")
            if source_path.startswith(f"{IMAGE_ONLY_ASSET_PREFIX}/"):
                warnings.append(
                    f"Image-only reference path leaked into output source for {owner}: {source_path}"
                )
            if target_path.startswith(f"{IMAGE_ONLY_ASSET_PREFIX}/"):
                warnings.append(
                    f"Image-only reference path leaked into output target for {owner}: {target_path}"
                )
    return warnings


def _art_image_token(value: str) -> str:
    clean = _normalize_pack_path(value).strip("/")
    return clean.split("/")[0] if clean else ""


def _image_asset_token(path: str) -> str:
    parts = [part for part in _normalize_pack_path(path).split("/") if part]
    for index, part in enumerate(parts):
        if part == "characters" and index > 0 and parts[index - 1] == "ui" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _write_delta_diagnostics(
    output_path: Path,
    recipe: Recipe,
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
    campaign_script: str | None,
    warnings: list[str] | None = None,
) -> None:
    diagnostics_path = output_path.with_suffix(".diagnostics.json")
    diagnostics = {
        "outputPack": str(output_path),
        "warnings": warnings or [],
        "workItems": [
            {
                "kind": work.get("kind"),
                "title": work.get("title"),
                "workNumber": work.get("workNumber"),
                "workSlug": work.get("workSlug"),
            }
            for work in recipe.work_items
        ],
        "tables": rows_by_table,
        "loc": loc_rows,
        "campaignScriptPath": "script/campaign/mod/hby_mtu_pack_editor_player_spawn.lua" if campaign_script else "",
        "campaignScript": campaign_script or "",
        "spawnEntries": _spawn_entries_for_clones(recipe.character_clones),
        "imageAssets": [
            {
                "owner": getattr(item, "new_template_key", None) or getattr(item, "template_key", None),
                "path": asset.get("path"),
                "targetPath": asset.get("targetPath") or asset.get("path"),
                "sourcePath": asset.get("sourcePath"),
            }
            for item in [*recipe.character_clones, *recipe.character_patches]
            for asset in (item.image_assets or [])
        ],
    }
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _spawn_entries_for_clones(clones: list[CharacterClone]) -> list[dict[str, Any]]:
    spawn_clones = [
        clone
        for clone in clones
        if clone.spawn_event in {"campaign_start", "delayed_join"}
    ]
    entries = []
    for clone in spawn_clones:
        subtype = clone.template_overrides.get("subtype")
        if not subtype:
            continue
        min_turn = 0
        if clone.spawn_event == "delayed_join":
            try:
                min_turn = max(0, int(float(clone.template_overrides.get("min_spawn_round") or 0)))
            except (TypeError, ValueError):
                min_turn = 0
        save_seed = f"{clone.new_template_key}:{clone.spawn_event}".encode("utf-8")
        entries.append({
            "template": clone.new_template_key,
            "subtype": str(subtype),
            "event": clone.spawn_event,
            "turn": min_turn,
            "saveKey": f"hby_mtu_pack_editor_player_spawn_{zlib.crc32(save_seed) & 0xffffffff:08x}",
            "incident": _incident_key_for_clone(clone),
        })
    return entries


def _campaign_start_spawn_script(clones: list[CharacterClone]) -> str | None:
    entries = _spawn_entries_for_clones(clones)

    if not entries:
        return None

    lines = [
        "-- Auto-generated by MTU Pack Editor.",
        "-- Gives selected generated characters to the local player's faction.",
        "local hby_mtu_player_spawn_characters = {",
    ]
    for entry in entries:
        lines.append(
            f'    {{ template = "{_lua_escape(entry["template"])}", subtype = "{_lua_escape(entry["subtype"])}", event = "{_lua_escape(entry["event"] or "")}", turn = {entry["turn"]}, save_key = "{_lua_escape(entry["saveKey"])}", incident = "{_lua_escape(entry["incident"])}" }},'
        )
    lines.extend([
        "}",
        "",
        "local function hby_mtu_all_player_spawns_done()",
        "    for i = 1, #hby_mtu_player_spawn_characters do",
        "        local item = hby_mtu_player_spawn_characters[i]",
        "        if not cm:get_saved_value(item.save_key) then",
        "            return false",
        "        end",
        "    end",
        "    return true",
        "end",
        "",
        "local function hby_mtu_spawn_for_player(faction_key)",
        "    if hby_mtu_all_player_spawns_done() then",
        "        return",
        "    end",
        "",
        "    if not cdir_events_manager or not cdir_events_manager.spawn_character_subtype_template_in_faction then",
        '        output("MTU Pack Editor: cdir_events_manager spawn API not ready.")',
        "        return",
        "    end",
        "",
        '    if not faction_key or faction_key == "" then',
        '        output("MTU Pack Editor: no local player faction found.")',
        "        return",
        "    end",
        "",
        "    local turn_number = cm:turn_number() or 0",
        "    for i = 1, #hby_mtu_player_spawn_characters do",
        "        local item = hby_mtu_player_spawn_characters[i]",
        '        local can_spawn = item.event == "campaign_start" or turn_number >= item.turn',
        "        if not cm:get_saved_value(item.save_key) and can_spawn then",
        "            cdir_events_manager:spawn_character_subtype_template_in_faction(faction_key, item.subtype, item.template)",
        "            if item.incident and cm.trigger_incident then",
        "                pcall(function() cm:trigger_incident(faction_key, item.incident, true) end)",
        "            end",
        "            cm:set_saved_value(item.save_key, true)",
        "        end",
        "    end",
        "end",
        "",
        "function hby_mtu_pack_editor_player_spawn(faction_key)",
        "    hby_mtu_spawn_for_player(faction_key)",
        "end",
        "",
        "cm:add_first_tick_callback(function()",
        '    cm:set_saved_value("hby_mtu_player_spawn_listener_registered", true)',
        "    local faction_key = cm:get_local_faction(true) or cm:get_local_faction()",
        "    hby_mtu_spawn_for_player(faction_key)",
        "end)",
        "",
        "core:add_listener(",
        '    "hby_mtu_pack_editor_player_spawn_turn_start",',
        '    "FactionTurnStart",',
        "    function(context)",
        "        return context:faction():is_human() and not hby_mtu_all_player_spawns_done()",
        "    end,",
        "    function(context)",
        "        hby_mtu_spawn_for_player(context:faction():name())",
        "    end,",
        "    true",
        ")",
        "",
    ])
    return "\n".join(lines)


def _lua_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _name_id_for_clone(clone: CharacterClone, names: list[dict[str, Any]]) -> int:
    used = {str(row.get("id")) for row in names}
    seed = f"{clone.new_template_key}:{clone.display_name or ''}".encode("utf-8")
    value = 2_000_000_000 + (zlib.crc32(seed) % 100_000_000)
    while str(value) in used:
        value += 1
    return value


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


def _find_delta_row(
    rows_by_table: dict[str, list[dict[str, Any]]],
    key_field: str | Any,
    key: Any,
    table_name: str | None = None,
) -> dict[str, Any] | None:
    row_groups = [rows_by_table.get(table_name, [])] if table_name else rows_by_table.values()
    for rows in row_groups:
        for row in rows:
            row_key = key_field(row) if callable(key_field) else row.get(key_field)
            if row_key == key:
                return row
    return None


def _unique_numeric_delta_value(
    seed: str,
    rows: list[dict[str, Any]],
    field: str,
    minimum: int = 1_700_000_000,
    span: int = 300_000_000,
) -> int:
    used = {str(row.get(field)) for row in rows if row.get(field) not in (None, "")}
    value = minimum + (zlib.crc32(seed.encode("utf-8")) % span)
    while str(value) in used:
        value += 1
        if value >= minimum + span:
            value = minimum
    return value


def _clean_source_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not str(key).startswith("_source")}


def _find_required(rows: list[dict[str, Any]], key_field: str, key: str) -> dict[str, Any]:
    for row in rows:
        if row.get(key_field) == key:
            return row
    raise ValueError(f"Row not found: {key_field}={key}")


def _find_required_by(rows: list[dict[str, Any]], key_func: Any, key: str) -> dict[str, Any]:
    for row in rows:
        if str(key_func(row)) == str(key):
            return row
    raise ValueError(f"Row not found: {key}")


def _find_row(rows: list[dict[str, Any]], key_field: str, key: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get(key_field)) == str(key):
            return row
    return None


def _detail_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("character_generation_template"), row.get("game_mode")


def _art_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("art_set_id"),
        row.get("age"),
        row.get("is_female"),
        row.get("has_come_of_age"),
    )


def _attribute_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return _attribute_set_key(row), _attribute_override_key(row)


def _attribute_set_key(row: dict[str, Any]) -> str:
    for column in (
        "set_name",
        "attribute_set",
        "character_attribute_set",
        "character_attribute_set_key",
        "attribute_set_key",
        "set",
        "key",
    ):
        value = row.get(column)
        if value:
            return str(value)
    for value in row.values():
        text = str(value or "")
        if "_attribute_set_" in text or "attribute_set_" in text:
            return text
    return ""


def _with_attribute_set_key(row: dict[str, Any], set_key: str) -> dict[str, Any]:
    clean = _clean_source_row(dict(row))
    for column in (
        "set_name",
        "attribute_set",
        "character_attribute_set",
        "character_attribute_set_key",
        "attribute_set_key",
        "set",
        "key",
    ):
        value = clean.get(column)
        if value and ("attribute_set" in str(value) or column != "key"):
            clean[column] = set_key
            return clean
    clean["set_name"] = set_key
    return clean


def _attribute_override_key(row: dict[str, Any]) -> str:
    value = str(
        row.get("attribute_type")
        or row.get("attribute")
        or row.get("character_attribute")
        or row.get("attribute_key")
        or row.get("key")
        or ""
    ).lower()
    stat_key = _attribute_override_key_from_text(value)
    if stat_key:
        return stat_key
    for cell in row.values():
        stat_key = _attribute_override_key_from_text(str(cell or "").lower())
        if stat_key:
            return stat_key
    return value


def _attribute_override_key_from_text(value: str) -> str | None:
    if "attribute_set" in value:
        return None
    if "expertise" in value or "metal" in value:
        return "expertise"
    if "resolve" in value or "wood" in value:
        return "resolve"
    if "cunning" in value or "water" in value:
        return "cunning"
    if "instinct" in value or "fire" in value:
        return "instinct"
    if "authority" in value or "earth" in value:
        return "authority"
    return None


def _attribute_value_column(row: dict[str, Any]) -> str | None:
    for column in ("value", "attribute_value", "base_value", "initial_value", "starting_value", "amount"):
        if isinstance(row.get(column), (int, float)):
            return column
    skip_columns = {
        "set_name",
        "attribute_set",
        "character_attribute_set",
        "character_attribute_set_key",
        "attribute_set_key",
        "set",
        "key",
        "attribute_type",
        "attribute",
        "character_attribute",
        "attribute_key",
        "minimum_value",
        "maximum_value",
        "min_value",
        "max_value",
        "min",
        "max",
    }
    for column, value in row.items():
        if str(column).startswith("_") or column in skip_columns:
            continue
        if isinstance(value, (int, float)):
            return column
    return None


def _skill_link_key(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    return row.get("parent_key"), row.get("child_key"), row.get("link_type")


def _skill_effect_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("character_skill_key"),
        row.get("effect_key"),
        row.get("effect_scope"),
        row.get("level"),
    )


def _retinue_aspect_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("retinue"), row.get("aspect")


def _retinue_slot_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("retinue"), row.get("slot_index")


def _land_unit_ability_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("land_unit"), row.get("ability")


def _main_unit_key(row: dict[str, Any]) -> Any:
    return row.get("unit") if "unit" in row else row.get("key")


def _effect_key(row: dict[str, Any]) -> str:
    return str(row.get("key") or row.get("effect") or "")


def _raise_rpfm_error(response: dict[str, Any]) -> None:
    data = response.get("data")
    if isinstance(data, dict) and "Error" in data:
        raise ValueError(data["Error"])
