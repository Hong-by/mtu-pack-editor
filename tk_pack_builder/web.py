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
    if not input_path:
        raise ValueError("inputPath is required.")
    pack_path = Path(input_path)
    if not payload.get("forceRefresh"):
        cached = PACK_CACHE.get_open_payload(pack_path, include_vanilla)
        if cached is not None:
            return cached

    session = _open_session(payload)
    try:
        analysis = analyze_pack(session).to_dict()
        character_data = read_character_data(session, include_vanilla=include_vanilla)
        PACK_CACHE.put_open_payload(pack_path, include_vanilla, analysis, character_data)
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


def read_character_data(session: Any, include_vanilla: bool = False) -> dict[str, Any]:
    tables = _read_character_tables(session, "pack")
    loc_text = _read_all_loc_text(session)
    asset_files = session.list_files()
    data = {
        "pack": summarize_character_tables(tables, loc_text, asset_files),
        "vanilla": {"available": False, "error": None, "summary": None},
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
) -> dict[str, Any]:
    loc_text = loc_text or {}
    asset_files = asset_files or []
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
        art_sets.append(
            {
                "key": art_set_id,
                "label": _friendly_art_set_label(str(art_set_id)),
                "rowCount": len(art_rows),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "portraitImagePath": _find_character_image(asset_files, portrait_path, "halfbody_large"),
                "cardImagePath": _find_character_image(asset_files, card_path, "unitcards"),
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

    characters = []
    for template in tables["character_generation_templates"]:
        key = str(template.get("key", ""))
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
        combat_stats = _combat_stats_for_details(details, combat_stats_by_initial_ceo)
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
                "cardImagePath": art_set_summary.get("cardImagePath"),
                "combatStats": combat_stats,
                "templateRow": template,
                "details": details,
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
        armour_row = armour_types.get(str((armour or {}).get("armour") or ""))
        if weapon_row or armour_row:
            stats[initial_key] = {
                "weaponCeo": (weapon or {}).get("ceos_key"),
                "weaponStatKey": (weapon or {}).get("primary_melee_weapon"),
                "armourCeo": (armour or {}).get("ceos_key"),
                "armourStatKey": (armour or {}).get("armour"),
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
        "unit_armour_types",
    ):
        try:
            table_name = _resolve_stat_table(session, alias, source)
            tables[alias] = session.read_table(table_name, source)
        except ValueError:
            tables[alias] = []
    return tables


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
    ]
    assets = set(asset_files)
    for path in preferred:
        if path in assets:
            return path
    matches = [
        path for path in asset_files
        if path.startswith(f"ui/characters/{normalized}/")
        and f"/stills/{image_kind}/" in path
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
    raise ValueError(f"Required stat table is missing in {source}: {alias}")


def _open_session(payload: dict[str, Any]) -> Any:
    adapter_name = payload.get("adapter", "mock")
    input_path = payload.get("inputPath")
    if not input_path:
        raise ValueError("inputPath is required.")
    if adapter_name == "rpfm":
        _ensure_rpfm_server()
    return adapter_for(adapter_name).open_pack(Path(input_path))


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
