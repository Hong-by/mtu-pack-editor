from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


FACTION_LABELS = {
    "ironic_faction_goguryeo": ("goguryeo", "고구려"),
    "ironic_faction_bakaja": ("baekje", "백제"),
    "ironic_faction_shitla": ("silla", "신라"),
    "ironic_faction_tamno": ("tamna", "탐라"),
    "ironic_faction_gaya": ("gaya", "가야"),
    "ironic_faction_buyeo": ("buyeo", "부여"),
    "ironic_faction_korea_ye": ("ye", "예"),
}

TEMPLATE_NAME_HINTS = {
    "gogukcheon": "고남무",
    "chogo": "부여초고",
    "beolhyu": "석벌휴",
    "hae_ganwigeo": "해간위거",
    "munseong": "문성",
    "yeonbul": "연불",
    "go_baekgo": "고백고",
    "go": "고",
    "go_balgi": "고발기",
    "go_yeonu": "고연우",
    "go_gyesu": "고계수",
    "an_ryo": "안류",
    "queen_woo": "왕후 우씨",
    "woo_so": "우소",
    "hae": "해",
    "jwagaryeo": "좌가려",
    "eobiryu": "어비류",
    "buyeo_giru": "부여기루",
    "buyeo_gaeru": "부여개루",
    "buyeo_jil": "부여질",
    "buyeo_gusu": "부여구수",
    "buyeo_goi": "부여고이",
    "buyeo_usu": "부여우수",
    "gilseon": "길선",
    "jin_gwa": "진과",
    "kim_suro": "김수로",
    "kim_geodeung": "김거등",
    "heo_hwangok": "허황옥",
    "tam_hari": "탐하리",
    "hae_mayeo": "해마여",
    "woo_wigeo": "우위거",
    "seok_goljeong": "석골정",
    "seok": "석",
    "seok_imae": "석이매",
    "seok_naehae": "석내해",
    "seok_cheomhae": "석첨해",
    "seok_jobun": "석조분",
    "mulgyeja": "물계자",
    "lady_seok": "석부인",
    "kim_gudo": "김구도",
    "gu_suhye": "구수혜",
    "lady_sulye": "술례부인",
    "heung_sun": "흥선",
    "seol_bu": "설부",
    "chung_hwon": "충훤",
    "yeon_jin": "연진",
    "yun_jong": "윤종",
    "seok_uro": "석우로",
    "seok_naleum": "석내음",
    "seok_aihyeo": "석아이혜",
    "kim_michu": "김미추",
    "kim_malgu": "김말구",
    "yieum": "이음",
    "guk_ryang": "국량",
    "sul_myeong": "술명",
    "go_seongbang": "고성방",
    "hoe_hoe": "회회",
    "hwon_gyeon": "훤견",
    "eul_paso": "을파소",
    "gang_hwon": "강훤",
    "myeongrim_eosu": "명림어수",
    "mil_u": "밀우",
    "deuk_rae": "득래",
    "yu_okgu": "유옥구",
    "hunyeo": "후녀",
    "go_uwigeo": "고우위거",
    "woo_du": "우두",
    "go_su": "고수",
    "yu_yu": "유유",
    "jin_ga": "진가",
    "yu_gi": "유기",
    "gon_no": "곤노",
    "buyeo_saban": "부여사반",
    "buyeo": "부여",
}

SPAWN_CALL_RE = re.compile(
    r'(spawn_and_promote|spawn_character_type_faction)\(\s*"(?P<faction>[^"]+)"\s*,\s*(?P<subtype_var>\w+)\s*,\s*"(?P<template>[^"]+)"',
    re.IGNORECASE,
)
CREATE_CALL_RE = re.compile(
    r'create_character_from_template\(\s*"general"\s*,\s*"(?P<subtype>3k_general_[^"]+)"\s*,\s*(?P<template_var>\w+|"(?:[^"]+)")',
    re.IGNORECASE,
)
LOCAL_TEMPLATE_RE = re.compile(r'local\s+(?P<name>\w+)\s*=\s*"(?P<template>3k_mod_template_[^"]+)"')
SAFE_SPAWN_RE = re.compile(
    r'Spawn(?P<faction>Goguryeo|Baekje|Silla)CharacterSafely\(\s*"(?P<subtype>3k_general_[^"]+)"\s*,\s*"(?P<template>3k_mod_template_[^"]+)"',
    re.IGNORECASE,
)
SUBTYPE_VARS = {
    "earth": "3k_general_earth",
    "fire": "3k_general_fire",
    "wood": "3k_general_wood",
    "metal": "3k_general_metal",
    "water": "3k_general_water",
}
SAFE_FACTIONS = {
    "goguryeo": "ironic_faction_goguryeo",
    "baekje": "ironic_faction_bakaja",
    "silla": "ironic_faction_shitla",
}


@dataclass(frozen=True)
class KoreaCharacterInfo:
    faction_key: str
    faction: str
    faction_label: str
    role: str
    subtype: str
    source_script: str
    display_name_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "isKoreaAddon": True,
            "koreaFactionKey": self.faction_key,
            "koreaFaction": self.faction,
            "koreaFactionLabel": self.faction_label,
            "koreaRole": self.role,
            "koreaSubtype": self.subtype,
            "koreaSourceScript": self.source_script,
            "koreaDisplayNameHint": self.display_name_hint,
        }


@lru_cache(maxsize=1)
def korea_character_index() -> dict[str, dict[str, Any]]:
    root = Path(__file__).resolve().parents[1]
    script_root = root / "work" / "korea_mechanics_extract" / "!!190expande_korea_addon" / "script" / "campaign"
    if not script_root.is_dir():
        return {}

    index: dict[str, KoreaCharacterInfo] = {}
    for path in sorted(script_root.rglob("*.lua")):
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue
        _collect_spawn_calls(index, path, text)
        _collect_safe_spawn_calls(index, path, text)
        _collect_create_calls(index, path, text)
    return {key: value.to_dict() for key, value in index.items()}


def korea_character_metadata(template_key: str) -> dict[str, Any] | None:
    return korea_character_index().get(_normalize_template_key(template_key))


def _collect_spawn_calls(index: dict[str, KoreaCharacterInfo], path: Path, text: str) -> None:
    for match in SPAWN_CALL_RE.finditer(text):
        faction_key = match.group("faction")
        if faction_key not in FACTION_LABELS:
            continue
        role = "leader" if match.group(1).lower() == "spawn_and_promote" else "general"
        _add_entry(
            index,
            template_key=match.group("template"),
            faction_key=faction_key,
            role=role,
            subtype=SUBTYPE_VARS.get(match.group("subtype_var"), ""),
            path=path,
        )


def _collect_safe_spawn_calls(index: dict[str, KoreaCharacterInfo], path: Path, text: str) -> None:
    for match in SAFE_SPAWN_RE.finditer(text):
        faction_key = SAFE_FACTIONS.get(match.group("faction").lower())
        if not faction_key:
            continue
        _add_entry(
            index,
            template_key=match.group("template"),
            faction_key=faction_key,
            role="event",
            subtype=match.group("subtype"),
            path=path,
        )


def _collect_create_calls(index: dict[str, KoreaCharacterInfo], path: Path, text: str) -> None:
    local_templates = {
        match.group("name"): match.group("template")
        for match in LOCAL_TEMPLATE_RE.finditer(text)
    }
    for match in CREATE_CALL_RE.finditer(text):
        template_ref = match.group("template_var")
        template_key = template_ref.strip('"') if template_ref.startswith('"') else local_templates.get(template_ref, "")
        if not template_key:
            continue
        faction_key = _nearby_faction_key(text, match.start())
        if faction_key not in FACTION_LABELS:
            continue
        _add_entry(
            index,
            template_key=template_key,
            faction_key=faction_key,
            role="event",
            subtype=match.group("subtype"),
            path=path,
        )


def _nearby_faction_key(text: str, position: int) -> str:
    window = text[max(0, position - 600):position]
    matches = re.findall(r'"(ironic_faction_[a-z0-9_]+)"', window, flags=re.IGNORECASE)
    for value in reversed(matches):
        if value in FACTION_LABELS:
            return value
    return ""


def _add_entry(
    index: dict[str, KoreaCharacterInfo],
    template_key: str,
    faction_key: str,
    role: str,
    subtype: str,
    path: Path,
) -> None:
    normalized_key = _normalize_template_key(template_key)
    if not normalized_key or normalized_key in index:
        return
    faction, faction_label = FACTION_LABELS[faction_key]
    index[normalized_key] = KoreaCharacterInfo(
        faction_key=faction_key,
        faction=faction,
        faction_label=faction_label,
        role=role,
        subtype=subtype,
        source_script=path.name,
        display_name_hint=_display_name_hint(normalized_key),
    )


def _normalize_template_key(value: str) -> str:
    return str(value or "").strip().lower()


def _display_name_hint(template_key: str) -> str:
    token = template_key
    for prefix in ("3k_mod_template_historical_", "3k_mod_template_dummy_hero_"):
        token = token.removeprefix(prefix)
    for suffix in ("_hero_earth", "_hero_fire", "_hero_metal", "_hero_water", "_hero_wood", "_earth", "_fire", "_metal", "_water", "_wood"):
        token = token.removesuffix(suffix)
    return TEMPLATE_NAME_HINTS.get(token.lower(), "")
