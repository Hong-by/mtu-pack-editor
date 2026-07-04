from __future__ import annotations

from typing import Any


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def element_from_subtype(subtype: str) -> str:
    lower = subtype.lower()
    if "water" in lower:
        return "water"
    if "wood" in lower:
        return "wood"
    if "fire" in lower:
        return "fire"
    if "earth" in lower:
        return "earth"
    return "metal"


def voiceover_actor_for_template_gender(is_male: bool, subtype: str) -> str:
    gender = "male" if is_male else "female"
    element = element_from_subtype(subtype)
    return f"vo_actor_group_generic_{gender}_{element}_general"


def generic_initial_ceo_key_for_template_gender(is_male_value: Any, subtype: Any) -> str:
    if is_male_value in (None, ""):
        return ""
    gender = "m" if coerce_bool(is_male_value) else "f"
    element = element_from_subtype(str(subtype or ""))
    return f"3k_main_ceo_initial_data_character_generic_{gender}_{element}_general"


def gender_compatible_initial_ceo_key(initial_ceo: Any, is_male_value: Any, subtype: Any) -> str:
    key = str(initial_ceo or "")
    if not key or is_male_value in (None, ""):
        return key
    is_male = coerce_bool(is_male_value)
    lower = key.lower()
    if is_male:
        if "generic_f_" in lower:
            return key.replace("generic_f_", "generic_m_")
        return key
    if "generic_f_" in lower:
        return key
    if "generic_m_" in lower:
        return key.replace("generic_m_", "generic_f_")
    return key


def spawn_safe_initial_ceo_key(initial_ceo: Any, is_male_value: Any, subtype: Any) -> str:
    return gender_compatible_initial_ceo_key(initial_ceo, is_male_value, subtype)
