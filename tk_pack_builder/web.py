from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .adapters import adapter_for
from .analyzer import analyze_pack
from .builder import build_pack
from .character_clone import CHARACTER_TABLE_ALIASES, resolve_character_table_name
from .recipe import recipe_from_dict
from .validation import has_errors, messages_to_dicts, validate


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "web"


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), WebHandler)
    print(f"Three Kingdoms Pack Builder UI: http://{host}:{port}", flush=True)
    server.serve_forever()


class WebHandler(BaseHTTPRequestHandler):
    server_version = "TKPackBuilderWeb/0.1"

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._serve_static("index.html")
            return
        if self.path == "/app.css":
            self._serve_static("app.css")
            return
        if self.path == "/app.js":
            self._serve_static("app.js")
            return
        if self.path == "/api/health":
            self._send_json({"ok": True})
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


def open_pack_payload(payload: dict[str, Any]) -> dict[str, Any]:
    session = _open_session(payload)
    try:
        analysis = analyze_pack(session).to_dict()
        character_data = read_character_data(session, include_vanilla=bool(payload.get("includeVanilla")))
        return {"ok": True, "analysis": analysis, "characters": character_data}
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
        messages = build_pack(session, recipe, output_path, in_place=bool(payload.get("inPlace")))
        return {
            "ok": not any(message["level"] == "error" for message in messages),
            "messages": messages,
        }
    finally:
        _close_session(session)


def read_character_data(session: Any, include_vanilla: bool = False) -> dict[str, Any]:
    tables = _read_character_tables(session, "pack")
    loc_text = _read_all_loc_text(session)
    data = {
        "pack": summarize_character_tables(tables, loc_text),
        "vanilla": {"available": False, "error": None, "summary": None},
    }
    if include_vanilla:
        try:
            vanilla_tables = _read_character_tables(session, "vanilla")
            data["vanilla"] = {
                "available": True,
                "error": None,
                "summary": summarize_character_tables(vanilla_tables, loc_text),
            }
        except ValueError as error:
            data["vanilla"] = {"available": False, "error": str(error), "summary": None}
    return data


def summarize_character_tables(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str] | None = None,
) -> dict[str, Any]:
    loc_text = loc_text or {}
    details_by_template: dict[str, list[dict[str, Any]]] = {}
    for row in tables["character_generation_template_game_mode_details"]:
        details_by_template.setdefault(str(row.get("character_generation_template", "")), []).append(row)

    art_rows_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in tables["campaign_character_arts"]:
        art_rows_by_set.setdefault(str(row.get("art_set_id", "")), []).append(row)

    characters = []
    for template in tables["character_generation_templates"]:
        key = str(template.get("key", ""))
        display_name = _character_display_name(template, loc_text)
        characters.append(
            {
                "key": key,
                "displayName": display_name,
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
                "details": sorted(
                    [
                        {
                            "gameMode": detail.get("game_mode", ""),
                            "retinue": detail.get("retinue"),
                            "attributeSet": detail.get("attribute_set"),
                            "skillSet": detail.get("skill_set_override"),
                            "initialCeos": detail.get("initial_ceos"),
                        }
                        for detail in details_by_template.get(key, [])
                    ],
                    key=lambda item: str(item["gameMode"]),
                ),
            }
        )

    return {
        "characters": sorted(characters, key=lambda item: (item["displayName"] or item["key"], item["key"])),
        "artSets": sorted(
            [row.get("art_set_id") for row in tables["campaign_character_art_sets"] if row.get("art_set_id")],
            key=str,
        ),
        "artRowsBySet": {
            key: len(rows)
            for key, rows in sorted(art_rows_by_set.items())
        },
        "ageRanges": sorted(
            [row.get("key") for row in tables["character_generation_spawn_age_ranges"] if row.get("key")],
            key=str,
        ),
        "initialCeos": sorted(
            [row.get("key") for row in tables["ceo_initial_datas"] if row.get("key")],
            key=str,
        ),
    }


def _read_character_tables(session: Any, source: str) -> dict[str, list[dict[str, Any]]]:
    tables = {}
    for alias in CHARACTER_TABLE_ALIASES:
        table_name = resolve_character_table_name(session, alias) if source == "pack" else _resolve_source_table(session, alias, source)
        tables[alias] = session.read_table(table_name, source)
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
    parts = [
        _name_text(template.get("family_name"), loc_text),
        _name_text(template.get("forename"), loc_text),
        _name_text(template.get("other_name"), loc_text),
    ]
    id_text = "".join(part for part in parts if part)
    key_text = _display_name_from_key(str(template.get("key", "")), loc_text)
    if key_text and len(key_text) > len(id_text):
        return key_text
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


def _resolve_source_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in CHARACTER_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    raise ValueError(f"Required character table is missing in {source}: {alias}")


def _open_session(payload: dict[str, Any]) -> Any:
    adapter_name = payload.get("adapter", "mock")
    input_path = payload.get("inputPath")
    if not input_path:
        raise ValueError("inputPath is required.")
    return adapter_for(adapter_name).open_pack(Path(input_path))


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
