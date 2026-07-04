from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any


PANEL_STATES = ("angry", "happy", "norm")
PANEL_KINDS = ("large_panel", "small_panel")
STILL_KINDS = (
    "bobbleheads",
    "bobbleheads/large",
    "halfbody_large",
    "halfbody_large/large",
    "halfbody_small",
    "halfbody_small/large",
    "mini",
    "mini/large",
    "unitcards",
    "unitcards/large",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _normalize_path(path: Path) -> str:
    return path.as_posix().lower()


def _has_png(path: Path) -> bool:
    return path.is_dir() and any(child.is_file() and child.suffix.lower() == ".png" for child in path.iterdir())


def _png_comment(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data.startswith(PNG_SIGNATURE):
        return None
    offset = len(PNG_SIGNATURE)
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        if chunk_data_end + 4 > len(data):
            return None
        if chunk_type == b"tEXt":
            chunk_data = data[chunk_data_start:chunk_data_end]
            key, _, value = chunk_data.partition(b"\x00")
            if key == b"Comment":
                return value.decode("latin-1", errors="replace")
        offset = chunk_data_end + 4
    return None


def _character_roots(root: Path) -> list[Path]:
    roots: list[Path] = []
    for characters_dir in root.rglob("characters"):
        if not characters_dir.is_dir():
            continue
        normalized = _normalize_path(characters_dir)
        if "__image_only_reference__" in normalized:
            continue
        if "/ui/characters" not in normalized and "\\ui\\characters" not in str(characters_dir).lower():
            continue
        for child in characters_dir.iterdir():
            if child.is_dir():
                roots.append(child)
    return sorted(set(roots), key=lambda path: str(path).lower())


def _panel_file_candidates(panel_dir: Path, state: str) -> list[Path]:
    candidates = [panel_dir / f"{state}.png", panel_dir / "noanim.png"]
    if state == "norm":
        candidates.append(panel_dir / "normal.png")
    return candidates


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def audit_character_root(character_root: Path) -> dict[str, Any]:
    missing: list[str] = []
    missing_comments: list[str] = []
    present_panels = 0
    present_stills = 0

    for panel_kind in PANEL_KINDS:
        for state in PANEL_STATES:
            panel_dir = character_root / "composites" / panel_kind / state
            existing = _first_existing(_panel_file_candidates(panel_dir, state))
            if existing is None:
                missing.append(str(Path("composites") / panel_kind / state / f"{state}.png"))
                continue
            present_panels += 1
            if _png_comment(existing) in (None, ""):
                missing_comments.append(str(existing.relative_to(character_root)))

    for still_kind in STILL_KINDS:
        still_dir = character_root / "stills" / still_kind
        if _has_png(still_dir):
            present_stills += 1
        else:
            missing.append(str(Path("stills") / still_kind / "*.png"))

    return {
        "key": character_root.name,
        "root": str(character_root),
        "presentPanels": present_panels,
        "presentStills": present_stills,
        "missing": missing,
        "missingComments": missing_comments,
        "ok": not missing and not missing_comments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit extracted Total War character image asset sets.")
    parser.add_argument("roots", nargs="*", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--only-broken", action="store_true")
    args = parser.parse_args()

    roots = args.roots or [Path("work/assets/hby_generated_character_sets")]
    reports: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            reports.append({
                "key": "",
                "root": str(root),
                "presentPanels": 0,
                "presentStills": 0,
                "missing": ["root not found"],
                "missingComments": [],
                "ok": False,
            })
            continue
        reports.extend(audit_character_root(character_root) for character_root in _character_roots(root))

    all_reports = reports
    if args.only_broken:
        reports = [report for report in all_reports if not report["ok"]]

    payload = {
        "summary": {
            "roots": [str(root) for root in roots],
            "sets": len(all_reports),
            "ok": sum(1 for report in all_reports if report["ok"]),
            "broken": sum(1 for report in all_reports if not report["ok"]),
            "reported": len(reports),
        },
        "sets": reports,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
