from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .pfh import read_pfh_index

CANDIDATE_PATTERNS = [
    "ancillar",
    "ceo_",
    "effect_bonus",
    "effects_tables",
    "character_generation",
    "names_tables",
    ".loc",
    "ui\\ancillaries",
    "ui/ancillaries",
]


@dataclass(frozen=True)
class PackProbe:
    path: str
    size_bytes: int
    magic: str
    is_total_war_pack: bool
    candidate_paths: list[str]
    files_count: int | None = None
    pack_type: str | None = None
    data_offset: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sizeBytes": self.size_bytes,
            "magic": self.magic,
            "isTotalWarPack": self.is_total_war_pack,
            "packType": self.pack_type,
            "filesCount": self.files_count,
            "dataOffset": self.data_offset,
            "candidatePaths": self.candidate_paths,
        }


def probe_pack(path: Path, limit: int = 200) -> PackProbe:
    with path.open("rb") as handle:
        magic_bytes = handle.read(4)

    magic = magic_bytes.decode("ascii", errors="replace")
    candidates: list[str]
    files_count = None
    pack_type = None
    data_offset = None
    if magic.startswith("PFH"):
        index = read_pfh_index(path)
        files_count = index.files_count
        pack_type = index.pack_type
        data_offset = index.data_offset
        candidates = _filter_candidates([entry.path for entry in index.entries], limit)
    else:
        candidates = _filter_candidates(_iter_ascii_strings(path), limit)

    return PackProbe(
        path=str(path),
        size_bytes=os.path.getsize(path),
        magic=magic,
        is_total_war_pack=magic.startswith("PFH"),
        candidate_paths=candidates,
        files_count=files_count,
        pack_type=pack_type,
        data_offset=data_offset,
    )


def _filter_candidates(values, limit: int) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    lowered_patterns = [pattern.lower() for pattern in CANDIDATE_PATTERNS]
    for value in values:
        lowered = value.lower()
        if any(pattern in lowered for pattern in lowered_patterns):
            if value not in seen:
                candidates.append(value)
                seen.add(value)
            if len(candidates) >= limit:
                break
    return candidates


def _iter_ascii_strings(path: Path, min_length: int = 4, chunk_size: int = 1024 * 1024):
    buffer = bytearray()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            for byte in chunk:
                if 32 <= byte <= 126:
                    buffer.append(byte)
                else:
                    if len(buffer) >= min_length:
                        yield buffer.decode("ascii", errors="ignore")
                    buffer.clear()
    if len(buffer) >= min_length:
        yield buffer.decode("ascii", errors="ignore")
