from __future__ import annotations

import shutil
import re
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "work" / "이미지 편집"
TARGET_SOURCE_ROOT = ROOT / "work" / "assets" / "hby_generated_character_sets"
TARGET_ROOT = TARGET_SOURCE_ROOT / "ui" / "characters"
SUN_CE_ROOT = ROOT / "work" / "assets" / "17309a40b912" / "ui" / "characters" / "3k_main_hero_special_fire_sun_ce"

NAME_TO_KEY = {
    "고연화": "hby_hero_special_go_yeon_hwa",
    "금령": "hby_hero_special_geum_ryeong",
    "노리코": "hby_hero_special_no_ri_ko",
    "설화": "hby_hero_special_seol_hwa",
    "소마": "hby_hero_special_so_ma",
    "연지우": "hby_hero_special_yeon_jiwoo",
    "유혜린": "hby_hero_special_yu_hyerin",
    "윤이서": "hby_hero_special_yun_i_seo",
    "채린": "hby_hero_special_chae_rin",
    "화령": "hby_hero_special_hwa_ryeong",
}

PANEL_SOURCES = {
    ("large_panel", "angry"): Path("large_panel/norm/norm.png"),
    ("large_panel", "happy"): Path("large_panel/norm/norm.png"),
    ("large_panel", "norm"): Path("large_panel/norm/norm.png"),
    ("small_panel", "angry"): Path("small_panel/norm/norm.png"),
    ("small_panel", "happy"): Path("small_panel/norm/norm.png"),
    ("small_panel", "norm"): Path("small_panel/norm/norm.png"),
}

PANEL_COORDS = {
    "large_panel": (-21, 147),
    "small_panel": (-15, 102),
}

STILL_SOURCES = {
    Path("stills/bobbleheads/{key}.png"): Path("stills/bobbleheads.png"),
    Path("stills/bobbleheads/large/{key}.png"): Path("stills/bobbleheads/large.png"),
    Path("stills/halfbody_large/{key}.png"): Path("stills/halfbody_large.png"),
    Path("stills/halfbody_large/large/{key}.png"): Path("stills/halfbody_large/large.png"),
    Path("stills/halfbody_small/{key}.png"): Path("stills/halfbody_small.png"),
    Path("stills/halfbody_small/large/{key}.png"): Path("stills/halfbody_small/large.png"),
    Path("stills/mini/{key}.png"): Path("stills/mini.png"),
    Path("stills/mini/large/{key}.png"): Path("stills/mini/large.png"),
    Path("stills/unitcards/{key}.png"): Path("stills/unitcards.png"),
    Path("stills/unitcards/large/{key}.png"): Path("stills/unitcards/large.png"),
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_IDAT_CHUNK_SIZE = 64 * 1024


def read_png_comment(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"Not a PNG: {path}")
    offset = len(PNG_SIGNATURE)
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        if kind == b"tEXt":
            payload = data[payload_start:payload_end]
            if payload.startswith(b"Comment\x00"):
                return payload.split(b"\x00", 1)[1]
        offset = payload_end + 4
    raise ValueError(f"Sun Ce panel PNG has no Comment tEXt chunk: {path}")


def set_png_comment(source: Path, target: Path, comment: bytes) -> None:
    data = source.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"Not a PNG: {source}")
    chunks: list[tuple[bytes, bytes]] = []
    offset = len(PNG_SIGNATURE)
    inserted = False
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        payload = data[payload_start:payload_end]
        if kind == b"tEXt" and payload.startswith(b"Comment\x00"):
            if not inserted:
                chunks.append((b"tEXt", b"Comment\x00" + comment))
                inserted = True
        else:
            chunks.append((kind, payload))
            if kind == b"IHDR" and not inserted:
                chunks.append((b"tEXt", b"Comment\x00" + comment))
                inserted = True
        offset = payload_end + 4
        if kind == b"IEND":
            break
    if not inserted:
        chunks.insert(1, (b"tEXt", b"Comment\x00" + comment))
    target.parent.mkdir(parents=True, exist_ok=True)
    chunks = normalize_idat_chunks(chunks)
    target.write_bytes(PNG_SIGNATURE + b"".join(write_chunk(kind, payload) for kind, payload in chunks))


def write_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def normalize_idat_chunks(chunks: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    idat_payloads = [payload for kind, payload in chunks if kind == b"IDAT"]
    if not idat_payloads:
        return chunks
    compressed = zlib.compress(zlib.decompress(b"".join(idat_payloads)), level=9)
    normalized: list[tuple[bytes, bytes]] = []
    inserted = False
    for kind, payload in chunks:
        if kind == b"IDAT":
            if inserted:
                continue
            for offset in range(0, len(compressed), MAX_IDAT_CHUNK_SIZE):
                normalized.append((b"IDAT", compressed[offset:offset + MAX_IDAT_CHUNK_SIZE]))
            inserted = True
            continue
        normalized.append((kind, payload))
    return normalized


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def panel_comment(panel: str, state: str) -> bytes:
    source_name = state
    path = SUN_CE_ROOT / "composites" / panel / state / f"{source_name}.png"
    return normalize_panel_comment(panel, read_png_comment(path))


def normalize_panel_comment(panel: str, comment: bytes) -> bytes:
    x, y = PANEL_COORDS[panel]
    text = comment.decode("latin1")
    text, x_count = re.subn(r"x:-?\d+;", f"x:{x};", text, count=1)
    text, y_count = re.subn(r"y:-?\d+;", f"y:{y};", text, count=1)
    if x_count != 1 or y_count != 1:
        raise ValueError(f"Panel comment has no x/y coordinates: {comment!r}")
    return text.encode("latin1")


def rebuild() -> None:
    if not SOURCE_ROOT.is_dir():
        raise FileNotFoundError(SOURCE_ROOT)
    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    comments = {
        (panel, state): panel_comment(panel, state)
        for panel, state in PANEL_SOURCES
    }
    built: list[tuple[str, str, int]] = []
    for source_dir in sorted(
        (SOURCE_ROOT / name for name in NAME_TO_KEY),
        key=lambda path: path.name,
    ):
        if not source_dir.is_dir():
            raise FileNotFoundError(source_dir)
        key = NAME_TO_KEY.get(source_dir.name)
        target_character_root = TARGET_ROOT / key
        for (panel, state), relative_source in PANEL_SOURCES.items():
            source_file = source_dir / relative_source
            target_file = target_character_root / "composites" / panel / state / f"{state}.png"
            set_png_comment(source_file, target_file, comments[(panel, state)])
        for target_template, relative_source in STILL_SOURCES.items():
            source_file = source_dir / relative_source
            target_file = target_character_root / Path(str(target_template).format(key=key))
            copy_file(source_file, target_file)
        built.append((source_dir.name, key, len(list(target_character_root.rglob("*.png")))))

    print(f"rebuilt {len(built)} hby character asset set(s)")
    for name, key, count in built:
        print(f"{name} -> {key}: {count} png")


if __name__ == "__main__":
    rebuild()
