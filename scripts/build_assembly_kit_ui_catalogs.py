from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSEMBLY_KIT_DB = Path(
    "E:/SteamLibrary/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/db"
)
DEFAULT_MATERIALS = ROOT / "work" / "internal_materials" / "materials.v015.json"
DEFAULT_SKILL_OUTPUT = ROOT / "tk_pack_builder" / "data" / "assembly_kit_skill_effects.ko.json"
DEFAULT_TITLE_OUTPUT = ROOT / "tk_pack_builder" / "data" / "assembly_kit_title_effects.ko.json"
DEFAULT_REPORT_OUTPUT = ROOT / "output" / "assembly_kit_ui_catalog_report.json"

_TRANSLATION_TOKENS = {
    "military_supplies": "군량",
    "public_order": "공공 질서",
    "map_province": "군",
    "map_provinces": "군",
    "map_region": "지역",
    "map_regions": "지역",
    "prime_minister": "승상",
    "only_if_faction_leader_factionwide": "(세력 지도자일 경우, 세력 전체)",
    "only_if_faction_leader": "(세력 지도자일 경우)",
    "only_if_minister": "(조정의 고관일 경우)",
}

_EFFECT_FALLBACKS = {
    "3k_main_character_wealth": "재산",
    "3k_main_effect_character_governor_independence_mod": "태수의 독립 성향",
    "3k_main_effect_character_salary_mod_hidden": "봉급",
    "3k_main_effect_force_military_supplies_from_characters": "군량 %+n",
    "3k_main_effect_province_public_order_base": "공공 질서 %+n",
    "3k_main_effect_province_public_order_faction": "공공 질서 %+n",
    "3k_main_effect_province_public_order_from_administrators": "공공 질서 %+n",
    "3k_main_effect_province_public_order_from_characters": "공공 질서 %+n",
    "3k_main_effect_province_public_order_from_characters_minister": "공공 질서 %+n",
    "3k_main_effect_undercover_character_max_count_bonus": "첩자 배치 가능 인원 %+n",
    "3k_dlc04_effect_region_fervour_regional_characters": "지역 열의 %+n",
    "3k_dummy_effect_ceo_subcategory_armour_fire": "선봉장 갑옷 %+n",
}

_SKILL_NAME_FALLBACKS = {
    "3k_dlc04_custom_battle_loadout_caltrops_smokescreen": "마름쇠와 연막",
    "3k_dlc04_skill_unit_base_mod_imperial": "황실 부대 기본 보정",
    "3k_main_custom_battle_loadout_ammunitions_attribute": "탄약 속성",
    "3k_main_custom_battle_loadout_attribute_authority": "권위 효과 구성",
    "3k_main_custom_battle_loadout_attribute_cunning": "책략 효과 구성",
    "3k_main_custom_battle_loadout_attribute_expertise": "전문성 효과 구성",
    "3k_main_custom_battle_loadout_attribute_instinct": "본능 효과 구성",
    "3k_main_custom_battle_loadout_attribute_resolve": "결의 효과 구성",
    "3k_main_custom_battle_loadout_encourages": "격려",
    "3k_main_custom_battle_loadout_formations": "진형 구성",
    "3k_main_custom_battle_loadout_formations_commander": "지휘관 진형",
}

_PERCENT_ABILITY_STATS = {
    "stat_missile_block_chance",
    "stat_resistance_all",
    "stat_resistance_fire",
    "stat_resistance_magic",
    "stat_resistance_missile",
    "stat_resistance_physical",
}

_ABILITY_ATTRIBUTE_FALLBACKS = {
    "unspottable": (
        "발견 불가 — 현재 위치에서 은신할 수 있다면 "
        "적이 아주 가까이 접근하기 전까지 발각되지 않습니다."
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Korean skill/title UI catalogs from Three Kingdoms Assembly Kit DB XML."
    )
    parser.add_argument("--assembly-kit-db", type=Path, default=DEFAULT_ASSEMBLY_KIT_DB)
    parser.add_argument("--materials", type=Path, default=DEFAULT_MATERIALS)
    parser.add_argument("--skill-output", type=Path, default=DEFAULT_SKILL_OUTPUT)
    parser.add_argument("--title-output", type=Path, default=DEFAULT_TITLE_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_OUTPUT)
    args = parser.parse_args()

    loc_text = load_merged_loc(args.materials)
    effect_rows = keyed_rows(args.assembly_kit_db / "effects.xml", "effects", "effect")
    scope_rows = loc_text
    ability_catalog = build_ability_effect_catalog(args.assembly_kit_db, loc_text)

    skill_entries = build_skill_entries(
        args.assembly_kit_db,
        loc_text,
        effect_rows,
        scope_rows,
        ability_catalog,
    )
    title_entries = build_title_entries(
        args.assembly_kit_db,
        loc_text,
        effect_rows,
        scope_rows,
        ability_catalog,
    )

    write_json(args.skill_output, skill_entries)
    write_json(args.title_output, title_entries)

    report = {
        "assemblyKitDb": str(args.assembly_kit_db.resolve()),
        "materials": str(args.materials.resolve()),
        "skillOutput": str(args.skill_output.resolve()),
        "titleOutput": str(args.title_output.resolve()),
        "skillCount": len(skill_entries),
        "skillKoreanNameCount": sum(contains_hangul(row.get("name")) for row in skill_entries),
        "skillEffectCount": sum(bool(row.get("effectSummary")) for row in skill_entries),
        "abilityGrantEffectCount": len(ability_catalog),
        "abilityDetailCount": sum(len(rows) for rows in ability_catalog.values()),
        "titleCount": len(title_entries),
        "titleKoreanNameCount": sum(contains_hangul(row.get("title")) for row in title_entries),
        "titleEffectCount": sum(bool(row.get("effects")) for row in title_entries),
    }
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def load_merged_loc(materials_path: Path) -> dict[str, str]:
    payload = json.loads(materials_path.read_text(encoding="utf-8"))
    merged: dict[str, str] = {}
    for entry in payload.get("loc", {}).values():
        if not isinstance(entry, dict):
            continue
        for key, value in (entry.get("rows") or {}).items():
            merged[str(key)] = str(value)
    return merged


def xml_rows(path: Path, row_tag: str) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    root = ET.parse(path).getroot()
    return [
        {child.tag: str(child.text or "").strip() for child in row}
        for row in root.findall(row_tag)
    ]


def optional_xml_rows(path: Path, row_tag: str) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return xml_rows(path, row_tag)


def keyed_rows(path: Path, row_tag: str, key_field: str) -> dict[str, dict[str, str]]:
    return {
        row[key_field]: row
        for row in xml_rows(path, row_tag)
        if row.get(key_field)
    }


def build_ability_effect_catalog(
    assembly_db: Path,
    loc_text: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve campaign effects that grant battle abilities to their mechanics."""
    grant_rows = optional_xml_rows(
        assembly_db / "effect_bonus_value_unit_ability_junctions.xml",
        "effect_bonus_value_unit_ability_junctions",
    )
    ability_rows = {
        row["key"]: row
        for row in optional_xml_rows(assembly_db / "unit_abilities.xml", "unit_abilities")
        if row.get("key")
    }
    special_rows = {
        row["key"]: row
        for row in optional_xml_rows(
            assembly_db / "unit_special_abilities.xml",
            "unit_special_abilities",
        )
        if row.get("key")
    }
    stat_localisation_keys = {
        row["stat_key"]: row.get("localisation", "")
        for row in optional_xml_rows(
            assembly_db / "modifiable_unit_stats.xml",
            "modifiable_unit_stats",
        )
        if row.get("stat_key")
    }
    phase_rows = {
        row["id"]: row
        for row in optional_xml_rows(
            assembly_db / "special_ability_phases.xml",
            "special_ability_phases",
        )
        if row.get("id")
    }

    phase_keys_by_ability: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in optional_xml_rows(
        assembly_db / "special_ability_to_special_ability_phase_junctions.xml",
        "special_ability_to_special_ability_phase_junctions",
    ):
        ability_key = row.get("special_ability", "")
        phase_key = row.get("phase", "")
        if ability_key and phase_key:
            phase_keys_by_ability[ability_key].append(
                (int(numeric_value(row.get("order")) or 0), phase_key)
            )

    stats_by_phase: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in optional_xml_rows(
        assembly_db / "special_ability_phase_stat_effects.xml",
        "special_ability_phase_stat_effects",
    ):
        stats_by_phase[row.get("phase", "")].append(row)

    attributes_by_phase: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in optional_xml_rows(
        assembly_db / "special_ability_phase_attribute_effects.xml",
        "special_ability_phase_attribute_effects",
    ):
        attributes_by_phase[row.get("phase", "")].append(row)

    details_by_ability: dict[str, dict[str, Any]] = {}
    for ability_key in {
        row.get("unit_ability", "")
        for row in grant_rows
        if row.get("bonus_value_id") == "enable"
    }:
        if not ability_key:
            continue
        phases = [
            phase_rows[phase_key]
            for _, phase_key in sorted(phase_keys_by_ability.get(ability_key, []))
            if phase_key in phase_rows
        ]
        phase_keys = [row.get("id", "") for row in phases]
        details_by_ability[ability_key] = build_ability_detail(
            ability_key,
            ability_rows.get(ability_key, {}),
            special_rows.get(ability_key, {}),
            phases,
            [
                row
                for phase_key in phase_keys
                for row in stats_by_phase.get(phase_key, [])
            ],
            [
                row
                for phase_key in phase_keys
                for row in attributes_by_phase.get(phase_key, [])
            ],
            loc_text,
            stat_localisation_keys,
        )

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in grant_rows:
        if row.get("bonus_value_id") != "enable":
            continue
        effect_key = row.get("effect", "")
        ability_key = row.get("unit_ability", "")
        detail = details_by_ability.get(ability_key)
        if effect_key and detail and detail not in result[effect_key]:
            result[effect_key].append(detail)
    return dict(result)


def build_ability_detail(
    ability_key: str,
    ability_row: dict[str, str],
    special_row: dict[str, str],
    phases: list[dict[str, str]],
    stat_rows: list[dict[str, str]],
    attribute_rows: list[dict[str, str]],
    loc_text: dict[str, str],
    stat_localisation_keys: dict[str, str],
) -> dict[str, Any]:
    name = preferred_localised_text(
        loc_text,
        f"unit_abilities_onscreen_name_{ability_key}",
        ability_row.get("onscreen_name", ""),
        fallback=humanize_key(ability_key),
    )
    description = preferred_localised_text(
        loc_text,
        f"unit_abilities_tooltip_text_{ability_key}",
        ability_row.get("tooltip_text", ""),
    )
    ability_type = clean_ui_text(
        loc_text.get(f"unit_ability_types_onscreen_name_{ability_key}", "")
    )

    mechanics: list[str] = []
    if len(phases) > 1:
        for index, phase in enumerate(phases, start=1):
            phase_key = phase.get("id", "")
            phase_mechanics = [
                format_ability_stat(row, loc_text, stat_localisation_keys)
                for row in stat_rows
                if row.get("phase") == phase_key
            ]
            phase_mechanics.extend(
                format_ability_attribute(row, loc_text)
                for row in attribute_rows
                if row.get("phase") == phase_key
            )
            phase_mechanics.extend(format_phase_mechanics(phase))
            phase_mechanics = dedupe_preserving_order(phase_mechanics)
            duration = numeric_value(phase.get("duration"))
            duration_text = (
                f" ({format_number(duration, signed=False)}초)"
                if duration is not None and duration > 0
                else ""
            )
            if phase_mechanics:
                mechanics.append(
                    f"{index}단계{duration_text}: " + ", ".join(phase_mechanics)
                )
    else:
        for row in stat_rows:
            text = format_ability_stat(row, loc_text, stat_localisation_keys)
            if text:
                mechanics.append(text)
        for row in attribute_rows:
            text = format_ability_attribute(row, loc_text)
            if text:
                mechanics.append(text)
        for phase in phases:
            mechanics.extend(format_phase_mechanics(phase))
    mechanics.extend(format_special_ability_mechanics(special_row))
    mechanics = dedupe_preserving_order(mechanics)

    timing = ability_timing_text(special_row, phases)
    target = ability_target_text(special_row, phases)
    if timing == "상시 효과" and ability_type.startswith("상시"):
        timing = ""
    detail_parts = dedupe_preserving_order(
        part
        for part in (
            description,
            ability_type,
            target,
            timing,
            *mechanics,
        )
        if part and clean_ui_text(part).lower() != clean_ui_text(name).lower()
    )
    summary = f"능력: {name}"
    if detail_parts:
        summary += " — " + " · ".join(detail_parts)
    return {
        "abilityKey": ability_key,
        "name": name,
        "description": description,
        "type": ability_type,
        "target": target,
        "timing": timing,
        "mechanics": mechanics,
        "summary": summary,
    }


def format_ability_stat(
    row: dict[str, str],
    loc_text: dict[str, str],
    stat_localisation_keys: dict[str, str],
) -> str:
    stat_key = row.get("stat", "")
    value = numeric_value(row.get("value"))
    if not stat_key or value is None:
        return ""
    localisation_key = stat_localisation_keys.get(stat_key) or stat_key
    name = clean_ui_text(
        loc_text.get(f"unit_stat_localisations_onscreen_name_{localisation_key}")
        or loc_text.get(f"unit_stat_localisations_abbreviated_name_{localisation_key}")
        or humanize_key(stat_key)
    )
    how = row.get("how", "").lower()
    if how == "mult":
        value_text = f"×{format_number(value, signed=False)}"
    elif stat_key in _PERCENT_ABILITY_STATS:
        value_text = f"{format_number(value, signed=True)}%"
    else:
        value_text = format_number(value, signed=True)
    return f"{name} {value_text}".strip()


def format_ability_attribute(row: dict[str, str], loc_text: dict[str, str]) -> str:
    attribute = row.get("attribute", "")
    if not attribute:
        return ""
    fallback = _ABILITY_ATTRIBUTE_FALLBACKS.get(attribute, "")
    name = clean_ui_text(
        loc_text.get(f"unit_attributes_imued_effect_text_{attribute}")
        or fallback
        or humanize_key(attribute)
    )
    text = clean_ui_text(loc_text.get(f"unit_attributes_bullet_text_{attribute}") or name)
    if fallback and (not contains_hangul(text) or text.lower() == "placeholder"):
        return fallback
    if name and text.startswith(name) and text != name:
        text = f"{name} — {text[len(name):].strip()}"
    if row.get("attribute_type", "").lower() == "negative" and text:
        return f"{text} (해제)"
    return text


def format_phase_mechanics(phase: dict[str, str]) -> list[str]:
    result: list[str] = []
    numeric_fields = (
        ("ability_recharge_change", "능력 재사용 시간", "초"),
        ("damage_amount", "피해", ""),
        ("damage_chance", "피해 확률", "%"),
        ("heal_amount", "회복량", ""),
        ("fatigue_change_ratio", "피로 변화", ""),
        ("inspiration_aura_range_mod", "격려 범위", ""),
    )
    for field, name, suffix in numeric_fields:
        value = numeric_value(phase.get(field))
        if value not in {None, 0}:
            result.append(f"{name} {format_number(value, signed=True)}{suffix}")
    if phase.get("unbreakable") == "1":
        result.append("불굴")
    if phase.get("cant_move") == "1":
        result.append("이동 불가")
    if phase.get("freeze_fatigue") == "1":
        result.append("피로 고정")
    if phase.get("imbue_magical") == "1":
        result.append("마법 피해 부여")
    if phase.get("imbue_ignition") == "1":
        result.append("점화 부여")
    if phase.get("resurrect") == "1":
        result.append("전투원 부활")
    return result


def format_special_ability_mechanics(row: dict[str, str]) -> list[str]:
    if not row:
        return []
    result: list[str] = []
    splash_damage = numeric_value(row.get("splash_attack_damage"))
    if splash_damage not in {None, 0}:
        result.append(f"특수 공격 피해 {format_number(splash_damage, signed=False)}")
    uses = numeric_value(row.get("num_uses"))
    if uses is not None and uses > 0:
        result.append(f"전투당 {format_number(uses, signed=False)}회")
    hp_cost = numeric_value(row.get("hp_cost"))
    if hp_cost is not None and hp_cost > 0:
        suffix = "%" if row.get("hp_cost_is_percentage") == "1" else ""
        result.append(f"체력 비용 {format_number(hp_cost, signed=False)}{suffix}")
    if row.get("activated_projectile"):
        result.append("투사체 공격")
    if row.get("bombardment"):
        result.append("포격 공격")
    if row.get("vortex"):
        result.append("범위 지속 공격")
    if row.get("spawned_unit"):
        result.append("부대 소환")
    return result


def ability_timing_text(
    special_row: dict[str, str],
    phases: list[dict[str, str]],
) -> str:
    if special_row.get("passive") == "1":
        return "상시 효과"
    durations = [
        value
        for value in (
            *(numeric_value(row.get("duration")) for row in phases),
            numeric_value(special_row.get("active_time")),
        )
        if value is not None and value > 0
    ]
    recharges = [
        value
        for value in (
            *(numeric_value(row.get("recharge_time")) for row in phases),
            numeric_value(special_row.get("recharge_time")),
        )
        if value is not None and value > 0
    ]
    parts: list[str] = []
    if durations:
        parts.append(f"지속 {format_number(max(durations), signed=False)}초")
    if recharges:
        parts.append(f"재사용 {format_number(max(recharges), signed=False)}초")
    return " / ".join(parts)


def ability_target_text(
    special_row: dict[str, str],
    phases: list[dict[str, str]],
) -> str:
    if not special_row and not phases:
        return ""
    affects_allies = any(row.get("affects_allies") == "1" for row in phases)
    affects_enemies = any(row.get("affects_enemies") == "1" for row in phases)
    affects_self = (
        special_row.get("affect_self") == "1"
        or special_row.get("target_self") == "1"
    )
    effect_range = numeric_value(special_row.get("effect_range"))
    intercept_range = numeric_value(special_row.get("target_intercept_range"))
    radius = effect_range if effect_range is not None and effect_range > 0 else intercept_range

    targets: list[str] = []
    if affects_self:
        targets.append("자신")
    if effect_range == -1:
        if affects_allies:
            targets.append("모든 아군")
        if affects_enemies:
            targets.append("모든 적군")
    elif radius is not None and radius > 0:
        if affects_allies:
            targets.append(
                f"범위 {format_number(radius, signed=False)}m 내 아군"
            )
        if affects_enemies:
            targets.append(
                f"범위 {format_number(radius, signed=False)}m 내 적군"
            )
    else:
        if affects_allies or special_row.get("target_friends") == "1":
            targets.append("아군")
        if affects_enemies or special_row.get("target_enemies") == "1":
            targets.append("적군")
    if special_row.get("target_ground") == "1":
        targets.append("지면")
    return "대상: " + " 및 ".join(dedupe_preserving_order(targets)) if targets else ""


def build_skill_entries(
    assembly_db: Path,
    loc_text: dict[str, str],
    effect_rows: dict[str, dict[str, str]],
    scope_rows: dict[str, str],
    ability_catalog: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    skills = xml_rows(assembly_db / "character_skills.xml", "character_skills")
    junctions = xml_rows(
        assembly_db / "character_skill_level_to_effects_junctions.xml",
        "character_skill_level_to_effects_junctions",
    )
    effects_by_skill: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in junctions:
        effects_by_skill[row.get("character_skill_key", "")].append(row)

    entries: list[dict[str, Any]] = []
    for row in skills:
        key = row.get("key", "")
        if not key:
            continue
        name = preferred_localised_text(
            loc_text,
            f"character_skills_localised_name_{key}",
            row.get("localised_name", ""),
            fallback=humanize_key(key),
        )
        if not contains_hangul(name) and key in _SKILL_NAME_FALLBACKS:
            name = _SKILL_NAME_FALLBACKS[key]
        description = preferred_localised_text(
            loc_text,
            f"character_skills_localised_description_{key}",
            row.get("localised_description", ""),
        )
        description = korean_skill_description(key, name, description, loc_text)
        effect_lines, structured_effects = summarize_effect_relations(
            effects_by_skill.get(key, []),
            effect_rows,
            scope_rows,
            level_field="level",
            ability_catalog=ability_catalog,
        )
        entries.append(
            {
                "key": key,
                "name": name,
                "description": description,
                "effectSummary": " / ".join(effect_lines),
                "effects": effect_lines,
                "effectRows": structured_effects,
                "element": element_from_text(key),
                "source": source_label(key),
                "sourceKind": "assembly_kit",
            }
        )
    return sorted(entries, key=lambda item: str(item["key"]))


def build_title_entries(
    assembly_db: Path,
    loc_text: dict[str, str],
    effect_rows: dict[str, dict[str, str]],
    scope_rows: dict[str, str],
    ability_catalog: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    nodes = xml_rows(assembly_db / "ceo_nodes.xml", "ceo_nodes")
    junctions = xml_rows(
        assembly_db / "ceo_effect_list_to_effects.xml",
        "ceo_effect_list_to_effects",
    )
    effects_by_list: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in junctions:
        effects_by_list[row.get("effect_list", "")].append(row)

    entries: list[dict[str, Any]] = []
    for row in nodes:
        key = row.get("key", "")
        if "_ceo_node_career_" not in key:
            continue
        title = preferred_localised_text(
            loc_text,
            f"ceo_nodes_title_{key}",
            row.get("title", ""),
            fallback=humanize_key(key),
        )
        description = preferred_localised_text(
            loc_text,
            f"ceo_nodes_description_{key}",
            row.get("description", ""),
        )
        effect_lines, structured_effects = summarize_effect_relations(
            effects_by_list.get(row.get("ceo_effect_list", ""), []),
            effect_rows,
            scope_rows,
            ability_catalog=ability_catalog,
        )
        if not effect_lines and title.strip().lower() == "placeholder":
            continue
        entries.append(
            {
                "key": key,
                "keys": title_aliases(key),
                "title": title,
                "description": description,
                "category": "어셈블리킷 칭호",
                "effects": effect_lines,
                "effectRows": structured_effects,
                "sourceKind": "assembly_kit",
            }
        )
    return sorted(entries, key=lambda item: str(item["key"]))


def summarize_effect_relations(
    relations: list[dict[str, str]],
    effect_rows: dict[str, dict[str, str]],
    loc_text: dict[str, str],
    *,
    level_field: str = "",
    ability_catalog: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    grouped: dict[int, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    structured: list[dict[str, Any]] = []
    has_real_ability_grant = any(
        bool((ability_catalog or {}).get(
            relation.get("effect_key") or relation.get("effect") or ""
        ))
        for relation in relations
    )
    for relation in relations:
        effect_key = relation.get("effect_key") or relation.get("effect") or ""
        if not effect_key or "ai_hint" in effect_key.lower():
            continue
        if has_real_ability_grant and "_dummy_skill_" in effect_key.lower():
            continue
        raw_value = relation.get("value", "")
        value = numeric_value(raw_value)
        effect_row = effect_rows.get(effect_key, {})
        # Assembly Kit explicitly documents priority 0 as hidden from the UI.
        # These rows are AI hints, item subcategory markers, or other engine
        # bookkeeping and should not be presented as player-facing effects.
        if str(effect_row.get("priority") or "").strip() == "0":
            continue
        abilities = (ability_catalog or {}).get(effect_key, [])
        label = (
            " / ".join(str(ability.get("summary") or "") for ability in abilities)
            if abilities
            else effect_text(effect_key, effect_row, loc_text, value)
        )
        if not label:
            continue
        scope_key = relation.get("effect_scope", "")
        scope = scope_text(scope_key, loc_text)
        line = f"{label} {scope}".strip()
        level = int(numeric_value(relation.get(level_field, "1")) or 1) if level_field else 1
        detail = {
            "effectKey": effect_key,
            "name": clean_ui_text(
                _EFFECT_FALLBACKS.get(effect_key)
                or loc_text.get(f"effects_description_{effect_key}")
                or effect_row.get("description")
                or humanize_key(effect_key)
            ),
            "scopeKey": scope_key,
            "scope": scope,
            "level": level,
            "value": value,
            "text": line,
        }
        if abilities:
            detail["abilities"] = abilities
        grouped[level].append((line, detail))
        structured.append(detail)

    levels = sorted(grouped)
    multiple_levels = len(levels) > 1
    lines: list[str] = []
    for level in levels:
        values = dedupe_preserving_order(line for line, _ in grouped[level])
        prefix = f"{level}단계: " if multiple_levels else ""
        lines.append(prefix + " · ".join(values))
    return lines, structured


def effect_text(
    key: str,
    row: dict[str, str],
    loc_text: dict[str, str],
    value: int | float | None,
) -> str:
    raw = (
        _EFFECT_FALLBACKS.get(key)
        or loc_text.get(f"effects_description_{key}")
        or row.get("description")
        or ""
    )
    if not raw or raw.strip().upper() in {"[HIDDEN]", "HIDDEN", "PLACEHOLDER"}:
        return ""
    text = clean_ui_text(raw, preserve_number_token=True)
    if not text:
        return ""
    if value is None:
        return clean_ui_text(text)

    signed = format_number(value, signed=True)
    plain = format_number(value, signed=False)
    replacements = (
        (r"%\+n%", f"{signed}%"),
        (r"%\+n", signed),
        (r"%-n%", f"{format_number(-value, signed=True)}%"),
        (r"%-n", format_number(-value, signed=True)),
        (r"%n%", f"{plain}%"),
        (r"%n", plain),
    )
    replaced = False
    for pattern, replacement in replacements:
        text, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)
        replaced = replaced or bool(count)
    if not replaced:
        if value in {0, 1} and any(
            token in key.lower()
            for token in ("ability", "enable", "unlock", "permission")
        ):
            return clean_ui_text(text)
        text = f"{text} {signed}"
    return clean_ui_text(text)


def scope_text(scope_key: str, loc_text: dict[str, str]) -> str:
    if not scope_key or scope_key == "default":
        return ""
    text = clean_ui_text(
        loc_text.get(f"campaign_effect_scopes_localised_text_{scope_key}", "")
    )
    if text:
        return text
    fallbacks = {
        "character_to_character_provincewide": "(현지 군)",
        "character_to_character_factionwide": "(세력 전체)",
        "character_to_faction_own": "(소속 세력)",
        "character_to_force_own": "(해당 군대)",
        "character_to_province_own": "(해당 군)",
    }
    return fallbacks.get(scope_key, "")


def preferred_localised_text(
    loc_text: dict[str, str],
    loc_key: str,
    source_text: str,
    *,
    fallback: str = "",
) -> str:
    localised = clean_ui_text(loc_text.get(loc_key, ""))
    if contains_hangul(localised):
        return localised
    source = clean_ui_text(source_text)
    return localised or source or fallback


def korean_skill_description(
    key: str,
    name: str,
    description: str,
    loc_text: dict[str, str],
) -> str:
    if not description or contains_hangul(description):
        return description
    if "_archive_skill_" in key:
        suffix = key.split("_archive_skill_", 1)[1]
        for prefix in (
            "3k_main_ability_",
            "3k_dlc04_ability_",
            "3k_dlc05_ability_",
            "3k_dlc06_ability_",
            "3k_dlc07_ability_",
        ):
            text = clean_ui_text(
                loc_text.get(f"unit_abilities_tooltip_text_{prefix}{suffix}", "")
            )
            if contains_hangul(text):
                return text
    if "custom_battle_loadout" in key:
        return f"커스텀 전투에서 {name} 효과를 구성합니다."
    return f"{name}의 게임 내 효과입니다."


def clean_ui_text(value: Any, *, preserve_number_token: bool = False) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = re.sub(r"\[\[/?[a-z0-9_:\-]+(?:\s+[^\]]*)?\]\]", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\{\{tr:([^}]+)\}\}",
        lambda match: _TRANSLATION_TOKENS.get(match.group(1).lower(), match.group(1).replace("_", " ")),
        text,
        flags=re.IGNORECASE,
    )
    if not preserve_number_token:
        text = re.sub(r"%[+\-]?n%?", "", text, flags=re.IGNORECASE)
    text = text.replace("\\\\n", " ").replace("\\n", " ")
    text = text.replace("||", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text.strip(" ·-/")


def numeric_value(value: Any) -> int | float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def format_number(value: int | float, *, signed: bool) -> str:
    number = f"{value:g}"
    if signed and value > 0:
        return f"+{number}"
    return number


def contains_hangul(value: Any) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in str(value or ""))


def element_from_text(value: str) -> str:
    lowered = value.lower()
    for element in ("earth", "fire", "wood", "water", "metal"):
        if f"_{element}_" in lowered or lowered.endswith(f"_{element}"):
            return element
    return ""


def source_label(key: str) -> str:
    lowered = key.lower()
    if lowered.startswith("3k_main"):
        return "바닐라"
    if lowered.startswith(("3k_dlc", "3k_ytr", "ep_")):
        return "DLC"
    return "어셈블리킷"


def title_aliases(key: str) -> list[str]:
    aliases = [
        f"ceo_nodes_title_{key}",
        f"ceo_nodes_description_{key}",
    ]
    if "_ceo_node_career_" in key:
        career = re.sub(r"_\d\d$", "", key.replace("_ceo_node_career_", "_ceo_career_"))
        aliases.append(career)
        if "_ceo_career_historical_" in career:
            aliases.append(
                career.replace(
                    "_ceo_career_historical_",
                    "_ceo_initial_data_character_historical_",
                )
            )
    return dedupe_preserving_order(aliases)


def humanize_key(value: str) -> str:
    text = re.sub(
        r"^(?:3k_(?:main|dlc\d+|cp\d+|ytr)_|ep_)",
        "",
        str(value or "").lower(),
    )
    text = re.sub(
        r"^(?:ceo_node_career_|character_skill_|skill_|effect_)",
        "",
        text,
    )
    return " ".join(part.capitalize() for part in text.split("_") if part)


def dedupe_preserving_order(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
