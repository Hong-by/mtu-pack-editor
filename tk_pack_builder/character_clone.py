from __future__ import annotations

from typing import Any

from .adapters import PackSession
from .character_rules import (
    coerce_bool as _coerce_bool,
    gender_compatible_initial_ceo_key as _gender_compatible_initial_ceo_key,
    spawn_safe_initial_ceo_key as _spawn_safe_initial_ceo_key,
)
from .recipe import CharacterClone, CharacterPatch


PLAYER_SPAWN_EVENTS = {"campaign_start", "delayed_join"}
CHARACTER_GAME_MODES = ("historical", "romance")

CHARACTER_TABLE_ALIASES = {
    "character_generation_templates": [
        "character_generation_templates",
        "db/character_generation_templates_tables/_mtu_characters",
    ],
    "character_generation_template_game_mode_details": [
        "character_generation_template_game_mode_details",
        "db/character_generation_template_game_mode_details_tables/_mtu_characters",
    ],
    "campaign_character_art_sets": [
        "campaign_character_art_sets",
        "db/campaign_character_art_sets_tables/_mtu_characters",
    ],
    "campaign_character_arts": [
        "campaign_character_arts",
        "db/campaign_character_arts_tables/_mtu_characters",
    ],
    "character_generation_spawn_age_ranges": [
        "character_generation_spawn_age_ranges",
        "db/character_generation_spawn_age_ranges_tables/_mtu_characters",
    ],
    "ceo_initial_datas": [
        "ceo_initial_datas",
        "db/ceo_initial_datas_tables/_mtu_characters_ceo",
    ],
}


def validate_character_clone(session: PackSession, clone: CharacterClone) -> None:
    tables = _load_tables(session)
    source_template = _find_row(tables["character_generation_templates"], "key", clone.source_template_key)
    _require_missing(
        source_template,
        f"Source character template not found: {clone.source_template_key}",
    )
    _require_absent(
        tables["character_generation_templates"],
        "key",
        clone.new_template_key,
        f"New character template already exists: {clone.new_template_key}",
    )

    detail_rows = [
        row for row in tables["character_generation_template_game_mode_details"]
        if row.get("character_generation_template") == clone.detail_source_template_key
    ]
    if not detail_rows:
        raise ValueError(f"Source game mode details not found: {clone.detail_source_template_key}")

    if clone.new_art_set_id:
        source_art_set = clone.art_set_source_id or _find_row(
            tables["character_generation_templates"],
            "key",
            clone.source_template_key,
        )["art_set_override"]
        if _find_row(tables["campaign_character_art_sets"], "art_set_id", source_art_set):
            _require_absent(
                tables["campaign_character_art_sets"],
                "art_set_id",
                clone.new_art_set_id,
                f"New art set already exists: {clone.new_art_set_id}",
            )
            if not [
                row for row in tables["campaign_character_arts"]
                if row.get("art_set_id") == source_art_set
            ]:
                raise ValueError(f"Source character art rows not found: {source_art_set}")

    if clone.new_age_range_key:
        source_age = clone.age_range_source_key or _find_row(
            tables["character_generation_templates"],
            "key",
            clone.source_template_key,
        )["spawn_age_range"]
        _require_missing(
            _find_row(tables["character_generation_spawn_age_ranges"], "key", source_age),
            f"Source age range not found: {source_age}",
        )
        _require_absent(
            tables["character_generation_spawn_age_ranges"],
            "key",
            clone.new_age_range_key,
            f"New age range already exists: {clone.new_age_range_key}",
        )

    source_art_set_row = None
    if clone.new_art_set_id:
        source_art_set = clone.art_set_source_id or (source_template or {}).get("art_set_override")
        source_art_set_row = _find_row(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
    final_is_male = (
        clone.art_set_overrides.get("is_male")
        if clone.art_set_overrides.get("is_male") not in (None, "")
        else (
            source_art_set_row.get("is_male")
            if source_art_set_row and source_art_set_row.get("is_male") not in (None, "")
            else clone.template_overrides.get("is_male", (source_template or {}).get("is_male"))
        )
    )
    final_subtype = clone.template_overrides.get("subtype", (source_template or {}).get("subtype"))
    seen_initial_ceos: set[str] = set()
    for detail in _required_game_mode_details(detail_rows):
        overrides = clone.detail_overrides.get(detail.get("game_mode", ""), {})
        raw_initial_ceo = (
            overrides.get("initial_ceos")
            or clone.initial_ceo_source_key
            or detail.get("initial_ceos")
        )
        source_ceo = _clone_initial_ceo_key(clone, raw_initial_ceo, final_is_male, final_subtype)
        if not source_ceo or source_ceo in seen_initial_ceos:
            continue
        seen_initial_ceos.add(source_ceo)
        _require_missing(
            _find_row(tables["ceo_initial_datas"], "key", source_ceo),
            f"Source initial CEO not found: {source_ceo}",
        )
        if clone.new_initial_ceo_key and clone.new_initial_ceo_key != source_ceo:
            raise ValueError(
                "Creating new initial CEO keys is not supported because "
                "`ceo_initial_datas` is a key-only table. "
                f"requested={clone.new_initial_ceo_key}, source={source_ceo}"
            )


def validate_character_patch(session: PackSession, patch: CharacterPatch) -> None:
    tables = _load_tables(session)
    template = _find_row(tables["character_generation_templates"], "key", patch.template_key)
    _require_missing(
        template,
        f"Character template not found: {patch.template_key}",
    )
    unknown_template_columns = set(patch.template_overrides) - set(template or {})
    if unknown_template_columns:
        raise ValueError(
            f"Unknown character template column for {patch.template_key}: "
            f"{', '.join(sorted(unknown_template_columns))}"
        )

    if patch.detail_overrides:
        detail_rows = [
            row for row in tables["character_generation_template_game_mode_details"]
            if row.get("character_generation_template") == patch.template_key
        ]
        if not detail_rows:
            raise ValueError(f"Character game mode details not found: {patch.template_key}")
        existing_modes = {row.get("game_mode", "") for row in detail_rows}
        unknown_modes = set(patch.detail_overrides) - (existing_modes | set(CHARACTER_GAME_MODES))
        if unknown_modes:
            raise ValueError(
                f"Character detail game mode not found for {patch.template_key}: {', '.join(sorted(unknown_modes))}"
            )
        detail_columns = set(detail_rows[0])
        unknown_detail_columns = {
            column
            for overrides in patch.detail_overrides.values()
            for column in overrides
            if column not in detail_columns
        }
        if unknown_detail_columns:
            raise ValueError(
                f"Unknown character detail column for {patch.template_key}: "
                f"{', '.join(sorted(unknown_detail_columns))}"
            )


def apply_character_patches(session: PackSession, patches: list[CharacterPatch]) -> int:
    if not patches:
        return 0

    table_names = {
        alias: resolve_character_table_name(session, alias)
        for alias in (
            "character_generation_templates",
            "character_generation_template_game_mode_details",
        )
    }
    templates = session.read_table(table_names["character_generation_templates"])
    details = session.read_table(table_names["character_generation_template_game_mode_details"])

    changed = 0
    for patch in patches:
        validate_character_patch(session, patch)
        template = _find_required(templates, "key", patch.template_key)
        for column, value in patch.template_overrides.items():
            if template.get(column) != value:
                template[column] = value
                changed += 1

        source_detail_rows = [
            row for row in details
            if row.get("character_generation_template") == patch.template_key
        ]
        existing_modes = {
            str(row.get("game_mode") or "")
            for row in source_detail_rows
            if row.get("game_mode") not in (None, "")
        }
        fallback_mode = "historical" if "historical" in existing_modes else "romance"
        for detail in _required_game_mode_details(source_detail_rows):
            game_mode = str(detail.get("game_mode") or "")
            override_mode = game_mode
            if game_mode not in existing_modes and game_mode not in patch.detail_overrides:
                override_mode = fallback_mode
            target_detail = next(
                (
                    row for row in details
                    if row.get("character_generation_template") == patch.template_key
                    and row.get("game_mode") == game_mode
                ),
                None,
            )
            if target_detail is None:
                target_detail = {
                    **detail,
                    "character_generation_template": patch.template_key,
                    "game_mode": game_mode,
                }
                details.append(target_detail)
            overrides = patch.detail_overrides.get(override_mode, {})
            for column, value in overrides.items():
                if target_detail.get(column) != value:
                    target_detail[column] = value
                    changed += 1

    session.replace_table(table_names["character_generation_templates"], templates)
    session.replace_table(table_names["character_generation_template_game_mode_details"], details)
    return changed


def apply_character_clones(session: PackSession, clones: list[CharacterClone]) -> int:
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
        alias: session.read_table(table_name)
        for alias, table_name in table_names.items()
    }

    created = 0
    for clone in clones:
        validate_character_clone(session, clone)
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
            source_art_set = clone.art_set_source_id or source_template["art_set_override"]
            source_art_set_row = _find_row(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
            if source_art_set_row:
                new_template["art_set_override"] = clone.new_art_set_id
                if source_art_set_row.get("is_male") not in (None, ""):
                    is_male = _coerce_bool(source_art_set_row.get("is_male"))
                    new_template["is_male"] = is_male
                _clone_art_set_rows(tables, source_art_set, clone)
            else:
                new_template["art_set_override"] = source_art_set

        if clone.new_age_range_key:
            new_template["spawn_age_range"] = clone.new_age_range_key
            source_age = clone.age_range_source_key or source_template["spawn_age_range"]
            _clone_keyed_row(
                tables["character_generation_spawn_age_ranges"],
                "key",
                source_age,
                clone.new_age_range_key,
                clone.age_range_overrides,
            )

        tables["character_generation_templates"].append(new_template)
        created += 1

        source_details = _required_game_mode_details([
            row for row in tables["character_generation_template_game_mode_details"]
            if row.get("character_generation_template") == clone.detail_source_template_key
        ])
        for source_detail in source_details:
            game_mode = source_detail.get("game_mode", "")
            overrides = clone.detail_overrides.get(game_mode, {})
            override_initial_ceo = str(overrides.get("initial_ceos") or "")
            new_detail = {
                **source_detail,
                "character_generation_template": clone.new_template_key,
                **overrides,
            }
            raw_initial_ceo = (
                override_initial_ceo
                or clone.initial_ceo_source_key
                or new_detail.get("initial_ceos")
            )
            if raw_initial_ceo:
                if clone.new_initial_ceo_key and clone.new_initial_ceo_key != raw_initial_ceo:
                    raise ValueError(
                        "Creating new initial CEO keys is not supported because "
                        "`ceo_initial_datas` is a key-only table. "
                        f"requested={clone.new_initial_ceo_key}, source={raw_initial_ceo}"
                    )
                compatible_initial_ceo = _clone_initial_ceo_key(
                    clone,
                    raw_initial_ceo,
                    new_template.get("is_male"),
                    new_template.get("subtype"),
                )
                if compatible_initial_ceo:
                    new_detail["initial_ceos"] = compatible_initial_ceo
            tables["character_generation_template_game_mode_details"].append(new_detail)

    for alias, rows in tables.items():
        if alias not in table_names:
            continue
        session.replace_table(table_names[alias], rows)
    return created


def _clone_initial_ceo_key(clone: CharacterClone, initial_ceo: Any, is_male: Any, subtype: Any) -> str:
    if clone.spawn_event in PLAYER_SPAWN_EVENTS:
        return _spawn_safe_initial_ceo_key(initial_ceo, is_male, subtype)
    return _gender_compatible_initial_ceo_key(initial_ceo, is_male, subtype)


def _initial_ceo_from_title_ceo_key(title_ceo_key: Any) -> str:
    key = str(title_ceo_key or "").strip()
    if "_ceo_career_historical_" not in key:
        return ""
    return key.replace("_ceo_career_historical_", "_ceo_initial_data_character_historical_")


def _required_game_mode_details(source_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not source_details:
        return []
    by_mode = {
        str(row.get("game_mode") or ""): row
        for row in source_details
        if row.get("game_mode") not in (None, "")
    }
    fallback = by_mode.get("historical") or by_mode.get("romance") or source_details[0]
    return [
        {**(by_mode.get(game_mode) or fallback), "game_mode": game_mode}
        for game_mode in CHARACTER_GAME_MODES
    ]


def resolve_character_table_name(session: PackSession, alias: str) -> str:
    table_list = session.list_tables()
    tables = set(table_list)
    for candidate in CHARACTER_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    table_folder = f"{alias}_tables"
    matches = [path for path in table_list if f"/{table_folder}/" in path]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"Required character table is missing: {alias}")


def _load_tables(session: PackSession) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for alias in CHARACTER_TABLE_ALIASES:
        try:
            tables[alias] = session.read_table(resolve_character_table_name(session, alias))
        except ValueError:
            if alias != "ceo_initial_datas":
                raise
            tables[alias] = []
    return tables


def _clone_art_set_rows(
    tables: dict[str, list[dict[str, Any]]],
    source_art_set: str,
    clone: CharacterClone,
) -> None:
    _clone_keyed_row(
        tables["campaign_character_art_sets"],
        "art_set_id",
        source_art_set,
        clone.new_art_set_id or source_art_set,
        clone.art_set_overrides,
    )
    for art_row in [
        row for row in tables["campaign_character_arts"]
        if row.get("art_set_id") == source_art_set
    ]:
        tables["campaign_character_arts"].append(
            {
                **art_row,
                "art_set_id": clone.new_art_set_id,
                **clone.art_overrides,
            }
        )


def _clone_keyed_row(
    rows: list[dict[str, Any]],
    key_field: str,
    source_key: str,
    new_key: str,
    overrides: dict[str, Any],
) -> None:
    source = _find_required(rows, key_field, source_key)
    rows.append({**source, key_field: new_key, **overrides})


def _find_row(rows: list[dict[str, Any]], key_field: str, key: str | None) -> dict[str, Any] | None:
    if key is None:
        return None
    for row in rows:
        if row.get(key_field) == key:
            return row
    return None


def _find_required(rows: list[dict[str, Any]], key_field: str, key: str) -> dict[str, Any]:
    row = _find_row(rows, key_field, key)
    if row is None:
        raise ValueError(f"Row not found: {key_field}={key}")
    return row


def _require_missing(row: dict[str, Any] | None, message: str) -> None:
    if row is None:
        raise ValueError(message)


def _require_absent(
    rows: list[dict[str, Any]],
    key_field: str,
    key: str,
    message: str,
) -> None:
    if _find_row(rows, key_field, key) is not None:
        raise ValueError(message)
