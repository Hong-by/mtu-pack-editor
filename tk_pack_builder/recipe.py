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


@dataclass(frozen=True)
class CharacterPatch:
    template_key: str
    template_overrides: dict[str, Any]
    detail_overrides: dict[str, dict[str, Any]]
    display_name: str | None = None
    image_assets: list[dict[str, str]] | None = None
    art_overrides: dict[str, Any] | None = None
    art_set_overrides: dict[str, Any] | None = None


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


def _derived_age_range_key(source_key: str, overrides: dict[str, Any]) -> str:
    seed = json.dumps([source_key, overrides], sort_keys=True, ensure_ascii=True).encode("utf-8")
    suffix = zlib.crc32(seed) & 0xffffffff
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", source_key).strip("_").lower()
    return f"hby_age_{slug}_{suffix:08x}"[:120]
