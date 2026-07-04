from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402


DEFAULT_MATERIALS = ROOT / "work" / "internal_materials" / "materials.v015.json"
DEFAULT_GAME_DATA = Path("E:/SteamLibrary/steamapps/common/Total War THREE KINGDOMS/data")
DEFAULT_LOC_PACKS = ("local_en.pack", "local_kr.pack")
TARGET_LOC_PATH = "text/mtu_pack_editor/ceo_node_titles_from_game.loc"
TITLE_PREFIXES = ("ceo_nodes_title_", "ceo_nodes_description_")
TR_REFERENCE_RE = re.compile(r"\{\{tr:([^}]+)\}\}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich internal materials with title CEO loc rows from game localization packs.")
    parser.add_argument("--materials", type=Path, default=DEFAULT_MATERIALS)
    parser.add_argument("--game-data", type=Path, default=DEFAULT_GAME_DATA)
    parser.add_argument("--pack", action="append", dest="packs", help="Localization pack filename or path. Defaults to local_en then local_kr.")
    parser.add_argument("--report", type=Path, default=ROOT / "work" / "internal_materials" / "title_loc_enrichment_report.json")
    args = parser.parse_args()

    materials_path = args.materials.resolve()
    if not materials_path.is_file():
        raise SystemExit(f"Materials file not found: {materials_path}")

    pack_paths = resolve_pack_paths(args.game_data.resolve(), args.packs or list(DEFAULT_LOC_PACKS))
    if not pack_paths:
        raise SystemExit(f"No localization packs found under: {args.game_data}")

    _ensure_rpfm_server()
    rows_by_source: list[tuple[Path, dict[str, str]]] = []
    merged_rows: dict[str, str] = {}
    for pack_path in pack_paths:
        rows = read_title_loc_rows(pack_path)
        rows_by_source.append((pack_path, rows))
        merged_rows.update(rows)

    if not merged_rows:
        raise SystemExit("No ceo_nodes_title_/ceo_nodes_description_ rows found.")

    materials = json.loads(materials_path.read_text(encoding="utf-8"))
    loc = materials.setdefault("loc", {})
    loc[TARGET_LOC_PATH] = {
        "sourcePath": ";".join(str(path) for path, _ in rows_by_source),
        "rows": dict(sorted(merged_rows.items())),
    }
    materials_path.write_text(json.dumps(materials, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "ok": True,
        "materials": str(materials_path),
        "targetLocPath": TARGET_LOC_PATH,
        "packs": [
            {"path": str(path), "rows": len(rows)}
            for path, rows in rows_by_source
        ],
        "mergedRows": len(merged_rows),
        "titleRows": sum(1 for key in merged_rows if key.startswith("ceo_nodes_title_")),
        "descriptionRows": sum(1 for key in merged_rows if key.startswith("ceo_nodes_description_")),
        "referenceRows": sum(1 for key in merged_rows if not key.startswith(TITLE_PREFIXES)),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def resolve_pack_paths(game_data: Path, packs: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for item in packs:
        path = Path(item)
        if not path.is_absolute():
            path = game_data / item
        if path.is_file():
            resolved.append(path.resolve())
    return resolved


def read_title_loc_rows(pack_path: Path) -> dict[str, str]:
    session = open_pack_with_retry(pack_path)
    try:
        all_rows: dict[str, str] = {}
        for loc_path in session.list_loc_files():
            try:
                all_rows.update(session.read_loc(loc_path))
            except (NotImplementedError, ValueError):
                continue
    finally:
        session.close()

    wanted = {
        key
        for key in all_rows
        if key.startswith(TITLE_PREFIXES)
    }
    wanted.update(referenced_loc_keys(all_rows, wanted))
    return {
        key: all_rows[key]
        for key in sorted(wanted)
        if key in all_rows
    }


def open_pack_with_retry(pack_path: Path) -> Any:
    last_error: Exception | None = None
    for _ in range(2):
        try:
            _ensure_rpfm_server()
            return adapter_for("rpfm").open_pack(pack_path)
        except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError) as error:
            last_error = error
            time.sleep(0.8)
    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to open pack: {pack_path}")


def referenced_loc_keys(all_rows: dict[str, str], initial_keys: set[str]) -> set[str]:
    found: set[str] = set()
    pending = list(initial_keys)
    while pending:
        key = pending.pop()
        for match in TR_REFERENCE_RE.finditer(all_rows.get(key, "")):
            ref_key = match.group(1)
            if ref_key in all_rows and ref_key not in found and ref_key not in initial_keys:
                found.add(ref_key)
                pending.append(ref_key)
    return found


if __name__ == "__main__":
    main()
