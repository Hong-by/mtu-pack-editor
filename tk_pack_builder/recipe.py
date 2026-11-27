from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StatPatch:
    equipment_key: str
    stat_table: str
    column: str
    value: Any
    game_mode: str | None = None


@dataclass(frozen=True)
class LandUnitClone:
    source_key: str
    new_key: str
    overrides: dict[str, Any]
    source_retinue_key: str | None = None
    new_retinue_key: str | None = None


@dataclass(frozen=True)
class ArmourTypeClone:
    source_key: str
    new_key: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class SkillSetClone:
    source_set_key: str
    new_set_key: str
    replacements: dict[str, str]
    armour_bonus: int = 0
    melee_defence_bonus: int = 0
    melee_attack_bonus: int = 0
    melee_damage_bonus: int = 0
    ap_melee_damage_bonus: int = 0
    charge_bonus: int = 0
    missile_defence_bonus: int = 0


@dataclass(frozen=True)
class AttributeSetClone:
    source_set_key: str
    new_set_key: str
    overrides: dict[str, int | float]


@dataclass(frozen=True)
class AgeRangeClone:
    source_key: str
    new_key: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class DedicatedArmourAssignment:
    source_ceo_key: str
    source_initial_ceo_key: str
    source_armour_type_key: str
    armour_value: int
    source_armour_value: int | None = None
    pool_id: str = ""
    slot_id: str = ""
    armour_ceo_key: str = ""
    initial_ceo_key: str = ""
    armour_type_key: str = ""
    melee_defence_bonus: int = 0
    melee_attack_bonus: int = 0
    melee_damage_bonus: int = 0
    ap_melee_damage_bonus: int = 0
    charge_bonus: int = 0
    missile_defence_bonus: int = 0


@dataclass(frozen=True)
class CharacterClone:
    new_template_key: str
    source_template_key: str
    detail_source_template_key: str
    new_art_set_id: str | None
    art_set_source_id: str | None
    new_age_range_key: str | None
    age_range_source_key: str | None
    new_initial_ceo_key: str | None
    initial_ceo_source_key: str | None
    template_overrides: dict[str, Any]
    detail_overrides: dict[str, dict[str, Any]]
    art_set_overrides: dict[str, Any]
    art_overrides: dict[str, Any]
    age_range_overrides: dict[str, Any]
    spawn_event: str | None = None
    display_name: str | None = None
    image_assets: list[dict[str, str]] | None = None
    title_ceo_key: str | None = None
    removable_title_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    trait_set_key: str | None = None
    trait_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    removable_trait_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    equipment_set_key: str | None = None
    equipment_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    removable_equipment_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    default_equipment_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    dedicated_armour: DedicatedArmourAssignment | None = None


@dataclass(frozen=True)
class CharacterPatch:
    template_key: str
    template_overrides: dict[str, Any]
    detail_overrides: dict[str, dict[str, Any]]
    display_name: str | None = None
    image_assets: list[dict[str, str]] | None = None
    art_overrides: dict[str, Any] | None = None
    art_set_overrides: dict[str, Any] | None = None
    title_ceo_key: str | None = None
    removable_title_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    trait_set_key: str | None = None
    trait_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    removable_trait_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    equipment_set_key: str | None = None
    equipment_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    removable_equipment_ceo_keys: tuple[str, ...] = field(default_factory=tuple)
    default_equipment_ceo_keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Recipe:
    mod_name: str
    equipment_stat_patches: list[StatPatch] = field(default_factory=list)
    armour_type_clones: list[ArmourTypeClone] = field(default_factory=list)
    land_unit_clones: list[LandUnitClone] = field(default_factory=list)
    skill_set_clones: list[SkillSetClone] = field(default_factory=list)
    attribute_set_clones: list[AttributeSetClone] = field(default_factory=list)
    age_range_clones: list[AgeRangeClone] = field(default_factory=list)
    character_clones: list[CharacterClone] = field(default_factory=list)
    character_patches: list[CharacterPatch] = field(default_factory=list)
    work_items: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def load_recipe(path: Path) -> Recipe:
    data = json.loads(path.read_text(encoding="utf-8"))
    return recipe_from_dict(data)


def recipe_from_dict(data: dict[str, Any]) -> Recipe:
    data = _normalize_age_range_clones(data)
    data = _normalize_attribute_set_clones(data)
    patches = _coalesce_stat_patches([
        StatPatch(
            equipment_key=item["equipmentKey"],
            stat_table=item["statTable"],
            column=item["column"],
            value=item["value"],
            game_mode=item.get("gameMode"),
        )
        for item in data.get("equipmentStatPatches", [])
    ])
    land_unit_clones = [
        LandUnitClone(
            source_key=item["sourceKey"],
            new_key=item["newKey"],
            overrides=item.get("overrides", {}),
            source_retinue_key=item.get("sourceRetinueKey"),
            new_retinue_key=item.get("newRetinueKey"),
        )
        for item in data.get("landUnitClones", [])
    ]
    armour_type_clones = [
        ArmourTypeClone(
            source_key=item["sourceKey"],
            new_key=item["newKey"],
            overrides=item.get("overrides", {}),
        )
        for item in data.get("armourTypeClones", [])
    ]
    skill_set_clones = [
        SkillSetClone(
            source_set_key=item["sourceSetKey"],
            new_set_key=item["newSetKey"],
            replacements={
                str(replacement["nodeKey"]): str(replacement["skillKey"])
                for replacement in item.get("replacements", [])
                if replacement.get("nodeKey") and replacement.get("skillKey")
            },
            armour_bonus=int(item.get("armourBonus") or 0),
            melee_defence_bonus=int(item.get("meleeDefenceBonus") or 0),
            melee_attack_bonus=int(item.get("meleeAttackBonus") or 0),
            melee_damage_bonus=int(item.get("meleeDamageBonus") or 0),
            ap_melee_damage_bonus=int(item.get("apMeleeDamageBonus") or 0),
            charge_bonus=int(item.get("chargeBonus") or 0),
            missile_defence_bonus=int(item.get("missileDefenceBonus") or 0),
        )
        for item in data.get("skillSetClones", [])
    ]
    attribute_set_clones = [
        AttributeSetClone(
            source_set_key=item["sourceSetKey"],
            new_set_key=item["newSetKey"],
            overrides={
                str(key): value
                for key, value in item.get("overrides", {}).items()
                if isinstance(value, (int, float))
            },
        )
        for item in data.get("attributeSetClones", [])
    ]
    age_range_clones = [
        AgeRangeClone(
            source_key=item["sourceKey"],
            new_key=item["newKey"],
            overrides=item.get("overrides", {}),
        )
        for item in data.get("ageRangeClones", [])
    ]
    character_clones = [
        CharacterClone(
            new_template_key=item["newTemplateKey"],
            source_template_key=item["sourceTemplateKey"],
            detail_source_template_key=item.get("detailSourceTemplateKey", item["sourceTemplateKey"]),
            new_art_set_id=item.get("newArtSetId"),
            art_set_source_id=item.get("artSetSourceId"),
            new_age_range_key=item.get("newAgeRangeKey"),
            age_range_source_key=item.get("ageRangeSourceKey"),
            new_initial_ceo_key=item.get("newInitialCeoKey"),
            initial_ceo_source_key=item.get("initialCeoSourceKey"),
            template_overrides=item.get("templateOverrides", {}),
            detail_overrides=item.get("detailOverrides", {}),
            art_set_overrides=item.get("artSetOverrides", {}),
            art_overrides=item.get("artOverrides", {}),
            age_range_overrides=item.get("ageRangeOverrides", {}),
            spawn_event=item.get("spawnEvent"),
            display_name=item.get("displayName") or item.get("newName"),
            image_assets=item.get("imageAssets") or [],
            title_ceo_key=item.get("titleCeoKey"),
            removable_title_ceo_keys=_string_tuple(item.get("removableTitleCeoKeys")),
            trait_set_key=item.get("traitSetKey"),
            trait_ceo_keys=_string_tuple(item.get("traitCeoKeys")),
            removable_trait_ceo_keys=_string_tuple(item.get("removableTraitCeoKeys")),
            equipment_set_key=item.get("equipmentSetKey"),
            equipment_ceo_keys=_string_tuple(item.get("equipmentCeoKeys")),
            removable_equipment_ceo_keys=_string_tuple(item.get("removableEquipmentCeoKeys")),
            default_equipment_ceo_keys=_string_tuple(item.get("defaultEquipmentCeoKeys")),
            dedicated_armour=_dedicated_armour_assignment(item.get("dedicatedArmour")),
        )
        for item in data.get("characterCloneRecipes", [])
    ]
    character_patches = [
        CharacterPatch(
            template_key=item["templateKey"],
            template_overrides=item.get("templateOverrides", {}),
            detail_overrides=item.get("detailOverrides", {}),
            display_name=item.get("displayName"),
            image_assets=item.get("imageAssets") or [],
            art_overrides=item.get("artOverrides") or {},
            art_set_overrides=item.get("artSetOverrides") or {},
            title_ceo_key=item.get("titleCeoKey"),
            removable_title_ceo_keys=_string_tuple(item.get("removableTitleCeoKeys")),
            trait_set_key=item.get("traitSetKey"),
            trait_ceo_keys=_string_tuple(item.get("traitCeoKeys")),
            removable_trait_ceo_keys=_string_tuple(item.get("removableTraitCeoKeys")),
            equipment_set_key=item.get("equipmentSetKey"),
            equipment_ceo_keys=_string_tuple(item.get("equipmentCeoKeys")),
            removable_equipment_ceo_keys=_string_tuple(item.get("removableEquipmentCeoKeys")),
            default_equipment_ceo_keys=_string_tuple(item.get("defaultEquipmentCeoKeys")),
        )
        for item in data.get("characterPatches", [])
    ]
    return Recipe(
        mod_name=data.get("modName", "unnamed_mod"),
        equipment_stat_patches=patches,
        armour_type_clones=armour_type_clones,
        land_unit_clones=land_unit_clones,
        skill_set_clones=skill_set_clones,
        attribute_set_clones=attribute_set_clones,
        age_range_clones=age_range_clones,
        character_clones=character_clones,
        character_patches=character_patches,
        work_items=data.get("workItems", []),
        raw=data,
    )


def _coalesce_stat_patches(patches: list[StatPatch]) -> list[StatPatch]:
    merged: dict[tuple[str, str, str, str | None], StatPatch] = {}
    order: list[tuple[str, str, str, str | None]] = []
    for patch in patches:
        key = (
            _canonical_equipment_key(patch.equipment_key),
            patch.stat_table,
            patch.column,
            patch.game_mode,
        )
        if key not in merged:
            order.append(key)
        merged[key] = patch
    return [merged[key] for key in order]


def _canonical_equipment_key(value: str) -> str:
    return str(value).replace("_ancilliary_", "_ancillary_")


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value if str(item or "").strip())


def _dedicated_armour_assignment(value: Any) -> DedicatedArmourAssignment | None:
    if not isinstance(value, dict):
        return None
    source_armour_value_raw = value.get("sourceArmourValue")
    source_armour_value = (
        int(source_armour_value_raw)
        if source_armour_value_raw not in (None, "")
        else None
    )
    armour_bonus_raw = value.get("armourBonus")
    if armour_bonus_raw not in (None, ""):
        armour_bonus = int(armour_bonus_raw)
        if not -500 <= armour_bonus <= 500:
            raise ValueError("방어력 보정치는 -500~500 사이여야 합니다.")
        armour_value = (source_armour_value or 0) + armour_bonus
    else:
        armour_value = int(value.get("armourValue", 0))
    if armour_bonus_raw in (None, "") and not 0 <= armour_value <= 500:
        raise ValueError("전용 갑옷 방어력은 0~500 사이여야 합니다.")
    combat_bonuses = {
        "melee_attack_bonus": int(value.get("meleeAttackBonus") or 0),
        "melee_damage_bonus": int(value.get("meleeDamageBonus") or 0),
        "ap_melee_damage_bonus": int(value.get("apMeleeDamageBonus") or 0),
        "charge_bonus": int(value.get("chargeBonus") or 0),
    }
    invalid_bonuses = [
        name
        for name, bonus in combat_bonuses.items()
        if not -500 <= bonus <= 500
    ]
    if invalid_bonuses:
        raise ValueError(
            "Character combat bonuses must be between -500 and 500: "
            + ", ".join(invalid_bonuses)
        )
    defence_bonuses = {
        "melee_defence_bonus": int(value.get("meleeDefenceBonus") or 0),
        "missile_defence_bonus": int(value.get("missileDefenceBonus") or 0),
    }
    invalid_defence_bonuses = [
        name
        for name, bonus in defence_bonuses.items()
        if not -100 <= bonus <= 100
    ]
    if invalid_defence_bonuses:
        raise ValueError(
            "Character defence chance bonuses must be between -100 and 100: "
            + ", ".join(invalid_defence_bonuses)
        )
    required = {
        key: str(value.get(key) or "").strip()
        for key in (
            "sourceCeoKey",
            "sourceInitialCeoKey",
            "sourceArmourTypeKey",
        )
    }
    missing = [key for key, item in required.items() if not item]
    if missing:
        raise ValueError("전용 갑옷 설정 필드가 비었습니다: " + ", ".join(missing))
    return DedicatedArmourAssignment(
        source_ceo_key=required["sourceCeoKey"],
        source_initial_ceo_key=required["sourceInitialCeoKey"],
        source_armour_type_key=required["sourceArmourTypeKey"],
        source_armour_value=source_armour_value,
        armour_value=armour_value,
        pool_id=str(value.get("poolId") or "").strip(),
        slot_id=str(value.get("slotId") or "").strip(),
        armour_ceo_key=str(value.get("armourCeoKey") or "").strip(),
        initial_ceo_key=str(value.get("initialCeoKey") or "").strip(),
        armour_type_key=str(value.get("armourTypeKey") or "").strip(),
        **combat_bonuses,
        **defence_bonuses,
    )


def _normalize_age_range_clones(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    remaps: dict[str, str] = {}
    age_items: list[dict[str, Any]] = []
    for item in data.get("ageRangeClones", []):
        age_item = dict(item)
        source_key = str(age_item.get("sourceKey") or "")
        new_key = str(age_item.get("newKey") or "")
        overrides = age_item.get("overrides") or {}
        if source_key and new_key == source_key and overrides:
            new_key = _derived_age_range_key(source_key, overrides)
            age_item["newKey"] = new_key
            remaps[source_key] = new_key
        age_items.append(age_item)
    normalized["ageRangeClones"] = age_items
    if not remaps:
        return normalized

    def remap_template_overrides(item: dict[str, Any]) -> dict[str, Any]:
        copied = dict(item)
        overrides = dict(copied.get("templateOverrides") or {})
        age_key = str(overrides.get("spawn_age_range") or "")
        if age_key in remaps:
            overrides["spawn_age_range"] = remaps[age_key]
            copied["templateOverrides"] = overrides
        return copied

    normalized["characterCloneRecipes"] = [
        remap_template_overrides(item)
        for item in data.get("characterCloneRecipes", [])
    ]
    normalized["characterPatches"] = [
        remap_template_overrides(item)
        for item in data.get("characterPatches", [])
    ]
    return normalized


def _normalize_attribute_set_clones(data: dict[str, Any]) -> dict[str, Any]:
    """Remap generated attribute sets into 190E's supported key namespace.

    190E extracts a character CQI from its UI object id with a pattern that
    assumes the attribute-set key starts with
    ``3k_main_attribute_set_general``. Older editor recipes used
    ``hby_attribute_set_`` and therefore made 190E pass the entire object id
    to ``SetContextObject`` when the character details panel opened.

    Remap the cloned row and all character-detail references at recipe load so
    persisted work queues and older recipe files are fixed at build time too.
    """
    normalized = dict(data)
    remaps: dict[str, str] = {}
    attribute_items: list[dict[str, Any]] = []
    for item in data.get("attributeSetClones", []):
        copied = dict(item)
        old_key = str(copied.get("newSetKey") or "")
        if old_key.startswith("hby_attribute_set_"):
            suffix = old_key.removeprefix("hby_attribute_set_")
            new_key = f"3k_main_attribute_set_general_hby_{suffix}"
            copied["newSetKey"] = new_key
            remaps[old_key] = new_key
        attribute_items.append(copied)
    normalized["attributeSetClones"] = attribute_items
    if not remaps:
        return normalized

    def remap_detail_overrides(item: dict[str, Any]) -> dict[str, Any]:
        copied = dict(item)
        details: dict[str, Any] = {}
        for mode, raw_overrides in (copied.get("detailOverrides") or {}).items():
            overrides = dict(raw_overrides or {})
            attribute_set = str(overrides.get("attribute_set") or "")
            if attribute_set in remaps:
                overrides["attribute_set"] = remaps[attribute_set]
            details[str(mode)] = overrides
        copied["detailOverrides"] = details
        return copied

    normalized["characterCloneRecipes"] = [
        remap_detail_overrides(item)
        for item in data.get("characterCloneRecipes", [])
    ]
    normalized["characterPatches"] = [
        remap_detail_overrides(item)
        for item in data.get("characterPatches", [])
    ]
    return normalized


def _derived_age_range_key(source_key: str, overrides: dict[str, Any]) -> str:
    seed = json.dumps([source_key, overrides], sort_keys=True, ensure_ascii=True).encode("utf-8")
    suffix = zlib.crc32(seed) & 0xffffffff
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", source_key).strip("_").lower()
    return f"hby_age_{slug}_{suffix:08x}"[:120]
