from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server, _read_all_loc_text  # noqa: E402


DEFAULT_SOURCE_PACKS = [
    ROOT / "work" / "packs" / "refs" / "local_kr.pack",
    Path(r"E:\SteamLibrary\steamapps\common\Total War THREE KINGDOMS\data\local_kr.pack"),
]
DEFAULT_OUTPUT = ROOT / "work" / "internal_dbs" / "localisation_kr.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract Korean localisation rows into the app's internal JSON DB."
    )
    parser.add_argument("--source-pack", dest="source_packs", action="append", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_packs = [
        path.expanduser().resolve()
        for path in (args.source_packs if args.source_packs is not None else DEFAULT_SOURCE_PACKS)
        if path
    ]
    existing_packs = _unique_existing_paths(source_packs)
    if not existing_packs:
        raise SystemExit("No localisation source pack found.")

    _ensure_rpfm_server()
    loc_text: dict[str, str] = {}
    sources: list[dict[str, Any]] = []
    for source_pack in existing_packs:
        session = adapter_for("rpfm").open_pack(source_pack)
        try:
            rows = _read_all_loc_text(session)
        finally:
            close = getattr(session, "close", None)
            if close:
                close()
        before = len(loc_text)
        loc_text.update(rows)
        sources.append({
            "path": str(source_pack),
            "rows": len(rows),
            "addedOrReplaced": len(loc_text) - before,
        })

    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "createdAt": time.time(),
        "sourcePacks": sources,
        "locText": loc_text,
        "counts": {"locText": len(loc_text)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0


def _unique_existing_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        unique.append(path)
    return unique


if __name__ == "__main__":
    raise SystemExit(main())
