from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import time
import hashlib
import traceback
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from .adapters import adapter_for
from .analyzer import analyze_pack
from .builder import build_pack
from .character_clone import CHARACTER_TABLE_ALIASES, resolve_character_table_name
from . import delta_builder as delta_builder_module
from .internal_materials import MaterialPackSession
from .korea_addon import korea_character_metadata
from .korean_names import korean_character_name
from .pack_cache import PackCache
from .recipe import Recipe, recipe_from_dict
from .rpfm_runtime import resolve_rpfm_server
from .stat_tables import TABLE_ALIASES
from .validation import allow_reference_backed_clone_sources, has_errors, messages_to_dicts, validate


ROOT = Path(os.environ.get("TK_PACK_EDITOR_ROOT", Path(__file__).resolve().parents[1])).resolve()
STATIC_ROOT = ROOT / "web"
RPFM_SERVER_CANDIDATES = [
    ROOT / "work" / "rpfm-dist" / "rpfm_server.exe",
    Path("E:/rpfm-v5.0.3-x86_64-pc-windows-msvc/rpfm_server.exe"),
] if os.name == "nt" else [
    ROOT / "work" / "rpfm-master" / "target" / "debug" / "rpfm_server",
]
DEFAULT_RPFM_SERVER = next((path for path in RPFM_SERVER_CANDIDATES if path.is_file()), RPFM_SERVER_CANDIDATES[0])
PACK_CACHE = PackCache(ROOT / "work" / "pack_cache.sqlite3")
REFERENCE_SNAPSHOT = ROOT / "work" / "reference_snapshot.json"
REFERENCE_SNAPSHOT_VERSION = 2
INTERNAL_CHARACTER_CATALOG = ROOT / "work" / "internal_dbs" / "character_catalog.json"
INTERNAL_MATERIALS_PATH = ROOT / "work" / "internal_materials" / "materials.v015.json"
INTERNAL_ASSET_MANIFEST = ROOT / "work" / "internal_materials" / "asset_manifest.v015.json"
INTERNAL_MATERIAL_SUMMARY = ROOT / "work" / "internal_materials" / "materials.v015.summary.json"
EXTRACTED_ASSET_ROOT = ROOT / "work" / "assets"
IMAGE_ONLY_ASSET_PREFIX = "__image_only_reference__"
RPFM_PROCESS: subprocess.Popen[bytes] | None = None
RPFM_LOG_HANDLE: Any | None = None

SKILL_TABLE_ALIASES = {
    "character_skill_node_sets": [
        "character_skill_node_sets",
        "db/character_skill_node_sets_tables/_mtu_characters",
    ],
    "character_skill_nodes": [
        "character_skill_nodes",
        "db/character_skill_nodes_tables/_mtu_characters",
    ],
    "character_skill_node_links": [
        "character_skill_node_links",
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
}

_SKILL_PHRASE_LABELS: dict[str, str] = {}


def _elapsed(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 4)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), WebHandler)
    print(f"Three Kingdoms Pack Builder UI: http://{host}:{port}", flush=True)
    server.serve_forever()


def _log_api_build_error(error: BaseException) -> None:
    log_path = ROOT / "work" / "api-build-error.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] /api/build failed\n")
        handle.write("".join(traceback.format_exception(type(error), error, error.__traceback__)))


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
        if path == "/reference_names.js":
            self._serve_static("reference_names.js")
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
            if self.path == "/api/build":
                _log_api_build_error(error)
            self._send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            if self.path == "/api/build":
                _log_api_build_error(error)
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
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_pack_asset(self, query: dict[str, list[str]]) -> None:
        input_path = query.get("inputPath", [""])[0]
        requested_packed_path = query.get("path", [""])[0]
        if not input_path or not requested_packed_path:
            self.send_error(HTTPStatus.BAD_REQUEST, "inputPath and path are required")
            return
        packed_path = _real_packed_asset_path(requested_packed_path)
        pack_path = _resolve_user_path(input_path)
        extracted = _extracted_asset_path(pack_path, requested_packed_path)
        if extracted.is_file():
            content_type = mimetypes.guess_type(extracted.name)[0] or "application/octet-stream"
            self._send_bytes(extracted.read_bytes(), content_type, cache_hit=True)
            return
        extracted_any = _find_extracted_asset(requested_packed_path) or _find_extracted_asset(packed_path)
        if extracted_any is not None:
            content_type = mimetypes.guess_type(extracted_any.name)[0] or "application/octet-stream"
            self._send_bytes(extracted_any.read_bytes(), content_type, cache_hit=True)
            return
        cached = PACK_CACHE.get_asset(pack_path, packed_path)
        if cached is not None:
            content_type, data = cached
            _write_extracted_asset(extracted, data)
            self._send_bytes(data, content_type, cache_hit=True)
            return

        session = None
        try:
            _ensure_rpfm_server()
            if not pack_path.is_file():
                fallback_pack = _fallback_pack_path(pack_path)
                if fallback_pack is not None:
                    pack_path = fallback_pack
                    extracted = _extracted_asset_path(pack_path, requested_packed_path)
                    if extracted.is_file():
                        content_type = mimetypes.guess_type(extracted.name)[0] or "application/octet-stream"
                        self._send_bytes(extracted.read_bytes(), content_type, cache_hit=True)
                        return
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
        _write_extracted_asset(extracted, data)
        self._send_bytes(data, content_type, cache_hit=False)

    def _send_bytes(self, data: bytes, content_type: str, cache_hit: bool = False) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "private, max-age=3600")
        self.send_header("x-pack-cache", "hit" if cache_hit else "miss")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _extracted_asset_path(pack_path: Path, packed_path: str) -> Path:
    pack_id = hashlib.sha1(str(pack_path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:12]
    clean_parts = [
        part
        for part in packed_path.replace("\\", "/").split("/")
        if part and part not in {".", ".."}
    ]
    return EXTRACTED_ASSET_ROOT / pack_id / Path(*clean_parts)


def _source_scoped_asset_path(source_path: Path, packed_path: str) -> str:
    source_id = hashlib.sha1(str(source_path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:12]
    normalized = packed_path.replace("\\", "/")
    return f"{IMAGE_ONLY_ASSET_PREFIX}/{source_id}/{normalized}"


def _real_packed_asset_path(packed_path: str) -> str:
    normalized = packed_path.replace("\\", "/")
    prefix = f"{IMAGE_ONLY_ASSET_PREFIX}/"
    if not normalized.startswith(prefix):
        return normalized
    parts = normalized.split("/", 2)
    return parts[2] if len(parts) >= 3 else normalized


def _write_extracted_asset(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.stat().st_size != len(data):
        path.write_bytes(data)


def _find_extracted_asset(packed_path: str) -> Path | None:
    clean_parts = [
        part
        for part in packed_path.replace("\\", "/").split("/")
        if part and part not in {".", ".."}
    ]
    if not clean_parts or not EXTRACTED_ASSET_ROOT.is_dir():
        return None
    suffix = Path(*clean_parts)
    for pack_dir in EXTRACTED_ASSET_ROOT.iterdir():
        candidate = pack_dir / suffix
        if candidate.is_file():
            return candidate
    return None


def _fallback_pack_path(pack_path: Path) -> Path | None:
    candidates = [
        ROOT / "work" / "packs" / pack_path.name,
        ROOT / "work" / "packs" / "refs" / pack_path.name,
        ROOT / "work" / "packs" / "my_hero.pack",
    ]
    return next((path for path in candidates if path.is_file()), None)


def open_pack_payload(payload: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    timings: dict[str, float] = {}
    input_path = payload.get("inputPath")
    include_vanilla = bool(payload.get("includeVanilla"))
    reference_paths = _reference_pack_paths(payload)
    if not input_path:
        raise ValueError("inputPath is required.")
    pack_path = _resolve_user_path(input_path)
    if not payload.get("forceRefresh"):
        cache_started = time.perf_counter()
        cached = PACK_CACHE.get_open_payload(pack_path, include_vanilla, reference_paths) if pack_path.exists() else None
        timings["cacheLookup"] = _elapsed(cache_started)
        if cached is not None:
            _enrich_korea_addon_character_data(cached.get("characters", {}))
            cached["timings"] = {**timings, "total": _elapsed(started_at)}
            return cached
        snapshot_started = time.perf_counter()
        snapshot = _load_reference_snapshot()
        timings["snapshotLookup"] = _elapsed(snapshot_started)
        if snapshot is not None:
            _enrich_korea_addon_character_data(snapshot.get("characters", {}))
            snapshot["timings"] = {**timings, "total": _elapsed(started_at)}
            return snapshot

    open_started = time.perf_counter()
    session = _open_session(payload)
    timings["openSession"] = _elapsed(open_started)
    try:
        analyze_started = time.perf_counter()
        analysis = analyze_pack(session).to_dict()
        timings["analyze"] = _elapsed(analyze_started)
        read_started = time.perf_counter()
        character_data = read_character_data(
            session,
            include_vanilla=include_vanilla,
            reference_paths=reference_paths,
            adapter_name=payload.get("adapter", "auto"),
        )
        timings["readCharacterData"] = _elapsed(read_started)
        cache_write_started = time.perf_counter()
        PACK_CACHE.put_open_payload(pack_path, include_vanilla, analysis, character_data, reference_paths)
        _write_reference_snapshot(analysis, character_data)
        timings["cacheWrite"] = _elapsed(cache_write_started)
        timings["total"] = _elapsed(started_at)
        return {
            "ok": True,
            "analysis": analysis,
            "characters": character_data,
            "cache": {
                "hit": False,
                "path": str(PACK_CACHE.db_path),
            },
            "timings": timings,
        }
    finally:
        _close_session(session)


def _load_reference_snapshot() -> dict[str, Any] | None:
    if not REFERENCE_SNAPSHOT.is_file():
        return None
    with REFERENCE_SNAPSHOT.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schemaVersion") != REFERENCE_SNAPSHOT_VERSION:
        return None
    return {
        "ok": True,
        "analysis": payload.get("analysis", {}),
        "characters": payload.get("characters", {}),
        "cache": {
            "hit": True,
            "type": "reference_snapshot",
            "path": str(REFERENCE_SNAPSHOT),
        },
    }


def _enrich_korea_addon_character_data(character_data: dict[str, Any]) -> None:
    _merge_internal_material_character_summary(character_data)
    _merge_auxiliary_catalog_characters(character_data)
    for summary in _iter_character_summaries(character_data):
        for character in summary.get("characters", []):
            if not isinstance(character, dict):
                continue
            metadata = korea_character_metadata(str(character.get("key", ""))) or {}
            if not metadata:
                continue
            character.update(metadata)
            if metadata.get("koreaDisplayNameHint"):
                display_name = str(metadata["koreaDisplayNameHint"])
                character["displayName"] = display_name
                character["label"] = display_name


def _merge_internal_material_character_summary(character_data: dict[str, Any]) -> None:
    target_summary = character_data.get("pack")
    if not isinstance(target_summary, dict) or not INTERNAL_MATERIALS_PATH.is_file():
        return
    try:
        internal_summary = _load_internal_material_summary()
    except Exception:
        return

    target_characters = target_summary.setdefault("characters", [])
    if not isinstance(target_characters, list):
        return
    target_by_key = {
        str(character.get("key", "")).lower(): character
        for character in target_characters
        if isinstance(character, dict)
    }
    for character in internal_summary.get("characters", []):
        if not isinstance(character, dict):
            continue
        key = str(character.get("key", "")).lower()
        if not key:
            continue
        if key in target_by_key:
            target_by_key[key].update(character)
        else:
            target_characters.append(character)
            target_by_key[key] = character
    target_summary["characters"] = _dedupe_characters_by_key(target_characters)
    _merge_summary_supporting_rows(target_summary, internal_summary)


@lru_cache(maxsize=1)
def _load_internal_material_summary() -> dict[str, Any]:
    cached = _read_internal_material_summary_cache()
    if cached is not None:
        return cached

    session = MaterialPackSession.open(INTERNAL_MATERIALS_PATH)
    tables = _read_internal_material_reference_tables(session)
    asset_files = session.list_files()
    asset_sources: dict[str, str] = {}
    known_assets = set(asset_files)
    _merge_internal_asset_manifest(asset_files, asset_sources, known_assets)
    _merge_extracted_asset_inventory(asset_files, asset_sources, known_assets)
    summary = summarize_character_tables(tables, _read_all_loc_text(session), asset_files, asset_sources)
    _write_internal_material_summary_cache(summary)
    return summary


def _internal_material_cache_token() -> dict[str, Any]:
    paths = [INTERNAL_MATERIALS_PATH, INTERNAL_ASSET_MANIFEST]
    return {
        "version": 6,
        "sources": {
            str(path): path.stat().st_mtime
            for path in paths
            if path.is_file()
        },
    }


def _read_internal_material_summary_cache() -> dict[str, Any] | None:
    if not INTERNAL_MATERIAL_SUMMARY.is_file():
        return None
    try:
        with INTERNAL_MATERIAL_SUMMARY.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("cache") != _internal_material_cache_token():
        return None
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else None


def _write_internal_material_summary_cache(summary: dict[str, Any]) -> None:
    try:
        INTERNAL_MATERIAL_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        with INTERNAL_MATERIAL_SUMMARY.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "cache": _internal_material_cache_token(),
                    "summary": summary,
                },
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
    except OSError:
        return


def _iter_character_summaries(character_data: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    pack_summary = character_data.get("pack")
    if isinstance(pack_summary, dict):
        summaries.append(pack_summary)
    vanilla = character_data.get("vanilla", {})
    vanilla_summary = vanilla.get("summary") if isinstance(vanilla, dict) else None
    if isinstance(vanilla_summary, dict):
        summaries.append(vanilla_summary)
    for report in character_data.get("referencePacks", []):
        if isinstance(report, dict) and isinstance(report.get("summary"), dict):
            summaries.append(report["summary"])
    return summaries


def _merge_auxiliary_catalog_characters(character_data: dict[str, Any]) -> None:
    # AW image-only packs do not contain the full in-game composite portrait set,
    # so keep them out of the editor catalog instead of offering broken choices.
    return


@lru_cache(maxsize=1)
def _load_internal_character_catalog_pack() -> dict[str, Any] | None:
    if not INTERNAL_CHARACTER_CATALOG.is_file():
        return None
    try:
        with INTERNAL_CHARACTER_CATALOG.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    summary = payload.get("characters", {}).get("pack")
    return summary if isinstance(summary, dict) else None


def _is_aw_image_only_character(character: dict[str, Any]) -> bool:
    if not (character.get("virtualImageOnly") or character.get("imageOnly")):
        return False
    text = " ".join(
        str(character.get(field, ""))
        for field in [
            "sourceTag",
            "referenceSourcePath",
            "portraitImageSourcePath",
            "cardImageSourcePath",
            "portraitImagePath",
            "cardImagePath",
            "sourcePackName",
            "sourceIdentity",
            "key",
        ]
    ).lower()
    return any(token in text for token in ["aw-design", "aw addon", "aw_", "aw-"])


def _dedupe_characters_by_key(characters: list[Any]) -> list[Any]:
    by_key: dict[str, dict[str, Any]] = {}
    key_order: list[str] = []
    passthrough: list[Any] = []
    for character in characters:
        if not isinstance(character, dict):
            passthrough.append(character)
            continue
        key = str(character.get("key", "")).lower()
        if not key:
            passthrough.append(character)
            continue
        if key not in by_key:
            key_order.append(key)
        by_key[key] = character
    return passthrough + [by_key[key] for key in key_order]


def _merge_summary_supporting_rows(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in [
        "artSets",
        "ageRanges",
        "initialCeos",
        "retinues",
        "attributeSets",
        "skillSets",
        "subtypes",
        "landUnits",
        "mainUnits",
        "retinueSlotInitialUnits",
    ]:
        _merge_list_by_key(target, source, field)
    for field in ["artRowsBySet", "attributeStatsBySet", "skillTrees", "locKeys"]:
        target_dict = target.setdefault(field, {})
        source_dict = source.get(field, {})
        if isinstance(target_dict, dict) and isinstance(source_dict, dict):
            for key, value in source_dict.items():
                target_dict.setdefault(key, value)


def _merge_list_by_key(target: dict[str, Any], source: dict[str, Any], field: str) -> None:
    target_rows = target.setdefault(field, [])
    source_rows = source.get(field, [])
    if not isinstance(target_rows, list) or not isinstance(source_rows, list):
        return
    existing = {_row_identity(row) for row in target_rows if isinstance(row, dict)}
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        identity = _row_identity(row)
        if not identity or identity in existing:
            continue
        target_rows.append(row)
        existing.add(identity)


def _row_identity(row: dict[str, Any]) -> str:
    for field in [
        "key",
        "artSet",
        "art_set_id",
        "ageRange",
        "initialCeo",
        "ceoNodeKey",
        "retinue",
        "attributeSet",
        "skillSet",
        "subtype",
        "landUnitKey",
        "mainUnitKey",
    ]:
        value = row.get(field)
        if value:
            return str(value)
    return ""


def _write_reference_snapshot(analysis: dict[str, Any], characters: dict[str, Any]) -> None:
    REFERENCE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": REFERENCE_SNAPSHOT_VERSION,
        "createdAt": time.time(),
        "analysis": analysis,
        "characters": characters,
    }
    with REFERENCE_SNAPSHOT.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("useInternalMaterials"):
        material_path = _resolve_user_path(payload.get("materialPath") or "")
        session = MaterialPackSession.open(material_path)
        try:
            recipe = recipe_from_dict(payload.get("recipe", {}))
            messages = validate(session, recipe, payload.get("outputPath"))
            return {"ok": not has_errors(messages), "messages": messages_to_dicts(messages)}
        finally:
            _close_session(session)
    session = _open_session(payload)
    try:
        recipe = recipe_from_dict(payload.get("recipe", {}))
        messages = validate(session, recipe, payload.get("outputPath"))
        if _reference_pack_paths(payload):
            messages = allow_reference_backed_clone_sources(messages)
        return {"ok": not has_errors(messages), "messages": messages_to_dicts(messages)}
    finally:
        _close_session(session)


def _build_response(messages: list[dict[str, Any]], output_path: Path | None = None) -> dict[str, Any]:
    has_error = any(message.get("level") == "error" for message in messages)
    if not has_error:
        detail = f"경로: {output_path}" if output_path is not None else ""
        messages = [{"level": "success", "code": "pack_written", "message": "팩 생성 완료", "detail": detail}]
    return {
        "ok": not has_error,
        "messages": messages or [{"level": "success", "code": "pack_written", "message": "팩 생성 완료"}],
    }


def build_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("useInternalMaterials"):
        if not payload.get("delta"):
            raise ValueError("Internal materials build is only available for patch pack output.")
        recipe = recipe_from_dict(payload.get("recipe", {}))
        output_path = _resolve_user_path(payload["outputPath"]) if payload.get("outputPath") else None
        if output_path is None:
            raise ValueError("Patch pack output path is required.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        material_path = _resolve_user_path(payload.get("materialPath") or "")
        source_session = MaterialPackSession.open(material_path)
        writer_session = _open_session(payload)
        previous_core = delta_builder_module.CORE_ASSET_SOURCE_ID
        if payload.get("coreAssetSourceId"):
            delta_builder_module.CORE_ASSET_SOURCE_ID = str(payload["coreAssetSourceId"])
        try:
            build_messages = delta_builder_module.build_delta_pack_from_materials(
                source_session,
                writer_session,
                recipe,
                output_path,
                _reference_pack_paths(payload),
            )
        finally:
            delta_builder_module.CORE_ASSET_SOURCE_ID = previous_core
            _close_session(writer_session)
            _close_session(source_session)
        verify_messages = _verify_saved_pack_image_chain(output_path, recipe) if payload.get("verifyAfterSave") else []
        return _build_response([*build_messages, *verify_messages], output_path)
        return {
            "ok": True,
            "messages": [{"level": "success", "code": "pack_written", "message": "팩 생성 완료"}],
        }
    session = _open_session(payload)
    try:
        recipe = recipe_from_dict(payload.get("recipe", {}))
        output_path = _resolve_user_path(payload["outputPath"]) if payload.get("outputPath") else None
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        build_messages = build_pack(
            session,
            recipe,
            output_path,
            in_place=bool(payload.get("inPlace")),
            delta=bool(payload.get("delta")),
            reference_paths=_reference_pack_paths(payload),
        )
        target_path = Path(payload["inputPath"]) if payload.get("inPlace") else output_path
        verify_messages = _verify_saved_pack_image_chain(target_path, recipe) if target_path and payload.get("verifyAfterSave") else []
        return _build_response([*build_messages, *verify_messages], target_path)
        return {
            "ok": True,
            "messages": [{"level": "success", "code": "pack_written", "message": "팩 생성 완료"}],
        }
    finally:
        _close_session(session)


def _verify_saved_pack_image_chain(pack_path: Path | None, recipe: Recipe) -> list[dict[str, Any]]:
    if pack_path is None or not pack_path.exists():
        return []
    expectations = _image_chain_expectations(recipe)
    if not expectations:
        return []

    session = adapter_for("rpfm").open_pack(pack_path)
    try:
        files = {path.replace("\\", "/") for path in session.list_files()}
        table_paths = set(session.list_tables())
    finally:
        _close_session(session)

    messages: list[dict[str, Any]] = []
    for expected in expectations:
        label = expected["label"]
        owner = expected["owner"]
        for table_kind, table_prefix in (
            ("장수 템플릿", "db/character_generation_templates_tables/"),
            ("아트셋", "db/campaign_character_art_sets_tables/"),
            ("이미지 연결", "db/campaign_character_arts_tables/"),
        ):
            if not any(path.startswith(table_prefix) for path in table_paths):
                messages.append({
                    "level": "error",
                    "code": "missing_image_chain_table",
                    "message": f"{label} 이미지의 {table_kind} DB가 누락되었습니다.",
                    "detail": f"owner={owner}, table={table_prefix}",
                })
                break
        for path in sorted(expected["paths"]):
            if path not in files:
                slot = _image_slot_label(path)
                messages.append({
                    "level": "error",
                    "code": "missing_image_asset",
                    "message": f"{label} 이미지의 {slot}가 누락되었습니다.",
                    "detail": path,
                })
    if messages:
        return messages
    return [{
        "level": "success",
        "code": "image_chain_verified",
        "message": f"이미지 체인 검증 완료: {len(expectations)}명",
    }]


def _image_chain_expectations(recipe: Recipe) -> list[dict[str, Any]]:
    title_by_owner = _recipe_work_title_by_owner(recipe)
    items: list[dict[str, Any]] = []
    for patch in recipe.character_patches:
        paths = _expected_image_paths(patch.art_overrides or {}, patch.image_assets or [])
        if paths:
            owner = patch.template_key
            items.append({
                "owner": owner,
                "label": _display_label(title_by_owner.get(owner) or patch.display_name or owner),
                "paths": paths,
            })
    for clone in recipe.character_clones:
        paths = _expected_image_paths(clone.art_overrides or {}, clone.image_assets or [])
        if paths:
            owner = clone.new_template_key
            items.append({
                "owner": owner,
                "label": _display_label(title_by_owner.get(owner) or clone.display_name or owner),
                "paths": paths,
            })
    return items


def _expected_image_paths(art_overrides: dict[str, Any], image_assets: list[dict[str, str]]) -> set[str]:
    paths = {
        _normalize_pack_asset_path(asset.get("targetPath") or asset.get("path") or "")
        for asset in image_assets
    }
    paths.discard("")
    portrait = str(art_overrides.get("portrait") or "").replace("\\", "/").strip("/")
    card = str(art_overrides.get("card") or "").replace("\\", "/").strip("/")
    token = portrait or card
    if token:
        card = card or token
        paths.update({
            f"ui/characters/{token}/composites/noanim.png",
            f"ui/characters/{token}/composites/large_panel/norm/noanim.png",
            f"ui/characters/{token}/composites/small_panel/norm/noanim.png",
            f"ui/characters/{token}/stills/halfbody_large/{card}.png",
            f"ui/characters/{token}/stills/halfbody_small/{card}.png",
            f"ui/characters/{token}/stills/bobbleheads/{card}.png",
            f"ui/characters/{token}/stills/unitcards/{card}.png",
        })
    return paths


def _normalize_pack_asset_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip("/")


def _image_slot_label(path: str) -> str:
    lower = path.lower()
    if "/stills/unitcards/" in lower:
        return "unitcard"
    if "/stills/halfbody_large/" in lower:
        return "halfbody_large"
    if "/stills/halfbody_small/" in lower:
        return "halfbody_small"
    if "/composites/large_panel/" in lower:
        return "large_panel"
    if "/composites/small_panel/" in lower:
        return "small_panel"
    if "/composites/" in lower:
        return "composite"
    return "이미지 파일"


def _recipe_work_title_by_owner(recipe: Recipe) -> dict[str, str]:
    titles: dict[str, str] = {}
    for work in recipe.work_items or []:
        title = str(work.get("title") or "").strip()
        if not title:
            continue
        work_recipe = work.get("recipe") or {}
        for patch in work_recipe.get("characterPatches", []) or []:
            key = patch.get("templateKey")
            if key:
                titles[str(key)] = title
        for clone in work_recipe.get("characterCloneRecipes", []) or []:
            key = clone.get("newTemplateKey")
            if key:
                titles[str(key)] = title
    return titles


def _display_label(value: str) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+(수정|생성)$", "", text) or "선택한 장수"


def read_character_data(
    session: Any,
    include_vanilla: bool = False,
    reference_paths: list[Path] | None = None,
    adapter_name: str = "mock",
) -> dict[str, Any]:
    timings: dict[str, Any] = {}
    started = time.perf_counter()
    step = time.perf_counter()
    tables = _read_character_tables(session, "pack")
    timings["readTables"] = _elapsed(step)
    step = time.perf_counter()
    loc_text = _read_all_loc_text(session)
    timings["readLoc"] = _elapsed(step)
    step = time.perf_counter()
    asset_files = session.list_files()
    timings["listPrimaryFiles"] = _elapsed(step)
    asset_sources: dict[str, str] = {}
    step = time.perf_counter()
    reference_report = _merge_reference_packs(
        tables,
        loc_text,
        asset_files,
        asset_sources,
        reference_paths or [],
        adapter_name,
        session.pack_path,
    )
    internal_report = _merge_internal_materials(tables, loc_text, asset_files, asset_sources)
    if internal_report:
        reference_report.append(internal_report)
    timings["mergeReferences"] = _elapsed(step)
    step = time.perf_counter()
    pack_summary = summarize_character_tables(tables, loc_text, asset_files, asset_sources)
    timings["summarizePack"] = _elapsed(step)
    timings["total"] = _elapsed(started)
    data = {
        "pack": pack_summary,
        "vanilla": {"available": False, "error": None, "summary": None},
        "referencePacks": reference_report,
        "timings": timings,
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
    asset_index = _build_asset_index(asset_files)
    details_by_template: dict[str, list[dict[str, Any]]] = {}
    for row in tables["character_generation_template_game_mode_details"]:
        details_by_template.setdefault(str(row.get("character_generation_template", "")), []).append(row)

    art_rows_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in tables["campaign_character_arts"]:
        art_rows_by_set.setdefault(str(row.get("art_set_id", "")), []).append(row)
    external_art_set_ids = {
        str(row.get("art_set_id", ""))
        for row in tables["campaign_character_arts"]
        if row.get("art_set_id") and _is_bfg_reference(str(row.get("_referenceSourcePath") or row.get("_externalImageSetSourcePath") or ""))
    }

    art_sets = []
    known_art_set_ids: set[str] = set()
    for row in tables["campaign_character_art_sets"]:
        art_set_id = row.get("art_set_id")
        if not art_set_id:
            continue
        known_art_set_ids.add(str(art_set_id))
        art_rows = art_rows_by_set.get(str(art_set_id), [])
        primary_art = _primary_art_row(art_rows)
        art_set_label = _friendly_art_set_label(str(art_set_id), loc_text)
        reference_source = str(
            row.get("_referenceSourcePath")
            or row.get("_externalImageSetSourcePath")
            or primary_art.get("_referenceSourcePath")
            or primary_art.get("_externalImageSetSourcePath")
            or ""
        )
        external_image_set = _is_bfg_reference(reference_source) or str(art_set_id) in external_art_set_ids
        if external_image_set and not reference_source:
            reference_source = "BFG_Astral.pack"
        portrait_path = str(primary_art.get("portrait") or "").strip("/")
        card_path = str(primary_art.get("card") or "").strip("/")
        portrait_image_path = _find_character_image(asset_index, portrait_path, "halfbody_large")
        card_image_path = _find_character_image(asset_index, card_path, "unitcards")
        if _is_image_only_reference(asset_sources.get(portrait_image_path or "", "")):
            portrait_image_path = None
        if _is_image_only_reference(asset_sources.get(card_image_path or "", "")):
            card_image_path = None
        image_assets = [] if external_image_set else _non_image_only_reference_assets(
            _character_image_assets(asset_index, asset_sources, portrait_path, card_path)
        )
        art_sets.append(
            {
                "key": art_set_id,
                "label": art_set_label,
                "rowCount": len(art_rows),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "uniformLabel": _friendly_model_set_label(primary_art.get("uniform"), art_set_label),
                "isMale": row.get("is_male"),
                "referenceSourcePath": reference_source,
                "externalImageSet": external_image_set,
                "portraitImagePath": portrait_image_path,
                "portraitImageSourcePath": asset_sources.get(portrait_image_path or ""),
                "cardImagePath": card_image_path,
                "cardImageSourcePath": asset_sources.get(card_image_path or ""),
                "imageAssets": image_assets,
                "rows": art_rows,
            }
        )
    for art_set_id, art_rows in sorted(art_rows_by_set.items()):
        if not art_set_id or art_set_id in known_art_set_ids:
            continue
        primary_art = _primary_art_row(art_rows)
        art_set_label = _friendly_art_set_label(str(art_set_id), loc_text)
        reference_source = str(primary_art.get("_referenceSourcePath") or primary_art.get("_externalImageSetSourcePath") or "")
        external_image_set = _is_bfg_reference(reference_source) or str(art_set_id) in external_art_set_ids
        if external_image_set and not reference_source:
            reference_source = "BFG_Astral.pack"
        portrait_path = str(primary_art.get("portrait") or "").strip("/")
        card_path = str(primary_art.get("card") or "").strip("/")
        portrait_image_path = _find_character_image(asset_index, portrait_path, "halfbody_large")
        card_image_path = _find_character_image(asset_index, card_path, "unitcards")
        if _is_image_only_reference(asset_sources.get(portrait_image_path or "", "")):
            portrait_image_path = None
        if _is_image_only_reference(asset_sources.get(card_image_path or "", "")):
            card_image_path = None
        image_assets = [] if external_image_set else _non_image_only_reference_assets(
            _character_image_assets(asset_index, asset_sources, portrait_path, card_path)
        )
        art_sets.append(
            {
                "key": art_set_id,
                "label": art_set_label,
                "rowCount": len(art_rows),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "uniformLabel": _friendly_model_set_label(primary_art.get("uniform"), art_set_label),
                "isMale": next((row.get("is_male") for row in tables["campaign_character_art_sets"] if row.get("art_set_id") == art_set_id), None),
                "referenceSourcePath": reference_source,
                "virtual": True,
                "externalImageSet": external_image_set,
                "portraitImagePath": portrait_image_path,
                "portraitImageSourcePath": asset_sources.get(portrait_image_path or ""),
                "cardImagePath": card_image_path,
                "cardImageSourcePath": asset_sources.get(card_image_path or ""),
                "imageAssets": image_assets,
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
    attribute_stats_by_set = _attribute_stats_by_set(tables)
    land_units = {str(row.get("key")): row for row in tables.get("land_units", []) if row.get("key")}

    characters = []
    for template in tables["character_generation_templates"]:
        key = str(template.get("key", ""))
        korea_metadata = korea_character_metadata(key) or {}
        reference_source = template.get("_referenceSourcePath")
        display_name = _character_display_name(template, loc_text)
        if korea_metadata.get("koreaDisplayNameHint"):
            display_name = str(korea_metadata["koreaDisplayNameHint"])
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
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "isMale": template.get("is_male"),
                "voiceoverActor": template.get("voiceover_actor"),
                "portraitImagePath": art_set_summary.get("portraitImagePath"),
                "portraitImageSourcePath": art_set_summary.get("portraitImageSourcePath"),
                "cardImagePath": art_set_summary.get("cardImagePath"),
                "cardImageSourcePath": art_set_summary.get("cardImageSourcePath"),
                "imageAssets": art_set_summary.get("imageAssets", []),
                "combatStats": combat_stats,
                "attributeStats": _attribute_stats_for_details(details, attribute_stats_by_set),
                "titleInfo": title_info,
                "templateRow": template,
                "details": details,
                "source": "reference" if reference_source else "pack",
                "referenceSourcePath": reference_source,
                **korea_metadata,
            }
        )

    _append_image_only_characters(characters, art_sets, asset_index, asset_sources)
    detail_rows = tables["character_generation_template_game_mode_details"]
    skill_trees = _summarize_skill_trees(tables, loc_text, characters)
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
        "attributeStatsBySet": attribute_stats_by_set,
        "skillSets": _unique_options(row.get("skill_set_override") for row in detail_rows),
        "skillTrees": skill_trees,
        "subtypes": _unique_options(row.get("subtype") for row in tables["character_generation_templates"]),
        "locKeys": sorted(loc_text.keys()),
    }


def _append_image_only_characters(
    characters: list[dict[str, Any]],
    art_sets: list[dict[str, Any]],
    asset_index: dict[str, Any],
    asset_sources: dict[str, str],
) -> None:
    existing_image_paths = {
        str(character.get("portraitImagePath") or "").lower()
        for character in characters
        if character.get("portraitImagePath")
    }
    existing_character_keys = {str(character.get("key") or "") for character in characters}
    existing_art_keys = {str(art_set.get("key") or "") for art_set in art_sets}
    image_paths = sorted(
        [
            path for path in asset_index.get("files", [])
            if "/stills/halfbody_large/" in path.lower()
            and path.lower().endswith(".png")
            and "/large/" not in path.lower()
            and "/" not in path.lower().split("/stills/halfbody_large/", 1)[1]
        ],
        key=lambda path: (
            0 if Path(path).stem.lower() == path.lower().split("/stills/halfbody_large/", 1)[0].rsplit("/", 1)[-1] else 1,
            path.lower(),
        ),
    )
    seen_image_folders: set[str] = set()
    for path in image_paths:
        real_path = _real_packed_asset_path(path)
        lower = real_path.lower()
        marker = "/stills/halfbody_large/"
        if lower in existing_image_paths:
            if not _is_image_only_reference(asset_sources.get(path, "")):
                continue
        if _is_non_character_image_path(real_path.lower()):
            continue
        folder = real_path[: lower.index(marker)]
        folder_key = folder.lower()
        source_path = asset_sources.get(path, "")
        source_folder_key = f"{source_path}|{folder_key}"
        if source_folder_key in seen_image_folders:
            continue
        seen_image_folders.add(source_folder_key)
        image_key = folder.removeprefix("ui/characters/").strip("/")
        if not image_key:
            continue
        card_path = _find_character_image(asset_index, image_key, "unitcards")
        label = _friendly_image_character_label(_image_label_key(image_key, real_path))
        source_slug = _image_only_source_slug(source_path)
        art_key = f"image_only_{source_slug}_{image_key}".replace("/", "_")
        image_assets = _character_image_assets(asset_index, asset_sources, image_key, image_key)
        if art_key not in existing_art_keys:
            art_sets.append({
                "key": art_key,
                "label": label,
                "rowCount": 0,
                "portrait": image_key,
                "card": image_key,
                "uniform": "",
                "uniformLabel": "紐⑤뜽 ?놁쓬",
                "referenceSourcePath": source_path,
                "virtual": True,
                "imageOnly": True,
                "externalImageSet": False,
                "portraitImagePath": path,
                "portraitImageSourcePath": source_path,
                "cardImagePath": card_path,
                "cardImageSourcePath": asset_sources.get(card_path or ""),
                "imageAssets": image_assets,
                "rows": [],
                "sourcePackName": Path(source_path).name if source_path else "",
                "sourceIdentity": _image_only_source_identity(source_path, image_key, card_path),
            })
            existing_art_keys.add(art_key)
        character_key = f"image_only_{source_slug}_{image_key}".replace("/", "_")
        if character_key in existing_character_keys:
            character_key = f"{character_key}_{hashlib.sha1(path.encode('utf-8')).hexdigest()[:8]}".replace("/", "_")
        characters.append({
            "key": character_key,
            "displayName": label,
            "label": label,
            "forename": label,
            "familyName": "",
            "clanName": "",
            "subtype": "",
            "weight": 100,
            "artSet": art_key,
            "ageRange": "",
            "minSpawnRound": 0,
            "maxSpawnRound": 999,
            "voiceoverActor": "",
            "portrait": image_key,
            "card": image_key,
            "uniform": "",
            "uniformLabel": "紐⑤뜽 ?놁쓬",
            "details": [],
            "combatStats": {},
            "attributeStats": {},
            "titleInfo": {},
            "templateRow": {},
            "source": "reference",
            "referenceSourcePath": source_path,
            "virtualImageOnly": True,
            "portraitImagePath": path,
            "portraitImageSourcePath": source_path,
            "cardImagePath": card_path,
            "cardImageSourcePath": asset_sources.get(card_path or ""),
            "imageAssets": image_assets,
            "sourcePackName": Path(source_path).name if source_path else "",
            "sourceIdentity": _image_only_source_identity(source_path, image_key, card_path),
        })
        existing_image_paths.add(lower)
        existing_character_keys.add(character_key)


def _image_only_source_slug(source_path: str) -> str:
    name = Path(source_path).stem if source_path else "unknown"
    slug = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:8]
    return f"{slug or 'unknown'}_{digest}"


def _image_only_source_identity(source_path: str, portrait_key: str, card_path: str | None) -> str:
    source_name = Path(source_path).name if source_path else "unknown"
    card_key = ""
    if card_path:
        normalized = card_path.replace("\\", "/")
        marker = "/unitcards/"
        if marker in normalized:
            card_key = normalized.split(marker, 1)[1].rsplit("/", 1)[0]
    parts = [source_name, portrait_key]
    if card_key and card_key != portrait_key:
        parts.append(card_key)
    return " 쨌 ".join(part for part in parts if part)


def _non_image_only_reference_assets(assets: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        asset for asset in assets
        if not _is_image_only_reference(asset.get("sourcePath", ""))
    ]


def _is_non_character_image_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if re.search(r"(^|[_\-/])(?:\d{1,2}yo|baby|child|children|kid|kids|infant|toddler)(?:[_\-/]|$)", normalized):
        return True
    child_tokens = {"baby", "child", "children", "kid", "kids", "infant", "toddler"}
    non_character_tokens = {
        "ancillary",
        "ancillaries",
        "armour",
        "armor",
        "weapon",
        "weapons",
        "mount",
        "mounts",
        "horse",
        "horses",
        "accessory",
        "accessories",
        "aura",
        "banner",
        "banners",
        "common",
        "face",
        "faces",
        "generic",
        "prop",
        "props",
        "shared",
        "ui_composite_scene",
    }
    return any(
        part in child_tokens
        or bool(child_tokens.intersection(part.replace("-", "_").split("_")))
        or bool(non_character_tokens.intersection(part.replace("-", "_").split("_")))
        or part.startswith(("baby_", "child_", "kid_", "infant_", "toddler_"))
        or part.endswith(("_baby", "_child", "_kid", "_infant", "_toddler"))
        for part in parts
    )


def _friendly_image_character_label(image_key: str) -> str:
    lower = image_key.lower()
    known = {
        "diao_chan": "珥덉꽑",
        "lu_bu": "?ы룷",
    }
    for token, label in known.items():
        if token in lower:
            return label
    label = _friendly_character_label(image_key)
    for prefix in ("lb special ", "special "):
        if label.startswith(prefix):
            label = label[len(prefix):]
    return label


def _image_label_key(image_key: str, image_path: str) -> str:
    normalized = image_key.replace("\\", "/").strip("/")
    lower = normalized.lower()
    stem = Path(image_path).stem
    folder_leaf = normalized.rsplit("/", 1)[-1] if normalized else ""
    generic_folder_tokens = (
        "add_unique",
        "artsets",
        "generic_arts",
        "composites",
        "faces",
        "baby",
    )
    if "/" in normalized or any(token in lower for token in generic_folder_tokens):
        return stem
    if stem and stem.lower() != folder_leaf.lower() and stem.lower().startswith(("3k_", "sad_", "mod_")):
        return stem
    return image_key


def _summarize_skill_trees(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
    characters: list[dict[str, Any]],
) -> dict[str, Any]:
    node_sets = {str(row.get("key")): row for row in tables.get("character_skill_node_sets", []) if row.get("key")}
    nodes_by_set: dict[str, list[dict[str, Any]]] = {}
    node_by_key: dict[str, dict[str, Any]] = {}
    for row in tables.get("character_skill_nodes", []):
        set_key = str(row.get("character_skill_node_set_key") or "")
        key = str(row.get("key") or "")
        if not set_key or not key:
            continue
        nodes_by_set.setdefault(set_key, []).append(row)
        node_by_key[key] = row

    links_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in tables.get("character_skill_node_links", []):
        parent = str(row.get("parent_key") or "")
        child = str(row.get("child_key") or "")
        node = node_by_key.get(parent) or node_by_key.get(child)
        set_key = str(node.get("character_skill_node_set_key") or "") if node else ""
        if set_key:
            links_by_set.setdefault(set_key, []).append(row)

    effects_by_skill: dict[str, list[dict[str, Any]]] = {}
    effects = {str(row.get("key")): row for row in tables.get("effects", []) if row.get("key")}
    for row in tables.get("character_skill_level_to_effects_junctions", []):
        skill_key = str(row.get("character_skill_key") or "")
        if not skill_key:
            continue
        effect_key = str(row.get("effect_key") or "")
        effect_row = effects.get(effect_key, {})
        effects_by_skill.setdefault(skill_key, []).append({
            "effectKey": effect_key,
            "name": _effect_label(effect_key, effect_row, loc_text),
            "scope": row.get("effect_scope"),
            "level": row.get("level"),
            "value": row.get("value"),
        })

    owners_by_skill: dict[str, list[dict[str, str]]] = {}
    for character in characters:
        for detail in character.get("details", []):
            if detail.get("gameMode") != "romance":
                continue
            skill_set = str(detail.get("skillSet") or "")
            if not skill_set:
                continue
            owners_by_skill.setdefault(skill_set, []).append({
                "key": str(character.get("key") or ""),
                "name": str(character.get("label") or character.get("displayName") or character.get("key") or ""),
            })

    skill_index: dict[str, dict[str, Any]] = {}
    trees = []
    for set_key, rows in sorted(nodes_by_set.items()):
        owners = owners_by_skill.get(set_key, [])
        if not owners:
            continue
        nodes = []
        for row in rows:
            skill_key = str(row.get("character_skill_key") or "")
            effects_for_skill = effects_by_skill.get(skill_key, [])
            skill_info = skill_index.setdefault(skill_key, _skill_index_entry(skill_key, loc_text, effects_for_skill))
            skill_info["sources"].append({
                "setKey": set_key,
                "nodeKey": str(row.get("key") or ""),
                "owners": owners,
            })
            nodes.append(_skill_node_summary(row, loc_text, effects_for_skill, skill_info))
        trees.append({
            "key": set_key,
            "name": _skill_set_label(set_key, node_sets.get(set_key), loc_text),
            "owners": owners,
            "nodes": sorted(nodes, key=lambda item: (item["position"]["x"], item["position"]["y"], item["key"])),
            "links": [
                {
                    "parent": row.get("parent_key"),
                    "child": row.get("child_key"),
                    "type": row.get("link_type"),
                }
                for row in links_by_set.get(set_key, [])
            ],
        })
    return {
        "romance": trees,
        "nodeCount": sum(len(tree["nodes"]) for tree in trees),
        "skillIndex": dict(sorted(skill_index.items(), key=lambda item: (item[1]["name"], item[0]))),
    }


def _skill_node_summary(
    row: dict[str, Any],
    loc_text: dict[str, str],
    effects: list[dict[str, Any]],
    skill_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = str(row.get("key") or "")
    skill_info = skill_info or {}
    return {
        "key": key,
        "skillKey": row.get("character_skill_key"),
        "setKey": row.get("character_skill_node_set_key"),
        "name": skill_info.get("name") or _skill_node_label(key, row, loc_text),
        "description": skill_info.get("description") or "",
        "icon": row.get("icon") or row.get("icon_path") or row.get("onscreen_name"),
        "position": _skill_node_position(row),
        "tier": _first_present(row, ("tier", "required_level", "level", "min_level")),
        "row": row,
        "effects": effects,
        "effectSummary": _effect_summary(effects),
    }


def _skill_index_entry(skill_key: str, loc_text: dict[str, str], effects: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "key": skill_key,
        "name": _skill_name_for_key(skill_key, loc_text),
        "description": _skill_description_for_key(skill_key, loc_text),
        "effects": effects,
        "effectSummary": _effect_summary(effects),
        "element": _skill_element(skill_key),
        "sources": [],
    }


def _skill_name_for_key(skill_key: str, loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"character_skills_localised_name_{skill_key}",
        f"character_skills_name_{skill_key}",
        f"character_skill_names_{skill_key}",
    ):
        if loc_text.get(loc_key):
            label = loc_text[loc_key]
            if _contains_hangul(label):
                return label
            translated = _friendly_effect_key(label)
            return translated if _contains_hangul(translated) else _translate_skill_name_text(label)
    return _friendly_skill_key(skill_key)


def _skill_description_for_key(skill_key: str, loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"character_skills_localised_description_{skill_key}",
        f"character_skills_description_{skill_key}",
    ):
        if loc_text.get(loc_key):
            return loc_text[loc_key]
    return ""


def _skill_element(skill_key: str) -> str:
    value = skill_key.lower()
    for element in ("earth", "fire", "wood", "water", "metal"):
        if f"_{element}_" in value or value.endswith(f"_{element}"):
            return element
    return ""


def _contains_hangul(value: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in str(value or ""))


def _translate_skill_name_text(value: str) -> str:
    return _friendly_key(str(value or ""))


def _friendly_skill_key(skill_key: str) -> str:
    value = str(skill_key or "")
    replacements = {
        "expertise": "전문성",
        "resolve": "결의",
        "cunning": "책략",
        "instinct": "본능",
        "authority": "권위",
        "mobility": "기동",
        "clarity": "명료",
        "intensity": "열의",
        "flexibility": "유연",
        "dignity": "위엄",
        "meditation": "명상",
        "nobility": "고귀",
        "zeal": "열정",
        "composure": "침착",
        "understanding": "이해",
        "perception": "통찰",
        "stability": "안정",
    }
    for english, korean in replacements.items():
        if english in value.lower():
            return korean
    return _friendly_key(value)


def _skill_node_position(row: dict[str, Any]) -> dict[str, int | float]:
    x = _number_or_none(_first_present(row, ("x", "ui_x", "column", "indent", "position_x", "tree_position_x")))
    y = _number_or_none(_first_present(row, ("y", "ui_y", "row", "tier", "position_y", "tree_position_y")))
    return {"x": x if x is not None else 0, "y": y if y is not None else 0}


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row.get(key) not in {None, ""}:
            return row.get(key)
    return None


def _skill_set_label(key: str, row: dict[str, Any] | None, loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"character_skill_node_sets_name_{key}",
        f"character_skill_node_set_name_{key}",
        f"character_skillsets_name_{key}",
    ):
        if loc_text.get(loc_key):
            return loc_text[loc_key]
    if row:
        for field in ("onscreen_name", "name", "loc_key"):
            value = row.get(field)
            if value and loc_text.get(str(value)):
                return loc_text[str(value)]
            if value:
                return _friendly_key(str(value))
    return _friendly_key(key)


def _skill_node_label(key: str, row: dict[str, Any], loc_text: dict[str, str]) -> str:
    skill_key = str(row.get("character_skill_key") or "")
    for loc_key in (
        f"character_skills_localised_name_{skill_key}",
        f"character_skills_name_{skill_key}",
        f"character_skill_names_{skill_key}",
        f"character_skills_localised_name_{key}",
        f"character_skill_nodes_name_{key}",
        f"character_skill_node_name_{key}",
        f"character_skills_name_{key}",
    ):
        if loc_text.get(loc_key):
            return loc_text[loc_key]
    for field in ("onscreen_name", "name", "loc_key"):
        value = row.get(field)
        if value and loc_text.get(str(value)):
            return loc_text[str(value)]
        if value:
            return _friendly_key(str(value))
    return _friendly_key(key)


def _effect_label(key: str, row: dict[str, Any], loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"effects_description_{key}",
        f"effects_localised_description_{key}",
        f"effects_localised_title_{key}",
        f"effects_name_{key}",
    ):
        if loc_text.get(loc_key):
            label = loc_text[loc_key]
            if _contains_hangul(label):
                return label
            translated = _friendly_effect_key(label)
            return translated if _contains_hangul(translated) else _translate_skill_name_text(label)
    for field in ("description", "onscreen_name", "name", "icon"):
        value = row.get(field)
        if value and loc_text.get(str(value)):
            label = loc_text[str(value)]
            if _contains_hangul(label):
                return label
            translated = _friendly_effect_key(label)
            return translated if _contains_hangul(translated) else _translate_skill_name_text(label)
        if value and field != "icon":
            return _friendly_key(str(value))
    return _friendly_effect_key(key)


def _friendly_effect_key(key: str) -> str:
    value = str(key or "")
    lower = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lower).strip("_")
    normalized = re.sub(r"^(?:3k_(?:main|dlc\d+|mtu)_)?(?:effect|effects|enable|unlock|skill|ability)_", "", normalized)
    if normalized in _SKILL_PHRASE_LABELS:
        return _SKILL_PHRASE_LABELS[normalized]
    for phrase_key, label in _SKILL_PHRASE_LABELS.items():
        if phrase_key in normalized or phrase_key in lower:
            return label
    replacements = {
        "expertise": "???",
        "resolve": "??",
        "cunning": "??",
        "instinct": "??",
        "authority": "??",
        "satisfaction": "???",
        "morale": "??",
        "movement": "????",
        "replenishment": "???",
        "charge": "??",
        "fatigue": "??",
        "ambush": "??",
        "armour": "??",
        "armor": "??",
        "ammo": "??",
        "income": "??",
        "gdp": "??",
        "food": "??",
        "diplomacy": "??",
        "ability": "??",
    }
    for needle, label in replacements.items():
        if needle in lower:
            return label
    return _friendly_key(value)

def _visible_effect_label(effect: dict[str, Any]) -> str:
    key = str(effect.get("effectKey") or "")
    name = str(effect.get("name") or "")
    label = name if name and not name.lower().startswith("effect ") else _friendly_effect_key(key)
    if label and not _contains_hangul(label):
        label = _friendly_effect_key(key)
    lower = f"{key} {label}".lower()
    if "ai_hint" in lower or "ai hint" in lower:
        return ""
    return label.strip()


def _effect_summary(effects: list[dict[str, Any]]) -> str:
    useful_effects = [effect for effect in effects if _visible_effect_label(effect)]
    if not useful_effects:
        return "?? ?? ??"
    pieces = []
    for effect in useful_effects[:4]:
        label = _visible_effect_label(effect)
        value = effect.get("value")
        suffix = f" {value:+g}" if isinstance(value, (int, float)) else f" {value}" if value not in {None, ""} else ""
        pieces.append(f"{label}{suffix}")
    if len(useful_effects) > 4:
        pieces.append(f"? {len(useful_effects) - 4}?")
    return " ? ".join(pieces)


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
                "armourCeo": (armour or {}).get("ceos_key") if armour_row else None,
                "armourStatKey": (armour or {}).get("armour") if armour_row else None,
                "armourAudioType": (armour_row or {}).get("audio_type"),
                "armourFromReference": bool(
                    (armour or {}).get("_referenceSourcePath")
                    or (armour_row or {}).get("_referenceSourcePath")
                ),
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
        "note": "set_title/career CEO? CCD/startpos ???? ??? ?? ?????.",
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
        return "?? ?? ??"
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
    for alias in SKILL_TABLE_ALIASES:
        try:
            table_name = _resolve_skill_table(session, alias, source)
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
        reference_started = time.perf_counter()
        resolved = reference_path.expanduser()
        if _is_aw_reference(resolved):
            report.append({
                "path": str(resolved),
                "ok": False,
                "error": "skipped_aw_image_pack",
                "seconds": _elapsed(reference_started),
            })
            continue
        if _skip_bfg_resource_pack_for_fast_open(resolved):
            report.append({
                "path": str(resolved),
                "ok": False,
                "error": "skipped_bfg_resource_pack",
                "seconds": _elapsed(reference_started),
            })
            continue
        if not resolved.exists():
            report.append({"path": str(resolved), "ok": False, "error": "file_not_found", "seconds": _elapsed(reference_started)})
            continue
        if resolved.resolve() == primary_pack_path.resolve():
            report.append({"path": str(resolved), "ok": False, "error": "same_as_input_pack", "seconds": _elapsed(reference_started)})
            continue
        session = None
        before_counts = {alias: len(rows) for alias, rows in tables.items()}
        try:
            step = time.perf_counter()
            actual_adapter = _detect_adapter(resolved) if adapter_name == "auto" else adapter_name
            if actual_adapter == "rpfm":
                _ensure_rpfm_server()
            session = adapter_for(actual_adapter).open_pack(resolved)
            open_seconds = _elapsed(step)
            step = time.perf_counter()
            reference_tables = {} if _is_image_only_reference(resolved) else _read_reference_tables(session)
            table_seconds = _elapsed(step)
            step = time.perf_counter()
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
                elif alias == "character_skill_node_links":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("parent_key", "child_key", "link_type"),
                        str(resolved),
                    )
                elif alias == "character_skill_level_to_effects_junctions":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("character_skill_key", "effect_key", "effect_scope", "level"),
                        str(resolved),
                    )
                elif alias == "character_attribute_sets":
                    _append_missing_rows_by_key(
                        tables.setdefault(alias, []),
                        rows,
                        _attribute_set_key,
                        str(resolved),
                    )
                elif alias == "character_attributes":
                    _append_missing_rows_by_key(
                        tables.setdefault(alias, []),
                        rows,
                        lambda row: (_attribute_set_key(row), _attribute_stat_key(row) or ""),
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
            loc_seconds = _elapsed(step)
            step = time.perf_counter()
            added_assets = 0
            image_only_reference = _is_image_only_reference(resolved)
            for asset_path in session.list_files():
                stored_asset_path = _source_scoped_asset_path(resolved, asset_path) if image_only_reference else asset_path
                if stored_asset_path in known_assets:
                    continue
                if not image_only_reference and asset_path in known_assets:
                    continue
                asset_files.append(stored_asset_path)
                known_assets.add(stored_asset_path)
                asset_sources[stored_asset_path] = str(resolved)
                added_assets += 1
            asset_seconds = _elapsed(step)
            added = {
                alias: len(tables.get(alias, [])) - before_counts.get(alias, 0)
                for alias in reference_tables
            }
            row_counts = {alias: len(rows) for alias, rows in reference_tables.items()}
            report.append({
                "path": str(resolved),
                "ok": True,
                "tables": sorted(reference_tables),
                "rowCounts": row_counts,
                "addedRows": {key: value for key, value in added.items() if value},
                "addedAssets": added_assets,
                "seconds": _elapsed(reference_started),
                "timings": {
                    "open": open_seconds,
                    "tablesAndRows": table_seconds,
                    "loc": loc_seconds,
                    "assets": asset_seconds,
                },
            })
        except Exception as error:
            report.append({"path": str(resolved), "ok": False, "error": str(error), "seconds": _elapsed(reference_started)})
        finally:
            if session is not None:
                _close_session(session)
    return report


def _merge_internal_materials(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
    asset_files: list[str],
    asset_sources: dict[str, str],
) -> dict[str, Any] | None:
    if not INTERNAL_MATERIALS_PATH.is_file():
        return None
    started = time.perf_counter()
    known_assets = set(asset_files)
    before_counts = {alias: len(rows) for alias, rows in tables.items()}
    try:
        session = MaterialPackSession.open(INTERNAL_MATERIALS_PATH)
        reference_tables = _read_internal_material_reference_tables(session)
        for alias, rows in reference_tables.items():
            if alias == "campaign_character_arts":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("art_set_id", "age", "portrait", "card", "uniform"),
                    str(INTERNAL_MATERIALS_PATH),
                )
            elif alias == "character_generation_template_game_mode_details":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("character_generation_template", "game_mode"),
                    str(INTERNAL_MATERIALS_PATH),
                )
            elif alias == "character_skill_node_links":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("parent_key", "child_key", "link_type"),
                    str(INTERNAL_MATERIALS_PATH),
                )
            elif alias == "character_skill_level_to_effects_junctions":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("character_skill_key", "effect_key", "effect_scope", "level"),
                    str(INTERNAL_MATERIALS_PATH),
                )
            elif alias == "character_attribute_sets":
                _append_missing_rows_by_key(
                    tables.setdefault(alias, []),
                    rows,
                    _attribute_set_key,
                    str(INTERNAL_MATERIALS_PATH),
                )
            elif alias == "character_attributes":
                _append_missing_rows_by_key(
                    tables.setdefault(alias, []),
                    rows,
                    lambda row: (_attribute_set_key(row), _attribute_stat_key(row) or ""),
                    str(INTERNAL_MATERIALS_PATH),
                )
            else:
                _append_missing_rows(
                    tables.setdefault(alias, []),
                    rows,
                    _key_field_for_alias(alias),
                    str(INTERNAL_MATERIALS_PATH),
                )
        for key, text in _read_all_loc_text(session).items():
            loc_text.setdefault(key, text)
        added_assets = _merge_internal_asset_manifest(asset_files, asset_sources, known_assets)
        added_assets += _merge_extracted_asset_inventory(asset_files, asset_sources, known_assets)
        added = {
            alias: len(tables.get(alias, [])) - before_counts.get(alias, 0)
            for alias in reference_tables
        }
        return {
            "path": str(INTERNAL_MATERIALS_PATH),
            "ok": True,
            "internalMaterials": True,
            "tables": sorted(reference_tables),
            "rowCounts": {alias: len(rows) for alias, rows in reference_tables.items()},
            "addedRows": {key: value for key, value in added.items() if value},
            "addedAssets": added_assets,
            "seconds": _elapsed(started),
        }
    except Exception as error:
        return {
            "path": str(INTERNAL_MATERIALS_PATH),
            "ok": False,
            "internalMaterials": True,
            "error": str(error),
            "seconds": _elapsed(started),
        }


def _merge_internal_asset_manifest(
    asset_files: list[str],
    asset_sources: dict[str, str],
    known_assets: set[str],
) -> int:
    if not INTERNAL_ASSET_MANIFEST.is_file():
        return 0
    try:
        with INTERNAL_ASSET_MANIFEST.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return 0
    assets = manifest.get("assets", {})
    if not isinstance(assets, dict):
        return 0
    added = 0
    for packed_path, info in assets.items():
        if not packed_path or packed_path in known_assets:
            continue
        if _is_aw_asset_path(str(packed_path)):
            continue
        asset_files.append(str(packed_path))
        known_assets.add(str(packed_path))
        source = ""
        if isinstance(info, dict):
            source = str(info.get("sourcePack") or info.get("sourcePath") or "")
        asset_sources[str(packed_path)] = source or str(INTERNAL_ASSET_MANIFEST)
        added += 1
    return added


def _merge_extracted_asset_inventory(
    asset_files: list[str],
    asset_sources: dict[str, str],
    known_assets: set[str],
) -> int:
    if not EXTRACTED_ASSET_ROOT.is_dir():
        return 0
    added = 0
    pack_dirs = sorted(
        (path for path in EXTRACTED_ASSET_ROOT.iterdir() if path.is_dir()),
        key=lambda path: (0 if path.name == "hby_generated_character_sets" else 1, path.name.lower()),
    )
    for pack_dir in pack_dirs:
        for path in pack_dir.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.relative_to(pack_dir).as_posix()
            if not suffix.lower().startswith("ui/characters/"):
                continue
            if not suffix.lower().endswith((".png", ".jpg", ".jpeg", ".dds")):
                continue
            if _is_aw_asset_path(suffix):
                continue
            if suffix in known_assets:
                continue
            asset_files.append(suffix)
            known_assets.add(suffix)
            asset_sources[suffix] = str(pack_dir)
            added += 1
    return added


def _read_internal_material_reference_tables(session: Any) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    table_list = session.list_tables()
    aliases: dict[str, list[str]] = {
        **CHARACTER_TABLE_ALIASES,
        **{alias: TABLE_ALIASES.get(alias, [alias]) for alias in TABLE_ALIASES},
        **SKILL_TABLE_ALIASES,
        "character_attribute_sets": [
            "db/character_attribute_sets_tables/data__",
            "db/character_attribute_sets_tables/data",
        ],
        "character_attributes": [
            "db/character_attributes_tables/data__",
            "db/character_attributes_tables/data",
        ],
    }
    wanted_aliases = {
        *CHARACTER_TABLE_ALIASES,
        "campaign_character_art_sets",
        "campaign_character_arts",
        "character_attribute_sets",
        "character_attributes",
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
        *SKILL_TABLE_ALIASES,
    }
    for alias in wanted_aliases:
        rows: list[dict[str, Any]] = []
        for table_path in _all_reference_table_paths(table_list, alias, aliases.get(alias, [alias])):
            try:
                rows.extend(session.read_table(table_path))
            except ValueError:
                continue
        if rows:
            tables[alias] = rows
    return tables


def _all_reference_table_paths(table_list: list[str], alias: str, candidates: list[str]) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for candidate in candidates:
        if candidate in table_list and candidate not in seen:
            paths.append(candidate)
            seen.add(candidate)
    folder = (
        "/ceos_to_equipment_variants_tables/"
        if alias in {"equipment_variants_weapons", "equipment_variants_armours"}
        else f"/{alias}_tables/"
    )
    for path in sorted(table_list):
        if folder in path and path not in seen:
            paths.append(path)
            seen.add(path)
    return paths


def _skip_reference_pack_for_fast_open(path: Path) -> bool:
    return False


def _is_data_pack(path: Path) -> bool:
    return path.name.lower().startswith("data") or path.name.lower() in {"database.pack"}


def _is_aw_reference(path: Path | str) -> bool:
    if not path:
        return False
    return Path(path).name.lower().startswith(("aw-", "aw ", "aw_"))


def _is_aw_asset_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/aw_" in normalized or normalized.startswith("aw_") or "/characters/aw_" in normalized


def _is_lshz_reference(path: Path | str) -> bool:
    if not path:
        return False
    return Path(path).name.lower().startswith("lshz_")


def _is_image_only_reference(path: Path | str) -> bool:
    return _is_aw_reference(path) or _is_lshz_reference(path)


def _skip_bfg_resource_pack_for_fast_open(path: Path) -> bool:
    name = path.name.lower()
    return name == "bfg_astral.pack"


def _is_bfg_pack(path: Path) -> bool:
    return path.name.lower().startswith("bfg_")


def _is_bfg_reference(path: str) -> bool:
    return Path(path).name.lower().startswith("bfg_") if path else False


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
        "character_attribute_sets",
        "character_attributes",
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
    ):
        try:
            if alias in {
                "campaign_character_art_sets",
                "campaign_character_arts",
                "character_attribute_sets",
                "character_attributes",
            }:
                table_name = _resolve_reference_character_table(session, alias)
            else:
                table_name = _resolve_stat_table(session, alias, "pack")
            tables[alias] = session.read_table(table_name)
        except (KeyError, ValueError):
            continue
    for alias in SKILL_TABLE_ALIASES:
        try:
            table_name = _resolve_skill_table(session, alias, "pack")
            tables[alias] = session.read_table(table_name)
        except ValueError:
            continue
    return tables


def _read_data_pack_reference_tables(session: Any) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for alias in ("character_attribute_sets", "character_attributes"):
        try:
            table_name = _resolve_reference_character_table(session, alias)
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
        tuple(row.get(field) for field in fields): row
        for row in target
    }
    for row in source:
        key = tuple(row.get(field) for field in fields)
        if key in existing:
            if _is_bfg_reference(reference_path):
                existing[key].setdefault("_externalImageSetSourcePath", reference_path)
            continue
        target.append({**row, "_referenceSourcePath": reference_path})
        existing[key] = target[-1]


def _append_missing_rows_by_key(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    key_func: Any,
    reference_path: str,
) -> None:
    existing = {key_func(row): row for row in target if key_func(row)}
    for row in source:
        key = key_func(row)
        if not key or key in existing:
            continue
        target.append({**row, "_referenceSourcePath": reference_path})
        existing[key] = target[-1]


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
            retinue_key = str(detail.get("retinue") or "")
            row = land_units.get(retinue_key)
            if row:
                return _unit_stats_from_row(row, retinue_key)
    for detail in details:
        retinue_key = str(detail.get("retinue") or "")
        row = land_units.get(retinue_key)
        if row:
            return _unit_stats_from_row(row, retinue_key)
    name_token = _character_token_from_template(template_key)
    row = _best_land_unit(name_token, land_units)
    if row:
        return _unit_stats_from_row(row)
    return {}


def _unit_stats_from_row(row: dict[str, Any], source_retinue_key: str = "") -> dict[str, Any]:
    return {
        "landUnitKey": row.get("key"),
        "sourceRetinueKey": source_retinue_key,
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


def _attribute_stats_by_set(tables: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in tables.get("character_attributes", []):
        set_key = _attribute_set_key(row)
        if not set_key:
            continue
        attr_key = _attribute_stat_key(row)
        value = _attribute_stat_value(row)
        if not attr_key or value is None:
            continue
        grouped.setdefault(set_key, {})[attr_key] = value
    for set_key, stats in _DEFAULT_ATTRIBUTE_STATS_BY_SET.items():
        grouped.setdefault(set_key, dict(stats))
    return grouped


_ATTRIBUTE_STAT_PRESETS = {
    "balanced": {"expertise": 40, "resolve": 40, "cunning": 40, "instinct": 40, "authority": 40},
    "earth": {"expertise": 45, "resolve": 30, "cunning": 40, "instinct": 35, "authority": 50},
    "fire": {"expertise": 40, "resolve": 35, "cunning": 30, "instinct": 50, "authority": 45},
    "metal": {"expertise": 50, "resolve": 40, "cunning": 45, "instinct": 30, "authority": 35},
    "water": {"expertise": 35, "resolve": 45, "cunning": 50, "instinct": 40, "authority": 30},
    "wood": {"expertise": 30, "resolve": 50, "cunning": 35, "instinct": 45, "authority": 40},
    "healer": {"expertise": 30, "resolve": 45, "cunning": 35, "instinct": 50, "authority": 40},
    "scholar": {"expertise": 50, "resolve": 40, "cunning": 30, "instinct": 35, "authority": 45},
    "veteran": {"expertise": 35, "resolve": 50, "cunning": 45, "instinct": 40, "authority": 30},
}


def _build_default_attribute_stats_by_set() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for element in ("earth", "fire", "metal", "water", "wood"):
        for suffix in ("records", "romance"):
            result[f"3k_main_attribute_set_general_{element}_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS[element])
            result[f"3k_dlc06_attribute_set_general_nanman_{element}_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS[element])
    for suffix in ("records", "romance"):
        result[f"3k_dlc06_attribute_set_general_nanman_balanced_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS["balanced"])
        for role in ("healer", "scholar", "veteran"):
            result[f"3k_ytr_attribute_set_general_{role}_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS[role])
    return result


_DEFAULT_ATTRIBUTE_STATS_BY_SET = _build_default_attribute_stats_by_set()


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


def _attribute_stats_for_details(
    details: list[dict[str, Any]],
    stats_by_set: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") != game_mode:
                continue
            stats = stats_by_set.get(str(detail.get("attributeSet") or ""))
            if stats:
                return stats
    for detail in details:
        stats = stats_by_set.get(str(detail.get("attributeSet") or ""))
        if stats:
            return stats
    return {}


def _attribute_stat_key(row: dict[str, Any]) -> str | None:
    value = str(
        row.get("attribute_type")
        or row.get("attribute")
        or row.get("character_attribute")
        or row.get("attribute_key")
        or row.get("key")
        or ""
    ).lower()
    stat_key = _attribute_stat_key_from_text(value)
    if stat_key:
        return stat_key
    for cell in row.values():
        stat_key = _attribute_stat_key_from_text(str(cell or "").lower())
        if stat_key:
            return stat_key
    return None


def _attribute_stat_key_from_text(value: str) -> str | None:
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


def _attribute_stat_value(row: dict[str, Any]) -> int | float | None:
    for column in ("value", "attribute_value", "base_value", "initial_value", "starting_value", "amount"):
        value = row.get(column)
        if isinstance(value, (int, float)):
            return value
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
            return value
    return None


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


def _friendly_art_set_label(value: str, loc_text: dict[str, str] | None = None) -> str:
    loc_text = loc_text or {}
    korean_name = _korean_name_from_art_or_model_key(value, loc_text)
    if korean_name:
        return korean_name
    token = _character_token_from_art_or_model_key(value)
    return " ".join(part for part in token.split("_") if part) if token else _friendly_key(value)


def _friendly_model_set_label(value: Any, fallback_name: str) -> str:
    model_key = str(value or "")
    if not model_key:
        return fallback_name
    model_name = _korean_name_from_art_or_model_key(model_key, {})
    if model_name:
        return f"{model_name} 紐⑤뜽"
    if fallback_name:
        return f"{fallback_name} 紐⑤뜽"
    return _friendly_key(model_key)


def _korean_name_from_art_or_model_key(value: str, loc_text: dict[str, str]) -> str | None:
    token = _character_token_from_art_or_model_key(value)
    if not token:
        return None
    prefixes = _key_prefix_candidates(value)
    element_suffixes = ["earth", "fire", "metal", "water", "wood"]
    candidates: list[str] = []
    for prefix in prefixes:
        candidates.extend(
            f"{prefix}_template_historical_{token}_hero_{element}"
            for element in element_suffixes
        )
        candidates.append(f"{prefix}_template_historical_{token}")
    for candidate in candidates:
        korean_name = korean_character_name(candidate)
        if korean_name:
            return korean_name
        display_name = _display_name_from_key(candidate, loc_text)
        if display_name:
            return display_name
    return None


def _key_prefix_candidates(value: str) -> list[str]:
    parts = value.split("_")
    candidates = []
    if len(parts) >= 2 and parts[0] == "3k":
        candidates.append("_".join(parts[:2]))
    if parts and parts[0] in {"ep"}:
        candidates.append(parts[0])
    for prefix in ["3k_main", "3k_mtu", "3k_dlc04", "3k_dlc05", "3k_dlc06", "3k_dlc07", "3k_ytr", "ep"]:
        if prefix not in candidates:
            candidates.append(prefix)
    return candidates


def _character_token_from_art_or_model_key(value: str) -> str:
    token = value
    for marker in (
        "_art_set_historical_",
        "_art_set_generated_",
        "_hero_skin_",
        "_general_",
        "_template_historical_",
    ):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    for suffix in (
        "_general",
        "_hero",
        "_earth",
        "_fire",
        "_metal",
        "_water",
        "_wood",
    ):
        token = token.removesuffix(suffix)
    return token.strip("_")


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


def _build_asset_index(asset_files: list[str]) -> dict[str, Any]:
    normalized_files = [path.replace("\\", "/") for path in asset_files]
    lower_to_path: dict[str, str] = {}
    priority: dict[str, int] = {}
    stills_by_name: dict[tuple[str, str], list[str]] = {}
    for index, path in enumerate(normalized_files):
        lower = path.lower()
        lower_to_path.setdefault(lower, path)
        priority.setdefault(lower, index)
        if "/stills/" in lower and lower.endswith(".png"):
            parts = lower.rsplit("/", 1)
            name = parts[-1].removesuffix(".png") if parts else ""
            kind = lower.split("/stills/", 1)[1].split("/", 1)[0]
            stills_by_name.setdefault((name, kind), []).append(path)
    return {
        "files": normalized_files,
        "lower_to_path": lower_to_path,
        "priority": priority,
        "stills_by_name": stills_by_name,
        "prefix_cache": {},
    }


def _find_character_image(asset_index: dict[str, Any], image_key: str, image_kind: str) -> str | None:
    if not image_key:
        return None
    asset_files = asset_index["files"]
    normalized = image_key.strip("/")
    image_name = normalized.rsplit("/", 1)[-1]
    preferred = [
        f"ui/characters/{normalized}/stills/{image_kind}/{normalized}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/large/{normalized}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/{image_name}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/large/{image_name}.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/norm.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/happy.png",
        f"ui/eventpics/{image_name}.png",
    ]
    if image_name.startswith("ep_"):
        preferred.append(f"ui/eventpics/ep_event_{image_name.removeprefix('ep_')}.png")
    assets_by_lower = asset_index["lower_to_path"]
    for path in preferred:
        found = assets_by_lower.get(path.lower())
        if found:
            return found
    still_matches = asset_index["stills_by_name"].get((image_name.lower(), image_kind.lower()), [])
    if still_matches:
        return sorted(still_matches, key=lambda path: (
            _character_still_priority(path, image_kind),
            asset_index["priority"].get(path.lower(), 10**9),
        ))[0]
    folder_candidates = _image_folder_candidates(normalized)
    for folder in folder_candidates:
        found = _find_character_image_in_folder(asset_index, folder, image_kind)
        if found:
            return found
    composite_prefixes = _character_composite_prefixes(normalized)
    for prefix in composite_prefixes:
        candidates = [
            path
            for path in _asset_files_for_prefix(asset_index, prefix)
            if "/large_panel/" in path.lower()
            and path.lower().endswith(("/norm.png", "/happy.png", "/angry.png", "/noanim.png"))
        ]
        if candidates:
            return sorted(candidates, key=lambda path: (*_character_preview_priority(path), asset_index["priority"].get(path.lower(), 10**9)))[0]
    if "/" in normalized:
        return None
    return _find_character_image_in_folder(asset_index, normalized, image_kind)


def _image_folder_candidates(value: str) -> list[str]:
    normalized = str(value or "").replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    candidates: list[str] = []
    if not parts:
        return candidates
    lower_parts = [part.lower() for part in parts]
    if "characters" in lower_parts:
        index = lower_parts.index("characters")
        if len(parts) > index + 1:
            candidates.append(parts[index + 1])
    if "stills" in lower_parts:
        index = lower_parts.index("stills")
        if index > 0:
            candidates.append(parts[index - 1])
    if len(parts) == 1:
        candidates.append(parts[0])
    return list(dict.fromkeys(candidate.strip("/") for candidate in candidates if candidate))


def _find_character_image_in_folder(asset_index: dict[str, Any], folder: str, image_kind: str) -> str | None:
    normalized = str(folder or "").strip("/").lower()
    if not normalized:
        return None
    matches = [
        path for path in _asset_files_for_prefix(asset_index, f"ui/characters/{normalized}/")
        if path.lower().startswith(f"ui/characters/{normalized}/")
        and (
            f"/stills/{image_kind.lower()}/" in path.lower()
            or "/composites/large_panel/norm/" in path.lower()
            or "/composites/large_panel/happy/" in path.lower()
        )
        and path.lower().endswith(".png")
    ]
    return sorted(matches, key=lambda path: (
        _character_still_priority(path, image_kind),
        asset_index["priority"].get(path.lower(), 10**9),
    ))[0] if matches else None


def _character_still_priority(path: str, image_kind: str) -> int:
    lower = path.lower().replace("\\", "/")
    marker = f"/stills/{image_kind.lower()}/"
    if marker in lower:
        tail = lower.split(marker, 1)[1]
        if "/" not in tail:
            return 0
        if tail.startswith("large/"):
            return 1
        return 5
    if "/composites/large_panel/norm/" in lower:
        return 2
    if "/composites/large_panel/happy/" in lower:
        return 3
    return 4


def _asset_files_for_prefix(asset_index: dict[str, Any], prefix: str) -> list[str]:
    normalized_prefix = prefix.lower()
    cache = asset_index["prefix_cache"]
    if normalized_prefix not in cache:
        cache[normalized_prefix] = [
            path for path in asset_index["files"]
            if path.lower().startswith(normalized_prefix)
        ]
    return cache[normalized_prefix]


def _character_composite_prefixes(normalized_key: str) -> list[str]:
    parts = [part for part in normalized_key.lower().strip("/").split("/") if part]
    prefixes: list[str] = []
    if len(parts) >= 2:
        first, second = parts[0], parts[1]
        gender = second if second in {"female", "male"} else None
        element = first.split("_", 1)[0]
        if gender and element in {"earth", "fire", "metal", "water", "wood"}:
            if first == "water_strategist":
                prefixes.append(f"ui/characters/water_strategist_ban/{gender}/")
            prefixes.append(f"ui/characters/{first}/{gender}/")
            prefixes.append(f"ui/characters/{element}/{gender}/")
    if parts:
        prefixes.append(f"ui/characters/{parts[0]}/")
    return prefixes


def _character_preview_priority(path: str) -> tuple[int, str]:
    lower = path.lower()
    if "/large_panel/norm/norm.png" in lower:
        return (0, lower)
    if "/large_panel/happy/happy.png" in lower:
        return (1, lower)
    if "/large_panel/angry/angry.png" in lower:
        return (2, lower)
    return (3, lower)


def _character_image_assets(
    asset_index: dict[str, Any],
    asset_sources: dict[str, str],
    portrait_key: str,
    card_key: str,
) -> list[dict[str, str]]:
    asset_files = asset_index["files"]
    exact_prefixes: list[str] = []
    for key, kind in ((portrait_key, "halfbody_large"), (card_key, "unitcards")):
        preview_path = _find_character_image(asset_index, str(key or ""), kind)
        composite_prefix = _composite_asset_prefix_from_path(preview_path or "")
        if composite_prefix:
            exact_prefixes.append(composite_prefix)

    folders = []
    for key in (portrait_key, card_key):
        for folder in _image_folder_candidates(str(key or "")):
            if folder and folder not in folders:
                folders.append(folder)

    assets = []
    seen = set()
    prefixes = exact_prefixes or [f"ui/characters/{folder.lower()}/" for folder in folders]
    for prefix in dict.fromkeys(prefixes):
        for path in _asset_files_for_prefix(asset_index, prefix):
            normalized_path = path
            lower_path = normalized_path.lower()
            if normalized_path in seen:
                continue
            if _is_duplicate_character_folder_path(normalized_path):
                continue
            if not lower_path.startswith(prefix):
                continue
            if not lower_path.endswith((".png", ".jpg", ".jpeg", ".dds")):
                continue
            assets.append({
                "path": normalized_path,
                "sourcePath": asset_sources.get(path, asset_sources.get(normalized_path, "")),
            })
            seen.add(normalized_path)
    return sorted(assets, key=lambda item: item["path"])


def _is_duplicate_character_folder_path(path: str) -> bool:
    parts = [part for part in path.replace("\\", "/").strip("/").split("/") if part]
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


def _composite_asset_prefix_from_path(path: str) -> str | None:
    lower = path.replace("\\", "/").lower()
    marker = "/large_panel/"
    if marker in lower and "/composites/" in lower:
        return lower.split(marker, 1)[0] + "/"
    marker = "/small_panel/"
    if marker in lower and "/composites/" in lower:
        return lower.split(marker, 1)[0] + "/"
    return None


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


def _resolve_skill_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in SKILL_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    matches = sorted(table for table in tables if table.startswith(f"db/{alias}_tables/"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preferred = [
            table for table in matches
            if "/_mtu" in table or "/data__" in table or "/data_" in table
        ]
        return preferred[0] if preferred else matches[0]
    raise ValueError(f"Required skill table is missing in {source}: {alias}")


def _resolve_reference_character_table(session: Any, alias: str) -> str:
    tables = set(session.list_tables("pack"))
    for candidate in CHARACTER_TABLE_ALIASES.get(alias, [alias]):
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
    input_path = payload.get("inputPath")
    if not input_path:
        raise ValueError("inputPath is required.")
    pack_path = _resolve_user_path(input_path)
    adapter_name = payload.get("adapter", "auto")
    if adapter_name == "auto":
        adapter_name = _detect_adapter(pack_path)
    if adapter_name == "rpfm":
        _ensure_rpfm_server()
    return adapter_for(adapter_name).open_pack(pack_path)


def _reference_pack_paths(payload: dict[str, Any]) -> list[Path]:
    raw_paths = payload.get("referencePackPaths") or []
    if isinstance(raw_paths, str):
        raw_paths = [line.strip() for line in raw_paths.splitlines()]
    paths = []
    for raw_path in raw_paths:
        if not raw_path:
            continue
        paths.append(_resolve_user_path(raw_path))
    return [
        path
        for _, path in sorted(
            enumerate(paths),
            key=lambda item: (_reference_pack_priority(item[1]), item[0]),
        )
    ]


def _reference_pack_priority(path: Path) -> int:
    name = path.name.lower()
    if name.startswith("bfg_"):
        return 0
    if name.startswith("data") or name == "database.pack":
        return 1
    if name.startswith("lshz_"):
        return 2
    if name.startswith(("aw-", "aw ")):
        return 3
    return 4


def _detect_adapter(pack_path: Path) -> str:
    try:
        with pack_path.open("rb") as handle:
            prefix = handle.read(64).lstrip()
    except FileNotFoundError:
        raise ValueError(f"Pack file not found: {pack_path}")
    if prefix.startswith(b"{"):
        return "mock"
    return "rpfm"


def _resolve_user_path(raw_path: Any) -> Path:
    text = str(raw_path).strip().strip('"')
    text = text.replace("\u00a5", "\\").replace("\u20a9", "\\")
    if os.name == "nt":
        normalized = text.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() == "users" and ":" not in parts[0]:
            home_parts = Path.home().parts
            if len(home_parts) >= 2 and home_parts[-2].lower() == "users":
                return Path.home().joinpath(*parts[2:])
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def _ensure_rpfm_server() -> None:
    global RPFM_PROCESS, RPFM_LOG_HANDLE
    if _port_open("127.0.0.1", 45127):
        return
    if os.environ.get("MTU_RPFM_EXTERNAL_ONLY") == "1":
        raise ValueError("RPFM server is not running on 127.0.0.1:45127.")
    if RPFM_PROCESS is not None and RPFM_PROCESS.poll() is None:
        _wait_for_port("127.0.0.1", 45127)
        return
    rpfm_server = resolve_rpfm_server(ROOT, DEFAULT_RPFM_SERVER)
    if not rpfm_server.is_file():
        raise ValueError(f"RPFM server binary not found: {rpfm_server}")
    _stop_stale_rpfm_processes(rpfm_server.name)
    redirect_root = ROOT / "work" / "rpfm-runtime-config"
    redirect_root.mkdir(parents=True, exist_ok=True)
    redirect_path = redirect_root / f"config-{int(time.time() * 1000)}"
    (rpfm_server.parent / "config_folder.txt").write_text(str(redirect_path), encoding="utf-8")
    log_path = ROOT / "work" / "rpfm-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if RPFM_LOG_HANDLE is not None and not RPFM_LOG_HANDLE.closed:
        RPFM_LOG_HANDLE.close()
    RPFM_LOG_HANDLE = log_path.open("ab")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    RPFM_PROCESS = subprocess.Popen(
        [str(rpfm_server)],
        cwd=rpfm_server.parent,
        env=_rpfm_env(),
        stdout=RPFM_LOG_HANDLE,
        stderr=RPFM_LOG_HANDLE,
        creationflags=creationflags,
    )
    _wait_for_port("127.0.0.1", 45127)


def _stop_stale_rpfm_processes(process_name: str) -> None:
    if os.name != "nt":
        return
    subprocess.run(
        ["taskkill", "/F", "/IM", process_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(0.5)


def _rotate_rpfm_config_dir() -> None:
    if os.name != "nt":
        return
    local_roots = [
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")),
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")),
        Path.home() / "AppData" / "Local",
        Path.home() / "AppData" / "Roaming",
        _rpfm_local_appdata_root(),
        ROOT / "work" / "rpfm-local-appdata" / "config",
    ]
    for local_appdata in local_roots:
        config_dir = local_appdata / "FrodoWazEre" / "rpfm" / "config"
        if not config_dir.exists():
            continue
        backup = config_dir.with_name(f"config.mtu-backup-{int(time.time())}")
        try:
            config_dir.rename(backup)
        except OSError:
            shutil.rmtree(config_dir, ignore_errors=True)


def _rpfm_local_appdata_root() -> Path:
    return ROOT / "work" / "rpfm-local-appdata"


def _rpfm_env() -> dict[str, str]:
    blocked_prefixes = ("PYINSTALLER_", "PYI_", "PYTHON")
    blocked_keys = {"TK_PACK_EDITOR_ROOT", "_MEIPASS"}
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper in blocked_keys or any(upper.startswith(prefix) for prefix in blocked_prefixes):
            continue
        if upper == "PATH" and any(existing.upper() == "PATH" for existing in env):
            continue
        env[key] = value
    if os.name != "nt":
        config_root = _rpfm_local_appdata_root()
        config_root.mkdir(parents=True, exist_ok=True)
        env["XDG_CONFIG_HOME"] = str(config_root)
    return env


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
