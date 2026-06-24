from __future__ import annotations

import json
import mimetypes
import socket
import subprocess
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from .adapters import adapter_for
from .analyzer import analyze_pack
from .builder import build_pack
from .character_clone import CHARACTER_TABLE_ALIASES, resolve_character_table_name
from .korean_names import korean_character_name
from .pack_cache import PackCache
from .recipe import recipe_from_dict
from .stat_tables import TABLE_ALIASES
from .validation import has_errors, messages_to_dicts, validate


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "web"
DEFAULT_RPFM_SERVER = ROOT / "work" / "rpfm-master" / "target" / "debug" / "rpfm_server"
PACK_CACHE = PackCache(ROOT / "work" / "pack_cache.sqlite3")
RPFM_PROCESS: subprocess.Popen[bytes] | None = None


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), WebHandler)
    print(f"Three Kingdoms Pack Builder UI: http://{host}:{port}", flush=True)
    server.serve_forever()


class WebHandler(BaseHTTPRequestHandler):
    server_version = "TKPackBuilderWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/" or path == "/index.html":
            self._serve_static("index.html")
            return
        if path == "/app.css":
            self._serve_static("app.css")
            return
        if path == "/app.js":
            self._serve_static("app.js")
            return
        if path == "/api/health":
            self._send_json({"ok": True})
            return
        if path == "/api/asset":
            self._serve_pack_asset(parse_qs(parsed.query))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/api/open":
                self._send_json(open_pack_payload(payload))
                return
            if self.path == "/api/validate":
                self._send_json(validate_payload(payload))
                return
            if self.path == "/api/build":
                self._send_json(build_payload(payload))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as error:
            self._send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self._send_json({"ok": False, "error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_static(self, name: str) -> None:
        path = STATIC_ROOT / name
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_pack_asset(self, query: dict[str, list[str]]) -> None:
        input_path = query.get("inputPath", [""])[0]
        packed_path = query.get("path", [""])[0]
        if not input_path or not packed_path:
            self.send_error(HTTPStatus.BAD_REQUEST, "inputPath and path are required")
            return
        pack_path = Path(input_path)
        cached = PACK_CACHE.get_asset(pack_path, packed_path)
        if cached is not None:
            content_type, data = cached
            self._send_bytes(data, content_type, cache_hit=True)
            return

        session = None
        try:
            _ensure_rpfm_server()
            session = adapter_for("rpfm").open_pack(pack_path)
            data = session.read_file_bytes(packed_path)
        except Exception as error:
            self.send_error(HTTPStatus.NOT_FOUND, str(error))
            return
        finally:
            if session is not None:
                _close_session(session)
        content_type = mimetypes.guess_type(packed_path)[0] or "application/octet-stream"
        PACK_CACHE.put_asset(pack_path, packed_path, content_type, data)
        self._send_bytes(data, content_type, cache_hit=False)

    def _send_bytes(self, data: bytes, content_type: str, cache_hit: bool = False) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "private, max-age=3600")
        self.send_header("x-pack-cache", "hit" if cache_hit else "miss")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def open_pack_payload(payload: dict[str, Any]) -> dict[str, Any]:
    input_path = payload.get("inputPath")
    include_vanilla = bool(payload.get("includeVanilla"))
    reference_paths = _reference_pack_paths(payload)
    if not input_path:
        raise ValueError("inputPath is required.")
    pack_path = Path(input_path)
    if not payload.get("forceRefresh"):
        cached = PACK_CACHE.get_open_payload(pack_path, include_vanilla, reference_paths)
        if cached is not None:
            return cached

    session = _open_session(payload)
    try:
        analysis = analyze_pack(session).to_dict()
        character_data = read_character_data(
            session,
            include_vanilla=include_vanilla,
            reference_paths=reference_paths,
            adapter_name=payload.get("adapter", "mock"),
        )
        PACK_CACHE.put_open_payload(pack_path, include_vanilla, analysis, character_data, reference_paths)
        return {
            "ok": True,
            "analysis": analysis,
            "characters": character_data,
            "cache": {
                "hit": False,
                "path": str(PACK_CACHE.db_path),
            },
        }
    finally:
        _close_session(session)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    session = _open_session(payload)
    try:
        recipe = recipe_from_dict(payload.get("recipe", {}))
        messages = validate(session, recipe, payload.get("outputPath"))
        return {"ok": not has_errors(messages), "messages": messages_to_dicts(messages)}
    finally:
        _close_session(session)


def build_payload(payload: dict[str, Any]) -> dict[str, Any]:
    session = _open_session(payload)
    try:
        recipe = recipe_from_dict(payload.get("recipe", {}))
        output_path = Path(payload["outputPath"]) if payload.get("outputPath") else None
        messages = build_pack(
            session,
            recipe,
            output_path,
            in_place=bool(payload.get("inPlace")),
            delta=bool(payload.get("delta")),
        )
        return {
            "ok": not any(message["level"] == "error" for message in messages),
            "messages": messages,
        }
    finally:
        _close_session(session)


def read_character_data(
    session: Any,
    include_vanilla: bool = False,
    reference_paths: list[Path] | None = None,
    adapter_name: str = "mock",
) -> dict[str, Any]:
    tables = _read_character_tables(session, "pack")
    loc_text = _read_all_loc_text(session)
    asset_files = session.list_files()
    asset_sources: dict[str, str] = {}
    reference_report = _merge_reference_packs(
        tables,
        loc_text,
        asset_files,
        asset_sources,
        reference_paths or [],
        adapter_name,
        session.pack_path,
    )
    data = {
        "pack": summarize_character_tables(tables, loc_text, asset_files, asset_sources),
        "vanilla": {"available": False, "error": None, "summary": None},
        "referencePacks": reference_report,
    }
    if include_vanilla:
        try:
            vanilla_tables = _read_character_tables(session, "vanilla")
            data["vanilla"] = {
                "available": True,
                "error": None,
                "summary": summarize_character_tables(vanilla_tables, loc_text, []),
            }
        except ValueError as error:
            data["vanilla"] = {"available": False, "error": str(error), "summary": None}
    return data


def summarize_character_tables(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str] | None = None,
    asset_files: list[str] | None = None,
    asset_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    loc_text = loc_text or {}
    asset_files = asset_files or []
    asset_sources = asset_sources or {}
    details_by_template: dict[str, list[dict[str, Any]]] = {}
    for row in tables["character_generation_template_game_mode_details"]:
        details_by_template.setdefault(str(row.get("character_generation_template", "")), []).append(row)

    art_rows_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in tables["campaign_character_arts"]:
        art_rows_by_set.setdefault(str(row.get("art_set_id", "")), []).append(row)

    art_sets = []
    for row in tables["campaign_character_art_sets"]:
        art_set_id = row.get("art_set_id")
        if not art_set_id:
            continue
        art_rows = art_rows_by_set.get(str(art_set_id), [])
        primary_art = _primary_art_row(art_rows)
        portrait_path = str(primary_art.get("portrait") or "").strip("/")
        card_path = str(primary_art.get("card") or "").strip("/")
        portrait_image_path = _find_character_image(asset_files, portrait_path, "halfbody_large")
        card_image_path = _find_character_image(asset_files, card_path, "unitcards")
        art_sets.append(
            {
                "key": art_set_id,
                "label": _friendly_art_set_label(str(art_set_id)),
                "rowCount": len(art_rows),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "portraitImagePath": portrait_image_path,
                "portraitImageSourcePath": asset_sources.get(portrait_image_path or ""),
                "cardImagePath": card_image_path,
                "cardImageSourcePath": asset_sources.get(card_image_path or ""),
                "rows": art_rows,
            }
        )

    age_ranges = [
        {
            "key": row.get("key"),
            "label": _friendly_key(str(row.get("key", ""))),
            "birthYear": row.get("birth_year"),
            "minSpawnYearRound": row.get("min_spawn_year_round"),
            "maxSpawnYearRound": row.get("max_spawn_year_round"),
            "row": row,
        }
        for row in tables["character_generation_spawn_age_ranges"]
        if row.get("key")
    ]

    initial_ceos = [
        {
            "key": row.get("key"),
            "label": _friendly_key(str(row.get("key", ""))),
            "row": row,
        }
        for row in tables["ceo_initial_datas"]
        if row.get("key")
    ]
    combat_stats_by_initial_ceo = _combat_stats_by_initial_ceo(tables)
    land_units = {str(row.get("key")): row for row in tables.get("land_units", []) if row.get("key")}

    characters = []
    for template in tables["character_generation_templates"]:
        key = str(template.get("key", ""))
        reference_source = template.get("_referenceSourcePath")
        display_name = _character_display_name(template, loc_text)
        details = sorted(
            [
                {
                    "gameMode": detail.get("game_mode", ""),
                    "retinue": detail.get("retinue"),
                    "attributeSet": detail.get("attribute_set"),
                    "skillSet": detail.get("skill_set_override"),
                    "initialCeos": detail.get("initial_ceos"),
                    "row": detail,
                }
                for detail in details_by_template.get(key, [])
            ],
            key=lambda item: str(item["gameMode"]),
        )
        art_set = str(template.get("art_set_override") or "")
        art_rows = art_rows_by_set.get(art_set, [])
        primary_art = _primary_art_row(art_rows)
        art_set_summary = next((row for row in art_sets if row["key"] == art_set), {})
        combat_stats = _combat_stats_for_details(details, combat_stats_by_initial_ceo) or {}
        combat_stats.update(_unit_stats_for_details(key, details, land_units))
        title_info = _title_info_for_character(template, details, loc_text)
        characters.append(
            {
                "key": key,
                "displayName": display_name,
                "label": display_name or _friendly_character_label(key),
                "forename": template.get("forename"),
                "familyName": template.get("family_name"),
                "clanName": template.get("clan_name"),
                "subtype": template.get("subtype"),
                "weight": template.get("weight"),
                "artSet": template.get("art_set_override"),
                "ageRange": template.get("spawn_age_range"),
                "minSpawnRound": template.get("min_spawn_round"),
                "maxSpawnRound": template.get("max_spawn_round"),
                "voiceoverActor": template.get("voiceover_actor"),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "portraitImagePath": art_set_summary.get("portraitImagePath"),
                "portraitImageSourcePath": art_set_summary.get("portraitImageSourcePath"),
                "cardImagePath": art_set_summary.get("cardImagePath"),
                "cardImageSourcePath": art_set_summary.get("cardImageSourcePath"),
                "combatStats": combat_stats,
                "titleInfo": title_info,
                "templateRow": template,
                "details": details,
                "source": "reference" if reference_source else "pack",
                "referenceSourcePath": reference_source,
            }
        )

    detail_rows = tables["character_generation_template_game_mode_details"]
    return {
        "characters": sorted(characters, key=lambda item: (item["displayName"] or item["key"], item["key"])),
        "artSets": sorted(art_sets, key=lambda item: str(item["key"])),
        "artRowsBySet": {
            key: len(rows)
            for key, rows in sorted(art_rows_by_set.items())
        },
        "ageRanges": sorted(age_ranges, key=lambda item: str(item["key"])),
        "initialCeos": sorted(initial_ceos, key=lambda item: str(item["key"])),
        "retinues": _unique_options(row.get("retinue") for row in detail_rows),
        "attributeSets": _unique_options(row.get("attribute_set") for row in detail_rows),
        "skillSets": _unique_options(row.get("skill_set_override") for row in detail_rows),
        "subtypes": _unique_options(row.get("subtype") for row in tables["character_generation_templates"]),
        "locKeys": sorted(loc_text.keys()),
    }


def _combat_stats_by_initial_ceo(tables: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    weapon_ceos = {
        str(row.get("ceos_key")): row
        for row in tables.get("equipment_variants_weapons", [])
        if row.get("ceos_key")
    }
    armour_ceos = {
        str(row.get("ceos_key")): row
        for row in tables.get("equipment_variants_armours", [])
        if row.get("ceos_key")
    }
    melee_weapons = {str(row.get("key")): row for row in tables.get("melee_weapons", [])}
    missile_weapons = {str(row.get("key")): row for row in tables.get("missile_weapons", [])}
    projectiles = {str(row.get("key")): row for row in tables.get("projectiles", [])}
    armour_types = {str(row.get("key")): row for row in tables.get("unit_armour_types", [])}

    initial_keys = {
        str(row.get("key") or "")
        for row in tables.get("ceo_initial_datas", [])
        if row.get("key")
    }
    initial_keys.update(
        str(row.get("initial_ceos") or "")
        for row in tables.get("character_generation_template_game_mode_details", [])
        if row.get("initial_ceos")
    )

    stats: dict[str, dict[str, Any]] = {}
    for initial_key in sorted(initial_keys):
        if not initial_key:
            continue
        name_token = _character_token_from_initial_ceo(initial_key)
        weapon = _best_equipment_variant(name_token, weapon_ceos, "weapon")
        armour = _best_equipment_variant(name_token, armour_ceos, "armour")
        weapon_row = melee_weapons.get(str((weapon or {}).get("primary_melee_weapon") or ""))
        missile_weapon_row = missile_weapons.get(str((weapon or {}).get("primary_missile_weapon") or ""))
        projectile_row = projectiles.get(str((missile_weapon_row or {}).get("default_projectile") or ""))
        armour_row = armour_types.get(str((armour or {}).get("armour") or ""))
        if weapon_row or missile_weapon_row or projectile_row or armour_row:
            stats[initial_key] = {
                "weaponCeo": (weapon or {}).get("ceos_key"),
                "weaponStatKey": (weapon or {}).get("primary_melee_weapon"),
                "weaponDamage": _number_or_none((weapon_row or {}).get("damage")),
                "weaponApDamage": _number_or_none((weapon_row or {}).get("ap_damage")),
                "weaponType": (weapon_row or {}).get("melee_weapon_type"),
                "missileWeaponStatKey": (weapon or {}).get("primary_missile_weapon"),
                "projectileStatKey": (missile_weapon_row or {}).get("default_projectile"),
                "projectileDamage": _number_or_none((projectile_row or {}).get("damage")),
                "projectileApDamage": _number_or_none((projectile_row or {}).get("ap_damage")),
                "projectileRange": _number_or_none((projectile_row or {}).get("effective_range")),
                "armourCeo": (armour or {}).get("ceos_key"),
                "armourStatKey": (armour or {}).get("armour"),
                "armourAudioType": (armour_row or {}).get("audio_type"),
                "baseAttack": _sum_numeric(weapon_row, ("damage", "ap_damage")),
                "baseDefense": _number_or_none((armour_row or {}).get("armour_value")),
            }
    return stats


def _combat_stats_for_details(
    details: list[dict[str, Any]],
    stats_by_initial_ceo: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") != game_mode:
                continue
            stats = stats_by_initial_ceo.get(str(detail.get("initialCeos") or ""))
            if stats:
                return stats
    for detail in details:
        stats = stats_by_initial_ceo.get(str(detail.get("initialCeos") or ""))
        if stats:
            return stats
    return None


def _character_token_from_initial_ceo(initial_key: str) -> str:
    token = initial_key
    for marker in (
        "ceo_initial_data_character_historical_",
        "ceo_initial_data_character_romance_",
        "ceo_initial_data_character_",
    ):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    return token.removeprefix("lady_")


def _title_info_for_character(
    template: dict[str, Any],
    details: list[dict[str, Any]],
    loc_text: dict[str, str],
) -> dict[str, Any]:
    initial_key = _preferred_initial_ceo(details)
    token = _character_token_from_initial_ceo(initial_key) if initial_key else _character_token_from_template(str(template.get("key", "")))
    candidates = _title_candidate_keys(token)
    matched = next((key for key in candidates if _loc_title_for_ceo_node(key, loc_text)), candidates[0] if candidates else "")
    return {
        "status": "read_only_spike",
        "label": _loc_title_for_ceo_node(matched, loc_text) or _friendly_title_label(matched),
        "ceoNodeKey": matched,
        "initialCeoKey": initial_key,
        "locTitleKey": f"ceo_nodes_title_{matched}" if matched else "",
        "descriptionKey": f"ceo_nodes_description_{matched}" if matched else "",
        "source": "campaigns/ceo_data.ccd",
        "note": "set_title/career CEO는 CCD/startpos 계층이라 쓰기는 별도 검증 후 지원",
    }


def _preferred_initial_ceo(details: list[dict[str, Any]]) -> str:
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") == game_mode and detail.get("initialCeos"):
                return str(detail.get("initialCeos"))
    for detail in details:
        if detail.get("initialCeos"):
            return str(detail.get("initialCeos"))
    return ""


def _title_candidate_keys(token: str) -> list[str]:
    if not token:
        return []
    normalized = token.removeprefix("lady_")
    tokens = [normalized]
    if token != normalized:
        tokens.append(token)
    prefixes = ("3k_mtu", "3k_main", "3k_dlc04", "3k_dlc05", "ep")
    candidates = []
    for prefix in prefixes:
        for item in tokens:
            candidates.append(f"{prefix}_ceo_node_career_historical_{item}_01")
    return candidates


def _loc_title_for_ceo_node(ceo_node_key: str, loc_text: dict[str, str]) -> str | None:
    if not ceo_node_key:
        return None
    return loc_text.get(f"ceo_nodes_title_{ceo_node_key}")


def _friendly_title_label(ceo_node_key: str) -> str:
    if not ceo_node_key:
        return "칭호 미확인"
    value = ceo_node_key
    for marker in ("_ceo_node_career_historical_", "_ceo_node_career_generated_"):
        if marker in value:
            value = value.split(marker, 1)[1]
            break
    return value.removesuffix("_01").replace("_", " ")


def _best_equipment_variant(
    name_token: str,
    variants_by_ceo: dict[str, dict[str, Any]],
    equipment_kind: str,
) -> dict[str, Any] | None:
    if not name_token:
        return None
    candidates = []
    for ceo_key, row in variants_by_ceo.items():
        normalized = ceo_key.lower()
        if name_token.lower() not in normalized:
            continue
        if equipment_kind == "weapon" and "weapon" not in normalized:
            continue
        if equipment_kind == "armour" and "armour" not in normalized:
            continue
        candidates.append((ceo_key.count("_"), ceo_key, row))
    if not candidates:
        return None
    return sorted(candidates)[0][2]


def _sum_numeric(row: dict[str, Any] | None, columns: tuple[str, ...]) -> int | float | None:
    if not row:
        return None
    values = [_number_or_none(row.get(column)) for column in columns]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(numeric_values)


def _number_or_none(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _read_character_tables(session: Any, source: str) -> dict[str, list[dict[str, Any]]]:
    tables = {}
    for alias in CHARACTER_TABLE_ALIASES:
        table_name = resolve_character_table_name(session, alias) if source == "pack" else _resolve_source_table(session, alias, source)
        tables[alias] = session.read_table(table_name, source)
    for alias in (
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
    ):
        try:
            table_name = _resolve_stat_table(session, alias, source)
            tables[alias] = session.read_table(table_name, source)
        except ValueError:
            tables[alias] = []
    return tables


def _merge_reference_packs(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
    asset_files: list[str],
    asset_sources: dict[str, str],
    reference_paths: list[Path],
    adapter_name: str,
    primary_pack_path: Path,
) -> list[dict[str, Any]]:
    report = []
    known_assets = set(asset_files)
    for reference_path in reference_paths:
        resolved = reference_path.expanduser()
        if not resolved.exists():
            report.append({"path": str(resolved), "ok": False, "error": "file_not_found"})
            continue
        if resolved.resolve() == primary_pack_path.resolve():
            report.append({"path": str(resolved), "ok": False, "error": "same_as_input_pack"})
            continue
        session = None
        before_counts = {alias: len(rows) for alias, rows in tables.items()}
        try:
            if adapter_name == "rpfm":
                _ensure_rpfm_server()
            session = adapter_for(adapter_name).open_pack(resolved)
            reference_tables = _read_reference_tables(session)
            for alias, rows in reference_tables.items():
                if alias == "campaign_character_arts":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("art_set_id", "age", "portrait", "card", "uniform"),
                        str(resolved),
                    )
                elif alias == "character_generation_template_game_mode_details":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("character_generation_template", "game_mode"),
                        str(resolved),
                    )
                else:
                    _append_missing_rows(
                        tables.setdefault(alias, []),
                        rows,
                        _key_field_for_alias(alias),
                        str(resolved),
                    )
            for key, text in _read_all_loc_text(session).items():
                loc_text.setdefault(key, text)
            added_assets = 0
            for asset_path in session.list_files():
                if asset_path in known_assets:
                    continue
                asset_files.append(asset_path)
                known_assets.add(asset_path)
                asset_sources[asset_path] = str(resolved)
                added_assets += 1
            added = {
                alias: len(tables.get(alias, [])) - before_counts.get(alias, 0)
                for alias in reference_tables
            }
            report.append({
                "path": str(resolved),
                "ok": True,
                "tables": sorted(reference_tables),
                "addedRows": {key: value for key, value in added.items() if value},
                "addedAssets": added_assets,
            })
        except Exception as error:
            report.append({"path": str(resolved), "ok": False, "error": str(error)})
        finally:
            if session is not None:
                _close_session(session)
    return report


def _read_reference_tables(session: Any) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for alias in CHARACTER_TABLE_ALIASES:
        try:
            table_name = _resolve_reference_character_table(session, alias)
            tables[alias] = session.read_table(table_name)
        except ValueError:
            continue
    for alias in (
        "campaign_character_art_sets",
        "campaign_character_arts",
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
    ):
        try:
            if alias in {"campaign_character_art_sets", "campaign_character_arts"}:
                table_name = _resolve_reference_character_table(session, alias)
            else:
                table_name = _resolve_stat_table(session, alias, "pack")
            tables[alias] = session.read_table(table_name)
        except ValueError:
            continue
    return tables


def _append_missing_rows(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    key_field: str,
    reference_path: str,
) -> None:
    existing = {row.get(key_field) for row in target if row.get(key_field) is not None}
    for row in source:
        key = row.get(key_field)
        if key is None or key in existing:
            continue
        target.append({**row, "_referenceSourcePath": reference_path})
        existing.add(key)


def _append_missing_rows_by_fields(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    fields: tuple[str, ...],
    reference_path: str,
) -> None:
    existing = {
        tuple(row.get(field) for field in fields)
        for row in target
    }
    for row in source:
        key = tuple(row.get(field) for field in fields)
        if key in existing:
            continue
        target.append({**row, "_referenceSourcePath": reference_path})
        existing.add(key)


def _key_field_for_alias(alias: str) -> str:
    if alias == "campaign_character_art_sets":
        return "art_set_id"
    if alias in {"equipment_variants_weapons", "equipment_variants_armours"}:
        return "ceos_key"
    return "key"


def _unit_stats_for_details(
    template_key: str,
    details: list[dict[str, Any]],
    land_units: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") != game_mode:
                continue
            row = land_units.get(str(detail.get("retinue") or ""))
            if row:
                return _unit_stats_from_row(row)
    for detail in details:
        row = land_units.get(str(detail.get("retinue") or ""))
        if row:
            return _unit_stats_from_row(row)
    name_token = _character_token_from_template(template_key)
    row = _best_land_unit(name_token, land_units)
    if row:
        return _unit_stats_from_row(row)
    return {}


def _unit_stats_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "landUnitKey": row.get("key"),
        "unitMeleeAttack": _number_or_none(row.get("melee_attack")),
        "unitMeleeDefence": _number_or_none(row.get("melee_defence")),
        "unitChargeBonus": _number_or_none(row.get("charge_bonus")),
        "unitMorale": _number_or_none(row.get("morale")),
        "unitPrimaryAmmo": _number_or_none(row.get("primary_ammo")),
        "unitCategory": row.get("category"),
        "unitClass": row.get("class"),
        "unitFromReference": bool(row.get("_referenceSourcePath")),
        "unitReferenceSource": row.get("_referenceSourcePath"),
    }


def _character_token_from_template(template_key: str) -> str:
    token = template_key
    for marker in ("template_historical_", "template_ancestral_"):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    for suffix in ("_hero_earth", "_hero_fire", "_hero_metal", "_hero_water", "_hero_wood"):
        token = token.removesuffix(suffix)
    return token.removeprefix("lady_")


def _best_land_unit(
    name_token: str,
    land_units: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not name_token:
        return None
    candidates = []
    for key, row in land_units.items():
        normalized = key.lower()
        if name_token.lower() not in normalized:
            continue
        priority = 0 if "_general_" in normalized else 1
        candidates.append((priority, key.count("_"), key, row))
    if not candidates:
        return None
    return sorted(candidates)[0][3]


def _read_all_loc_text(session: Any) -> dict[str, str]:
    texts: dict[str, str] = {}
    for loc_path in session.list_loc_files():
        try:
            texts.update(session.read_loc(loc_path))
        except (NotImplementedError, ValueError):
            continue
    return texts


def _character_display_name(template: dict[str, Any], loc_text: dict[str, str]) -> str | None:
    key = str(template.get("key", ""))
    korean_name = korean_character_name(key)
    if korean_name:
        return korean_name

    parts = [
        _name_text(template.get("family_name"), loc_text),
        _name_text(template.get("forename"), loc_text),
        _name_text(template.get("other_name"), loc_text),
    ]
    id_text = "".join(part for part in parts if part)
    key_text = _display_name_from_key(key, loc_text)
    return id_text or key_text


def _name_text(value: Any, loc_text: dict[str, str]) -> str | None:
    if value in {None, "", 0, "0"}:
        return None
    name_id = str(value)
    return (
        loc_text.get(f"names_alt_name_{name_id}")
        or loc_text.get(f"names_name_{name_id}")
    )


def _display_name_from_key(template_key: str, loc_text: dict[str, str]) -> str | None:
    tokens = _name_tokens_from_template_key(template_key)
    if not tokens:
        return None

    roman_to_alt = _romanized_name_lookup(loc_text)
    resolved: list[str] = []
    index = 0
    while index < len(tokens):
        two = "".join(tokens[index:index + 2]).lower()
        if index + 1 < len(tokens) and two in roman_to_alt:
            resolved.append(roman_to_alt[two])
            index += 2
            continue
        one = tokens[index].lower()
        if one in roman_to_alt:
            resolved.append(roman_to_alt[one])
        index += 1
    return "".join(resolved) or None


def _name_tokens_from_template_key(template_key: str) -> list[str]:
    marker = "_template_"
    if marker in template_key:
        template_key = template_key.split(marker, 1)[1]
    tokens = [
        token
        for token in template_key.split("_")
        if token not in {
            "3k",
            "main",
            "mtu",
            "dlc04",
            "dlc05",
            "template",
            "historical",
            "generated",
            "lady",
            "hero",
            "earth",
            "fire",
            "metal",
            "water",
            "wood",
        }
    ]
    return tokens


def _romanized_name_lookup(loc_text: dict[str, str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for key, romanized in loc_text.items():
        if not key.startswith("names_name_"):
            continue
        name_id = key.removeprefix("names_name_")
        alt = loc_text.get(f"names_alt_name_{name_id}")
        if romanized and alt:
            lookup[_normalize_romanized_name(romanized)] = alt
    return lookup


def _normalize_romanized_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _friendly_key(value: str) -> str:
    marker_words = {
        "3k",
        "main",
        "mtu",
        "template",
        "historical",
        "hero",
        "general",
        "character",
    }
    words = [word for word in value.split("_") if word and word not in marker_words]
    return " ".join(words[-4:]) if words else value


def _friendly_character_label(value: str) -> str:
    tokens = _name_tokens_from_template_key(value)
    return " ".join(tokens) if tokens else _friendly_key(value)


def _friendly_art_set_label(value: str) -> str:
    value = value.removeprefix("3k_mtu_art_set_historical_")
    value = value.removeprefix("3k_main_art_set_historical_")
    value = value.removesuffix("_general")
    return " ".join(part for part in value.split("_") if part)


def _primary_art_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    adult_rows = [row for row in rows if row.get("has_come_of_age") is True]
    if adult_rows:
        return sorted(adult_rows, key=lambda row: int(row.get("age") or 999))[0]
    non_baby_rows = [
        row for row in rows
        if str(row.get("portrait", "")).strip("/") not in {"baby", "child_01_male", "child_03_male", "child_01_female"}
    ]
    return non_baby_rows[0] if non_baby_rows else rows[0]


def _find_character_image(asset_files: list[str], image_key: str, image_kind: str) -> str | None:
    if not image_key:
        return None
    normalized = image_key.strip("/")
    preferred = [
        f"ui/characters/{normalized}/stills/{image_kind}/{normalized}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/large/{normalized}.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/norm.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/happy.png",
    ]
    assets = set(asset_files)
    for path in preferred:
        if path in assets:
            return path
    matches = [
        path for path in asset_files
        if path.startswith(f"ui/characters/{normalized}/")
        and (
            f"/stills/{image_kind}/" in path
            or "/composites/large_panel/norm/" in path
            or "/composites/large_panel/happy/" in path
        )
        and path.endswith(".png")
    ]
    return matches[0] if matches else None


def _unique_options(values: Any) -> list[dict[str, str]]:
    seen: set[str] = set()
    options: list[dict[str, str]] = []
    for value in values:
        if value in {None, "", 0, "0"}:
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        options.append({"key": key, "label": _friendly_key(key)})
    return sorted(options, key=lambda item: item["label"])


def _resolve_source_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in CHARACTER_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    raise ValueError(f"Required character table is missing in {source}: {alias}")


def _resolve_stat_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    generic_prefix = (
        "db/ceos_to_equipment_variants_tables/"
        if alias in {"equipment_variants_weapons", "equipment_variants_armours"}
        else f"db/{alias}_tables/"
    )
    matches = sorted(table for table in tables if table.startswith(generic_prefix))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preferred = [
            table for table in matches
            if "/data__" in table or table.endswith(f"/{alias}") or table.endswith(f"/_{alias}")
        ]
        if len(preferred) == 1:
            return preferred[0]
        return matches[0]
    raise ValueError(f"Required stat table is missing in {source}: {alias}")


def _resolve_reference_character_table(session: Any, alias: str) -> str:
    tables = set(session.list_tables("pack"))
    for candidate in CHARACTER_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    matches = sorted(table for table in tables if table.startswith(f"db/{alias}_tables/"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preferred = [
            table for table in matches
            if "/_mtu" in table or "/data__" in table
        ]
        return preferred[0] if preferred else matches[0]
    raise ValueError(f"Required reference character table is missing: {alias}")


def _open_session(payload: dict[str, Any]) -> Any:
    adapter_name = payload.get("adapter", "mock")
    input_path = payload.get("inputPath")
    if not input_path:
        raise ValueError("inputPath is required.")
    if adapter_name == "rpfm":
        _ensure_rpfm_server()
    return adapter_for(adapter_name).open_pack(Path(input_path))


def _reference_pack_paths(payload: dict[str, Any]) -> list[Path]:
    raw_paths = payload.get("referencePackPaths") or []
    if isinstance(raw_paths, str):
        raw_paths = [line.strip() for line in raw_paths.splitlines()]
    paths = []
    for raw_path in raw_paths:
        if not raw_path:
            continue
        paths.append(Path(str(raw_path)).expanduser())
    return paths


def _ensure_rpfm_server() -> None:
    global RPFM_PROCESS
    if _port_open("127.0.0.1", 45127):
        return
    if RPFM_PROCESS is not None and RPFM_PROCESS.poll() is None:
        _wait_for_port("127.0.0.1", 45127)
        return
    if not DEFAULT_RPFM_SERVER.is_file():
        raise ValueError(f"RPFM server binary not found: {DEFAULT_RPFM_SERVER}")
    RPFM_PROCESS = subprocess.Popen(
        [str(DEFAULT_RPFM_SERVER)],
        cwd=DEFAULT_RPFM_SERVER.parent.parent.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_port("127.0.0.1", 45127)


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _port_open(host, port):
            return
        time.sleep(0.2)
    raise ValueError(f"RPFM server did not become ready on {host}:{port}.")


def _close_session(session: Any) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="tk-pack-builder-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
