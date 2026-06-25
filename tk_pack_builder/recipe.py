from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StatPatch:
    equipment_key: str
    stat_table: str
    column: str
    value: int | float
    game_mode: str | None = None


@dataclass(frozen=True)
class LandUnitClone:
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


@dataclass(frozen=True)
class Recipe:
    mod_name: str
    equipment_stat_patches: list[StatPatch]
    land_unit_clones: list[LandUnitClone]
    skill_set_clones: list[SkillSetClone]
    attribute_set_clones: list[AttributeSetClone]
    age_range_clones: list[AgeRangeClone]
    character_clones: list[CharacterClone]
    character_patches: list[CharacterPatch]
    raw: dict[str, Any]


def load_recipe(path: Path) -> Recipe:
    data = json.loads(path.read_text(encoding="utf-8"))
    return recipe_from_dict(data)


def recipe_from_dict(data: dict[str, Any]) -> Recipe:
    patches = [
        StatPatch(
            equipment_key=item["equipmentKey"],
            stat_table=item["statTable"],
            column=item["column"],
            value=item["value"],
            game_mode=item.get("gameMode"),
        )
        for item in data.get("equipmentStatPatches", [])
    ]
    land_unit_clones = [
        LandUnitClone(
            source_key=item["sourceKey"],
            new_key=item["newKey"],
            overrides=item.get("overrides", {}),
        )
        for item in data.get("landUnitClones", [])
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
        )
        for item in data.get("characterPatches", [])
    ]
    return Recipe(
        mod_name=data.get("modName", "unnamed_mod"),
        equipment_stat_patches=patches,
        land_unit_clones=land_unit_clones,
        skill_set_clones=skill_set_clones,
        attribute_set_clones=attribute_set_clones,
        age_range_clones=age_range_clones,
        character_clones=character_clones,
        character_patches=character_patches,
        raw=data,
    )
