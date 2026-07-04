from __future__ import annotations

import argparse
import json
import shutil
import socket
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_internal_materials_v015 import (  # noqa: E402
    DEFAULT_SOURCES,
    MERGED_KOREAN_LOC_PATH,
    add_loc_source,
    finalize_loc_materials,
)
from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402

DEFAULT_MATERIALS = ROOT / "work" / "internal_materials" / "materials.v015.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge all available Korean loc rows into internal materials.")
    parser.add_argument("--materials", type=Path, default=DEFAULT_MATERIALS)
    parser.add_argument("--source", action="append", type=Path, dest="sources")
    parser.add_argument("--report", type=Path, default=ROOT / "work" / "internal_materials" / "loc_korean_merge_report.json")
    args = parser.parse_args()

    material_path = args.materials.resolve()
    if not material_path.is_file():
        raise SystemExit(f"Materials file not found: {material_path}")

    materials = json.loads(material_path.read_text(encoding="utf-8"))
    source_paths = [path.resolve() for path in (args.sources or default_loc_sources()) if path.is_file()]

    report: dict[str, Any] = {
        "ok": True,
        "createdAt": time.time(),
        "materials": str(material_path),
        "targetLocPath": MERGED_KOREAN_LOC_PATH,
        "sources": [],
    }

    _ensure_rpfm_server()
    for source in source_paths:
        report["sources"].append(read_loc_source(materials, source))

    finalize_loc_materials(materials)

    backup_path = material_path.with_suffix(f".loc-backup-{time.strftime('%Y%m%d%H%M%S')}.json")
    shutil.copy2(material_path, backup_path)
    material_path.write_text(json.dumps(materials, ensure_ascii=False, indent=2), encoding="utf-8")

    merged_rows = next(iter(materials.get("loc", {}).values()), {}).get("rows", {})
    report.update({
        "backup": str(backup_path),
        "locFileCount": len(materials.get("loc", {})),
        "mergedRows": len(merged_rows) if isinstance(merged_rows, dict) else 0,
        "sample": sample_rows(merged_rows if isinstance(merged_rows, dict) else {}),
    })
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def default_loc_sources() -> list[Path]:
    return [
        path for path in DEFAULT_SOURCES
        if path.name.lower().startswith("local_")
        or "kr" in path.name.lower()
        or "korea" in path.name.lower()
        or "korean" in path.name.lower()
        or "(kor)" in path.name.lower()
        or "190_expanded_kr" in path.name.lower()
    ]


def read_loc_source(materials: dict[str, Any], source: Path) -> dict[str, Any]:
    session = open_pack_with_retry(source)
    source_report = {
        "path": str(source),
        "locFileCount": 0,
        "decodedLocFileCount": 0,
        "rowCount": 0,
    }
    try:
        for loc_path in session.list_loc_files():
            source_report["locFileCount"] += 1
            try:
                loc_rows = session.read_loc(loc_path)
            except Exception:
                continue
            add_loc_source(materials, loc_path, source, loc_rows)
            source_report["decodedLocFileCount"] += 1
            source_report["rowCount"] += len(loc_rows)
    finally:
        session.close()
    return source_report


def open_pack_with_retry(source: Path) -> Any:
    last_error: Exception | None = None
    for _ in range(3):
        try:
            _ensure_rpfm_server()
            return adapter_for("rpfm").open_pack(source)
        except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError) as exc:
            last_error = exc
            time.sleep(0.8)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to open pack: {source}")


def sample_rows(rows: dict[str, str]) -> dict[str, str]:
    keys = [
        "ceo_nodes_title_3k_main_ceo_node_career_historical_liu_bei_01",
        "ceo_nodes_title_3k_main_ceo_node_career_historical_lu_bu_01",
        "character_skills_localised_name_3k_main_skill_bodyguard_zhou_yu",
        "names_name_2147343898",
    ]
    return {key: rows[key] for key in keys if key in rows}


if __name__ == "__main__":
    main()
