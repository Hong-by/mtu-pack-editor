from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapters import PackSession
from .analyzer import analyze_pack
from .character_clone import validate_character_clone, validate_character_patch
from .game import THREE_KINGDOMS_GAME_KEY
from .land_units import validate_land_unit_clone
from .recipe import Recipe
from .stat_tables import resolve_stat_target


FORBIDDEN_RECIPE_KEYS = {
    "newEquipment",
    "cloneEquipment",
    "createEquipment",
    "equipmentToCreate",
}


@dataclass(frozen=True)
class ValidationMessage:
    level: str
    code: str
    message: str


def validate(session: PackSession, recipe: Recipe, output_path: str | None = None) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    analysis = analyze_pack(session)
    if analysis.game_key != THREE_KINGDOMS_GAME_KEY:
        messages.append(
            ValidationMessage(
                "error",
                "unsupported_game",
                f"Only Total War: THREE KINGDOMS packs are supported. Expected gameKey '{THREE_KINGDOMS_GAME_KEY}', got '{analysis.game_key}'.",
            )
        )

    for table_name in analysis.missing_required_tables:
        messages.append(
            ValidationMessage("error", "missing_table", f"Required table is missing: {table_name}")
        )

    for key in FORBIDDEN_RECIPE_KEYS:
        if key in recipe.raw:
            messages.append(
                ValidationMessage(
                    "error",
                    "forbidden_equipment_operation",
                    f"Recipe key '{key}' is not allowed in this prototype.",
                )
            )

    if "equipment" in recipe.raw:
        for item in recipe.raw.get("equipment", []):
            if item.get("operation") in {"create", "clone"}:
                messages.append(
                    ValidationMessage(
                        "error",
                        "forbidden_equipment_operation",
                        "Creating or cloning equipment is out of scope.",
                    )
                )

    if "equipmentEffectPatches" in recipe.raw:
        messages.append(
            ValidationMessage(
                "error",
                "unsupported_recipe_key",
                "Use equipmentStatPatches for weapon/armour stat edits.",
            )
        )

    if (
        not recipe.equipment_stat_patches
        and not recipe.land_unit_clones
        and not recipe.skill_set_clones
        and not recipe.attribute_set_clones
        and not recipe.age_range_clones
        and not recipe.character_clones
        and not recipe.character_patches
    ):
        messages.append(
            ValidationMessage(
                "warning",
                "empty_recipe",
                "Recipe has no equipment stat patches, character patches, or character clones.",
            )
        )

    seen_land_unit_keys: set[str] = set()
    for clone in recipe.land_unit_clones:
        if clone.new_key in seen_land_unit_keys:
            messages.append(
                ValidationMessage(
                    "error",
                    "duplicate_land_unit_clone",
                    f"Duplicate land unit clone key: {clone.new_key}",
                )
            )
        seen_land_unit_keys.add(clone.new_key)
        try:
            validate_land_unit_clone(session, clone)
        except ValueError as error:
            messages.append(
                ValidationMessage("error", "invalid_land_unit_clone", str(error))
            )

    seen_character_patch_keys: set[str] = set()
    for patch in recipe.character_patches:
        if patch.template_key in seen_character_patch_keys:
            messages.append(
                ValidationMessage(
                    "error",
                    "duplicate_character_patch",
                    f"Duplicate character patch key: {patch.template_key}",
                )
            )
        seen_character_patch_keys.add(patch.template_key)
        try:
            validate_character_patch(session, patch)
        except ValueError as error:
            messages.append(
                ValidationMessage("error", "invalid_character_patch", str(error))
            )

    seen_character_keys: set[str] = set()
    for clone in recipe.character_clones:
        if clone.new_template_key in seen_character_keys:
            messages.append(
                ValidationMessage(
                    "error",
                    "duplicate_character_clone",
                    f"Duplicate character clone key: {clone.new_template_key}",
                )
            )
        seen_character_keys.add(clone.new_template_key)
        try:
            validate_character_clone(session, clone)
        except ValueError as error:
            messages.append(
                ValidationMessage("error", "invalid_character_clone", str(error))
            )

    seen_patch_keys: set[tuple[str, str, str, str | None]] = set()
    for patch in recipe.equipment_stat_patches:
        patch_key = (patch.equipment_key, patch.stat_table, patch.column, patch.game_mode)
        if patch_key in seen_patch_keys:
            messages.append(
                ValidationMessage(
                    "error",
                    "duplicate_patch",
                    f"Duplicate stat patch: {patch.equipment_key}/{patch.stat_table}/{patch.column}",
                )
            )
        seen_patch_keys.add(patch_key)

        string_patch = patch.stat_table == "armour" and patch.column == "audio_type"
        if string_patch:
            if not isinstance(patch.value, str) or not patch.value.strip():
                messages.append(
                    ValidationMessage(
                        "error",
                        "invalid_stat_value",
                        f"Audio type must be a non-empty string: {patch.equipment_key}/{patch.column}",
                    )
                )
                continue
        elif not isinstance(patch.value, (int, float)):
            messages.append(
                ValidationMessage(
                    "error",
                    "invalid_stat_value",
                    f"Stat value must be numeric: {patch.equipment_key}/{patch.stat_table}/{patch.column}",
                )
            )
            continue

        try:
            resolve_stat_target(
                session,
                patch.equipment_key,
                patch.stat_table,
                patch.column,
                patch.value,
                patch.game_mode,
            )
        except ValueError as error:
            messages.append(
                ValidationMessage("error", "invalid_stat_patch", str(error))
            )

    if output_path is not None and not output_path.endswith(".pack"):
        messages.append(
            ValidationMessage("error", "invalid_output_path", "Output path must end with .pack.")
        )

    return messages


def has_errors(messages: list[ValidationMessage]) -> bool:
    return any(message.level == "error" for message in messages)


def allow_reference_backed_clone_sources(messages: list[ValidationMessage]) -> list[ValidationMessage]:
    allowed_fragments = (
        "Source initial CEO not found:",
        "Source age range not found:",
        "Source character art rows not found:",
    )
    allowed_patch_fragments = (
        "Character template not found:",
        "Character game mode details not found:",
    )
    allowed_land_unit_fragments = (
        "Source land unit not found:",
    )
    allowed_stat_fragments = (
        "Equipment stat mapping not found:",
        "Stat row is missing:",
        "Required table is missing:",
    )
    return [
        message
        for message in messages
        if not (
            message.code == "invalid_character_clone"
            and any(fragment in message.message for fragment in allowed_fragments)
        ) and not (
            message.code == "invalid_character_patch"
            and any(fragment in message.message for fragment in allowed_patch_fragments)
        ) and not (
            message.code == "invalid_land_unit_clone"
            and any(fragment in message.message for fragment in allowed_land_unit_fragments)
        ) and not (
            message.code == "invalid_stat_patch"
            and any(fragment in message.message for fragment in allowed_stat_fragments)
        ) and not (
            message.code == "missing_table"
            and message.message.startswith("Required table is missing:")
        )
    ]


def messages_to_dicts(messages: list[ValidationMessage]) -> list[dict[str, Any]]:
    return [message.__dict__ for message in messages]
