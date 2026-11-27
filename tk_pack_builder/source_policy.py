"""The editor's supported source boundary: vanilla (including DLC) and MTU."""
from __future__ import annotations

from pathlib import Path
from dataclasses import asdict, is_dataclass
from typing import Any
from .source_profiles import current, BASE, directory

PROFILE = "vanilla-mtu-v1"
EXCLUDED_TEMPLATE_KEYS = frozenset({'3k_mtu_template_historical_lady_buyeo_wol_hero_water'})
MATERIAL_DIRECTORY = "vanilla_mtu"
REFERENCE_PACK = "mtu_vanilla_reference.pack"
VANILLA_PACKS = frozenset({
    "database.pack", "data.pack", "fast.pack", "data_mh.pack", "data_ep.pack",
    "data_dlc06.pack", "data_dlc07.pack", "data_bl.pack", "data_yt_bl.pack",
    "local_kr.pack", "local_en.pack",
})
MTU_PACKS = frozenset({"my_hero.pack", "[mod]mtu_original_v_0_0_2.pack",
                       "[mod]mtu_original_v_0_0_2_korean.pack"})
FOREIGN_MARKERS = ("ironic_", "190_expanded", "190expande", "korea_addon",
                   "korea_template_", "korea_tweak", "korea_generics",
                   "korean_unique", "korean_unque", "3k_mod_template_")


def source_name(value: str | Path) -> str:
    return str(value).replace("\\", "/").rsplit("/", 1)[-1].lower()


def supported_source(value: str | Path, *, reference: bool = False) -> bool:
    name = source_name(value)
    if current() != BASE and name in {'!!190_expanded_with_characters.pack', '!!190_expanded_overhauladdition.pack', '!!190_expanded_region.pack', '!!190_expanded_kr.pack'}:
        return True
    if current() == '190-korea' and name == '!!190expande_korea_addon.pack':
        return True
    return name in VANILLA_PACKS | MTU_PACKS or (reference and name == REFERENCE_PACK)


def require_supported_sources(paths: list[Path]) -> None:
    rejected = [str(path) for path in paths if not supported_source(path, reference=True)]
    if rejected:
        raise ValueError("바닐라·MTU 전용 모드에서 지원하지 않는 참조 팩입니다: " + ", ".join(rejected))


def foreign_reference(value: Any) -> str | None:
    if is_dataclass(value):
        return foreign_reference(asdict(value))
    if isinstance(value, dict):
        for key, item in value.items():
            # Labels are user-authored text, not references into a game DB.
            if key in {"name", "display_name", "description", "label", "new_name"}:
                continue
            found = foreign_reference(item)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = foreign_reference(item)
            if found:
                return found
    elif isinstance(value, str):
        markers = FOREIGN_MARKERS if current() == BASE else ()
        if value in EXCLUDED_TEMPLATE_KEYS or any(marker in value.lower() for marker in markers):
            return value
    return None


def require_clean_references(value: Any) -> None:
    if current() != BASE:
        from .title_registry import registry
        blocked = set(registry().get('blockedKeys', []))
        def inspect(item):
            if is_dataclass(item): item = asdict(item)
            if isinstance(item, dict): return any(inspect(v) for v in item.values())
            if isinstance(item, (tuple, list)): return any(inspect(v) for v in item)
            return isinstance(item, str) and item in blocked
        if inspect(value):
            raise ValueError('검수에서 누락·충돌이 확인되어 격리된 데이터입니다. 기준 장수 또는 스킬을 다시 선택하세요.')
    found = foreign_reference(value)
    if found:
        if found in EXCLUDED_TEMPLATE_KEYS:
            raise ValueError(f"불완전하여 제외된 장수 데이터입니다: {found}. 기준 장수를 다시 선택하세요.")
        raise ValueError(f"바닐라·MTU에서 사용할 수 없는 모드 참조입니다: {found}. 기준 장수·장비를 다시 선택하세요.")


def require_clean_materials(payload: dict[str, Any]) -> None:
    if payload.get('sourceProfile', PROFILE) != current():
        raise ValueError('선택한 모드 구성과 재료 DB가 일치하지 않습니다. 자료를 다시 적용하세요.')
    sources = payload.get("sources", [])
    rejected = [source for source in sources if not supported_source(source)]
    if rejected:
        raise ValueError("이 재료 DB에는 외부 모드가 섞여 있습니다. 바닐라·MTU 재료 DB를 다시 생성하세요: " + str(rejected[0]))
    for path, entry in payload.get("tables", {}).items():
        if '/character_generation_templates_tables/' in path:
            if any(row.get('key') in EXCLUDED_TEMPLATE_KEYS for row in entry.get('rows', [])):
                raise ValueError('불완전한 월 장수 데이터가 포함되어 있습니다. 내장 자료를 갱신하세요.')
        source = entry.get("sourcePath", "")
        if source and not supported_source(source):
            raise ValueError(f"지원하지 않는 재료 출처입니다: {source}")
        require_clean_references([path, entry.get("rows", [])])


def require_clean_pack(path: Path) -> None:
    """Inspect file paths and DB payloads too, so renaming a mixed pack is insufficient."""
    from .pfh import read_pfh_index, read_entry_bytes
    index = read_pfh_index(path)
    for entry in index.entries:
        require_clean_references(entry.path)
        if entry.path.replace("\\", "/").startswith(("db/", "ceo_db/")):
            data = read_entry_bytes(path, entry).lower()
            if any(marker.encode("ascii") in data for marker in FOREIGN_MARKERS):
                raise ValueError(f"외부 모드 DB 참조가 포함된 팩입니다: {path.name} ({entry.path})")
