from __future__ import annotations

from .rpfm_fields import field_names as _rpfm_field_names

import copy
import hashlib
import json
import os
import re
import struct
from dataclasses import replace as _dataclass_replace
from pathlib import Path
from typing import Any
import zlib

from .adapters import RpfmPackSession, _decode_rpfm_cell, _encode_rpfm_cell
from .character_clone import CHARACTER_TABLE_ALIASES, resolve_character_table_name
from .character_rules import (
    coerce_bool as _coerce_bool,
    element_from_subtype as _element_from_subtype,
    generic_initial_ceo_key_for_template_gender as _generic_initial_ceo_key_for_template_gender,
    gender_compatible_initial_ceo_key as _gender_compatible_initial_ceo_key,
)
from .campaign_script import build_campaign_start_script
from .ceo_ccd import (
    CeoCcd,
    initial_ceo_active_ceos,
    rebase_dedicated_armour_ceo_as_regular,
    rebase_dedicated_armour_initial_ceo,
)
from .dedicated_armour_pool import (
    CCD_PACK_PATH,
    DedicatedArmourPool,
    DedicatedArmourPoolError,
    load_dedicated_armour_pools,
    ordered_active_ccd_pack_paths,
    resolve_effective_ccd,
    resolve_pool_status,
    validate_pool_assignments,
    verify_pool_asset,
)
from .korea_addon import korea_related_template_keys
from .land_units import validate_land_unit_clone
from .pfh import find_entry, read_entry_bytes, read_pfh_index
from .recipe import AgeRangeClone, ArmourTypeClone, AttributeSetClone, CharacterClone, CharacterPatch, Recipe, SkillSetClone, recipe_from_dict
from .stat_tables import TABLE_ALIASES, StatTarget, resolve_stat_target, resolve_table_name


LEGACY_TEMPLATE_PACK = Path("work/legacy_template/8King_4P_1.7_up.pack")
ROOT = Path(os.environ.get("TK_PACK_EDITOR_ROOT", Path(__file__).resolve().parents[1])).resolve()
EXTRACTED_ASSET_ROOT = ROOT / "work" / "assets"
INTERNAL_MATERIALS_PATH = ROOT / "work" / "internal_materials" / "vanilla_mtu" / "materials.v015.json"
CORE_ASSET_SOURCE_ID = "17309a40b912"
IMAGE_ONLY_ASSET_PREFIX = "__image_only_reference__"
TEMP_IMAGE_ASSET_ROOT = ROOT / "work" / "tmp_delta_image_assets"
TEMP_LUA_SCRIPT_ROOT = ROOT / "work" / "tmp_delta_scripts"
TEMP_MODEL_ASSET_ROOT = ROOT / "work" / "tmp_delta_model_assets"
TEMP_DEDICATED_ARMOUR_CCD_ROOT = ROOT / "work" / "tmp_dedicated_armour_ccd"
DEDICATED_ARMOUR_POOL_ROOTS = (
    Path(__file__).resolve().parent / "data" / "dedicated_armour_pools",
    ROOT / "work" / "dedicated_armour_pools",
)
SPAWN_SCRIPT_SAVE_VERSION = 8
CEO_SET_SCRIPT_SAVE_VERSION = 9
EQUIPMENT_SCRIPT_SAVE_VERSION = 27
DEDICATED_ARMOUR_MIGRATION_SAVE_VERSION = 6
DEDICATED_ARMOUR_REGULAR_CEO_SOURCE = (
    "3k_main_ancillary_armour_medium_armour_metal_extraordinary"
)
CAMPAIGN_SPAWN_SCRIPT_PATH = "script/campaign/3k_main_campaign_map/mod/hby_mtu_pack_editor_player_spawn.lua"
CAMPAIGN_SPAWN_SCRIPT_PATHS = (
    CAMPAIGN_SPAWN_SCRIPT_PATH,
)
SPAWN_EVENT_TEMPLATE_WEIGHT = 19.5
GENERATED_CHARACTER_START_RANK = 3
SPAWN_INCIDENT_EVENT_CATEGORY = "historical"
CHARACTER_GAME_MODES = ("historical", "romance")
MTU_CHARACTER_ART_SETS_TABLE = "db/campaign_character_art_sets_tables/_mtu_characters"
MTU_CHARACTER_ARTS_TABLE = "db/campaign_character_arts_tables/_mtu_characters"
MTU_AGENT_UNIFORMS_TABLE = "db/agent_uniforms_tables/_mtu_characters"
MTU_VARIANTS_TABLE = "db/variants_tables/_mtu_characters_variants"
MTU_FRONTEND_CHARACTER_CEOS_TABLE = "db/frontend_character_ceos_tables/_mtu_characters_ceo"
FIXED_MODEL_AGENT_UNIFORMS_TABLE = "db/agent_uniforms_tables/fixed_unique_models"
FIXED_MODEL_VARIANTS_TABLE = "db/variants_tables/fixed_unique_models"
GENERIC_FEMALE_UNIFORM = "3k_main_hero_skin_female_01"
GENERIC_FEMALE_SHARED_FALLBACK = (
    "3k_main_ancillary_armour_light_armour_earth_metal_and_water_common_female"
)
GENERIC_FEMALE_COMPATIBILITY = {
    "earth": {
        "initial_ceo": "3k_main_ceo_initial_data_character_generic_f_earth_general",
        "fallback": GENERIC_FEMALE_SHARED_FALLBACK,
        "armour_displays": (
            "3k_main_ancillary_armour_light_leather_partial_common_shared_female",
            "3k_main_ancillary_armour_light_leather_partial_exceptional_earth_female",
            "3k_main_ancillary_armour_light_leather_partial_refined_shared_female",
            "3k_main_ancillary_armour_light_leather_partial_unique_earth_female",
            "3k_main_ancillary_armour_medium_leather_common_shared_female",
            "3k_main_ancillary_armour_medium_leather_exceptional_earth_female",
            "3k_main_ancillary_armour_medium_leather_refined_shared_female",
            "3k_main_ancillary_armour_medium_leather_unique_earth_female",
            "ep_ancillary_armour_light_leather_partial_exceptional_earth_female",
            "ep_ancillary_armour_light_leather_partial_unique_earth_female",
            "ep_ancillary_armour_medium_leather_exceptional_earth_female",
            "ep_ancillary_armour_medium_leather_unique_earth_female",
        ),
    },
    "metal": {
        "initial_ceo": "3k_main_ceo_initial_data_character_generic_f_metal_general",
        "fallback": GENERIC_FEMALE_SHARED_FALLBACK,
        "armour_displays": (
            "3k_main_ancillary_armour_light_leather_partial_common_shared_female",
            "3k_main_ancillary_armour_light_leather_partial_exceptional_metal_female",
            "3k_main_ancillary_armour_light_leather_partial_refined_shared_female",
            "3k_main_ancillary_armour_light_leather_partial_unique_metal_female",
            "3k_main_ancillary_armour_medium_leather_common_shared_female",
            "3k_main_ancillary_armour_medium_leather_exceptional_metal_female",
            "3k_main_ancillary_armour_medium_leather_refined_shared_female",
            "3k_main_ancillary_armour_medium_leather_unique_metal_female",
            "ep_ancillary_armour_light_leather_partial_exceptional_metal_female",
            "ep_ancillary_armour_light_leather_partial_unique_metal_female",
            "ep_ancillary_armour_medium_leather_exceptional_metal_female",
            "ep_ancillary_armour_medium_leather_unique_metal_female",
        ),
    },
    "water": {
        "initial_ceo": "3k_main_ceo_initial_data_character_generic_f_water_general",
        "fallback": "3k_main_ancillary_armour_strategist_light_armour_water_common_female",
        "armour_displays": (
            "3k_main_ancillary_armour_light_tunic_common_water_female",
            "3k_main_ancillary_armour_light_tunic_exceptional_water_female",
            "3k_main_ancillary_armour_light_tunic_refined_water_female",
            "3k_main_ancillary_armour_light_tunic_unique_water_female",
            "ep_ancillary_armour_light_tunic_exceptional_water_female",
            "ep_ancillary_armour_light_tunic_unique_water_female",
            "3k_main_ancillary_armour_light_leather_partial_common_shared_female",
            "3k_main_ancillary_armour_light_leather_partial_exceptional_water_female",
            "3k_main_ancillary_armour_light_leather_partial_refined_shared_female",
            "3k_main_ancillary_armour_light_leather_partial_unique_water_female",
        ),
    },
}
GENERIC_MALE_COMPATIBILITY = {
    "earth": {
        "fallback": "3k_main_ancillary_armour_light_armour_earth_metal_and_water_common",
        "armour_displays": (
            "3k_main_ancillary_armour_light_armour_earth_metal_and_water_common",
            "3k_main_ancillary_armour_light_armour_earth_metal_and_water_refined",
            "3k_main_ancillary_armour_light_armour_earth_extraordinary",
            "3k_main_ancillary_armour_light_armour_earth_unique",
            "3k_main_ancillary_armour_medium_armour_earth_and_metal_common",
            "3k_main_ancillary_armour_medium_armour_earth_and_metal_refined",
            "3k_main_ancillary_armour_medium_armour_earth_extraordinary",
            "3k_main_ancillary_armour_medium_armour_earth_unique",
            "ep_ancillary_armour_light_armour_earth_extraordinary",
            "ep_ancillary_armour_light_armour_earth_unique",
            "ep_ancillary_armour_medium_armour_earth_extraordinary",
            "ep_ancillary_armour_medium_armour_earth_unique",
        ),
    },
    "fire": {
        "fallback": "3k_main_ancillary_armour_medium_armour_wood_and_fire_common",
        "armour_displays": (
            "3k_main_ancillary_armour_medium_armour_wood_and_fire_common",
            "3k_main_ancillary_armour_medium_armour_wood_and_fire_refined",
            "3k_main_ancillary_armour_medium_armour_fire_extraordinary",
            "3k_main_ancillary_armour_medium_armour_fire_unique",
            "3k_main_ancillary_armour_heavy_armour_wood_and_fire_common",
            "3k_main_ancillary_armour_heavy_armour_wood_and_fire_refined",
            "3k_main_ancillary_armour_heavy_armour_fire_extraordinary",
            "3k_main_ancillary_armour_heavy_armour_fire_unique",
            "ep_ancillary_armour_medium_armour_fire_extraordinary",
            "ep_ancillary_armour_medium_armour_fire_unique",
            "ep_ancillary_armour_heavy_armour_fire_extraordinary",
            "ep_ancillary_armour_heavy_armour_fire_unique",
        ),
    },
    "wood": {
        "fallback": "3k_main_ancillary_armour_medium_armour_wood_and_fire_common",
        "armour_displays": (
            "3k_main_ancillary_armour_medium_armour_wood_and_fire_common",
            "3k_main_ancillary_armour_medium_armour_wood_and_fire_refined",
            "3k_main_ancillary_armour_medium_armour_wood_extraordinary",
            "3k_main_ancillary_armour_medium_armour_wood_unique",
            "3k_main_ancillary_armour_heavy_armour_wood_and_fire_common",
            "3k_main_ancillary_armour_heavy_armour_wood_and_fire_refined",
            "3k_main_ancillary_armour_heavy_armour_wood_extraordinary",
            "3k_main_ancillary_armour_heavy_armour_wood_unique",
            "ep_ancillary_armour_medium_armour_wood_extraordinary",
            "ep_ancillary_armour_medium_armour_wood_unique",
            "ep_ancillary_armour_heavy_armour_wood_extraordinary",
            "ep_ancillary_armour_heavy_armour_wood_unique",
        ),
    },
    "water": {
        "fallback": "3k_main_ancillary_armour_strategist_light_armour_water_common",
        "armour_displays": (
            "3k_main_ancillary_armour_strategist_light_armour_water_common",
            "3k_main_ancillary_armour_strategist_light_armour_water_refined",
            "3k_main_ancillary_armour_strategist_light_armour_water_extraordinary",
            "3k_main_ancillary_armour_strategist_light_armour_water_unique",
            "3k_main_ancillary_armour_light_armour_earth_metal_and_water_common",
            "3k_main_ancillary_armour_light_armour_earth_metal_and_water_refined",
            "ep_ancillary_armour_strategist_light_armour_water_extraordinary",
            "ep_ancillary_armour_strategist_light_armour_water_unique",
        ),
    },
    "metal": {
        "fallback": "3k_main_ancillary_armour_light_armour_earth_metal_and_water_common",
        "armour_displays": (
            "3k_main_ancillary_armour_light_armour_earth_metal_and_water_common",
            "3k_main_ancillary_armour_light_armour_earth_metal_and_water_refined",
            "3k_main_ancillary_armour_light_armour_metal_extraordinary",
            "3k_main_ancillary_armour_light_armour_metal_unique",
            "3k_main_ancillary_armour_medium_armour_earth_and_metal_common",
            "3k_main_ancillary_armour_medium_armour_earth_and_metal_refined",
            "3k_main_ancillary_armour_medium_armour_metal_extraordinary",
            "3k_main_ancillary_armour_medium_armour_metal_unique",
            "ep_ancillary_armour_light_armour_metal_extraordinary",
            "ep_ancillary_armour_light_armour_metal_unique",
            "ep_ancillary_armour_medium_armour_metal_extraordinary",
            "ep_ancillary_armour_medium_armour_metal_unique",
        ),
    },
}
# Vanilla has generic female campaign art only for earth, metal, and water.
# Fire and wood initial CEO records exist, but no matching female art family.
UNSUPPORTED_GENERIC_FEMALE_ELEMENTS = frozenset({"fire", "wood"})
# A VMD audit found these MTU art uniforms already contain enough baked model
# geometry to render without armour-driven `set_body` injection.  Generated
# variants remove that one slot when present and otherwise preserve the
# already-independent VMD verbatim.  Melee, shield and ranged slots remain
# untouched.  Both male and female source heroes are included; empty
# equipment wrappers are deliberately excluded.
_EQUIPMENT_INDEPENDENT_UNIQUE_MODEL_SOURCES = (
    (
        "3k_main_template_historical_lu_bu_hero_fire",
        "3k_main_lu_bu",
        "3k_main_hero_skin_male_lu_bu",
        "set_hero_skins/chinese_hero_skin_male_lu_bu",
    ),
    ("3k_mtu_template_historical_dong_min_hero_earth", "3k_mtu_dong_min", "3k_mtu_hero_earth_dong_min", "hero_earth_dong_min"),
    ("3k_mtu_template_historical_jian_yong_hero_metal", "3k_mtu_jian_yong", "3k_mtu_hero_metal_jian_yong", "hero_metal_jian_yong"),
    ("3k_mtu_template_historical_chen_jiu_hero_wood", "3k_mtu_chen_jiu", "3k_mtu_hero_wood_chen_jiu", "hero_wood_pang_de"),
    ("3k_main_template_historical_huang_zu_hero_wood", "3k_mtu_huang_zu", "3k_mtu_hero_wood_huang_zu", "hero_wood_huang_zu"),
    ("3k_mtu_template_historical_qu_gong_hero_wood", "3k_mtu_qu_gong", "3k_mtu_hero_wood_qu_gong", "hero_wood_qu_gong"),
    ("3k_mtu_template_historical_zhang_xun_hero_earth", "3k_mtu_gao_shun", "3k_mtu_hero_earth_zhang_xun", "hero_earth_zhang_xun"),
    ("3k_main_template_historical_lady_cai_yan_hero_water", "3k_mtu_lady_cai_yan", "3k_mtu_hero_water_lady_cai_yan", "hero_water_lady_cai_yan"),
    ("3k_mtu_template_historical_lady_dong_peishan_hero_earth", "3k_mtu_lady_dong_peishan", "3k_mtu_hero_earth_lady_dong_peishan", "hero_earth_lady_dong_peishan"),
    ("3k_mtu_template_historical_lady_du_hero_earth", "3k_mtu_lady_bian_huilan", "3k_mtu_hero_earth_lady_bian_huilan", "hero_earth_lady_bian_huilan"),
    ("3k_mtu_template_historical_lady_feng_hero_earth", "3k_mtu_lady_da_qiao", "3k_mtu_hero_earth_lady_da_qiao", "hero_earth_lady_da_qiao"),
    ("3k_mtu_template_historical_lady_gongsun_jinting_hero_water", "3k_mtu_lady_gongsun_jinting", "3k_mtu_hero_water_lady_gongsun_jinting", "hero_water_lady_gongsun_jinting"),
    ("3k_mtu_template_historical_lady_guan_yinping_hero_wood", "3k_mtu_lady_guan_yinping", "3k_mtu_hero_wood_lady_guan_yinping", "hero_wood_lady_guan_yinping"),
    ("3k_mtu_template_historical_lady_lu_ji_hero_wood", "3k_mtu_lady_lu_ji", "3k_mtu_hero_wood_lady_lu_ji", "hero_wood_lady_lu_ji"),
    ("3k_mtu_template_historical_lady_lu_zheng_hero_water", "3k_mtu_lady_lu_zheng", "3k_mtu_hero_water_lady_lu_zheng", "hero_water_lady_lu_zheng"),
    ("3k_mtu_template_historical_lady_ma_lanli_hero_metal", "3k_mtu_lady_ma_lanli", "3k_mtu_hero_fire_lady_ma_lanli", "hero_fire_lady_ma_lanli"),
    ("3k_mtu_template_historical_lady_ma_yunlu_hero_metal", "3k_mtu_lady_ma_yunlu", "3k_mtu_hero_metal_lady_ma_yunlu", "hero_metal_lady_ma_yunlu"),
    ("3k_mtu_template_historical_lady_trieu_hero_wood", "3k_mtu_lady_trieu", "3k_mtu_hero_wood_lady_trieu", "hero_wood_lady_trieu"),
    ("3k_mtu_template_historical_lady_wang_liting_hero_metal", "3k_mtu_lady_wang_liting", "3k_mtu_hero_metal_lady_wang_liting", "hero_metal_lady_wang_liting"),
    ("3k_mtu_template_historical_lady_yuan_anyang_hero_water", "3k_mtu_lady_xiao_qiao", "3k_mtu_hero_metal_lady_xiao_qiao", "hero_metal_lady_xiao_qiao"),
    ("3k_mtu_template_historical_lady_zhang_xingcai_hero_fire", "3k_mtu_lady_lu_ji", "3k_mtu_hero_wood_lady_lu_ji", "hero_wood_lady_lu_ji"),
    ("3k_mtu_template_historical_lady_zou_yuan_hero_water", "3k_mtu_lady_zou_yuan", "3k_mtu_hero_metal_lady_xiao_qiao", "hero_metal_lady_xiao_qiao"),
    ("3k_main_template_historical_hua_xin_hero_water", "3k_mtu_hua_xin", "3k_mtu_hero_water_hua_xin", "hero_water_hua_xin"),
    ("3k_mtu_template_historical_yan_xiang_hero_water", "3k_mtu_yan_xiang", "3k_mtu_hero_water_yan_xiang", "hero_water_xun_yu"),
    ("3k_mtu_template_historical_zhang_bao_hero_fire", "3k_mtu_zhang_bao", "3k_mtu_hero_fire_zhang_bao", "hero_fire_zhang_bao"),
    ("3k_main_template_historical_shen_pei_hero_water", "3k_mtu_shen_pei", "3k_mtu_hero_wood_shen_pei", "hero_wood_shen_pei"),
    ("3k_main_template_historical_chunyu_qiong_hero_fire", "3k_mtu_chunyu_qiong", "3k_mtu_hero_fire_chunyu_qiong", "hero_fire_chunyu_qiong"),
    ("3k_dlc04_template_historical_luo_jun_xiaoyuan_wood", "3k_mtu_luo_jun", "3k_mtu_hero_wood_luo_jun", "hero_wood_luo_jun"),
    ("3k_main_template_historical_dong_bai_hero_metal", "3k_mtu_lady_dong_bai", "3k_mtu_hero_metal_lady_xiao_qiao", "hero_metal_lady_xiao_qiao"),
    ("3k_mtu_template_historical_wu_anguo_hero_wood", "3k_mtu_wu_anguo", "3k_mtu_hero_wood_wu_anguo", "hero_wood_wu_anguo"),
    ("3k_mtu_template_historical_lady_buyeo_wol_hero_water", "3k_mtu_lady_zou_yuan", "3k_mtu_hero_metal_lady_xiao_qiao", "hero_metal_lady_xiao_qiao"),
)


def _fixed_unique_model_key(source_key: str, *, definition: bool = False) -> str:
    source_key = source_key.replace("\\", "_").replace("/", "_")
    if source_key.startswith("3k_"):
        return f"hby_{source_key[3:]}_fixed"
    prefix = "hby_mtu_" if definition else "hby_"
    return f"{prefix}{source_key}_fixed"


EQUIPMENT_INDEPENDENT_UNIQUE_MODELS = {
    template: {
        "source_uniform": source_uniform,
        "source_variant": source_variant,
        "source_definition": source_definition,
        "fixed_uniform": _fixed_unique_model_key(source_uniform),
        "fixed_variant": _fixed_unique_model_key(source_variant),
        # Base-game full-body definitions already have no set_body injection
        # slot and can be referenced directly.  MTU definitions are copied to
        # an isolated key so their one equipment injection slot can be removed.
        "fixed_definition": (
            source_definition
            if "/" in source_definition or "\\" in source_definition
            else _fixed_unique_model_key(source_definition, definition=True)
        ),
    }
    for template, source_uniform, source_variant, source_definition
    in _EQUIPMENT_INDEPENDENT_UNIQUE_MODEL_SOURCES
}
HISTORICAL_INITIAL_CEO_TOKEN_ALIASES = {
    "empress_he_fire": ("3k_dlc04_ceo_initial_data_character_historical_non_deployable_empress_he_fire",),
    "lady_sun_shangxiang": ("lady_sun",),
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def build_delta_pack(
    session: RpfmPackSession,
    recipe: Recipe,
    output_path: Path,
    reference_paths: list[Path] | None = None,
) -> list[dict[str, object]]:
    from .source_policy import require_supported_sources, require_clean_references, require_clean_pack
    require_supported_sources(reference_paths or [])
    require_clean_references(recipe)
    from .title_registry import validate_recipe_titles
    validate_recipe_titles(recipe)
    for reference_path in reference_paths or []:
        if reference_path.is_file():
            require_clean_pack(reference_path)
    output_path = output_path.resolve()
    messages: list[Any] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_dbs: dict[str, dict[str, Any]] = {}
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    loc_rows: dict[str, str] = {}
    opened_pack_keys = {str(session.pack_path.resolve()): session.pack_key}
    patched_skill_set_keys: set[str] = set()

    changed_stats = 0
    cloned_armour_types = 0
    cloned_land_units = 0
    attribute_sets = 0
    skill_sets = 0
    age_ranges = 0
    changed_character_fields = 0
    cloned_characters = 0
    copied_dependency_rows = 0
    processed_clones: list[CharacterClone] = []
    processed_patches: list[CharacterPatch] = []

    for work_recipe in _processing_recipes(recipe):
        _validate_hidden_armour_adjustment_links(work_recipe)
        patched_skill_set_keys.update(clone.new_set_key for clone in work_recipe.skill_set_clones)
        changed_stats += _collect_stat_patch_rows(
            session,
            work_recipe,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        cloned_armour_types += _collect_armour_type_clone_rows(
            session,
            work_recipe.armour_type_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        cloned_land_units += _collect_land_unit_clone_rows(
            session,
            work_recipe,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        attribute_sets += _collect_attribute_set_clone_rows(
            session,
            work_recipe.attribute_set_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        skill_sets += _collect_skill_set_clone_rows(
            session,
            work_recipe.skill_set_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        age_ranges += _collect_age_range_clone_rows(
            session,
            work_recipe.age_range_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        changed_character_fields += _collect_character_patch_rows(
            session,
            work_recipe.character_patches,
            source_dbs,
            rows_by_table,
            loc_rows,
            patched_skill_set_keys,
            reference_paths or [],
            opened_pack_keys,
        )
        cloned_characters += _collect_character_clone_rows(
            session,
            work_recipe.character_clones,
            source_dbs,
            rows_by_table,
            loc_rows,
            reference_paths or [],
            opened_pack_keys,
        )
        copied_dependency_rows += _collect_character_dependency_rows(
            session,
            work_recipe.character_clones,
            source_dbs,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        processed_clones.extend(work_recipe.character_clones)
        processed_patches.extend(work_recipe.character_patches)

    active_pack_paths = ordered_active_ccd_pack_paths(
        Path(session.pack_path),
        reference_paths or [],
    )
    source_ceo_defaults: dict[str, dict[str, Any]] = {}
    ceo_set_entries = _ceo_set_entries_for_characters(
        processed_clones,
        processed_patches,
        source_ceo_defaults=source_ceo_defaults,
    )
    equipment_entries = _equipment_entries_for_characters(
        processed_clones,
        processed_patches,
    )
    campaign_script = build_campaign_start_script(
        _spawn_entries_for_clones(processed_clones),
        ceo_set_entries,
        equipment_entries,
        work_entries=_diagnostic_work_entries(processed_clones, processed_patches),
        escape=_lua_escape,
        string_list=_lua_string_list,
    )
    dedicated_armour_pool = None
    dedicated_armour_ccd_path = None
    diagnostic_warnings = [
        *_clone_image_asset_target_warnings(processed_clones),
        *_image_asset_path_warnings([*processed_clones, *processed_patches]),
        *_character_clone_integrity_warnings(processed_clones, rows_by_table, loc_rows),
    ]
    processed_recipe = _recipe_with_processed_characters(recipe, processed_clones, processed_patches)
    _write_delta_diagnostics(
        output_path,
        processed_recipe,
        rows_by_table,
        loc_rows,
        campaign_script,
        diagnostic_warnings,
        ceo_set_entries=ceo_set_entries,
        equipment_entries=equipment_entries,
    )

    require_clean_references(list(rows_by_table))
    require_clean_references(list(rows_by_table.values()))
    target_key = _new_delta_pack(session)
    try:
        for table_path, rows in rows_by_table.items():
            source_db = source_dbs[table_path]
            _write_db_file(session, target_key, table_path, source_db, rows)

        if campaign_script:
            for campaign_script_path in CAMPAIGN_SPAWN_SCRIPT_PATHS:
                _write_lua_text_file(
                    session,
                    target_key,
                    campaign_script_path,
                    campaign_script,
                )

        if dedicated_armour_ccd_path is not None:
            _write_binary_packed_file(
                session,
                target_key,
                CCD_PACK_PATH,
                dedicated_armour_ccd_path,
            )

        if loc_rows:
            _write_loc_file(
                session,
                target_key,
                "text/hby_mtu_pack_editor_names.loc",
                loc_rows,
            )

        # Lua is the single spawn path. Pairing it with SPAWN_AGENT_OFF_MAP can
        # duplicate characters, while the DB-only event does not reliably fire.
        incident_tables = 0
        copied_assets = _copy_image_assets(
            session,
            target_key,
            [*processed_clones, *processed_patches],
            opened_pack_keys,
        )
        copied_model_assets = _copy_uniform_model_assets(
            session,
            target_key,
            rows_by_table,
            reference_paths or [],
            opened_pack_keys,
        )
        copied_fixed_model_assets = _write_equipment_independent_model_assets(
            session,
            target_key,
            rows_by_table,
            reference_paths or [],
        )
        copied_equipment_assets = _copy_equipment_ceo_raw_assets(
            session,
            target_key,
            [*processed_clones, *processed_patches],
            reference_paths or [],
            opened_pack_keys,
        )

        _raise_rpfm_error(session.client.send({"SavePackAs": [target_key, str(output_path)]}))
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise

    return [
        {"level": message.level, "code": message.code, "message": message.message}
        for message in messages
    ] + [
        {
            "level": "success",
            "code": "delta_pack_written",
            "message": (
                f"Wrote delta patch pack {output_path} ({output_path.stat().st_size} bytes) "
                f"with {len(rows_by_table)} DB table(s), {changed_stats} edited equipment stat value(s), "
                f"{cloned_armour_types} cloned armour type row(s), "
                f"{cloned_land_units} cloned land unit row(s), "
                f"{attribute_sets} cloned attribute set(s), "
                f"{skill_sets} cloned romance skill set(s), "
                f"{age_ranges} cloned age range row(s), "
                f"{changed_character_fields} edited character field(s), {cloned_characters} cloned character(s), "
                f"{copied_dependency_rows} referenced DB row(s), "
                f"{len(loc_rows)} name loc row(s), {incident_tables} spawn incident table(s), "
                f"{copied_assets} image asset(s), "
                f"{copied_model_assets} uniform model asset(s), "
                f"{copied_fixed_model_assets} equipment-independent model asset(s), "
                f"{copied_equipment_assets} equipment CEO asset(s), "
                f"0 dedicated armour CEO CCD(s), "
                f"and {1 if campaign_script else 0} campaign script(s)."
            ),
        }
    ]


def build_delta_pack_from_materials(
    source_session: Any,
    writer_session: RpfmPackSession,
    recipe: Recipe,
    output_path: Path,
    reference_paths: list[Path] | None = None,
) -> list[dict[str, object]]:
    class MaterialWriterSession:
        client = writer_session.client
        pack_key = writer_session.pack_key
        pack_path = writer_session.pack_path
        decoded_db_by_path = source_session.decoded_db_by_path

        def list_tables(self, source: str = "pack") -> list[str]:
            return source_session.list_tables(source)

        def read_table(self, table_name: str, source: str = "pack") -> list[dict[str, Any]]:
            return source_session.read_table(table_name, source)

        def _resolve_table_path(self, table_name: str, source: str = "pack") -> str:
            return source_session._resolve_table_path(table_name, source)

        def list_files(self) -> list[str]:
            return writer_session.list_files()

        def list_loc_files(self) -> list[str]:
            return writer_session.list_loc_files()

        def metadata(self) -> dict[str, Any]:
            return source_session.metadata()

        def material_source_path_for_table(self, table_name: str) -> str:
            path = source_session._resolve_table_path(table_name)
            entry = getattr(source_session, "payload", {}).get("tables", {}).get(path, {})
            if isinstance(entry, dict):
                return str(entry.get("sourcePath") or "")
            return ""

    return build_delta_pack(
        MaterialWriterSession(),  # type: ignore[arg-type]
        recipe,
        output_path,
        reference_paths or [],
    )


def _processing_recipes(recipe: Recipe) -> list[Recipe]:
    if not recipe.work_items:
        return [recipe]
    recipes: list[Recipe] = []
    for work in recipe.work_items:
        work_recipe = dict(work.get("recipe") or {})
        work_recipe["modName"] = recipe.mod_name
        recipes.append(recipe_from_dict(work_recipe))
    return recipes


def _validate_hidden_armour_adjustment_links(recipe: Recipe) -> None:
    skill_clones = {
        clone.new_set_key: clone
        for clone in recipe.skill_set_clones
    }
    for character in recipe.character_clones:
        assignment = character.dedicated_armour
        if assignment is None or assignment.slot_id != "hidden-skill-adjustment":
            continue
        source_value = assignment.source_armour_value
        if source_value is None:
            raise ValueError(
                "Hidden combat adjustment is missing the source armour value: "
                f"{character.new_template_key}"
            )
        bonuses = {
            "armour_bonus": int(assignment.armour_value) - int(source_value),
            "melee_defence_bonus": int(assignment.melee_defence_bonus),
            "melee_attack_bonus": int(assignment.melee_attack_bonus),
            "melee_damage_bonus": int(assignment.melee_damage_bonus),
            "ap_melee_damage_bonus": int(assignment.ap_melee_damage_bonus),
            "charge_bonus": int(assignment.charge_bonus),
            "missile_defence_bonus": int(assignment.missile_defence_bonus),
        }
        if not any(bonuses.values()):
            continue
        linked_set_keys = {
            str(overrides.get("skill_set_override") or "")
            for overrides in character.detail_overrides.values()
            if overrides.get("skill_set_override")
        }
        matching_sets = [
            skill_clones[set_key]
            for set_key in linked_set_keys
            if set_key in skill_clones
            and all(
                int(getattr(skill_clones[set_key], field_name)) == bonus
                for field_name, bonus in bonuses.items()
            )
        ]
        if not matching_sets:
            raise ValueError(
                "Hidden combat adjustment is not linked to the generated character skill set: "
                f"template={character.new_template_key}, bonuses={bonuses}"
            )


def _recipe_with_processed_characters(
    recipe: Recipe,
    clones: list[CharacterClone],
    patches: list[CharacterPatch],
) -> Recipe:
    return Recipe(
        mod_name=recipe.mod_name,
        equipment_stat_patches=recipe.equipment_stat_patches,
        armour_type_clones=recipe.armour_type_clones,
        land_unit_clones=recipe.land_unit_clones,
        skill_set_clones=recipe.skill_set_clones,
        attribute_set_clones=recipe.attribute_set_clones,
        age_range_clones=recipe.age_range_clones,
        character_clones=clones,
        character_patches=patches,
        work_items=recipe.work_items,
        raw=recipe.raw,
    )


def _collect_stat_patch_rows(
    session: RpfmPackSession,
    recipe: Recipe,
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    changed = 0
    tables, table_names = _load_reference_backed_stat_tables(
        session,
        source_dbs,
        reference_paths or [],
        opened_pack_keys,
    )
    for patch in recipe.equipment_stat_patches:
        try:
            target = _resolve_reference_backed_stat_target(
                tables,
                table_names,
                patch.equipment_key,
                patch.stat_table,
                patch.column,
                patch.value,
                patch.game_mode,
            )
        except ValueError as error:
            if str(error).startswith("Equipment stat mapping not found:"):
                continue
            raise
        rows = tables[target.stat_table]
        row = _find_required(rows, "key", target.row_key)
        patched = {**row, target.column: target.value}
        table_path = row.get("_sourceTablePath") or target.table_name
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(patched))
        row[target.column] = target.value
        changed += 1
    return changed


def _load_reference_backed_stat_tables(
    session: RpfmPackSession,
    source_dbs: dict[str, dict[str, Any]],
    reference_paths: list[Path],
    opened_pack_keys: dict[str, str] | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    aliases = {
        alias: TABLE_ALIASES[alias]
        for alias in (
            "equipment_variants_weapons",
            "equipment_variants_armours",
            "melee_weapons",
            "missile_weapons",
            "projectiles",
            "unit_armour_types",
            "land_units",
        )
    }
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths,
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    return tables, table_names


def _resolve_reference_backed_stat_target(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    equipment_key: str,
    stat_table: str,
    column: str,
    value: int | float,
    game_mode: str | None,
) -> StatTarget:
    if stat_table == "land_unit":
        row = _require_stat_row(tables.get("land_units", []), equipment_key, column)
        return StatTarget("land_units", row.get("_sourceTablePath") or table_names["land_units"], equipment_key, column, value)

    if stat_table == "armour":
        direct_row = _find_row(tables.get("unit_armour_types", []), "key", equipment_key)
        if direct_row is not None:
            _require_stat_row(
                tables.get("unit_armour_types", []),
                equipment_key,
                column,
                numeric=column != "audio_type",
            )
            return StatTarget(
                "unit_armour_types",
                direct_row.get("_sourceTablePath") or table_names["unit_armour_types"],
                equipment_key,
                column,
                value,
            )
        variants = tables.get("equipment_variants_armours", [])
        variant = _find_stat_variant_any(
            variants,
            _equipment_key_spellings(equipment_key),
            game_mode,
            "armour",
        )
        row_key = variant["armour"]
        row = _require_stat_row(
            tables.get("unit_armour_types", []),
            row_key,
            column,
            numeric=column != "audio_type",
        )
        return StatTarget("unit_armour_types", row.get("_sourceTablePath") or table_names["unit_armour_types"], row_key, column, value)

    if stat_table == "melee_weapon":
        variant = _find_stat_variant(tables.get("equipment_variants_weapons", []), equipment_key, game_mode, "primary_melee_weapon")
        row_key = variant["primary_melee_weapon"]
        row = _require_stat_row(tables.get("melee_weapons", []), row_key, column)
        return StatTarget("melee_weapons", row.get("_sourceTablePath") or table_names["melee_weapons"], row_key, column, value)

    variant = _find_stat_variant(tables.get("equipment_variants_weapons", []), equipment_key, game_mode, "primary_missile_weapon")
    missile_key = variant["primary_missile_weapon"]
    missile = _require_stat_row(tables.get("missile_weapons", []), missile_key, "default_projectile", numeric=False)
    row_key = missile["default_projectile"]
    row = _require_stat_row(tables.get("projectiles", []), row_key, column)
    return StatTarget("projectiles", row.get("_sourceTablePath") or table_names["projectiles"], row_key, column, value)


def _find_stat_variant(
    rows: list[dict[str, Any]],
    equipment_key: str,
    game_mode: str | None,
    stat_key_field: str,
) -> dict[str, Any]:
    matches = [
        row for row in rows
        if row.get("ceos_key") == equipment_key and row.get(stat_key_field)
    ]
    if game_mode is not None:
        matches = [row for row in matches if row.get("game_mode") == game_mode]
    if not matches:
        suffix = f" for gameMode {game_mode}" if game_mode else ""
        raise ValueError(f"Equipment stat mapping not found: {equipment_key}{suffix}")
    if len(matches) > 1 and game_mode is None:
        raise ValueError(f"Equipment stat mapping is ambiguous; provide gameMode: {equipment_key}")
    return matches[0]


def _find_stat_variant_any(
    rows: list[dict[str, Any]],
    equipment_keys: list[str],
    game_mode: str | None,
    stat_key_field: str,
) -> dict[str, Any]:
    last_error: ValueError | None = None
    for equipment_key in equipment_keys:
        try:
            return _find_stat_variant(rows, equipment_key, game_mode, stat_key_field)
        except ValueError as error:
            last_error = error
    raise last_error or ValueError(f"Equipment stat mapping not found: {equipment_keys[0] if equipment_keys else ''}")


def _equipment_key_spellings(equipment_key: str) -> list[str]:
    candidates = [equipment_key]
    if "_ancillary_" in equipment_key:
        candidates.append(equipment_key.replace("_ancillary_", "_ancilliary_"))
    if "_ancilliary_" in equipment_key:
        candidates.append(equipment_key.replace("_ancilliary_", "_ancillary_"))
    return list(dict.fromkeys(candidates))


def _require_stat_row(
    rows: list[dict[str, Any]],
    row_key: str,
    column: str,
    numeric: bool = True,
) -> dict[str, Any]:
    row = _find_required(rows, "key", row_key)
    if column not in row:
        raise ValueError(f"Column is missing on stat row: {row_key}/{column}")
    if numeric and not isinstance(row[column], (int, float)):
        raise ValueError(f"Column is not numeric on stat row: {row_key}/{column}")
    return row


def _collect_armour_type_clone_rows(
    session: RpfmPackSession,
    clones: list[ArmourTypeClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    aliases = {"unit_armour_types": TABLE_ALIASES["unit_armour_types"]}
    table_names = _optional_table_names(session, aliases)
    if "unit_armour_types" not in table_names:
        table_names["unit_armour_types"] = resolve_table_name(session, "unit_armour_types")
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    rows = tables["unit_armour_types"]
    created = 0
    for clone in clones:
        source = _find_required(rows, "key", clone.source_key)
        _validate_armour_type_clone_from_row(rows, source, clone)
        cloned = {**source, "key": clone.new_key, **clone.overrides}
        table_path = source.get("_sourceTablePath") or table_names["unit_armour_types"]
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(cloned))
        rows.append({**cloned, "_sourceTablePath": table_path})
        created += 1
    return created


def _validate_armour_type_clone_from_row(
    rows: list[dict[str, Any]],
    source: dict[str, Any],
    clone: ArmourTypeClone,
) -> None:
    if _find_row(rows, "key", clone.new_key) is not None:
        raise ValueError(f"New armour type already exists: {clone.new_key}")
    unknown_columns = set(clone.overrides) - {"armour_value", "audio_type"}
    if unknown_columns:
        raise ValueError(f"Unsupported armour type override column: {', '.join(sorted(unknown_columns))}")
    for column, value in clone.overrides.items():
        if column not in source:
            raise ValueError(f"Column is missing on armour type row: {clone.source_key}/{column}")
        if column == "audio_type":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Armour audio_type must be a non-empty string: {clone.new_key}/{column}")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Armour override must be a non-negative number: {clone.new_key}/{column}")


def _collect_land_unit_clone_rows(
    session: RpfmPackSession,
    recipe: Recipe,
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not recipe.land_unit_clones:
        return 0
    aliases = {
        "land_units": TABLE_ALIASES["land_units"],
        "main_units": TABLE_ALIASES["main_units"],
        "retinues": _character_dependency_aliases()["retinues"],
        "retinue_slot_initial_units": _character_dependency_aliases()["retinue_slot_initial_units"],
        "cai_retinues_to_aspects": _character_dependency_aliases()["cai_retinues_to_aspects"],
    }
    table_names = _optional_table_names(session, aliases)
    if "land_units" not in table_names:
        table_names["land_units"] = resolve_table_name(session, "land_units")
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    rows = tables["land_units"]
    created = 0
    for clone in recipe.land_unit_clones:
        source = _find_required(rows, "key", clone.source_key)
        _validate_land_unit_clone_from_row(rows, source, clone)
        cloned = {**source, "key": clone.new_key, **clone.overrides}
        table_path = source.get("_sourceTablePath") or table_names["land_units"]
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(cloned))
        rows.append({**cloned, "_sourceTablePath": table_path})
        main_unit_key = _clone_main_unit_for_land_unit(tables, table_names, rows_by_table, clone)
        _clone_retinue_chain_for_land_unit(tables, table_names, rows_by_table, clone, main_unit_key)
        created += 1
    return created


def _validate_land_unit_clone_from_row(
    rows: list[dict[str, Any]],
    source: dict[str, Any],
    clone: Any,
) -> None:
    if _find_row(rows, "key", clone.new_key) is not None:
        raise ValueError(f"New land unit already exists: {clone.new_key}")
    unknown_columns = set(clone.overrides) - {
        "armour",
        "charge_bonus",
        "dismounted_charge_bonus",
        "dismounted_melee_attack",
        "melee_attack",
        "melee_defence",
        "morale",
        "primary_ammo",
    }
    if unknown_columns:
        raise ValueError(f"Unsupported land unit override column: {', '.join(sorted(unknown_columns))}")
    for column, value in clone.overrides.items():
        if column not in source:
            raise ValueError(f"Column is missing on land unit row: {clone.source_key}/{column}")
        if column == "armour":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Land unit armour override must be a non-empty string: {clone.new_key}/{column}")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Land unit override must be a non-negative number: {clone.new_key}/{column}")


def _clone_retinue_chain_for_land_unit(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    clone: Any,
    main_unit_key: str | None = None,
) -> None:
    source_retinue_key = str(getattr(clone, "source_retinue_key", "") or "")
    new_retinue_key = str(getattr(clone, "new_retinue_key", "") or "")
    if not source_retinue_key or not new_retinue_key:
        return

    source_retinue = _find_row(tables.get("retinues", []), "key", source_retinue_key)
    if source_retinue is None:
        return
    retinue_table = source_retinue.get("_sourceTablePath") or table_names.get("retinues")
    if retinue_table:
        _upsert_delta_row(
            rows_by_table,
            retinue_table,
            "key",
            _clean_source_row({**source_retinue, "key": new_retinue_key}),
        )

    cloned_slot_count = 0
    for row in tables.get("retinue_slot_initial_units", []):
        if row.get("retinue") != source_retinue_key:
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("retinue_slot_initial_units")
        if not table_path:
            continue
        initial_unit = (
            main_unit_key or clone.new_key
            if row.get("initial_unit_record") == clone.source_key
            else row.get("initial_unit_record")
        )
        _upsert_delta_row(
            rows_by_table,
            table_path,
            _retinue_slot_key,
            _clean_source_row({**row, "retinue": new_retinue_key, "initial_unit_record": initial_unit}),
        )
        cloned_slot_count += 1

    if cloned_slot_count == 0:
        table_path = table_names.get("retinue_slot_initial_units")
        if table_path:
            _upsert_delta_row(
                rows_by_table,
                table_path,
                _retinue_slot_key,
                {
                    "retinue": new_retinue_key,
                    "slot_index": 0,
                    "initial_unit_record": main_unit_key or clone.new_key,
                    "campaign": "",
                },
            )

    for row in tables.get("cai_retinues_to_aspects", []):
        if row.get("retinue") != source_retinue_key:
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("cai_retinues_to_aspects")
        if table_path:
            _upsert_delta_row(
                rows_by_table,
                table_path,
                _retinue_aspect_key,
                _clean_source_row({**row, "retinue": new_retinue_key}),
            )


def _clone_main_unit_for_land_unit(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    clone: Any,
) -> str | None:
    rows = tables.get("main_units", [])
    if not rows:
        return None
    source = (
        _find_row(rows, "unit", clone.source_key)
        or _find_row(rows, "key", clone.source_key)
        or next((row for row in rows if row.get("land_unit") == clone.source_key), None)
    )
    if source is None:
        return None
    key_field = "unit" if "unit" in source else "key"
    if _find_row(rows, key_field, clone.new_key) is not None:
        raise ValueError(f"New main unit already exists: {clone.new_key}")
    cloned = {**source, key_field: clone.new_key}
    if "land_unit" in cloned:
        cloned["land_unit"] = clone.new_key
    if "unique_index" in cloned:
        cloned["unique_index"] = _unique_numeric_delta_value(
            f"main_units:{clone.new_key}",
            [*rows, *[row for table_rows in rows_by_table.values() for row in table_rows]],
            "unique_index",
        )
    table_path = source.get("_sourceTablePath") or table_names.get("main_units")
    if not table_path:
        return None
    _upsert_delta_row(rows_by_table, table_path, _main_unit_key, _clean_source_row(cloned))
    rows.append({**cloned, "_sourceTablePath": table_path})
    return clone.new_key


def _collect_attribute_set_clone_rows(
    session: RpfmPackSession,
    clones: list[AttributeSetClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
        if alias in {"character_attribute_sets", "character_attributes"}
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    created = 0
    for clone in clones:
        _ensure_attribute_set_rows_available(tables, source_dbs, clone.source_set_key)
        source_set = dict(_find_required_by(tables.get("character_attribute_sets", []), _attribute_set_key, clone.source_set_key))
        set_table = source_set.get("_sourceTablePath") or table_names.get("character_attribute_sets")
        if not set_table:
            raise ValueError("Source attribute set table not found.")
        new_set = _with_attribute_set_key(source_set, clone.new_set_key)
        _upsert_delta_row(rows_by_table, set_table, _attribute_set_key, new_set)

        source_attrs = [
            row for row in tables.get("character_attributes", [])
            if _attribute_set_key(row) == clone.source_set_key
        ]
        if not source_attrs:
            raise ValueError(f"Source attribute set has no attributes: {clone.source_set_key}")
        for source_attr in source_attrs:
            attr_key = _attribute_override_key(source_attr)
            value_column = _attribute_value_column(source_attr)
            new_attr = _with_attribute_set_key(source_attr, clone.new_set_key)
            if attr_key in clone.overrides and value_column:
                new_attr[value_column] = clone.overrides[attr_key]
            attr_table = source_attr.get("_sourceTablePath") or table_names.get("character_attributes")
            if attr_table:
                _upsert_delta_row(rows_by_table, attr_table, _attribute_key, _clean_source_row(new_attr))
        tables.setdefault("character_attribute_sets", []).append({**new_set, "_sourceTablePath": set_table})
        tables.setdefault("character_attributes", []).extend(
            _with_attribute_set_key(row, clone.new_set_key)
            for row in source_attrs
        )
        created += 1
    return created


def _collect_skill_set_clone_rows(
    session: RpfmPackSession,
    clones: list[SkillSetClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    # Material snapshots contain multiple physical DB files for the same table
    # folder (vanilla, DLC, MTU, and other supported references).  Reading only
    # the first resolved path made the web summary advertise real skills that
    # the pack builder could not later resolve.  Aggregate every matching table
    # from the active material session before resolving replacements and copying
    # their dependency graph.
    _merge_dependency_tables_from_pack(
        session,
        session.pack_key,
        session.list_tables(),
        aliases,
        tables,
        source_dbs,
    )
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    known_skill_keys = _known_character_skill_keys(tables)

    created = 0
    for clone in clones:
        source_set = dict(_find_required(tables.get("character_skill_node_sets", []), "key", clone.source_set_key))
        new_set = {**source_set, "key": clone.new_set_key}
        _upsert_delta_row(rows_by_table, table_names["character_skill_node_sets"], "key", new_set)

        source_nodes = [
            row for row in tables.get("character_skill_nodes", [])
            if row.get("character_skill_node_set_key") == clone.source_set_key
        ]
        if not source_nodes:
            raise ValueError(f"Source skill node set has no nodes: {clone.source_set_key}")
        node_key_map = {
            str(row.get("key")): _skill_node_clone_key(clone.source_set_key, clone.new_set_key, str(row.get("key")))
            for row in source_nodes
            if row.get("key")
        }
        used_skill_keys: set[str] = set()
        for source_node in source_nodes:
            old_key = str(source_node.get("key") or "")
            source_skill_key = str(source_node.get("character_skill_key") or "")
            requested_skill_key = str(clone.replacements.get(old_key) or "")
            # Recipes saved by older UI builds can contain catalog-only pseudo
            # keys.  Never write those broken references into a pack.  The UI
            # now exposes only real DB-backed keys; stale recipes safely retain
            # the source node skill instead of creating a dependency-less node.
            new_skill_key = (
                requested_skill_key
                if requested_skill_key in known_skill_keys
                else source_skill_key
            )
            if new_skill_key:
                used_skill_keys.add(str(new_skill_key))
            new_node = {
                **source_node,
                "key": node_key_map[old_key],
                "character_skill_node_set_key": clone.new_set_key,
                "character_skill_key": new_skill_key,
            }
            _upsert_delta_row(rows_by_table, table_names["character_skill_nodes"], "key", new_node)

        source_node_keys = set(node_key_map)
        for source_link in tables.get("character_skill_node_links", []):
            parent = str(source_link.get("parent_key") or "")
            child = str(source_link.get("child_key") or "")
            if parent not in source_node_keys and child not in source_node_keys:
                continue
            new_link = {
                **source_link,
                "parent_key": node_key_map.get(parent, parent),
                "child_key": node_key_map.get(child, child),
            }
            _upsert_delta_row(rows_by_table, table_names["character_skill_node_links"], _skill_link_key, new_link)

        if (
            clone.armour_bonus
            or clone.melee_defence_bonus
            or clone.missile_defence_bonus
        ):
            _add_hidden_armour_bonus_skill(
                clone,
                source_nodes,
                tables,
                table_names,
                rows_by_table,
            )

        _copy_skill_effect_dependencies(tables, table_names, rows_by_table, used_skill_keys)
        created += 1
    return created


def _known_character_skill_keys(
    tables: dict[str, list[dict[str, Any]]],
) -> set[str]:
    keys = {
        str(row.get("character_skill_key") or "")
        for row in tables.get("character_skill_nodes", [])
    }
    keys.update(
        str(row.get("character_skill_key") or "")
        for row in tables.get("character_skill_level_to_effects_junctions", [])
    )
    keys.update(
        str(row.get("key") or "")
        for row in tables.get("character_skills", [])
    )
    return {key for key in keys if key}


def _add_hidden_armour_bonus_skill(
    clone: SkillSetClone,
    source_nodes: list[dict[str, Any]],
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
) -> None:
    bonus_effects = [
        (
            "armour",
            int(clone.armour_bonus),
            "3k_main_effect_character_stat_mod_armour",
            "character_to_character_own",
            500,
        ),
        (
            "melee defence",
            int(clone.melee_defence_bonus),
            "3k_main_effect_character_stat_mod_melee_defence",
            "character_to_character_own",
            100,
        ),
        (
            "missile defence",
            int(clone.missile_defence_bonus),
            "3k_main_effect_character_stat_mod_missile_defence",
            "character_to_character_own",
            100,
        ),
    ]
    active_effects = [
        (label, bonus, effect_key, effect_scope, limit)
        for label, bonus, effect_key, effect_scope, limit in bonus_effects
        if bonus
    ]
    for label, bonus, _effect_key_value, _effect_scope, limit in active_effects:
        if not -limit <= bonus <= limit:
            raise ValueError(
                f"Hidden {label} skill bonus is outside -{limit}..{limit}: {bonus}"
            )
    if not source_nodes:
        raise ValueError(
            f"Cannot add combat bonuses to empty skill set: {clone.new_set_key}"
        )

    skill_key, node_key = _hidden_armour_skill_keys(
        clone.new_set_key,
        int(clone.armour_bonus),
        int(clone.melee_defence_bonus),
        int(clone.missile_defence_bonus),
    )
    source_skill = _find_row(
        tables.get("character_skills", []),
        "key",
        "3k_main_skill_bodyguard_water_strategist_alt_2",
    )
    if not source_skill:
        source_skill = next(iter(tables.get("character_skills", [])), None)
    if not source_skill:
        raise ValueError("Vanilla character_skills data is required for hidden combat bonuses.")
    skill_table = str(
        source_skill.get("_sourceTablePath")
        or table_names.get("character_skills")
        or ""
    )
    if not skill_table:
        raise ValueError("Output table for the hidden armour skill was not resolved.")
    hidden_skill = {
        **source_skill,
        "key": skill_key,
        "image_path": "",
        "localised_name": "Hidden combat adjustment",
        "localised_description": "Generated character combat adjustment",
        "unlocked_at_rank": 0,
        "is_background_skill": False,
        "is_female_only_background_skill": False,
        "is_male_only_background_skill": False,
        "background_weighting": 0.0,
    }
    _upsert_delta_row(
        rows_by_table,
        skill_table,
        "key",
        _clean_source_row(hidden_skill),
    )

    hidden_node = {
        **source_nodes[0],
        "key": node_key,
        "character_skill_node_set_key": clone.new_set_key,
        "character_skill_key": skill_key,
        "indent": 0.0,
        "tier": 0.0,
        "points_on_creation": 1,
        "required_num_parents": 0,
        "visible_in_ui": False,
        "can_meet_parent_requirment_with_children": True,
    }
    _upsert_delta_row(
        rows_by_table,
        table_names["character_skill_nodes"],
        "key",
        _clean_source_row(hidden_node),
    )

    effect_table = str(table_names.get("character_skill_level_to_effects_junctions") or "")
    if not effect_table:
        raise ValueError("Output table for the hidden combat effects was not resolved.")
    for _label, bonus, effect_key, effect_scope, _limit in active_effects:
        _upsert_delta_row(
            rows_by_table,
            effect_table,
            _skill_effect_key,
            {
                "character_skill_key": skill_key,
                "effect_key": effect_key,
                "effect_scope": effect_scope,
                "level": 1,
                "value": float(bonus),
            },
        )
        _copy_matching_rows(
            tables,
            table_names,
            rows_by_table,
            "effects",
            lambda row, expected=effect_key: _effect_key(row) == expected,
            _effect_key,
        )


def _hidden_armour_skill_keys(
    skill_set_key: str,
    armour_bonus: int,
    melee_defence_bonus: int = 0,
    missile_defence_bonus: int = 0,
) -> tuple[str, str]:
    if not melee_defence_bonus and not missile_defence_bonus:
        # Preserve the existing armour-only key so regenerated packs remain
        # compatible with saves made before the defence-chance controls.
        profile = f"armour:{int(armour_bonus)}"
    else:
        profile = (
            f"armour:{int(armour_bonus)}"
            f"|melee_defence:{int(melee_defence_bonus)}"
            f"|missile_defence:{int(missile_defence_bonus)}"
        )
    skill_checksum = zlib.crc32(profile.encode("utf-8")) & 0xFFFFFFFF
    skill_token = f"{skill_checksum:08x}"
    skill_key = f"hby_mtu_hidden_armour_adjustment_{skill_token}"
    node_profile = f"{skill_set_key}\0{skill_key}"
    node_checksum = zlib.crc32(node_profile.encode("utf-8")) & 0xFFFFFFFF
    node_token = f"{node_checksum:08x}"
    return (
        skill_key,
        f"hby_mtu_hidden_armour_adjustment_node_{node_token}",
    )


def _collect_character_patch_rows(
    session: RpfmPackSession,
    patches: list[CharacterPatch],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
    patched_skill_set_keys: set[str] | None = None,
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not patches:
        return 0
    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    for alias in (
        "character_generation_templates",
        "character_generation_template_game_mode_details",
    ):
        if alias not in table_names:
            table_names[alias] = resolve_character_table_name(session, alias)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    templates = tables["character_generation_templates"]
    details = tables["character_generation_template_game_mode_details"]
    patched_skill_set_keys = patched_skill_set_keys or set()

    changed = 0
    for patch in patches:
        art_set_overrides = patch.art_set_overrides or {}
        art_overrides = patch.art_overrides or {}
        source_template = _find_required(templates, "key", patch.template_key)
        source_art_set_id = str(source_template.get("art_set_override") or "")
        related_template_keys_list = [patch.template_key]
        related_template_keys = set(related_template_keys_list)
        if not related_template_keys:
            related_template_keys = {patch.template_key}
        allow_related_art_sets = len(related_template_keys_list) > 1
        patch_templates = [
            row for row in templates
            if str(row.get("key") or "").lower() in related_template_keys
            and (
                allow_related_art_sets
                or
                str(row.get("key") or "") == patch.template_key
                or str(row.get("art_set_override") or "") == source_art_set_id
            )
        ] or [source_template]
        patched_template_keys: set[str] = set()
        art_set_ids: list[str] = []
        for source_template_row in patch_templates:
            target_template_key = str(source_template_row.get("key") or "")
            template_table = source_template_row.get("_sourceTablePath") or table_names["character_generation_templates"]
            existing_template = _find_delta_row(rows_by_table, "key", target_template_key, template_table)
            template = dict(existing_template or source_template_row)
            for column, value in patch.template_overrides.items():
                if template.get(column) != value:
                    template[column] = value
                    changed += 1
            if _apply_character_patch_name(session, source_dbs, rows_by_table, template, patch, loc_rows):
                changed += 1
            _upsert_delta_row(
                rows_by_table,
                template_table,
                "key",
                _clean_source_row(template),
            )
            patched_template_keys.add(target_template_key)
            art_set_id = str(template.get("art_set_override") or "")
            if art_set_id and art_set_id not in art_set_ids:
                art_set_ids.append(art_set_id)
        for art_set_id in art_set_ids:
            if source_art_set_id and art_set_id != source_art_set_id:
                _clone_art_set_patch_delta(
                    tables,
                    table_names,
                    source_dbs,
                    rows_by_table,
                    source_art_set_id,
                    art_set_id,
                    art_set_overrides,
                    art_overrides,
                )
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_art_sets",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                "art_set_id",
            )
            if art_set_overrides:
                _patch_art_set_row(
                    tables,
                    table_names,
                    rows_by_table,
                    art_set_id,
                    art_set_overrides,
                )
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_arts",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                _art_key,
            )
            if art_overrides:
                _patch_art_rows(
                    tables,
                    table_names,
                    rows_by_table,
                    art_set_id,
                    art_overrides,
                )
            if art_set_overrides and "is_male" in art_set_overrides:
                _patch_child_art_rows_for_gender(
                    tables,
                    table_names,
                    rows_by_table,
                    art_set_id,
                    _coerce_bool(art_set_overrides["is_male"]),
                )
            _copy_agent_uniform_dependencies(
                tables,
                table_names,
                source_dbs,
                rows_by_table,
                _output_art_rows_for_art_set(rows_by_table, art_set_id),
            )
        for patched_template_key in patched_template_keys:
            patched_template = next(
                (
                    row for row in rows_by_table.get(table_names["character_generation_templates"], [])
                    if str(row.get("key") or "") == patched_template_key
                ),
                None,
            ) or next((row for row in patch_templates if str(row.get("key") or "") == patched_template_key), {})
            age_range = str(patched_template.get("spawn_age_range") or "")
            if age_range:
                _copy_matching_rows(
                    tables,
                    table_names,
                    rows_by_table,
                    "character_generation_spawn_age_ranges",
                    lambda row, key=age_range: row.get("key") == key,
                    "key",
                )

        patch_details: list[tuple[dict[str, Any], str]] = []
        for patched_template_key in sorted(patched_template_keys):
            source_detail_rows = [
                row for row in details
                if str(row.get("character_generation_template") or "") == patched_template_key
            ]
            existing_modes = {
                str(row.get("game_mode") or "")
                for row in source_detail_rows
                if row.get("game_mode") not in (None, "")
            }
            fallback_mode = "historical" if "historical" in existing_modes else "romance"
            for detail in _required_game_mode_details(source_detail_rows):
                game_mode = str(detail.get("game_mode") or "")
                override_mode = game_mode
                if game_mode not in existing_modes and game_mode not in patch.detail_overrides:
                    override_mode = fallback_mode
                patch_details.append((detail, override_mode))

        for detail, override_mode in patch_details:
            overrides = patch.detail_overrides.get(override_mode, {})
            detail_table = detail.get("_sourceTablePath") or table_names["character_generation_template_game_mode_details"]
            existing_detail = _find_delta_row(rows_by_table, _detail_key, _detail_key(detail), detail_table)
            patched = dict(existing_detail or detail)
            title_initial_override = _title_initial_override_to_ignore(patch.title_ceo_key, overrides.get("initial_ceos"))
            for column, value in overrides.items():
                if column == "initial_ceos" and title_initial_override:
                    continue
                if patched.get(column) != value:
                    patched[column] = value
                    changed += 1
            resolved_initial_ceo = _resolve_non_generic_initial_ceo(
                tables,
                table_names,
                source_dbs,
                patched.get("initial_ceos"),
                patch.template_key,
            )
            if resolved_initial_ceo and patched.get("initial_ceos") != resolved_initial_ceo:
                patched["initial_ceos"] = resolved_initial_ceo
                changed += 1
            _upsert_delta_row(
                rows_by_table,
                detail_table,
                _detail_key,
                _clean_source_row(patched),
            )
            _copy_initial_ceo_dependency(tables, table_names, source_dbs, rows_by_table, patched.get("initial_ceos"))
            _copy_attribute_dependency(tables, table_names, source_dbs, rows_by_table, patched.get("attribute_set"))
            if str(patched.get("skill_set_override") or "") not in patched_skill_set_keys:
                _copy_skill_dependency(tables, table_names, rows_by_table, patched.get("skill_set_override"))
            _copy_retinue_dependency(tables, table_names, rows_by_table, patched.get("retinue"))
            _copy_skill_source_retinue_abilities(
                tables,
                table_names,
                source_dbs,
                rows_by_table,
                patched.get("skill_set_override"),
                patched.get("retinue"),
            )
    return changed


def _apply_character_patch_name(
    session: RpfmPackSession,
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    template: dict[str, Any],
    patch: CharacterPatch,
    loc_rows: dict[str, str],
) -> bool:
    display_name = str(patch.display_name or "").strip()
    if not display_name:
        return False
    name_column, current_name_id = _active_template_name_column(template)
    seed = f"{patch.template_key}:{display_name}".encode("utf-8")
    name_id = 2_000_000_000 + (zlib.crc32(seed) % 100_000_000)
    used_name_ids = _used_name_ids(session, source_dbs)
    while str(name_id) in used_name_ids or f"names_name_{name_id}" in loc_rows:
        name_id += 1
    source_name, names_table = _find_source_name_row(session, source_dbs, current_name_id)
    if source_name and names_table:
        name_row = {
            **source_name,
            "id": str(name_id),
            "frequency": 1,
        }
        _bind_private_name_group(session, source_dbs, rows_by_table, name_row, name_column)
        _upsert_delta_row(rows_by_table, names_table, "id", _clean_source_row(name_row))
    _set_template_single_name(template, name_column, name_id)
    loc_rows[f"names_name_{name_id}"] = display_name
    loc_rows[f"names_alt_name_{name_id}"] = display_name
    return True


def _bind_private_name_group(session, source_dbs, rows_by_table, name_row, name_column):
    """Keep explicit custom names visible across bundled faction name groups.

    Zero-weight private pools cannot feed names into random character creation.
    Existing cultural pools and their probabilities are never rewritten.
    """
    families = ('names_groups', 'name_orders', 'faction_to_name_groups')
    paths = {family: next((p for p in session.list_tables()
                          if f'/{family}_tables/' in p), None) for family in families}
    if not all(paths.values()):
        return  # Older/base bundles retain their existing naming behaviour.
    rows = {family: _read_rows(session, path, source_dbs) for family, path in paths.items()}
    group = int(name_row['id'])
    used = {int(r['key']) for r in rows['names_groups']}
    used.update(int(r['key']) for r in rows_by_table.get(paths['names_groups'], []))
    while group in used:
        group += 1
    name_row['names_group'] = group
    name_row['frequency'] = 0
    _upsert_delta_row(rows_by_table, paths['names_groups'], 'key', {'key': group})
    _upsert_delta_row(rows_by_table, paths['name_orders'],
                      lambda r: (r['name_group'], r['order'], r['type'], r['optional_language']),
                      {'name_group': group, 'order': 0,
                       'type': 'other' if name_column == 'other_name' else name_column,
                       'optional_language': ''})
    for faction in sorted({r['faction'] for r in rows['faction_to_name_groups']}):
        _upsert_delta_row(rows_by_table, paths['faction_to_name_groups'],
                          lambda r: (r['faction'], r['name_group']),
                          {'faction': faction, 'name_group': group, 'probability': 0})


def _used_name_ids(
    session: RpfmPackSession,
    source_dbs: dict[str, dict[str, Any]],
) -> set[str]:
    used: set[str] = set()
    table_paths = _name_table_paths(session)
    try:
        table_paths.append("names")
    except Exception:
        pass
    for table_path in dict.fromkeys(table_paths):
        try:
            rows = _read_rows(session, table_path, source_dbs)
        except Exception:
            continue
        for row in rows:
            value = row.get("id")
            if value not in (None, ""):
                used.add(str(value))
    return used


def _find_source_name_row(
    session: RpfmPackSession,
    source_dbs: dict[str, dict[str, Any]],
    name_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if not name_id:
        return None, None
    for table_path in _name_table_paths(session):
        try:
            rows = _read_rows(session, table_path, source_dbs)
        except Exception:
            continue
        source_name = _find_row(rows, "id", name_id)
        if source_name:
            return source_name, str(source_name.get("_sourceTablePath") or table_path)
    try:
        rows = _read_rows(session, "names", source_dbs)
    except Exception:
        return None, None
    return (rows[0], _source_table_path_for_rows(rows, "names")) if rows else (None, None)


_TEMPLATE_NAME_COLUMNS = ("forename", "family_name", "other_name", "clan_name")


def _active_template_name_column(template: dict[str, Any]) -> tuple[str, str]:
    for column in _TEMPLATE_NAME_COLUMNS:
        value = template.get(column)
        if value not in (None, "", 0, "0"):
            return column, str(value)
    return "forename", ""


def _set_template_single_name(template: dict[str, Any], name_column: str, name_id: int | str) -> None:
    target_column = name_column if name_column in _TEMPLATE_NAME_COLUMNS else "forename"
    for column in _TEMPLATE_NAME_COLUMNS:
        if column in template:
            template[column] = 0
    template[target_column] = name_id


def _name_table_paths(session: RpfmPackSession) -> list[str]:
    try:
        table_paths = session.list_tables()
    except Exception:
        return []
    return sorted(path for path in table_paths if "/names_tables/" in path or path.startswith("db/names_tables/"))


def _patch_art_rows(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_set_id: str,
    overrides: dict[str, Any],
) -> None:
    clean_overrides = {key: value for key, value in overrides.items() if value not in (None, "")}
    if not clean_overrides:
        return
    art_rows = [
        row for row in tables.get("campaign_character_arts", [])
        if row.get("art_set_id") == art_set_id
    ]
    apply_all = not any(_is_adult_art_row(row) for row in art_rows)
    for row in art_rows:
        if not apply_all and not _is_adult_art_row(row):
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("campaign_character_arts")
        if not table_path:
            continue
        _upsert_delta_row(
            rows_by_table,
            table_path,
            _art_key,
            _clean_source_row({**row, **clean_overrides}),
        )


def _patch_child_art_rows_for_gender(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_set_id: str,
    is_male: bool,
) -> None:
    child_overrides = _child_art_overrides_for_gender(is_male)
    for row in tables.get("campaign_character_arts", []):
        if row.get("art_set_id") != art_set_id or _is_adult_art_row(row):
            continue
        portrait = str(row.get("portrait") or "")
        card = str(row.get("card") or "")
        if "child" not in portrait and "child" not in card:
            continue
        table_path = row.get("_sourceTablePath") or table_names.get("campaign_character_arts")
        if not table_path:
            continue
        _upsert_delta_row(
            rows_by_table,
            table_path,
            _art_key,
            _clean_source_row({**row, **child_overrides}),
        )


def _output_art_rows_for_art_set(
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_set_id: str,
) -> list[dict[str, Any]]:
    return [
        row
        for table_path, rows in rows_by_table.items()
        if "/campaign_character_arts_tables/" in _normalize_pack_path(table_path)
        for row in rows
        if str(row.get("art_set_id") or "") == str(art_set_id or "")
    ]


def _copy_agent_uniform_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_rows: list[dict[str, Any]],
) -> None:
    uniform_names = _unique_strings([row.get("uniform") for row in art_rows])
    if not uniform_names or "agent_uniforms" not in tables:
        return
    for uniform_name in uniform_names:
        source = _find_row(tables.get("agent_uniforms", []), "uniform_name", uniform_name)
        if not source:
            continue
        source_table = str(
            source.get("_sourceTablePath")
            or table_names.get("agent_uniforms")
            or MTU_AGENT_UNIFORMS_TABLE
        )
        if not source_table:
            continue
        if source_table not in source_dbs and "agent_uniforms" in table_names:
            _ensure_output_source_db(source_dbs, source_table, table_names["agent_uniforms"])
        if source_table not in source_dbs:
            continue
        _upsert_delta_row(
            rows_by_table,
            source_table,
            "uniform_name",
            _clean_source_row(source),
        )


def _child_art_overrides_for_gender(is_male: bool) -> dict[str, str]:
    if is_male:
        return {
            "portrait": "child_03_male/",
            "card": "child_03_male",
            "uniform": "3k_main_child_male",
        }
    return {
        "portrait": "child_01_female/",
        "card": "child_01_female",
        "uniform": "3k_main_child_female",
    }


def _patch_art_set_row(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    art_set_id: str,
    overrides: dict[str, Any],
) -> None:
    clean_overrides = {key: value for key, value in overrides.items() if value not in (None, "")}
    if not clean_overrides:
        return
    row = _find_row(tables.get("campaign_character_art_sets", []), "art_set_id", art_set_id)
    if not row:
        return
    table_path = row.get("_sourceTablePath") or table_names.get("campaign_character_art_sets")
    if not table_path:
        return
    _upsert_delta_row(
        rows_by_table,
        table_path,
        "art_set_id",
        _clean_source_row({**row, **clean_overrides}),
    )


def _collect_age_range_clone_rows(
    session: RpfmPackSession,
    clones: list[AgeRangeClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0
    table_name = resolve_character_table_name(session, "character_generation_spawn_age_ranges")
    rows = _read_rows(session, table_name, source_dbs)
    aliases = {
        "character_generation_spawn_age_ranges": CHARACTER_TABLE_ALIASES["character_generation_spawn_age_ranges"],
    }
    tables = {"character_generation_spawn_age_ranges": rows}
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, {"character_generation_spawn_age_ranges": table_name}, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        aliases,
        reference_paths or [],
        {"character_generation_spawn_age_ranges": table_name},
        tables,
        source_dbs,
        opened_pack_keys,
    )
    rows = tables["character_generation_spawn_age_ranges"]
    created = 0
    for clone in clones:
        if clone.new_key == clone.source_key:
            if clone.overrides:
                raise ValueError(f"Unsafe age range clone would overwrite source row: {clone.source_key}")
            continue
        source = _find_required(rows, "key", clone.source_key)
        overrides = _fixed_age_range_overrides(clone.overrides)
        new_row = {
            **source,
            "key": clone.new_key,
            **overrides,
        }
        table_path = source.get("_sourceTablePath") or table_name
        _upsert_delta_row(rows_by_table, table_path, "key", _clean_source_row(new_row))
        rows.append({**new_row, "_sourceTablePath": table_path})
        created += 1
    return created


def _collect_character_clone_rows(
    session: RpfmPackSession,
    clones: list[CharacterClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
    reference_paths: list[Path] | None = None,
    opened_pack_keys: dict[str, str] | None = None,
) -> int:
    if not clones:
        return 0

    table_names = {}
    for alias in CHARACTER_TABLE_ALIASES:
        try:
            table_names[alias] = resolve_character_table_name(session, alias)
        except ValueError:
            if alias != "ceo_initial_datas":
                raise
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    opened_pack_keys = opened_pack_keys or {str(session.pack_path.resolve()): session.pack_key}
    dependency_aliases = _character_dependency_aliases()
    dependency_aliases.update({
        alias: CHARACTER_TABLE_ALIASES[alias]
        for alias in CHARACTER_TABLE_ALIASES
    })
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), dependency_aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, dependency_aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(
        session,
        dependency_aliases,
        reference_paths or [],
        table_names,
        tables,
        source_dbs,
        opened_pack_keys,
    )
    names = _read_rows(session, "names", source_dbs)
    names_table = _source_table_path_for_rows(names, "names")

    for index, clone in enumerate(clones):
        source_template = dict(_find_required(
            tables["character_generation_templates"],
            "key",
            clone.source_template_key,
        ))
        preview_template = {
            **source_template,
            **clone.template_overrides,
        }
        compatible_clone = _with_equipment_independent_unique_model_compatibility(
            clone,
            preview_template,
        )
        clones[index] = _with_generic_female_art_compatibility(
            compatible_clone,
            preview_template,
        )

    _register_equipment_independent_unique_model_rows(
        tables,
        source_dbs,
        rows_by_table,
        clones,
    )
    _preserve_unique_armour_equipment(tables, clones)

    created = 0
    for clone in clones:
        source_template = dict(_find_required(
            tables["character_generation_templates"],
            "key",
            clone.source_template_key,
        ))
        new_template = {
            **source_template,
            "key": clone.new_template_key,
            **clone.template_overrides,
        }
        if clone.spawn_event in {"campaign_start", "delayed_join"}:
            # Lua creates these templates explicitly. Keep them out of the
            # natural-birth pool; otherwise the game replaces the fixed DB
            # birth year with a randomly generated adult age.
            new_template["weight"] = SPAWN_EVENT_TEMPLATE_WEIGHT
            new_template["can_be_born"] = False
        if clone.display_name:
            name_id = _name_id_for_clone(clone, names)
            name_column, source_name_id = _active_template_name_column(source_template)
            source_name = _find_row(names, "id", source_name_id) if source_name_id else None
            if not source_name and source_name_id:
                source_name, source_name_table = _find_source_name_row(session, source_dbs, source_name_id)
            else:
                source_name_table = None
            source_name = source_name or (names[0] if names else {})
            target_names_table = (
                str(source_name.get("_sourceTablePath") or source_name_table or names_table)
            )
            name_row = {
                **source_name,
                "id": str(name_id),
                "frequency": 1,
            }
            _bind_private_name_group(session, source_dbs, rows_by_table, name_row, name_column)
            _upsert_delta_row(rows_by_table, target_names_table, "id", _clean_source_row(name_row))
            names.append(name_row)
            _set_template_single_name(new_template, name_column, name_id)
            loc_rows[f"names_name_{name_id}"] = clone.display_name
            loc_rows[f"names_alt_name_{name_id}"] = clone.display_name

        if clone.new_art_set_id:
            source_art_set = clone.art_set_source_id or source_template["art_set_override"]
            source_art_set_row = _find_row(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
            if not source_art_set_row and source_art_set != source_template.get("art_set_override"):
                source_art_set = source_template.get("art_set_override")
                source_art_set_row = _find_row(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
            if source_art_set_row:
                new_template["art_set_override"] = clone.new_art_set_id
                is_male = _clone_template_gender(new_template, source_art_set_row, clone)
                if is_male is not None:
                    new_template["is_male"] = is_male
                art_set_overrides = dict(clone.art_set_overrides or {})
                if is_male is not None:
                    art_set_overrides["is_male"] = is_male
                _bind_generated_art_set_to_template_subtype(
                    art_set_overrides,
                    new_template,
                    source_art_set_row,
                )
                _clone_art_set_delta(
                    tables,
                    table_names,
                    source_dbs,
                    rows_by_table,
                    source_art_set,
                    clone,
                    art_set_overrides,
                    is_male,
                )
            else:
                raise ValueError(
                    f"Source art set row not found for character clone: "
                    f"template={clone.source_template_key}, art_set={source_art_set}"
                )

        if not clone.new_art_set_id:
            is_male = _clone_template_gender(new_template, {}, clone)
            if is_male is not None:
                new_template["is_male"] = is_male

        # Campaign-only templates are not frontend_characters. Copying their
        # source's frontend CEO rows creates dangling menu-character references.
        # Campaign traits/equipment continue to come from initial_ceos and Lua.

        if clone.new_age_range_key:
            new_template["spawn_age_range"] = clone.new_age_range_key
            source_age = clone.age_range_source_key or source_template["spawn_age_range"]
            age_range_overrides = _fixed_age_range_overrides(clone.age_range_overrides)
            _clone_keyed_delta(
                tables["character_generation_spawn_age_ranges"],
                rows_by_table,
                table_names["character_generation_spawn_age_ranges"],
                "key",
                source_age,
                clone.new_age_range_key,
                age_range_overrides,
            )
        elif clone.spawn_event in {"campaign_start", "delayed_join"} and clone.age_range_overrides:
            source_age = str(
                clone.age_range_source_key
                or new_template.get("spawn_age_range")
                or source_template.get("spawn_age_range")
                or ""
            )
            source_age_row = _find_row(tables["character_generation_spawn_age_ranges"], "key", source_age) if source_age else None
            if source_age_row:
                new_age_key = _event_spawn_age_range_key(clone)
                new_template["spawn_age_range"] = new_age_key
                _clone_keyed_delta(
                    tables["character_generation_spawn_age_ranges"],
                    rows_by_table,
                    table_names["character_generation_spawn_age_ranges"],
                    "key",
                    source_age,
                    new_age_key,
                    _event_spawn_age_range_overrides(source_age_row, clone),
                )

        _upsert_delta_row(
            rows_by_table,
            table_names["character_generation_templates"],
            "key",
            new_template,
        )
        created += 1

        source_details = _required_game_mode_details([
            row for row in tables["character_generation_template_game_mode_details"]
            if row.get("character_generation_template") == clone.detail_source_template_key
        ])
        if not source_details:
            raise ValueError(f"Row not found: character_generation_template={clone.detail_source_template_key}")
        for source_detail in source_details:
            game_mode = source_detail.get("game_mode", "")
            overrides = clone.detail_overrides.get(game_mode, {})
            new_detail = {
                **source_detail,
                "character_generation_template": clone.new_template_key,
                **overrides,
            }
            new_detail["min_rank"] = GENERATED_CHARACTER_START_RANK
            new_detail["max_rank"] = GENERATED_CHARACTER_START_RANK
            title_initial_override = _title_initial_override_to_ignore(
                clone.title_ceo_key,
                overrides.get("initial_ceos"),
            )
            if title_initial_override:
                new_detail["initial_ceos"] = source_detail.get("initial_ceos")
            raw_initial_ceo = (
                (None if title_initial_override else overrides.get("initial_ceos"))
                or
                clone.initial_ceo_source_key
                or source_detail.get("initial_ceos")
            )
            raw_initial_ceo = _resolve_non_generic_initial_ceo(
                tables,
                table_names,
                source_dbs,
                raw_initial_ceo,
                clone.source_template_key,
                preserve_generic=_clone_preserves_generic_initial_ceo(clone),
            )
            if raw_initial_ceo:
                requested_initial_ceo = str(clone.new_initial_ceo_key or "")
                if requested_initial_ceo and requested_initial_ceo != raw_initial_ceo:
                    raise ValueError(
                        "Creating new initial CEO keys is not supported because "
                        "`ceo_initial_datas` is a key-only table. "
                        f"template={clone.new_template_key}, requested={requested_initial_ceo}, "
                        f"source={raw_initial_ceo}"
                    )
                else:
                    new_detail["initial_ceos"] = raw_initial_ceo
            compatible_initial_ceo = _clone_initial_ceo_key(
                clone,
                new_detail.get("initial_ceos"),
                new_template.get("is_male"),
                new_template.get("subtype"),
            )
            if compatible_initial_ceo:
                new_detail["initial_ceos"] = compatible_initial_ceo
            _upsert_delta_row(
                rows_by_table,
                table_names["character_generation_template_game_mode_details"],
                _detail_key,
                new_detail,
            )
            _copy_initial_ceo_dependency_if_available(
                tables,
                table_names,
                source_dbs,
                rows_by_table,
                new_detail.get("initial_ceos"),
            )
    return created


def _preserve_unique_armour_equipment(
    tables: dict[str, list[dict[str, Any]]],
    clones: list[CharacterClone],
) -> None:
    # Keep the source hero's unique armour as an additional inventory fallback,
    # but never discard a user-selected generic armour. Lua grants both items
    # to faction inventory and does not equip either one, so there is no slot
    # conflict to resolve here.
    variants = tables.get("equipment_variants_armours", [])
    if not variants:
        return
    for index, clone in enumerate(clones):
        if _clone_uses_generic_initial_ceo(clone):
            # Generic characters already receive safe vanilla equipment from
            # their initial CEO chain. Do not re-introduce the source hero's
            # character-bound armour as a Lua inventory grant.
            continue
        unique_armour = _unique_armour_ceo_for_template_key(variants, clone.source_template_key)
        if not unique_armour:
            continue
        defaults = list(clone.default_equipment_ceo_keys or ())
        defaults.append(unique_armour)
        clones[index] = _dataclass_replace(
            clone,
            default_equipment_ceo_keys=tuple(_unique_strings(defaults)),
        )


def _materialize_dedicated_armour_db_rows(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
    clone: CharacterClone,
) -> None:
    assignment = clone.dedicated_armour
    if assignment is None:
        return

    initial_rows = tables.setdefault("ceo_initial_datas", [])
    source_initial = _find_row(
        initial_rows,
        "key",
        assignment.source_initial_ceo_key,
    )
    if not source_initial:
        raise ValueError(
            "전용 갑옷 기준 초기 CEO DB row를 찾지 못했습니다: "
            f"{assignment.source_initial_ceo_key}"
        )
    initial_table = str(
        source_initial.get("_sourceTablePath")
        or table_names.get("ceo_initial_datas")
        or ""
    )
    if not initial_table:
        raise ValueError("전용 갑옷 ceo_initial_datas 출력 테이블을 찾지 못했습니다.")
    new_initial = {
        **source_initial,
        "key": assignment.initial_ceo_key,
    }
    _upsert_delta_row(
        rows_by_table,
        initial_table,
        "key",
        _clean_source_row(new_initial),
    )
    if not _find_row(initial_rows, "key", assignment.initial_ceo_key):
        initial_rows.append({**new_initial, "_sourceTablePath": initial_table})

    variant_rows = tables.setdefault("equipment_variants_armours", [])
    source_variants = [
        row
        for row in variant_rows
        if str(row.get("ceos_key") or "") == assignment.source_ceo_key
        and str(row.get("armour") or "") == assignment.source_armour_type_key
    ]
    if not source_variants:
        raise ValueError(
            "전용 갑옷 기준 CEO의 장비 variant를 찾지 못했습니다: "
            f"ceo={assignment.source_ceo_key}, armour={assignment.source_armour_type_key}"
        )
    for source_variant in source_variants:
        variant_table = str(
            source_variant.get("_sourceTablePath")
            or table_names.get("equipment_variants_armours")
            or ""
        )
        if not variant_table:
            raise ValueError("전용 갑옷 equipment variant 출력 테이블을 찾지 못했습니다.")
        new_variant = {
            **source_variant,
            "ceos_key": assignment.armour_ceo_key,
            "armour": assignment.armour_type_key,
        }
        _upsert_delta_row(
            rows_by_table,
            variant_table,
            _equipment_variant_key,
            _clean_source_row(new_variant),
        )
        if not any(
            _equipment_variant_key(row) == _equipment_variant_key(new_variant)
            for row in variant_rows
        ):
            variant_rows.append({**new_variant, "_sourceTablePath": variant_table})

    armour_rows = tables.setdefault("unit_armour_types", [])
    source_armour = _find_row(
        armour_rows,
        "key",
        assignment.source_armour_type_key,
    )
    if not source_armour:
        raise ValueError(
            "전용 갑옷 기준 방어구 stat row를 찾지 못했습니다: "
            f"{assignment.source_armour_type_key}"
        )
    armour_table = str(
        source_armour.get("_sourceTablePath")
        or table_names.get("unit_armour_types")
        or ""
    )
    if not armour_table:
        raise ValueError("전용 갑옷 unit_armour_types 출력 테이블을 찾지 못했습니다.")
    new_armour = {
        **source_armour,
        "key": assignment.armour_type_key,
        "armour_value": assignment.armour_value,
    }
    _upsert_delta_row(
        rows_by_table,
        armour_table,
        "key",
        _clean_source_row(new_armour),
    )
    if not _find_row(armour_rows, "key", assignment.armour_type_key):
        armour_rows.append({**new_armour, "_sourceTablePath": armour_table})

    owner_name = str(clone.display_name or "").strip()
    armour_name = f"{owner_name}의 전용 갑옷" if owner_name else "전용 갑옷"
    loc_rows[f"ceo_nodes_title_{assignment.armour_ceo_key}"] = armour_name
    loc_rows[f"ceo_nodes_description_{assignment.armour_ceo_key}"] = (
        "신규 장수를 위해 제작된 전용 갑옷입니다."
    )


def _register_equipment_independent_unique_model_rows(
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    clones: list[CharacterClone],
) -> None:
    requested_models = {
        str(clone.art_overrides.get("uniform") or ""): model
        for clone in clones
        for model in [_equipment_independent_model_for_clone(clone)]
        if model and clone.art_overrides.get("uniform") == model["fixed_uniform"]
    }
    if not requested_models:
        return

    agent_uniforms = tables.get("agent_uniforms", [])
    variants = tables.get("variants", [])
    if not variants:
        raise ValueError(
            "MTU variants table is required for equipment-independent unique models. "
            "Refresh the bundled internal materials."
        )

    for model in requested_models.values():
        source_uniform = _find_required(
            agent_uniforms,
            "uniform_name",
            model["source_uniform"],
        )
        source_variant = _find_required(
            variants,
            "variant_name",
            model["source_variant"],
        )

        source_uniform_path = str(
            source_uniform.get("_sourceTablePath") or MTU_AGENT_UNIFORMS_TABLE
        )
        _ensure_output_source_db(
            source_dbs,
            FIXED_MODEL_AGENT_UNIFORMS_TABLE,
            source_uniform_path,
        )
        fixed_uniform = {
            **source_uniform,
            "uniform_name": model["fixed_uniform"],
            "filename": model["fixed_variant"],
            "battle_filename": model["fixed_variant"],
            "campaign_porthole_filename": model["fixed_variant"],
            "campaign_politician_filename": "",
            "_sourceTablePath": FIXED_MODEL_AGENT_UNIFORMS_TABLE,
        }
        _upsert_plain_row(agent_uniforms, "uniform_name", fixed_uniform)
        _upsert_delta_row(
            rows_by_table,
            FIXED_MODEL_AGENT_UNIFORMS_TABLE,
            "uniform_name",
            _clean_source_row(fixed_uniform),
        )

        source_variant_path = str(
            source_variant.get("_sourceTablePath") or MTU_VARIANTS_TABLE
        )
        _ensure_output_source_db(
            source_dbs,
            FIXED_MODEL_VARIANTS_TABLE,
            source_variant_path,
        )
        fixed_variant = {
            **source_variant,
            "variant_name": model["fixed_variant"],
            "variant_filename": model["fixed_definition"],
            "_sourceTablePath": FIXED_MODEL_VARIANTS_TABLE,
        }
        _upsert_delta_row(
            rows_by_table,
            FIXED_MODEL_VARIANTS_TABLE,
            "variant_name",
            _clean_source_row(fixed_variant),
        )


def _equipment_independent_model_for_clone(
    clone: CharacterClone,
) -> dict[str, str] | None:
    model = EQUIPMENT_INDEPENDENT_UNIQUE_MODELS.get(clone.source_template_key)
    return dict(model) if model else None


def _is_armour_ceo_key(value: Any) -> bool:
    key = str(value or "").lower()
    if "_ancillary_armour_" in key or "_ancilliary_armour_" in key:
        return True
    return "_ancillary_" in key and ("_armour_" in key or "_armor_" in key)


def _clone_uses_generic_initial_ceo(clone: CharacterClone) -> bool:
    initial_ceos = [
        str(overrides.get("initial_ceos") or "").lower()
        for overrides in (clone.detail_overrides or {}).values()
    ]
    initial_ceos.append(str(clone.initial_ceo_source_key or "").lower())
    return any("_ceo_initial_data_character_generic_" in key for key in initial_ceos if key)


def _clone_preserves_generic_initial_ceo(clone: CharacterClone) -> bool:
    model = _equipment_independent_model_for_clone(clone)
    return bool(
        model
        and clone.art_overrides.get("uniform") == model["fixed_uniform"]
        and _clone_uses_generic_initial_ceo(clone)
    )


def _with_equipment_independent_unique_model_compatibility(
    clone: CharacterClone,
    template: dict[str, Any],
) -> CharacterClone:
    """Keep an audited unique body while switching its equipment chain to generic.

    The fixed uniform works for both genders.  Custom portraits also receive
    the generic armour-display aliases for their gender and element so a later
    equipment change cannot make the campaign panel image disappear.
    """
    model = _equipment_independent_model_for_clone(clone)
    if not model:
        return clone

    art_overrides = dict(clone.art_overrides or {})
    if not (art_overrides.get("portrait") or art_overrides.get("card")):
        return clone
    if art_overrides.get("uniform") or not (clone.image_assets or []):
        return clone

    is_male = _coerce_bool(template.get("is_male"))
    subtype = str(template.get("subtype") or "")
    initial_ceo = _generic_initial_ceo_key_for_template_gender(is_male, subtype)
    if not initial_ceo:
        return clone

    art_overrides["uniform"] = model["fixed_uniform"]
    image_assets = list(clone.image_assets or [])
    compatibility = (
        GENERIC_MALE_COMPATIBILITY if is_male else GENERIC_FEMALE_COMPATIBILITY
    ).get(_element_from_subtype(subtype))
    if compatibility:
        art_overrides["fallback_composite_display"] = str(compatibility["fallback"])
        image_assets = _generic_image_alias_assets(
            image_assets,
            tuple(compatibility["armour_displays"]),
        )

    detail_overrides = {
        mode: dict(overrides)
        for mode, overrides in (clone.detail_overrides or {}).items()
    }
    for mode in CHARACTER_GAME_MODES:
        detail_overrides.setdefault(mode, {})["initial_ceos"] = initial_ceo
    return _dataclass_replace(
        clone,
        initial_ceo_source_key=None,
        detail_overrides=detail_overrides,
        art_overrides=art_overrides,
        image_assets=image_assets,
        # The fixed full-body model uses a safe generic initial CEO.  Do not
        # grant the source hero's character-bound armour as a separate item;
        # explicitly selected equipment-set items remain untouched.
        default_equipment_ceo_keys=tuple(
            key for key in (clone.default_equipment_ceo_keys or ())
            if not _is_armour_ceo_key(key)
        ),
    )


def _with_generic_female_art_compatibility(
    clone: CharacterClone,
    template: dict[str, Any],
) -> CharacterClone:
    """Detach custom female art from source-hero equipment dependencies.

    Vanilla supplies complete generic female campaign art families for earth,
    metal, and water.  Use the matching initial CEO, fallback display, and
    armour aliases for every custom-image female clone in those classes.
    Audited equipment-independent unique models are handled before this path;
    other clones use the matching vanilla generic female uniform.
    Fire and wood have no vanilla generic female art family and are deliberately
    left unchanged so we do not claim a compatibility path that does not exist.
    """
    if _coerce_bool(template.get("is_male")):
        return clone

    art_overrides = dict(clone.art_overrides or {})
    if not (art_overrides.get("portrait") or art_overrides.get("card")):
        return clone
    if art_overrides.get("uniform") or not (clone.image_assets or []):
        # An explicitly selected model/uniform remains authoritative.  The
        # compatibility path is only for imported custom image sets whose body
        # would otherwise inherit the source hero's equipment-bound model.
        return clone
    element = _element_from_subtype(str(template.get("subtype") or ""))
    compatibility = GENERIC_FEMALE_COMPATIBILITY.get(element)
    if not compatibility:
        return clone
    art_overrides.update({
        "uniform": GENERIC_FEMALE_UNIFORM,
        "fallback_composite_display": str(compatibility["fallback"]),
    })
    detail_overrides = {
        mode: dict(overrides)
        for mode, overrides in (clone.detail_overrides or {}).items()
    }
    for mode in CHARACTER_GAME_MODES:
        detail_overrides.setdefault(mode, {})["initial_ceos"] = str(compatibility["initial_ceo"])
    image_assets = _generic_female_image_alias_assets(
        clone.image_assets or [],
        tuple(compatibility["armour_displays"]),
    )
    return _dataclass_replace(
        clone,
        initial_ceo_source_key=None,
        detail_overrides=detail_overrides,
        art_overrides=art_overrides,
        image_assets=image_assets,
        # The generic initial CEO supplies its own safe armour.  Do not grant
        # the source hero's character-bound armour as a second inventory item.
        default_equipment_ceo_keys=tuple(
            key for key in (clone.default_equipment_ceo_keys or ())
            if not _is_armour_ceo_key(key)
        ),
    )


def _generic_female_image_alias_assets(
    image_assets: list[dict[str, str]],
    armour_displays: tuple[str, ...],
) -> list[dict[str, str]]:
    return _generic_image_alias_assets(image_assets, armour_displays)


def _generic_image_alias_assets(
    image_assets: list[dict[str, str]],
    armour_displays: tuple[str, ...],
) -> list[dict[str, str]]:
    result = [dict(asset) for asset in image_assets]
    existing_targets = {
        _normalize_pack_path(asset.get("targetPath") or asset.get("path") or "")
        for asset in result
    }
    by_suffix: dict[str, dict[str, str]] = {}
    for asset in result:
        target = _normalize_pack_path(asset.get("targetPath") or asset.get("path") or "")
        marker = "/composites/"
        if marker in target:
            suffix = target.split(marker, 1)[1]
            if suffix in {
                "large_panel/angry/angry.png",
                "large_panel/happy/happy.png",
                "large_panel/norm/norm.png",
                "small_panel/angry/angry.png",
                "small_panel/happy/happy.png",
                "small_panel/norm/norm.png",
            }:
                by_suffix[f"composites/{suffix}"] = asset
        marker = "/stills/"
        if marker in target:
            suffix = target.split(marker, 1)[1]
            parts = suffix.split("/")
            if len(parts) == 2 and parts[0] in {
                "bobbleheads", "halfbody_large", "halfbody_small", "mini", "unitcards",
            }:
                by_suffix[f"stills/{parts[0]}"] = asset
            elif len(parts) == 3 and parts[1] == "large" and parts[0] in {
                "bobbleheads", "halfbody_large", "halfbody_small", "mini", "unitcards",
            }:
                by_suffix[f"stills/{parts[0]}/large"] = asset

    portrait_root = ""
    for target in existing_targets:
        if "/composites/" in target:
            portrait_root = target.split("/composites/", 1)[0]
            break
    if not portrait_root:
        return result

    for display in armour_displays:
        for key, source in by_suffix.items():
            if key.startswith("composites/"):
                target = f"{portrait_root}/composites/{display}/{key.removeprefix('composites/')}"
            else:
                still_path = key.removeprefix("stills/")
                if still_path.endswith("/large"):
                    still_type = still_path.removesuffix("/large")
                    target = f"{portrait_root}/stills/{still_type}/large/{display}.png"
                else:
                    target = f"{portrait_root}/stills/{still_path}/{display}.png"
            if target in existing_targets:
                continue
            result.append({**source, "targetPath": target})
            existing_targets.add(target)
    return result


def _unique_armour_ceo_for_template_key(
    armour_variants: list[dict[str, Any]],
    template_key: Any,
) -> str:
    tokens = _template_slug_tokens(template_key)
    if not tokens:
        return ""
    unique_rows = [
        row for row in armour_variants
        if "unique" in str(row.get("ceos_key") or "").lower()
        and str(row.get("armour") or "")
    ]
    variant = _best_equipment_variant_for_tokens(tokens, unique_rows, "armour")
    if not variant:
        return ""
    return _runtime_armour_ceo_key(str(variant.get("ceos_key") or ""))


def _runtime_armour_ceo_key(value: Any) -> str:
    return str(value or "").strip()


def _template_slug_tokens(template_key: Any) -> list[str]:
    token = str(template_key or "").lower()
    for marker in ("_historical_", "_generated_", "_ancestral_"):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    token = re.sub(r"(?:_\d+)+$", "", token)
    for suffix in (
        "_hero_earth", "_hero_fire", "_hero_metal", "_hero_water", "_hero_wood",
        "_earth", "_fire", "_metal", "_water", "_wood",
    ):
        if token.endswith(suffix):
            token = token.removesuffix(suffix)
            break
    tokens = [token]
    if token.startswith("lady_"):
        tokens.append(token.removeprefix("lady_"))
    return _unique_strings([value for value in tokens if len(value) >= 4])


def _clone_art_set_delta(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    source_art_set: str,
    clone: CharacterClone,
    art_set_overrides: dict[str, Any] | None = None,
    final_is_male: bool | None = None,
) -> None:
    source_set = _find_required(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
    source_set_table = str(source_set.get("_sourceTablePath") or table_names["campaign_character_art_sets"])
    set_table = MTU_CHARACTER_ART_SETS_TABLE if clone.new_art_set_id else source_set_table
    _ensure_output_source_db(source_dbs, set_table, source_set_table)
    _clone_keyed_delta(
        tables["campaign_character_art_sets"],
        rows_by_table,
        set_table,
        "art_set_id",
        source_art_set,
        clone.new_art_set_id or source_art_set,
        art_set_overrides if art_set_overrides is not None else clone.art_set_overrides,
    )
    art_rows = [
        row for row in tables["campaign_character_arts"]
        if row.get("art_set_id") == source_art_set
    ]
    output_art_rows = _clone_output_art_rows(art_rows)
    apply_all = not any(_is_adult_art_row(row) for row in output_art_rows)
    new_art_rows: list[dict[str, Any]] = []
    for art_row in output_art_rows:
        overrides = clone.art_overrides if apply_all or _is_adult_art_row(art_row) else {}
        if final_is_male is not None and not _is_adult_art_row(art_row):
            portrait = str(art_row.get("portrait") or "")
            card = str(art_row.get("card") or "")
            if "child" in portrait or "child" in card:
                overrides = {**overrides, **_child_art_overrides_for_gender(final_is_male)}
        source_art_table = str(art_row.get("_sourceTablePath") or table_names["campaign_character_arts"])
        art_table = MTU_CHARACTER_ARTS_TABLE if clone.new_art_set_id else source_art_table
        _ensure_output_source_db(source_dbs, art_table, source_art_table)
        new_row = {
            **art_row,
            "art_set_id": clone.new_art_set_id,
            **overrides,
        }
        if "id" in new_row:
            new_row["id"] = _art_id_for_clone(clone.new_art_set_id or source_art_set, art_row)
        _upsert_delta_row(
            rows_by_table,
            art_table,
            _art_key,
            _clean_source_row(new_row),
        )
        new_art_rows.append(_clean_source_row(new_row))
    if clone.new_art_set_id:
        new_art_rows.extend(_append_age999_art_fallback_row(
            rows_by_table,
            MTU_CHARACTER_ARTS_TABLE,
            clone.new_art_set_id,
            new_art_rows,
        ))
    _copy_agent_uniform_dependencies(tables, table_names, source_dbs, rows_by_table, new_art_rows)


def _clone_template_gender(
    new_template: dict[str, Any],
    source_art_set_row: dict[str, Any],
    clone: CharacterClone,
) -> bool | None:
    for value in (
        clone.art_set_overrides.get("is_male"),
        source_art_set_row.get("is_male"),
        clone.template_overrides.get("is_male"),
        new_template.get("is_male"),
    ):
        if value not in (None, ""):
            return _coerce_bool(value)
    return None


def _clone_art_set_patch_delta(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    source_art_set: str,
    new_art_set: str,
    art_set_overrides: dict[str, Any],
    art_overrides: dict[str, Any],
) -> None:
    if _find_row(tables.get("campaign_character_art_sets", []), "art_set_id", new_art_set):
        return
    source_set = _find_required(tables["campaign_character_art_sets"], "art_set_id", source_art_set)
    source_set_table = str(source_set.get("_sourceTablePath") or table_names["campaign_character_art_sets"])
    set_table = MTU_CHARACTER_ART_SETS_TABLE
    _ensure_output_source_db(source_dbs, set_table, source_set_table)
    new_set = _clean_source_row({
        **source_set,
        "art_set_id": new_art_set,
        **{key: value for key, value in art_set_overrides.items() if value not in (None, "")},
    })
    _upsert_delta_row(rows_by_table, set_table, "art_set_id", new_set)
    tables.setdefault("campaign_character_art_sets", []).append({**new_set, "_sourceTablePath": set_table})

    source_rows = [
        row for row in tables.get("campaign_character_arts", [])
        if row.get("art_set_id") == source_art_set
    ]
    output_rows = _clone_output_art_rows(source_rows)
    apply_all = not any(_is_adult_art_row(row) for row in output_rows)
    new_art_rows: list[dict[str, Any]] = []
    for source_row in output_rows:
        overrides = art_overrides if apply_all or _is_adult_art_row(source_row) else {}
        source_art_table = str(source_row.get("_sourceTablePath") or table_names["campaign_character_arts"])
        art_table = MTU_CHARACTER_ARTS_TABLE
        _ensure_output_source_db(source_dbs, art_table, source_art_table)
        new_row = _clean_source_row({
            **source_row,
            "art_set_id": new_art_set,
            **{key: value for key, value in overrides.items() if value not in (None, "")},
        })
        if "id" in new_row:
            new_row["id"] = _art_id_for_clone(new_art_set, source_row)
        _upsert_delta_row(rows_by_table, art_table, _art_key, new_row)
        tables.setdefault("campaign_character_arts", []).append({**new_row, "_sourceTablePath": art_table})
        new_art_rows.append(new_row)
    new_art_rows.extend(_append_age999_art_fallback_row(
        rows_by_table,
        MTU_CHARACTER_ARTS_TABLE,
        new_art_set,
        new_art_rows,
    ))
    _copy_agent_uniform_dependencies(tables, table_names, source_dbs, rows_by_table, new_art_rows)


def _clone_keyed_delta(
    rows: list[dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_name: str,
    key_field: str,
    source_key: str,
    new_key: str,
    overrides: dict[str, Any],
) -> None:
    source = _find_required(rows, key_field, source_key)
    _upsert_delta_row(
        rows_by_table,
        table_name,
        key_field,
        {**source, key_field: new_key, **overrides},
    )


def _event_spawn_age_range_key(clone: CharacterClone) -> str:
    seed = f"{clone.new_template_key}:event_spawn_age:v1".encode("utf-8")
    suffix = zlib.crc32(seed) & 0xffffffff
    slug = "".join(
        char.lower() if char.isalnum() or char == "_" else "_"
        for char in clone.new_template_key
    ).strip("_")
    return f"hby_age_spawn_{slug}_{suffix:08x}"[:120]


def _explicit_birth_year(overrides: dict[str, Any] | None) -> int | None:
    value = (overrides or {}).get("birth_year")
    try:
        year = int(float(value))
    except (TypeError, ValueError):
        return None
    # 999 is the database sentinel for an open-ended year, not a real birth
    # year.  Treating it as a fixed birth year produces a random adult.
    return year if 0 < year < 999 else None


def _fixed_age_range_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    """Make an explicit birth year authoritative for DB character creation."""
    normalized = dict(overrides or {})
    birth_year = _explicit_birth_year(normalized)
    if birth_year is None:
        return normalized
    normalized["birth_year"] = birth_year
    normalized["min_spawn_year"] = birth_year
    normalized["has_valid_birth_year"] = True
    return normalized


def _event_spawn_age_range_overrides(source_age: dict[str, Any], clone: CharacterClone) -> dict[str, Any]:
    explicit = dict(clone.age_range_overrides or {})
    try:
        birth_year = int(float(explicit.get("birth_year", source_age.get("birth_year", 170))))
    except (TypeError, ValueError):
        birth_year = 170
    if birth_year <= 0:
        birth_year = 170

    overrides: dict[str, Any] = {
        "birth_year": birth_year,
        "min_spawn_year": birth_year,
        "min_spawn_year_round": 0,
        "max_spawn_year": 999,
        "max_spawn_year_round": 999,
        "min_random_age": int(source_age.get("min_random_age") or 18),
        "max_random_age": int(source_age.get("max_random_age") or 50),
        "min_age_for_birth_year": int(source_age.get("min_age_for_birth_year") or 0),
        "max_age_for_birth_year": int(source_age.get("max_age_for_birth_year") or 80),
        "has_valid_birth_year": True,
    }
    overrides.update(explicit)
    overrides = _fixed_age_range_overrides(overrides)
    try:
        if int(float(overrides.get("min_spawn_year") or 0)) > int(float(overrides.get("max_spawn_year") or 0)):
            overrides["max_spawn_year"] = 999
    except (TypeError, ValueError):
        overrides["max_spawn_year"] = 999
    return overrides


def _clone_output_art_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adult_rows = [row for row in rows if _is_adult_art_row(row)]
    return adult_rows or rows


def _append_age999_art_fallback_row(
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_name: str,
    art_set_id: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not art_set_id or not rows or any(_is_age999_art_row(row) for row in rows):
        return []
    adult_rows = [row for row in rows if _is_adult_art_row(row)]
    if not adult_rows:
        return []
    source = adult_rows[0]
    fallback = {
        **source,
        "art_set_id": art_set_id,
        "age": 999,
        "has_come_of_age": True,
    }
    if "id" in fallback:
        fallback["id"] = _art_id_for_clone(art_set_id, fallback)
    clean = _clean_source_row(fallback)
    _upsert_delta_row(rows_by_table, table_name, _art_key, clean)
    return [clean]


def _is_age999_art_row(row: dict[str, Any]) -> bool:
    try:
        return int(row.get("age") or 0) == 999
    except (TypeError, ValueError):
        return False


def _is_adult_art_row(row: dict[str, Any]) -> bool:
    if row.get("has_come_of_age") is True:
        return True
    try:
        return int(row.get("age") or 0) >= 16
    except (TypeError, ValueError):
        return False


def _art_id_for_clone(art_set_id: str, source_row: dict[str, Any]) -> int:
    seed = "|".join(
        str(value)
        for value in (
            art_set_id,
            source_row.get("age", ""),
            source_row.get("level", ""),
            source_row.get("season", ""),
            source_row.get("has_come_of_age", ""),
        )
    ).encode("utf-8")
    return 100_000_000 + (zlib.crc32(seed) % 1_900_000_000)


def _collect_character_dependency_rows(
    session: RpfmPackSession,
    clones: list[CharacterClone],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path],
    opened_pack_keys: dict[str, str],
) -> int:
    if not clones:
        return 0

    aliases = _character_dependency_aliases()
    table_names = _optional_table_names(session, aliases)
    tables = {
        alias: _read_rows(session, table_name, source_dbs)
        for alias, table_name in table_names.items()
    }
    _merge_dependency_tables_from_pack(session, session.pack_key, session.list_tables(), aliases, tables, source_dbs)
    _merge_vanilla_dependency_tables(session, aliases, table_names, tables, source_dbs)
    _merge_reference_dependency_tables(session, aliases, reference_paths, table_names, tables, source_dbs, opened_pack_keys)

    before = sum(len(rows) for rows in rows_by_table.values())
    for clone in clones:
        source_template = _find_row(
            tables.get("character_generation_templates", []),
            "key",
            clone.source_template_key,
        ) or {}
        art_set_id = str(
            clone.new_art_set_id
            or clone.template_overrides.get("art_set_override")
            or source_template.get("art_set_override")
            or ""
        )
        age_range = str(
            clone.template_overrides.get("spawn_age_range")
            or clone.new_age_range_key
            or source_template.get("spawn_age_range")
            or ""
        )
        if art_set_id:
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_art_sets",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                "art_set_id",
            )
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "campaign_character_arts",
                lambda row, key=art_set_id: row.get("art_set_id") == key,
                _art_key,
            )
            _copy_agent_uniform_dependencies(
                tables,
                table_names,
                source_dbs,
                rows_by_table,
                _output_art_rows_for_art_set(rows_by_table, art_set_id)
                or [
                    row for row in tables.get("campaign_character_arts", [])
                    if row.get("art_set_id") == art_set_id
                ],
            )
        if age_range:
            _copy_matching_rows(
                tables,
                table_names,
                rows_by_table,
                "character_generation_spawn_age_ranges",
                lambda row, key=age_range: row.get("key") == key,
                "key",
            )

        generated_details = [
            row
            for output_rows in rows_by_table.values()
            for row in output_rows
            if row.get("character_generation_template") == clone.new_template_key
        ]
        if generated_details:
            merged_details = generated_details
        else:
            source_details = _required_game_mode_details([
                row for row in tables.get("character_generation_template_game_mode_details", [])
                if row.get("character_generation_template") == clone.detail_source_template_key
            ])
            template_for_dependencies = {
                **source_template,
                **clone.template_overrides,
            }
            merged_details = []
            for source_detail in source_details:
                game_mode = str(source_detail.get("game_mode", ""))
                overrides = clone.detail_overrides.get(game_mode, {})
                merged_detail = {
                    **source_detail,
                    **overrides,
                }
                merged_detail["initial_ceos"] = _resolve_non_generic_initial_ceo(
                    tables,
                    table_names,
                    source_dbs,
                    (
                        overrides.get("initial_ceos")
                        or clone.initial_ceo_source_key
                        or source_detail.get("initial_ceos")
                    ),
                    clone.source_template_key,
                    preserve_generic=_clone_preserves_generic_initial_ceo(clone),
                )
                compatible_initial_ceo = _clone_initial_ceo_key(
                    clone,
                    merged_detail.get("initial_ceos"),
                    template_for_dependencies.get("is_male"),
                    template_for_dependencies.get("subtype"),
                )
                if compatible_initial_ceo:
                    merged_detail["initial_ceos"] = compatible_initial_ceo
                merged_details.append(merged_detail)

        for detail in merged_details:
            _copy_initial_ceo_dependency(tables, table_names, source_dbs, rows_by_table, detail.get("initial_ceos"))
            _copy_attribute_dependency(tables, table_names, source_dbs, rows_by_table, detail.get("attribute_set"))
            _copy_skill_dependency(tables, table_names, rows_by_table, detail.get("skill_set_override"))
            _copy_retinue_dependency(tables, table_names, rows_by_table, detail.get("retinue"))
            _copy_skill_source_retinue_abilities(
                tables,
                table_names,
                source_dbs,
                rows_by_table,
                detail.get("skill_set_override"),
                detail.get("retinue"),
            )
        for ceo_key in _unique_strings([
            *clone.equipment_ceo_keys,
            *clone.default_equipment_ceo_keys,
        ]):
            _copy_equipment_variant_dependency_for_ceo_key(
                tables,
                table_names,
                source_dbs,
                rows_by_table,
                ceo_key,
            )

    after = sum(len(rows) for rows in rows_by_table.values())
    return max(0, after - before)


def _clone_initial_ceo_key(clone: CharacterClone, initial_ceo: Any, is_male: Any, subtype: Any) -> str:
    return _gender_compatible_initial_ceo_key(initial_ceo, is_male, subtype)


def _bind_generated_art_set_to_template_subtype(
    art_set_overrides: dict[str, Any],
    template: dict[str, Any],
    source_art_set_row: dict[str, Any],
) -> None:
    # The generated template's art_set_override is the authoritative link for
    # custom portraits; narrowing art-set matching fields breaks metal clones.
    return


def _spawn_subtype_for_clone(clone: CharacterClone) -> str:
    return str(clone.template_overrides.get("subtype") or "")


def _required_game_mode_details(source_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not source_details:
        return []
    by_mode = {
        str(row.get("game_mode") or ""): row
        for row in source_details
        if row.get("game_mode") not in (None, "")
    }
    fallback = by_mode.get("historical") or by_mode.get("romance") or source_details[0]
    result: list[dict[str, Any]] = []
    for game_mode in CHARACTER_GAME_MODES:
        source = by_mode.get(game_mode) or fallback
        result.append({**source, "game_mode": game_mode})
    return result


def _initial_ceo_from_title_ceo_key(title_ceo_key: Any) -> str:
    key = str(title_ceo_key or "").strip()
    if "_ceo_career_historical_" not in key:
        return ""
    return key.replace("_ceo_career_historical_", "_ceo_initial_data_character_historical_")


def _title_initial_override_to_ignore(title_ceo_key: Any, initial_ceo_override: Any) -> bool:
    initial_key = str(initial_ceo_override or "").strip()
    if not initial_key:
        return False
    title_initial = _initial_ceo_from_title_ceo_key(title_ceo_key)
    return bool(title_initial and initial_key == title_initial)


def _resolve_non_generic_initial_ceo(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    initial_ceo: Any,
    source_template_key: Any,
    *,
    preserve_generic: bool = False,
) -> str:
    key = str(initial_ceo or "")
    if not key:
        return key
    if not _is_generic_initial_ceo_key(key):
        return _resolve_existing_initial_ceo_key(tables, table_names, source_dbs, key, source_template_key) or key
    if preserve_generic:
        return _resolve_existing_initial_ceo_key(
            tables,
            table_names,
            source_dbs,
            key,
            source_template_key,
        ) or key
    candidates = _named_initial_ceo_candidates(source_template_key, key)
    if not candidates:
        return key
    for candidate in candidates:
        resolved = _resolve_existing_initial_ceo_key(tables, table_names, source_dbs, candidate, source_template_key)
        if resolved:
            return resolved
    return candidates[0]


def _is_generic_initial_ceo_key(value: Any) -> bool:
    return "_ceo_initial_data_character_generic_" in str(value or "").lower()


def _named_initial_ceo_candidates(source_template_key: Any, source_initial_ceo: Any = "") -> list[str]:
    token = _character_token_from_template_key(str(source_template_key or ""))
    if not token:
        return []
    prefixes = _unique_strings([
        _initial_ceo_prefix(source_initial_ceo),
        _template_prefix(source_template_key),
        "3k_main",
        "3k_mtu",
    ])
    return [f"{prefix}_ceo_initial_data_character_historical_{token}" for prefix in prefixes if prefix]


def _resolve_existing_initial_ceo_key(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    initial_ceo: Any,
    source_template_key: Any,
) -> str:
    candidates = _initial_ceo_resolution_candidates(tables, initial_ceo, source_template_key)
    for candidate in candidates:
        if _find_row(tables.get("ceo_initial_datas", []), "key", candidate):
            return candidate
    for candidate in candidates:
        _ensure_initial_ceo_rows_available(tables, table_names, source_dbs, candidate)
        if _find_row(tables.get("ceo_initial_datas", []), "key", candidate):
            return candidate
    return ""


def _initial_ceo_resolution_candidates(
    tables: dict[str, list[dict[str, Any]]],
    initial_ceo: Any,
    source_template_key: Any,
) -> list[str]:
    key = str(initial_ceo or "").strip()
    token = _historical_initial_ceo_token(key)
    source_token = _character_token_from_template_key(str(source_template_key or ""))
    candidates: list[Any] = [key]
    prefixes = _unique_strings([
        _initial_ceo_prefix(key),
        _template_prefix(source_template_key),
        "3k_main",
        "3k_mtu",
    ])
    for alias_token in HISTORICAL_INITIAL_CEO_TOKEN_ALIASES.get(token, ()):
        if "_ceo_initial_data_character_" in alias_token:
            candidates.append(alias_token)
        else:
            candidates.extend(
                f"{prefix}_ceo_initial_data_character_historical_{alias_token}"
                for prefix in prefixes
                if prefix
            )
    if token and source_token and token == source_token:
        candidates.extend(_source_template_initial_ceo_candidates(tables, source_template_key))
    candidates.extend(_matching_existing_initial_ceo_candidates(tables, token))
    candidates.extend(_matching_internal_material_initial_ceo_candidates(token))
    return _unique_strings(candidates)


def _matching_existing_initial_ceo_candidates(
    tables: dict[str, list[dict[str, Any]]],
    token: str,
) -> list[str]:
    return _matching_initial_ceo_candidates_from_rows(tables.get("ceo_initial_datas", []), token)


def _matching_internal_material_initial_ceo_candidates(token: str) -> list[str]:
    if not INTERNAL_MATERIALS_PATH.is_file():
        return []
    try:
        with INTERNAL_MATERIALS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    material_tables = payload.get("tables", {})
    if not isinstance(material_tables, dict):
        return []
    rows: list[dict[str, Any]] = []
    for table_path, entry in material_tables.items():
        if "/ceo_initial_datas_tables/" not in str(table_path).replace("\\", "/"):
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("rows"), list):
            continue
        rows.extend(row for row in entry["rows"] if isinstance(row, dict))
    return _matching_initial_ceo_candidates_from_rows(rows, token)


def _matching_initial_ceo_candidates_from_rows(
    rows: list[dict[str, Any]],
    token: str,
) -> list[str]:
    requested = str(token or "").strip("_").lower()
    if not requested:
        return []
    scored: list[tuple[int, str]] = []
    for row in rows:
        key = str(row.get("key") or "").strip()
        candidate = _historical_initial_ceo_token(key).lower()
        score = _historical_initial_ceo_token_match_score(requested, candidate)
        if score > 0:
            scored.append((score, key))
    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score = scored[0][0]
    return [key for score, key in scored if score == best_score]


def _historical_initial_ceo_token_match_score(requested: str, candidate: str) -> int:
    if not requested or not candidate:
        return 0
    if requested == candidate:
        return 100
    requested_core = _strip_initial_ceo_token_noise(requested)
    candidate_core = _strip_initial_ceo_token_noise(candidate)
    if requested_core and requested_core == candidate_core:
        return 96
    if candidate_core.endswith(f"_{requested_core}") or candidate_core == requested_core:
        return 92
    if requested_core.endswith(f"_{candidate_core}") and len(candidate_core.split("_")) >= 2:
        return 82
    requested_without_element = _strip_initial_ceo_element_suffix(requested_core)
    candidate_without_element = _strip_initial_ceo_element_suffix(candidate_core)
    if requested_without_element and requested_without_element == candidate_without_element:
        return 78
    if requested_without_element and candidate_without_element.endswith(f"_{requested_without_element}"):
        return 74
    if candidate_without_element and requested_without_element.endswith(f"_{candidate_without_element}") and len(candidate_without_element.split("_")) >= 2:
        return 68
    return 0


def _strip_initial_ceo_token_noise(token: str) -> str:
    text = str(token or "").strip("_").lower()
    for prefix in ("non_deployable_", "deployable_"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _strip_initial_ceo_element_suffix(token: str) -> str:
    text = str(token or "").strip("_").lower()
    for suffix in ("_earth", "_fire", "_metal", "_water", "_wood"):
        if text.endswith(suffix):
            return text[:-len(suffix)]
    return text


def _source_template_initial_ceo_candidates(
    tables: dict[str, list[dict[str, Any]]],
    source_template_key: Any,
) -> list[str]:
    template_key = str(source_template_key or "")
    if not template_key:
        return []
    details = [
        row for row in tables.get("character_generation_template_game_mode_details", [])
        if str(row.get("character_generation_template") or "") == template_key
    ]
    details.sort(key=lambda row: 0 if str(row.get("game_mode") or "") == "historical" else 1)
    return _unique_strings([row.get("initial_ceos") for row in details])


def _historical_initial_ceo_token(initial_ceo: Any) -> str:
    key = str(initial_ceo or "")
    marker = "_ceo_initial_data_character_historical_"
    return key.split(marker, 1)[1].strip("_") if marker in key else ""


def _character_token_from_template_key(template_key: str) -> str:
    token = str(template_key or "")
    for marker in ("_template_historical_", "_template_"):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    for marker in ("_hero_", "_general_"):
        if marker in token:
            token = token.split(marker, 1)[0]
            break
    return token.strip("_")


def _initial_ceo_prefix(initial_ceo: Any) -> str:
    key = str(initial_ceo or "")
    marker = "_ceo_initial_data_character_"
    return key.split(marker, 1)[0] if marker in key else ""


def _template_prefix(template_key: Any) -> str:
    key = str(template_key or "")
    marker = "_template_"
    return key.split(marker, 1)[0] if marker in key else ""


def _unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _ensure_output_source_db(
    source_dbs: dict[str, dict[str, Any]],
    target_path: str,
    fallback_path: str,
) -> None:
    if target_path in source_dbs:
        return
    if fallback_path in source_dbs:
        source_db = copy.deepcopy(source_dbs[fallback_path])
        table = source_db.get("table")
        if isinstance(table, dict):
            table["table_name"] = target_path.replace("\\", "/").rsplit("/", 1)[-1]
        source_dbs[target_path] = source_db


def _character_dependency_aliases() -> dict[str, list[str]]:
    return {
        "character_generation_templates": [
            "character_generation_templates",
            "db/character_generation_templates_tables/_mtu_characters",
            "db/character_generation_templates_tables/data",
            "db/character_generation_templates_tables/data__",
            "db/character_generation_templates_tables/new_hero",
        ],
        "character_generation_template_game_mode_details": [
            "character_generation_template_game_mode_details",
            "db/character_generation_template_game_mode_details_tables/_mtu_characters",
            "db/character_generation_template_game_mode_details_tables/data",
            "db/character_generation_template_game_mode_details_tables/data__",
            "db/character_generation_template_game_mode_details_tables/new_hero",
        ],
        "campaign_character_art_sets": [
            "campaign_character_art_sets",
            "db/campaign_character_art_sets_tables/_mtu_characters",
            "db/campaign_character_art_sets_tables/data",
            "db/campaign_character_art_sets_tables/data__",
            "db/campaign_character_art_sets_tables/new_hero",
        ],
        "campaign_character_arts": [
            "campaign_character_arts",
            "db/campaign_character_arts_tables/_mtu_characters",
            "db/campaign_character_arts_tables/data",
            "db/campaign_character_arts_tables/data__",
            "db/campaign_character_arts_tables/new_hero",
        ],
        "agent_uniforms": [
            "agent_uniforms",
            "db/agent_uniforms_tables/_mtu_characters",
            "db/agent_uniforms_tables/data__",
            "db/agent_uniforms_tables/data",
            "db/agent_uniforms_tables/new_hero",
        ],
        "variants": [
            "variants",
            "db/variants_tables/_mtu_characters_variants",
            "db/variants_tables/data__",
            "db/variants_tables/data",
        ],
        "character_generation_spawn_age_ranges": [
            "character_generation_spawn_age_ranges",
            "db/character_generation_spawn_age_ranges_tables/_mtu_characters",
            "db/character_generation_spawn_age_ranges_tables/data",
            "db/character_generation_spawn_age_ranges_tables/data__",
            "db/character_generation_spawn_age_ranges_tables/new_hero",
        ],
        "ceo_initial_datas": [
            "ceo_initial_datas",
            "db/ceo_initial_datas_tables/_mtu_characters_ceo",
            "db/ceo_initial_datas_tables/data",
            "db/ceo_initial_datas_tables/data__",
            "db/ceo_initial_datas_tables/new_hero",
        ],
        "equipment_variants_weapons": TABLE_ALIASES["equipment_variants_weapons"],
        "equipment_variants_armours": TABLE_ALIASES["equipment_variants_armours"],
        "unit_armour_types": [
            *TABLE_ALIASES["unit_armour_types"],
            "db/unit_armour_types_tables/data__",
            "db/unit_armour_types_tables/data",
        ],
        "melee_weapons": TABLE_ALIASES["melee_weapons"],
        "missile_weapons": TABLE_ALIASES["missile_weapons"],
        "projectiles": TABLE_ALIASES["projectiles"],
        "frontend_character_ceos": [
            "frontend_character_ceos",
            "db/frontend_character_ceos_tables/_mtu_characters_ceo",
            "db/frontend_character_ceos_tables/data",
            "db/frontend_character_ceos_tables/data__",
        ],
        "retinues": [
            "retinues",
            "db/retinues_tables/data__",
        ],
        "retinue_slot_initial_units": [
            "retinue_slot_initial_units",
            "db/retinue_slot_initial_units_tables/data__",
            "db/retinue_slot_initial_units_tables/zhou_yu_fix",
        ],
        "cai_retinues_to_aspects": [
            "cai_retinues_to_aspects",
            "db/cai_retinues_to_aspects_tables/data__",
            "db/cai_retinues_to_aspects_tables/unit",
        ],
        "agent_subtypes": [
            "agent_subtypes",
            "db/agent_subtypes_tables/data__",
            "db/agent_subtypes_tables/data",
        ],
        "cai_agent_subtypes_to_aspects": [
            "cai_agent_subtypes_to_aspects",
            "db/cai_agent_subtypes_to_aspects_tables/data__",
            "db/cai_agent_subtypes_to_aspects_tables/data",
        ],
        "agent_subtype_loyalty_factor_junctions": [
            "agent_subtype_loyalty_factor_junctions",
            "db/agent_subtype_loyalty_factor_junctions_tables/data__",
            "db/agent_subtype_loyalty_factor_junctions_tables/data",
        ],
        "effect_bonus_value_agent_subtype_loyalty_factor_junctions": [
            "effect_bonus_value_agent_subtype_loyalty_factor_junctions",
            "db/effect_bonus_value_agent_subtype_loyalty_factor_junctions_tables/data__",
            "db/effect_bonus_value_agent_subtype_loyalty_factor_junctions_tables/data",
        ],
        "agent_subtype_weighted_selection_set_to_weights": [
            "agent_subtype_weighted_selection_set_to_weights",
            "db/agent_subtype_weighted_selection_set_to_weights_tables/data__",
            "db/agent_subtype_weighted_selection_set_to_weights_tables/data",
        ],
        "campaign_group_member_criteria_agent_subtypes": [
            "campaign_group_member_criteria_agent_subtypes",
            "db/campaign_group_member_criteria_agent_subtypes_tables/data__",
            "db/campaign_group_member_criteria_agent_subtypes_tables/data",
        ],
        "faction_agent_permitted_subtypes": [
            "faction_agent_permitted_subtypes",
            "db/faction_agent_permitted_subtypes_tables/data__",
            "db/faction_agent_permitted_subtypes_tables/data",
        ],
        "ministerial_postion_valid_agent_subtypes": [
            "ministerial_postion_valid_agent_subtypes",
            "db/ministerial_postion_valid_agent_subtypes_tables/data__",
            "db/ministerial_postion_valid_agent_subtypes_tables/data",
        ],
        "effect_bonus_value_agent_subtype_junctions": [
            "effect_bonus_value_agent_subtype_junctions",
            "db/effect_bonus_value_agent_subtype_junctions_tables/data__",
            "db/effect_bonus_value_agent_subtype_junctions_tables/data",
        ],
        "agent_subtype_subculture_overrides": [
            "agent_subtype_subculture_overrides",
            "db/agent_subtype_subculture_overrides_tables/data__",
            "db/agent_subtype_subculture_overrides_tables/data",
        ],
        "agent_subtype_civil_war_faction_overrides": [
            "agent_subtype_civil_war_faction_overrides",
            "db/agent_subtype_civil_war_faction_overrides_tables/data__",
            "db/agent_subtype_civil_war_faction_overrides_tables/data",
        ],
        "character_attribute_sets": [
            "character_attribute_sets",
            "db/character_attribute_sets_tables/data__",
            "db/character_attribute_sets_tables/data",
        ],
        "character_attributes": [
            "character_attributes",
            "db/character_attributes_tables/data__",
            "db/character_attributes_tables/data",
        ],
        "character_skill_node_sets": [
            "character_skill_node_sets",
            "db/character_skill_node_sets_tables/_mtu_characters_skills",
            "db/character_skill_node_sets_tables/_mtu_characters",
        ],
        "character_skill_nodes": [
            "character_skill_nodes",
            "db/character_skill_nodes_tables/_mtu_characters_skills_nodes_01_earth_commander",
            "db/character_skill_nodes_tables/_mtu_characters",
        ],
        "character_skill_node_links": [
            "character_skill_node_links",
            "db/character_skill_node_links_tables/_mtu_characters_skills",
            "db/character_skill_node_links_tables/_mtu_characters",
        ],
        "character_skills": [
            "character_skills",
            "db/character_skills_tables/_mtu_characters_skills",
            "db/character_skills_tables/data__",
        ],
        "character_skill_level_to_effects_junctions": [
            "character_skill_level_to_effects_junctions",
            "db/character_skill_level_to_effects_junctions_tables/_mtu_characters_skills",
            "db/character_skill_level_to_effects_junctions_tables/data__",
        ],
        "effects": [
            "effects",
            "db/effects_tables/_mtu_characters_skills_effects",
            "db/effects_tables/data__",
        ],
        "effect_bonus_value_ids_unit_sets": [
            "effect_bonus_value_ids_unit_sets",
            "db/effect_bonus_value_ids_unit_sets_tables/_mtu_characters_effects",
            "db/effect_bonus_value_ids_unit_sets_tables/data__",
        ],
        "effect_bonus_value_unit_ability_junctions": [
            "effect_bonus_value_unit_ability_junctions",
            "db/effect_bonus_value_unit_ability_junctions_tables/_mtu_characters_skills_effects",
            "db/effect_bonus_value_unit_ability_junctions_tables/data__",
        ],
        "land_units": [
            "land_units",
            "db/land_units_tables/_mtu_characters_custom_battles_land_units",
        ],
        "land_units_to_unit_abilites_junctions": [
            "land_units_to_unit_abilites_junctions",
            "db/land_units_to_unit_abilites_junctions_tables/_mtu_characters_skills_abilities_land_units",
            "db/land_units_to_unit_abilites_junctions_tables/_mtu_characters_skills_abilities_land_units_bug_unique",
            "db/land_units_to_unit_abilites_junctions_tables/_mtu_characters_skills_abilities_land_units_duel",
            "db/land_units_to_unit_abilites_junctions_tables/_mtu_characters_skills_abilities_land_units_elephant_skill",
            "db/land_units_to_unit_abilites_junctions_tables/data__",
        ],
        "unit_abilities": [
            "unit_abilities",
            "db/unit_abilities_tables/_mtu_characters_skills_abilities",
            "db/unit_abilities_tables/data__",
        ],
        "unit_special_abilities": [
            "unit_special_abilities",
            "db/unit_special_abilities_tables/_mtu_characters_skills_abilities",
            "db/unit_special_abilities_tables/data__",
        ],
        "special_ability_to_special_ability_phase_junctions": [
            "special_ability_to_special_ability_phase_junctions",
            "db/special_ability_to_special_ability_phase_junctions_tables/_mtu_characters_skills_abilities",
            "db/special_ability_to_special_ability_phase_junctions_tables/data__",
        ],
        "special_ability_phases": [
            "special_ability_phases",
            "db/special_ability_phases_tables/_mtu_characters_skills_abilities",
            "db/special_ability_phases_tables/data__",
        ],
        "special_ability_phase_stat_effects": [
            "special_ability_phase_stat_effects",
            "db/special_ability_phase_stat_effects_tables/_mtu_characters_skills_abilities",
            "db/special_ability_phase_stat_effects_tables/data__",
        ],
        "special_ability_phase_attribute_effects": [
            "special_ability_phase_attribute_effects",
            "db/special_ability_phase_attribute_effects_tables/_mtu_characters_skills_abilities",
            "db/special_ability_phase_attribute_effects_tables/data__",
        ],
        "special_ability_phase_displays": [
            "special_ability_phase_displays",
            "db/special_ability_phase_displays_tables/_mtu_characters_skills_abilities",
            "db/special_ability_phase_displays_tables/data__",
        ],
        "special_ability_to_auto_deactivate_flags": [
            "special_ability_to_auto_deactivate_flags",
            "db/special_ability_to_auto_deactivate_flags_tables/_mtu_characters_skills_abilities",
            "db/special_ability_to_auto_deactivate_flags_tables/data__",
        ],
        "special_ability_to_invalid_target_flags": [
            "special_ability_to_invalid_target_flags",
            "db/special_ability_to_invalid_target_flags_tables/_mtu_characters_skills_abilities",
            "db/special_ability_to_invalid_target_flags_tables/data__",
        ],
        "special_ability_to_invalid_usage_flags": [
            "special_ability_to_invalid_usage_flags",
            "db/special_ability_to_invalid_usage_flags_tables/_mtu_characters_skills_abilities",
            "db/special_ability_to_invalid_usage_flags_tables/_mtu_characters_skills_elephant_restraint",
            "db/special_ability_to_invalid_usage_flags_tables/data__",
        ],
        "projectile_bombardments": [
            "projectile_bombardments",
            "db/projectile_bombardments_tables/_mtu_characters_skills_abilities",
            "db/projectile_bombardments_tables/data__",
        ],
        "projectile_displays": [
            "projectile_displays",
            "db/projectile_displays_tables/_mtu_characters_skills_abilities",
            "db/projectile_displays_tables/data__",
        ],
        "projectile_impacts": [
            "projectile_impacts",
            "db/projectile_impacts_tables/_mtu_characters_skills_abilities",
            "db/projectile_impacts_tables/data__",
        ],
        "projectiles": [
            "projectiles",
            "db/projectiles_tables/_mtu_characters_skills_abilities",
            "db/projectiles_tables/_mtu_characters_weapons",
            "db/projectiles_tables/data__",
        ],
    }


def _copy_initial_ceo_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    initial_ceo: Any,
) -> None:
    key = str(initial_ceo or "")
    if not key:
        return
    resolved_key = _resolve_existing_initial_ceo_key(tables, table_names, source_dbs, key, "")
    if resolved_key:
        key = resolved_key
    if _delta_initial_ceo_row_exists(rows_by_table, key):
        _copy_initial_ceo_equipment_variant_dependencies(tables, table_names, source_dbs, rows_by_table, key)
        return
    _ensure_initial_ceo_rows_available(tables, table_names, source_dbs, key)
    source_row = _find_row(tables.get("ceo_initial_datas", []), "key", key)
    if not source_row:
        raise ValueError(f"Source initial CEO row not found after reference/material merge: {key}")
    table_path = source_row.get("_sourceTablePath") or table_names.get("ceo_initial_datas")
    if table_path:
        _upsert_delta_row(rows_by_table, str(table_path), "key", _clean_source_row(source_row))
    _copy_initial_ceo_equipment_variant_dependencies(tables, table_names, source_dbs, rows_by_table, key)


def _copy_initial_ceo_equipment_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    initial_ceo: Any,
) -> None:
    # Total War: THREE KINGDOMS stores character initial CEO data as a key-only
    # table in the shipped database. Earlier builds tried to synthesize a
    # stage/equipment/active-CEO chain here, but those tables are not present in
    # the real 3K DB or the working sample packs, and emitting them can create
    # invalid/ignored data. Keep the function as a compatibility no-op.
    return


def _copy_initial_ceo_dependency_if_available(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    initial_ceo: Any,
) -> None:
    try:
        _copy_initial_ceo_dependency(tables, table_names, source_dbs, rows_by_table, initial_ceo)
    except ValueError as exc:
        if "Source initial CEO row not found after reference/material merge:" not in str(exc):
            raise


def _delta_initial_ceo_row_exists(rows_by_table: dict[str, list[dict[str, Any]]], key: str) -> bool:
    for table_path, rows in rows_by_table.items():
        normalized_path = _normalize_pack_path(table_path)
        if "/ceo_initial_datas_tables/" not in normalized_path and normalized_path != "ceo_initial_datas":
            continue
        if any(str(row.get("key") or "") == key for row in rows):
            return True
    return False


def _materialize_equipment_initial_ceo(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    source_initial_ceo: Any,
    owner_key: str,
    equipment_ceo_keys: tuple[str, ...] | list[str],
    removable_equipment_ceo_keys: tuple[str, ...] | list[str] = (),
    active_ceo_keys: tuple[str, ...] | list[str] = (),
    removable_active_ceo_keys: tuple[str, ...] | list[str] = (),
) -> str | None:
    source_key = str(source_initial_ceo or "").strip()
    return source_key or None


def _copy_initial_ceo_equipment_variant_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    initial_ceo: Any,
) -> None:
    tokens = _equipment_tokens_from_initial_ceo(initial_ceo)
    if not tokens:
        return
    armour_variant = _best_equipment_variant_for_tokens(
        tokens,
        tables.get("equipment_variants_armours", []),
        "armour",
    )
    if armour_variant:
        _copy_equipment_variant_row(
            tables,
            table_names,
            source_dbs,
            rows_by_table,
            "equipment_variants_armours",
            armour_variant,
        )
        _copy_armour_type_dependency(
            tables,
            table_names,
            source_dbs,
            rows_by_table,
            armour_variant.get("armour"),
        )
    weapon_variant = _best_equipment_variant_for_tokens(
        tokens,
        tables.get("equipment_variants_weapons", []),
        "weapon",
    )
    if weapon_variant:
        _copy_equipment_variant_row(
            tables,
            table_names,
            source_dbs,
            rows_by_table,
            "equipment_variants_weapons",
            weapon_variant,
        )
        _copy_weapon_stat_dependencies(tables, table_names, rows_by_table, weapon_variant)


def _copy_equipment_variant_dependency_for_ceo_key(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    ceo_key: Any,
) -> None:
    key = str(ceo_key or "").strip()
    if not key:
        return
    for alias, kind in (
        ("equipment_variants_armours", "armour"),
        ("equipment_variants_weapons", "weapon"),
    ):
        variant = next(
            (
                row for row in tables.get(alias, [])
                if str(row.get("ceos_key") or "") == key
                or (kind == "armour" and _runtime_armour_ceo_key(row.get("ceos_key")) == key)
            ),
            None,
        )
        if not variant:
            continue
        _copy_equipment_variant_row(
            tables,
            table_names,
            source_dbs,
            rows_by_table,
            alias,
            variant,
        )
        if kind == "armour":
            _copy_armour_type_dependency(
                tables,
                table_names,
                source_dbs,
                rows_by_table,
                variant.get("armour"),
            )
        else:
            _copy_weapon_stat_dependencies(tables, table_names, rows_by_table, variant)
        return


def _equipment_tokens_from_initial_ceo(initial_ceo: Any) -> list[str]:
    raw = _historical_initial_ceo_token(initial_ceo)
    tokens = [raw]
    if raw.startswith("lady_"):
        tokens.append(raw.removeprefix("lady_"))
    return _unique_strings(tokens)


def _best_equipment_variant_for_tokens(
    tokens: list[str],
    rows: list[dict[str, Any]],
    equipment_kind: str,
) -> dict[str, Any] | None:
    candidates: list[tuple[int, int, int, str, dict[str, Any]]] = []
    for row in rows:
        ceo_key = str(row.get("ceos_key") or "")
        normalized = ceo_key.lower()
        if equipment_kind == "weapon" and "weapon" not in normalized:
            continue
        if equipment_kind == "armour" and "armour" not in normalized:
            continue
        for token_index, token in enumerate(tokens):
            match_rank = _equipment_variant_match_rank(row, normalized, token)
            if match_rank is None:
                continue
            candidates.append((token_index, match_rank, ceo_key.count("_"), ceo_key, row))
            break
    if not candidates:
        return None
    # Duplicate material/reference rows can produce candidates with identical
    # ranking fields.  Comparing the full tuples would then fall through to the
    # final row dict, which is not orderable on Python 3.  Keep the merge order
    # as the stable tie-breaker and compare only the scalar ranking fields.
    return min(candidates, key=lambda candidate: candidate[:4])[4]


def _equipment_variant_token_matches(normalized_ceo_key: str, token: Any) -> bool:
    token_text = str(token or "").lower()
    if not token_text:
        return False
    if len(token_text) >= 4 and token_text in normalized_ceo_key:
        return True
    parts = [part for part in re.split(r"[^a-z0-9]+", normalized_ceo_key) if part]
    return any(part == token_text or part == f"{token_text}s" for part in parts)


def _equipment_variant_match_rank(row: dict[str, Any], normalized_ceo_key: str, token: Any) -> int | None:
    if _equipment_variant_token_matches(normalized_ceo_key, token):
        return 0
    row_text = " ".join(
        str(value).lower()
        for value in row.values()
        if isinstance(value, str) and value
    )
    if _equipment_variant_token_matches(row_text, token):
        return 1
    return None


def _copy_equipment_variant_row(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    alias: str,
    row: dict[str, Any],
) -> None:
    ceo_key = str(row.get("ceos_key") or "")
    if ceo_key:
        _append_internal_material_keyed_rows(
            alias,
            "ceos_to_equipment_variants_tables",
            "ceos_key",
            ceo_key,
            tables,
            source_dbs,
        )
    table_path = row.get("_sourceTablePath") or table_names.get(alias)
    if not table_path:
        table_path = _ensure_dependency_table_name(
            table_names,
            source_dbs,
            alias,
            "ceos_to_equipment_variants_tables",
        )
    if table_path:
        _upsert_delta_row(rows_by_table, str(table_path), _equipment_variant_key, _clean_source_row(row))


def _copy_armour_type_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    armour_key: Any,
) -> None:
    key = str(armour_key or "")
    if not key:
        return
    _append_internal_material_keyed_rows(
        "unit_armour_types",
        "unit_armour_types_tables",
        "key",
        key,
        tables,
        source_dbs,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "unit_armour_types",
        lambda row: str(row.get("key") or "") == key,
        "key",
    )


def _copy_weapon_stat_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    variant: dict[str, Any],
) -> None:
    melee_key = str(variant.get("primary_melee_weapon") or "")
    missile_key = str(variant.get("primary_missile_weapon") or "")
    if melee_key:
        _copy_matching_rows_once(
            tables,
            table_names,
            rows_by_table,
            "melee_weapons",
            lambda row: str(row.get("key") or "") == melee_key,
            "key",
        )
    if not missile_key:
        return
    missile_rows = [
        row for row in tables.get("missile_weapons", [])
        if str(row.get("key") or "") == missile_key
    ]
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "missile_weapons",
        lambda row: str(row.get("key") or "") == missile_key,
        "key",
    )
    projectile_keys = _unique_strings([row.get("default_projectile") for row in missile_rows])
    for projectile_key in projectile_keys:
        _copy_matching_rows_once(
            tables,
            table_names,
            rows_by_table,
            "projectiles",
            lambda row, key=projectile_key: str(row.get("key") or "") == key,
            "key",
        )


def _equipment_kind_from_ceo_key(value: Any) -> str:
    text = str(value or "").lower()
    category_patterns = (
        ("weapon", "ancillary_weapon"),
        ("armour", "ancillary_armour"),
        ("follower", "ancillary_follower"),
        ("accessory", "ancillary_accessory"),
        ("mount", "ancillary_mount"),
    )
    for kind, pattern in category_patterns:
        if pattern in text:
            return kind
    for kind in ("weapon", "armour", "armor", "follower", "accessory", "mount"):
        if kind in text:
            return "armour" if kind == "armor" else kind
    return ""


def _ensure_initial_ceo_rows_available(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    initial_ceo_key: Any,
) -> None:
    key = str(initial_ceo_key or "")
    if not key:
        return
    target = tables.setdefault("ceo_initial_datas", [])
    if any(str(row.get("key") or "") == key for row in target):
        return
    _append_internal_material_keyed_rows(
        "ceo_initial_datas",
        "ceo_initial_datas_tables",
        "key",
        key,
        tables,
        source_dbs,
    )
    if any(str(row.get("key") or "") == key for row in target):
        _ensure_dependency_table_name(table_names, source_dbs, "ceo_initial_datas", "ceo_initial_datas_tables")
        return


def _copy_attribute_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    attribute_set: Any,
) -> None:
    key = str(attribute_set or "")
    if not key:
        return
    _ensure_attribute_set_rows_available(tables, source_dbs, key)
    _copy_matching_rows(tables, table_names, rows_by_table, "character_attribute_sets", lambda row: _attribute_set_key(row) == key, _attribute_set_key)
    _copy_matching_rows(tables, table_names, rows_by_table, "character_attributes", lambda row: _attribute_set_key(row) == key, _attribute_key)


def _ensure_attribute_set_rows_available(
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
    attribute_set_key: Any,
) -> None:
    key = str(attribute_set_key or "")
    if not key:
        return
    has_set = any(_attribute_set_key(row) == key for row in tables.get("character_attribute_sets", []))
    has_attrs = any(_attribute_set_key(row) == key for row in tables.get("character_attributes", []))
    if has_set and has_attrs:
        return
    if not INTERNAL_MATERIALS_PATH.is_file():
        return
    try:
        with INTERNAL_MATERIALS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return
    material_tables = payload.get("tables", {})
    if not isinstance(material_tables, dict):
        return
    _append_internal_material_attribute_rows(
        material_tables,
        "character_attribute_sets",
        "character_attribute_sets_tables",
        key,
        _attribute_set_key,
        tables,
        source_dbs,
    )
    _append_internal_material_attribute_rows(
        material_tables,
        "character_attributes",
        "character_attributes_tables",
        key,
        _attribute_key,
        tables,
        source_dbs,
    )


def _append_internal_material_keyed_rows(
    alias: str,
    folder: str,
    key_field: str,
    wanted_key: str,
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
) -> None:
    if not INTERNAL_MATERIALS_PATH.is_file():
        return
    try:
        with INTERNAL_MATERIALS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return
    material_tables = payload.get("tables", {})
    if not isinstance(material_tables, dict):
        return
    target = tables.setdefault(alias, [])
    existing = {str(row.get(key_field) or "") for row in target}
    for table_path, entry in material_tables.items():
        if f"/{folder}/" not in table_path:
            continue
        if not isinstance(entry, dict):
            continue
        rows = entry.get("rows", [])
        if not isinstance(rows, list):
            continue
        matched = False
        for row in rows:
            if not isinstance(row, dict) or str(row.get(key_field) or "") != wanted_key:
                continue
            if wanted_key in existing:
                continue
            clean_row = copy.deepcopy(row)
            clean_row["_sourceTablePath"] = table_path
            target.append(clean_row)
            existing.add(wanted_key)
            matched = True
        db = entry.get("db")
        if matched and isinstance(db, dict):
            source_dbs.setdefault(table_path, copy.deepcopy(db))


def _ensure_dependency_table_name(
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    alias: str,
    folder: str,
) -> str | None:
    if table_names.get(alias):
        return table_names[alias]
    for table_path in source_dbs:
        if f"/{folder}/" in table_path:
            table_names[alias] = table_path
            return table_path
    if not INTERNAL_MATERIALS_PATH.is_file():
        return None
    try:
        with INTERNAL_MATERIALS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    material_tables = payload.get("tables", {})
    if not isinstance(material_tables, dict):
        return None
    for table_path, entry in material_tables.items():
        if f"/{folder}/" not in table_path or not isinstance(entry, dict):
            continue
        db = entry.get("db")
        if isinstance(db, dict):
            source_dbs.setdefault(table_path, copy.deepcopy(db))
            table_names[alias] = table_path
            return table_path
    return None


def _append_internal_material_attribute_rows(
    material_tables: dict[str, Any],
    alias: str,
    folder: str,
    attribute_set_key: str,
    row_key: Any,
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
) -> None:
    target = tables.setdefault(alias, [])
    existing = {row_key(row) for row in target}
    for table_path, entry in material_tables.items():
        if f"/{folder}/" not in table_path:
            continue
        if not isinstance(entry, dict):
            continue
        rows = entry.get("rows", [])
        if not isinstance(rows, list):
            continue
        matched = False
        for row in rows:
            if not isinstance(row, dict) or _attribute_set_key(row) != attribute_set_key:
                continue
            clean_row = copy.deepcopy(row)
            clean_row["_sourceTablePath"] = table_path
            key = row_key(clean_row)
            if key in existing:
                continue
            target.append(clean_row)
            existing.add(key)
            matched = True
        db = entry.get("db")
        if matched and isinstance(db, dict):
            source_dbs.setdefault(table_path, copy.deepcopy(db))


def _copy_skill_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    skill_set: Any,
) -> None:
    key = str(skill_set or "")
    if not key:
        return
    _copy_matching_rows(tables, table_names, rows_by_table, "character_skill_node_sets", lambda row: row.get("key") == key, "key")
    skill_nodes = [
        row for row in tables.get("character_skill_nodes", [])
        if row.get("character_skill_node_set_key") == key
    ]
    node_keys = {str(row.get("key")) for row in skill_nodes if row.get("key")}
    for row in skill_nodes:
        table_path = row.get("_sourceTablePath") or table_names.get("character_skill_nodes")
        if table_path:
            clean_row = {key: value for key, value in row.items() if not key.startswith("_source")}
            _upsert_delta_row(rows_by_table, table_path, "key", clean_row)
    if node_keys:
        _copy_matching_rows(
            tables,
            table_names,
            rows_by_table,
            "character_skill_node_links",
            lambda row, keys=node_keys: str(row.get("parent_key")) in keys or str(row.get("child_key")) in keys,
            _skill_link_key,
        )
    skill_keys = {str(row.get("character_skill_key") or "") for row in skill_nodes if row.get("character_skill_key")}
    _copy_skill_effect_dependencies(tables, table_names, rows_by_table, skill_keys)


def _copy_skill_effect_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    skill_keys: set[str],
) -> None:
    if not skill_keys:
        return
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "character_skills",
        lambda row, keys=skill_keys: str(row.get("key") or "") in keys,
        "key",
    )
    effect_keys: set[str] = set()
    for row in tables.get("character_skill_level_to_effects_junctions", []):
        if str(row.get("character_skill_key") or "") not in skill_keys:
            continue
        effect_key = str(row.get("effect_key") or "")
        if effect_key:
            effect_keys.add(effect_key)
        table_path = row.get("_sourceTablePath") or table_names.get("character_skill_level_to_effects_junctions")
        if table_path:
            clean_row = {key: value for key, value in row.items() if not key.startswith("_source")}
            _upsert_delta_row(rows_by_table, table_path, _skill_effect_key, clean_row)
    if effect_keys:
        _copy_matching_rows(
            tables,
            table_names,
            rows_by_table,
            "effects",
            lambda row, keys=effect_keys: _effect_key(row) in keys,
            _effect_key,
        )
        _copy_effect_bonus_value_dependencies(tables, table_names, rows_by_table, effect_keys)


def _copy_effect_bonus_value_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    effect_keys: set[str],
) -> None:
    if not effect_keys:
        return
    bonus_value_ids: set[str] = set()
    for row in tables.get("effect_bonus_value_ids_unit_sets", []):
        effect_key = str(row.get("effect") or row.get("effect_key") or "")
        if effect_key not in effect_keys:
            continue
        bonus_value_id = _effect_bonus_value_id(row)
        if bonus_value_id:
            bonus_value_ids.add(bonus_value_id)
        table_path = row.get("_sourceTablePath") or table_names.get("effect_bonus_value_ids_unit_sets")
        if table_path:
            _upsert_delta_row_once(rows_by_table, table_path, _effect_bonus_value_unit_set_key, _clean_source_row(row))

    ability_keys: set[str] = set()
    for row in tables.get("effect_bonus_value_unit_ability_junctions", []):
        bonus_value_id = _effect_bonus_value_id(row)
        effect_key = str(row.get("effect") or row.get("effect_key") or "")
        if bonus_value_id not in bonus_value_ids and effect_key not in effect_keys:
            continue
        ability_key = _effect_bonus_unit_ability(row)
        if ability_key:
            ability_keys.add(ability_key)
        table_path = row.get("_sourceTablePath") or table_names.get("effect_bonus_value_unit_ability_junctions")
        if table_path:
            _upsert_delta_row_once(rows_by_table, table_path, _effect_bonus_value_unit_ability_key, _clean_source_row(row))

    _copy_unit_ability_dependencies(tables, table_names, rows_by_table, ability_keys)


def _skill_node_clone_key(source_set_key: str, new_set_key: str, source_node_key: str) -> str:
    if source_set_key == new_set_key:
        return source_node_key
    suffix = source_node_key
    prefix = f"{source_set_key}_"
    if source_node_key.startswith(prefix):
        suffix = source_node_key[len(prefix):]
    return f"{new_set_key}_{suffix}"


def _copy_retinue_dependency(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    retinue: Any,
) -> None:
    key = str(retinue or "")
    if not key:
        return
    _copy_matching_rows(tables, table_names, rows_by_table, "retinues", lambda row: row.get("key") == key, "key")
    _copy_matching_rows(tables, table_names, rows_by_table, "cai_retinues_to_aspects", lambda row: row.get("retinue") == key, _retinue_aspect_key)
    slot_rows = [
        row for row in tables.get("retinue_slot_initial_units", [])
        if row.get("retinue") == key
    ]
    unit_keys = {str(row.get("initial_unit_record")) for row in slot_rows if row.get("initial_unit_record")}
    for row in slot_rows:
        table_path = row.get("_sourceTablePath") or table_names.get("retinue_slot_initial_units")
        if table_path:
            clean_row = {key: value for key, value in row.items() if not key.startswith("_source")}
            _upsert_delta_row(rows_by_table, table_path, _retinue_slot_key, clean_row)
    for unit_key in unit_keys:
        _copy_matching_rows(tables, table_names, rows_by_table, "land_units", lambda row, key=unit_key: row.get("key") == key, "key")
        _copy_land_unit_ability_rows(tables, table_names, rows_by_table, unit_key)


def _copy_skill_source_retinue_abilities(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    skill_set: Any,
    target_retinue: Any,
) -> None:
    skill_set_key = str(skill_set or "")
    target_retinue_key = str(target_retinue or "")
    if not skill_set_key or not target_retinue_key:
        return
    target_slots = _retinue_unit_by_slot(tables.get("retinue_slot_initial_units", []), target_retinue_key)
    if not target_slots:
        return
    ability_keys = _battle_ability_keys_for_skill_set(
        tables,
        skill_set_key,
        rows_by_table,
    )
    if not ability_keys:
        return
    source_retinues = [
        str(row.get("retinue") or "")
        for row in tables.get("character_generation_template_game_mode_details", [])
        if row.get("skill_set_override") == skill_set_key
    ]
    for source_retinue in _unique_strings(source_retinues):
        if not source_retinue or source_retinue == target_retinue_key:
            continue
        source_slots = _retinue_unit_by_slot(tables.get("retinue_slot_initial_units", []), source_retinue)
        for slot_index, source_unit in source_slots.items():
            target_unit = target_slots.get(slot_index)
            if target_unit:
                _copy_land_unit_ability_rows(tables, table_names, rows_by_table, source_unit, target_unit, ability_keys)
    target_character_unit = _first_retinue_unit_key(target_slots)
    if not target_character_unit:
        return
    for row in tables.get("land_units_to_unit_abilites_junctions", []):
        ability_key = str(row.get("ability") or "")
        source_unit = str(row.get("land_unit") or "")
        if ability_key in ability_keys and _is_character_land_unit_key(source_unit):
            _copy_land_unit_ability_rows(tables, table_names, rows_by_table, source_unit, target_character_unit, ability_keys)
    for ability_key in ability_keys:
        _ensure_land_unit_ability_row(
            tables,
            table_names,
            source_dbs,
            rows_by_table,
            target_character_unit,
            ability_key,
        )


def _ensure_land_unit_ability_row(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    source_dbs: dict[str, dict[str, Any]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    target_unit: Any,
    ability: Any,
) -> bool:
    target_unit_key = str(target_unit or "")
    ability_key = str(ability or "")
    if not target_unit_key or not ability_key:
        return False
    _copy_unit_ability_dependencies(tables, table_names, rows_by_table, {ability_key})
    if _land_unit_ability_row_exists(tables, rows_by_table, target_unit_key, ability_key):
        return False
    table_path = _ensure_dependency_table_name(
        table_names,
        source_dbs,
        "land_units_to_unit_abilites_junctions",
        "land_units_to_unit_abilites_junctions_tables",
    )
    if not table_path:
        table_path = _first_source_table_path(tables.get("land_units_to_unit_abilites_junctions", []))
    if not table_path:
        return False
    return _upsert_delta_row_once(
        rows_by_table,
        table_path,
        _land_unit_ability_key,
        {"land_unit": target_unit_key, "ability": ability_key},
    )


def _land_unit_ability_row_exists(
    tables: dict[str, list[dict[str, Any]]],
    rows_by_table: dict[str, list[dict[str, Any]]],
    target_unit: str,
    ability: str,
) -> bool:
    for row in tables.get("land_units_to_unit_abilites_junctions", []):
        if str(row.get("land_unit") or "") == target_unit and str(row.get("ability") or "") == ability:
            return True
    for table_path, rows in rows_by_table.items():
        if "land_units_to_unit_abilites_junctions_tables" not in _normalize_pack_path(table_path):
            continue
        for row in rows:
            if str(row.get("land_unit") or "") == target_unit and str(row.get("ability") or "") == ability:
                return True
    return False


def _first_source_table_path(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        table_path = str(row.get("_sourceTablePath") or "")
        if table_path:
            return table_path
    return ""


def _retinue_unit_by_slot(rows: list[dict[str, Any]], retinue: str) -> dict[Any, str]:
    result: dict[Any, str] = {}
    for row in rows:
        if row.get("retinue") != retinue:
            continue
        unit_key = str(row.get("initial_unit_record") or "")
        if unit_key:
            result[row.get("slot_index")] = unit_key
    return result


def _first_retinue_unit_key(slots: dict[Any, str]) -> str:
    if not slots:
        return ""
    if 0 in slots:
        return slots[0]
    try:
        first_slot = sorted(slots)[0]
    except TypeError:
        first_slot = next(iter(slots))
    return slots.get(first_slot, "")


def _is_character_land_unit_key(unit_key: str) -> bool:
    return "_hero_" in unit_key or "_general_" in unit_key or unit_key.startswith(("3k_main_hero", "3k_main_general"))


def _battle_ability_keys_for_skill_set(
    tables: dict[str, list[dict[str, Any]]],
    skill_set: str,
    rows_by_table: dict[str, list[dict[str, Any]]] | None = None,
) -> set[str]:
    output_skill_nodes = _output_dependency_rows(
        rows_by_table or {},
        "character_skill_nodes_tables",
    )
    skill_keys = {
        str(row.get("character_skill_key") or "")
        for row in [*tables.get("character_skill_nodes", []), *output_skill_nodes]
        if row.get("character_skill_node_set_key") == skill_set and row.get("character_skill_key")
    }
    output_skill_effects = _output_dependency_rows(
        rows_by_table or {},
        "character_skill_level_to_effects_junctions_tables",
    )
    effect_keys = {
        str(row.get("effect_key") or "")
        for row in [
            *tables.get("character_skill_level_to_effects_junctions", []),
            *output_skill_effects,
        ]
        if str(row.get("character_skill_key") or "") in skill_keys and row.get("effect_key")
    }
    candidates: set[str] = set()
    for key in [*skill_keys, *effect_keys]:
        candidates.update(_battle_ability_key_candidates(key))
    known_land_unit_abilities = {
        str(row.get("ability") or "")
        for row in tables.get("land_units_to_unit_abilites_junctions", [])
        if row.get("ability")
    }
    known_unit_abilities = {
        str(row.get("key") or "")
        for row in tables.get("unit_abilities", [])
        if row.get("key")
    }
    effect_bonus_abilities = _battle_ability_keys_from_effect_bonus_rows(tables, effect_keys)
    explicit_abilities = {
        key
        for key in effect_bonus_abilities
        if key in known_land_unit_abilities or key in known_unit_abilities
    }
    existing_junction_abilities = {key for key in candidates if key in known_land_unit_abilities}
    return explicit_abilities | existing_junction_abilities


def _output_dependency_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_segment: str,
) -> list[dict[str, Any]]:
    marker = f"/{table_segment.lower()}/"
    return [
        row
        for table_path, rows in rows_by_table.items()
        if marker in f"/{_normalize_pack_path(table_path).lower()}/"
        for row in rows
    ]


def _battle_ability_keys_from_effect_bonus_rows(
    tables: dict[str, list[dict[str, Any]]],
    effect_keys: set[str],
) -> set[str]:
    if not effect_keys:
        return set()
    bonus_value_ids = {
        _effect_bonus_value_id(row)
        for row in tables.get("effect_bonus_value_ids_unit_sets", [])
        if str(row.get("effect") or row.get("effect_key") or "") in effect_keys
    }
    bonus_value_ids.discard("")
    return {
        _effect_bonus_unit_ability(row)
        for row in tables.get("effect_bonus_value_unit_ability_junctions", [])
        if (
            _effect_bonus_value_id(row) in bonus_value_ids
            or str(row.get("effect") or row.get("effect_key") or "") in effect_keys
        )
        and _effect_bonus_unit_ability(row)
    }


def _battle_ability_key_candidates(source_key: str) -> set[str]:
    key = str(source_key or "").strip()
    if not key:
        return set()
    candidates = {key}
    special_marker = "_skill_special_ability_"
    if special_marker in key:
        prefix, suffix = key.split(special_marker, 1)
        parts = suffix.split("_", 1)
        if parts[0] in {"metal", "wood", "water", "fire", "earth"} and len(parts) == 2:
            suffix = parts[1]
        candidates.add(f"{prefix}_ability_{suffix}")
        candidates.add(f"{prefix}_special_ability_{suffix}")
    for marker in ("_skill_", "_skill_effect_"):
        if marker in key:
            prefix, suffix = key.split(marker, 1)
            candidates.add(f"{prefix}_ability_{suffix}")
            candidates.add(f"{prefix}_special_ability_{suffix}")
    if key.startswith("3k_main_skill_"):
        candidates.add(f"3k_main_ability_{key.removeprefix('3k_main_skill_')}")
    return candidates


def _copy_land_unit_ability_rows(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    source_unit: Any,
    target_unit: Any | None = None,
    ability_filter: set[str] | None = None,
) -> int:
    source_unit_key = str(source_unit or "")
    target_unit_key = str(target_unit or source_unit_key)
    if not source_unit_key or not target_unit_key:
        return 0
    ability_keys: set[str] = set()
    copied = 0
    for row in tables.get("land_units_to_unit_abilites_junctions", []):
        if row.get("land_unit") != source_unit_key:
            continue
        ability_key = str(row.get("ability") or "")
        if ability_filter is not None and ability_key not in ability_filter:
            continue
        if ability_key:
            ability_keys.add(ability_key)
        table_path = row.get("_sourceTablePath") or table_names.get("land_units_to_unit_abilites_junctions")
        if not table_path:
            continue
        clean_row = _clean_source_row(row)
        clean_row["land_unit"] = target_unit_key
        if _upsert_delta_row_once(rows_by_table, table_path, _land_unit_ability_key, clean_row):
            copied += 1
    _copy_unit_ability_dependencies(tables, table_names, rows_by_table, ability_keys)
    return copied


def _copy_unit_ability_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    ability_keys: set[str],
    seen_special_abilities: set[str] | None = None,
    seen_projectiles: set[str] | None = None,
) -> None:
    ability_keys = {str(key) for key in ability_keys if str(key or "")}
    if not ability_keys:
        return
    special_ability_keys: set[str] = set()
    for row in tables.get("unit_abilities", []):
        ability_key = str(row.get("key") or "")
        if ability_key not in ability_keys:
            continue
        special_key = str(row.get("type") or "")
        if special_key:
            special_ability_keys.add(special_key)
        table_path = row.get("_sourceTablePath") or table_names.get("unit_abilities")
        if table_path:
            _upsert_delta_row_once(rows_by_table, table_path, "key", _clean_source_row(row))
    _copy_special_ability_dependencies(
        tables,
        table_names,
        rows_by_table,
        special_ability_keys,
        seen_special_abilities,
        seen_projectiles,
    )


def _copy_special_ability_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    special_ability_keys: set[str],
    seen_special_abilities: set[str] | None = None,
    seen_projectiles: set[str] | None = None,
) -> None:
    if seen_special_abilities is None:
        seen_special_abilities = set()
    special_ability_keys = {
        str(key)
        for key in special_ability_keys
        if str(key or "") and str(key) not in seen_special_abilities
    }
    if not special_ability_keys:
        return
    seen_special_abilities.update(special_ability_keys)
    projectile_keys: set[str] = set()
    bombardment_keys: set[str] = set()
    phase_keys: set[str] = set()
    for row in tables.get("unit_special_abilities", []):
        special_key = str(row.get("key") or "")
        if special_key not in special_ability_keys:
            continue
        projectile_key = str(row.get("activated_projectile") or "")
        if projectile_key:
            projectile_keys.add(projectile_key)
        bombardment_key = str(row.get("bombardment") or "")
        if bombardment_key:
            bombardment_keys.add(bombardment_key)
        table_path = row.get("_sourceTablePath") or table_names.get("unit_special_abilities")
        if table_path:
            _upsert_delta_row_once(rows_by_table, table_path, "key", _clean_source_row(row))
    for row in tables.get("special_ability_to_special_ability_phase_junctions", []):
        special_key = str(row.get("special_ability") or "")
        if special_key not in special_ability_keys:
            continue
        phase_key = str(row.get("phase") or "")
        if phase_key:
            phase_keys.add(phase_key)
        table_path = row.get("_sourceTablePath") or table_names.get("special_ability_to_special_ability_phase_junctions")
        if table_path:
            _upsert_delta_row_once(rows_by_table, table_path, _special_ability_phase_link_key, _clean_source_row(row))
    if not phase_keys:
        phase_keys.update(special_ability_keys)
    phase_display_keys = {
        str(row.get("phase_display") or row.get("display") or "")
        for row in tables.get("special_ability_phases", [])
        if str(row.get("id") or "") in phase_keys and str(row.get("phase_display") or row.get("display") or "")
    }
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "special_ability_phases",
        lambda row, keys=phase_keys: str(row.get("id") or "") in keys,
        "id",
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "special_ability_phase_stat_effects",
        lambda row, keys=phase_keys: str(row.get("phase") or "") in keys,
        _special_ability_phase_stat_effect_key,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "special_ability_phase_attribute_effects",
        lambda row, keys=phase_keys: str(row.get("phase") or "") in keys,
        _special_ability_phase_attribute_effect_key,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "special_ability_phase_displays",
        lambda row, keys=phase_display_keys: _generic_key_or_id(row) in keys,
        _generic_key_or_id,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "special_ability_to_auto_deactivate_flags",
        lambda row, keys=special_ability_keys: str(row.get("special_ability") or "") in keys,
        _special_ability_auto_deactivate_flag_key,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "special_ability_to_invalid_target_flags",
        lambda row, keys=special_ability_keys: str(row.get("special_ability") or "") in keys,
        _special_ability_invalid_target_flag_key,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "special_ability_to_invalid_usage_flags",
        lambda row, keys=special_ability_keys: str(row.get("special_ability") or "") in keys,
        _special_ability_invalid_usage_flag_key,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "projectile_bombardments",
        lambda row, keys=bombardment_keys: _generic_key_or_id(row) in keys,
        _generic_key_or_id,
    )
    if projectile_keys:
        _copy_projectile_dependencies(
            tables,
            table_names,
            rows_by_table,
            projectile_keys,
            seen_special_abilities,
            seen_projectiles,
        )


def _copy_projectile_dependencies(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    projectile_keys: set[str],
    seen_special_abilities: set[str] | None = None,
    seen_projectiles: set[str] | None = None,
) -> None:
    if seen_projectiles is None:
        seen_projectiles = set()
    projectile_keys = {
        str(key)
        for key in projectile_keys
        if str(key or "") and str(key) not in seen_projectiles
    }
    if not projectile_keys:
        return
    seen_projectiles.update(projectile_keys)

    contact_effect_keys: set[str] = set()
    display_keys: set[str] = set()
    impact_keys: set[str] = set()
    for row in tables.get("projectiles", []):
        projectile_key = str(row.get("key") or "")
        if projectile_key not in projectile_keys:
            continue
        for field in ("contact_stat_effect", "contact_phase"):
            contact_key = str(row.get(field) or "")
            if contact_key:
                contact_effect_keys.add(contact_key)
        for field in ("projectile_display", "projectile_audio"):
            display_key = str(row.get(field) or "")
            if display_key:
                display_keys.add(display_key)
        for field in ("projectile_impact", "impact", "detonation_impact", "collision_impact"):
            impact_key = str(row.get(field) or "")
            if impact_key:
                impact_keys.add(impact_key)
        table_path = row.get("_sourceTablePath") or table_names.get("projectiles")
        if table_path:
            _upsert_delta_row_once(rows_by_table, table_path, "key", _clean_source_row(row))

    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "projectile_displays",
        lambda row, keys=display_keys: _generic_key_or_id(row) in keys,
        _generic_key_or_id,
    )
    _copy_matching_rows_once(
        tables,
        table_names,
        rows_by_table,
        "projectile_impacts",
        lambda row, keys=impact_keys: _generic_key_or_id(row) in keys,
        _generic_key_or_id,
    )
    if contact_effect_keys:
        _copy_unit_ability_dependencies(
            tables,
            table_names,
            rows_by_table,
            contact_effect_keys,
            seen_special_abilities,
            seen_projectiles,
        )
        _copy_special_ability_dependencies(
            tables,
            table_names,
            rows_by_table,
            contact_effect_keys,
            seen_special_abilities,
            seen_projectiles,
        )


def _copy_matching_rows(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    alias: str,
    predicate: Any,
    key_field: str | Any,
) -> None:
    if alias not in tables:
        return
    for row in tables[alias]:
        if predicate(row):
            table_path = row.get("_sourceTablePath") or table_names.get(alias)
            if not table_path:
                continue
            clean_row = _clean_source_row(row)
            _upsert_delta_row(rows_by_table, table_path, key_field, clean_row)


def _copy_matching_rows_once(
    tables: dict[str, list[dict[str, Any]]],
    table_names: dict[str, str],
    rows_by_table: dict[str, list[dict[str, Any]]],
    alias: str,
    predicate: Any,
    key_field: str | Any,
) -> None:
    if alias not in tables:
        return
    for row in tables[alias]:
        if not predicate(row):
            continue
        table_path = row.get("_sourceTablePath") or table_names.get(alias)
        if not table_path:
            continue
        _upsert_delta_row_once(rows_by_table, table_path, key_field, _clean_source_row(row))


def _optional_table_names(session: RpfmPackSession, aliases: dict[str, list[str]]) -> dict[str, str]:
    table_list = session.list_tables()
    tables = set(table_list)
    resolved: dict[str, str] = {}
    for alias, candidates in aliases.items():
        for candidate in candidates:
            if candidate in tables:
                resolved[alias] = candidate
                break
        if alias in resolved:
            continue
        folder = f"{alias}_tables"
        matches = [path for path in table_list if f"/{folder}/" in path]
        if len(matches) == 1:
            resolved[alias] = matches[0]
    return resolved


def _merge_reference_dependency_tables(
    session: RpfmPackSession,
    aliases: dict[str, list[str]],
    reference_paths: list[Path],
    table_names: dict[str, str],
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
    opened_pack_keys: dict[str, str],
) -> None:
    for reference_path in reference_paths:
        resolved = reference_path.expanduser()
        if not resolved.exists():
            continue
        try:
            reference_key = _open_pack_reusing_existing(session, resolved, opened_pack_keys)
            reference_tables = _reference_table_paths(
                session,
                reference_key,
            )
            _merge_dependency_tables_from_pack(session, reference_key, reference_tables, aliases, tables, source_dbs)
            for alias, table_path in _optional_table_names_from_list(reference_tables, aliases).items():
                table_names.setdefault(alias, table_path)
        except Exception:
            continue


def _reference_table_paths(
    session: RpfmPackSession,
    pack_key: str,
) -> list[str]:
    """Return a reference pack's DB tree without repeating RPFM round trips.

    A multi-character recipe visits the same reference packs from several
    dependency collectors for every work item.  The pack tree cannot change
    during a build, so fetching it once per open pack is sufficient.
    """
    cache = getattr(session, "_delta_reference_table_paths", None)
    if cache is None:
        cache = {}
        setattr(session, "_delta_reference_table_paths", cache)
    cached = cache.get(pack_key)
    if cached is not None:
        return list(cached)

    tree = session.client.send({"GetPackFileDataForTreeView": pack_key})
    _raise_rpfm_error(tree)
    file_infos = tree["data"]["ContainerInfoVecRFileInfo"][1]
    reference_tables = tuple(sorted(
        info["path"]
        for info in file_infos
        if info.get("path", "").startswith(("db/", "ceo_db/"))
    ))
    cache[pack_key] = reference_tables
    return list(reference_tables)


def _merge_vanilla_dependency_tables(
    session: RpfmPackSession,
    aliases: dict[str, list[str]],
    table_names: dict[str, str],
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
) -> None:
    try:
        vanilla_tables = session.list_tables("vanilla")
        vanilla_key = session._pack_key_for_source("vanilla")
    except Exception:
        return
    _merge_dependency_tables_from_pack(session, vanilla_key, vanilla_tables, aliases, tables, source_dbs)
    for alias, table_path in _optional_table_names_from_list(vanilla_tables, aliases).items():
        table_names.setdefault(alias, table_path)


def _merge_dependency_tables_from_pack(
    session: RpfmPackSession,
    pack_key: str,
    table_list: list[str],
    aliases: dict[str, list[str]],
    tables: dict[str, list[dict[str, Any]]],
    source_dbs: dict[str, dict[str, Any]],
) -> None:
    is_internal_materials = False
    metadata = getattr(session, "metadata", None)
    if callable(metadata):
        try:
            is_internal_materials = metadata().get("adapter") == "internal-materials"
        except Exception:
            is_internal_materials = False
    if (is_internal_materials or not hasattr(session, "client")) and pack_key == getattr(session, "pack_key", None):
        for alias in aliases:
            for table_path in _matching_table_paths(table_list, alias, aliases[alias]):
                try:
                    rows = _read_rows(session, table_path, source_dbs)
                except Exception:
                    continue
                _append_dependency_rows(tables.setdefault(alias, []), rows, _dependency_key_for_alias(alias))
        return
    for alias in aliases:
        for table_path in _matching_table_paths(table_list, alias, aliases[alias]):
            try:
                rows = _read_rows_from_pack_key(session, pack_key, table_path, source_dbs)
            except Exception:
                continue
            _append_dependency_rows(tables.setdefault(alias, []), rows, _dependency_key_for_alias(alias))


def _matching_table_paths(table_list: list[str], alias: str, candidates: list[str]) -> list[str]:
    matches = []
    tables = set(table_list)
    for candidate in candidates:
        if candidate in tables:
            matches.append(candidate)
    folder = (
        "/ceos_to_equipment_variants_tables/"
        if alias in {"equipment_variants_weapons", "equipment_variants_armours"}
        else f"/{alias}_tables/"
    )
    matches.extend(path for path in table_list if folder in path and path not in matches)
    return sorted(matches)


def _open_pack_reusing_existing(
    session: RpfmPackSession,
    path: Path,
    opened_pack_keys: dict[str, str],
) -> str:
    resolved = path.resolve()
    for key in (str(path), str(resolved)):
        if key in opened_pack_keys:
            return opened_pack_keys[key]

    existing_key = _open_pack_key_for_path(session, resolved)
    if existing_key:
        opened_pack_keys[str(path)] = existing_key
        opened_pack_keys[str(resolved)] = existing_key
        return existing_key

    opened = session.client.send({"OpenPackFiles": [str(resolved)]})
    try:
        _raise_rpfm_error(opened)
    except ValueError:
        existing_key = _open_pack_key_for_path(session, resolved)
        if existing_key:
            opened_pack_keys[str(path)] = existing_key
            opened_pack_keys[str(resolved)] = existing_key
            return existing_key
        raise
    pack_key = opened["data"]["StringContainerInfo"][0]
    opened_pack_keys[str(path)] = pack_key
    opened_pack_keys[str(resolved)] = pack_key
    return pack_key


def _open_pack_key_for_path(session: RpfmPackSession, path: Path) -> str | None:
    response = session.client.send("ListOpenPacks")
    _raise_rpfm_error(response)
    for item in response.get("data", {}).get("VecStringContainerInfo", []):
        if not isinstance(item, list) or len(item) < 2:
            continue
        pack_key, info = item[0], item[1]
        file_path = str((info or {}).get("file_path") or "")
        if not file_path:
            continue
        try:
            if Path(file_path).resolve() == path.resolve():
                return str(pack_key)
        except OSError:
            if file_path.replace("\\", "/").lower() == str(path).replace("\\", "/").lower():
                return str(pack_key)
    return None


def _optional_table_names_from_list(table_list: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    tables = set(table_list)
    resolved: dict[str, str] = {}
    for alias, candidates in aliases.items():
        for candidate in candidates:
            if candidate in tables:
                resolved[alias] = candidate
                break
        if alias in resolved:
            continue
        folder = f"{alias}_tables"
        matches = [path for path in table_list if f"/{folder}/" in path]
        if len(matches) == 1:
            resolved[alias] = matches[0]
    return resolved


def _read_rows_from_pack_key(
    session: RpfmPackSession,
    pack_key: str,
    table_name: str,
    source_dbs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    cache = getattr(session, "_delta_decoded_rows_by_source", None)
    if cache is None:
        cache = {}
        setattr(session, "_delta_decoded_rows_by_source", cache)
    cache_key = (str(pack_key), table_name.replace("\\", "/"))
    cached_rows = cache.get(cache_key)
    if cached_rows is not None:
        # Callers may edit selected source rows before writing a delta table.
        # A shallow row copy is enough because decoded DB cells are scalars.
        return [dict(row) for row in cached_rows]

    response = session.client.send({"DecodePackedFile": [pack_key, table_name, "PackFile"]})
    _raise_rpfm_error(response)
    data = response.get("data", {})
    if "DBRFileInfo" not in data:
        cache[cache_key] = ()
        return []
    source_dbs.setdefault(table_name, copy.deepcopy(data["DBRFileInfo"][0]))
    table = data["DBRFileInfo"][0]["table"]
    fields = _rpfm_field_names(table)
    rows = [
        {
            field_name: _decode_rpfm_cell(value)
            for field_name, value in zip(fields, row, strict=False)
        }
        for row in table["table_data"]
    ]
    for row in rows:
        row["_sourceTablePath"] = table_name
    cache[cache_key] = tuple(dict(row) for row in rows)
    return rows


def _append_dependency_rows(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    key_field: str | Any,
) -> None:
    existing = {
        key_field(row) if callable(key_field) else row.get(key_field)
        for row in target
    }
    for row in source:
        key = key_field(row) if callable(key_field) else row.get(key_field)
        if key in existing:
            continue
        target.append(row)
        existing.add(key)


def _dependency_key_for_alias(alias: str) -> str | Any:
    if alias in {"equipment_variants_weapons", "equipment_variants_armours"}:
        return _equipment_variant_key
    if alias == "character_generation_template_game_mode_details":
        return _detail_key
    if alias == "campaign_character_art_sets":
        return "art_set_id"
    if alias == "campaign_character_arts":
        return _art_key
    if alias == "agent_uniforms":
        return "uniform_name"
    if alias == "variants":
        return "variant_name"
    if alias == "character_attributes":
        return _attribute_key
    if alias == "character_attribute_sets":
        return _attribute_set_key
    if alias == "character_skill_node_links":
        return _skill_link_key
    if alias == "character_skill_level_to_effects_junctions":
        return _skill_effect_key
    if alias == "effect_bonus_value_ids_unit_sets":
        return _effect_bonus_value_unit_set_key
    if alias == "effect_bonus_value_unit_ability_junctions":
        return _effect_bonus_value_unit_ability_key
    if alias == "frontend_character_ceos":
        return _frontend_character_ceo_key
    if alias == "retinue_slot_initial_units":
        return _retinue_slot_key
    if alias == "cai_retinues_to_aspects":
        return _retinue_aspect_key
    if alias == "cai_agent_subtypes_to_aspects":
        return lambda row: (row.get("agent_subtype"), row.get("aspect"))
    if alias == "agent_subtype_weighted_selection_set_to_weights":
        return lambda row: (row.get("subtype_set"), row.get("agent_subtype"), row.get("is_male"))
    if alias == "campaign_group_member_criteria_agent_subtypes":
        return lambda row: (row.get("member"), row.get("value"))
    if alias == "faction_agent_permitted_subtypes":
        return lambda row: (row.get("agent"), row.get("faction"), row.get("subtype"))
    if alias == "ministerial_postion_valid_agent_subtypes":
        return lambda row: (row.get("agent_subtype"), row.get("ministerial_position_cultural_variant"))
    if alias == "effect_bonus_value_agent_subtype_loyalty_factor_junctions":
        return lambda row: (
            row.get("agent_subtype_loyalty_factor_junction"),
            row.get("effect"),
            row.get("bonus_value_id"),
        )
    if alias == "effect_bonus_value_agent_subtype_junctions":
        return lambda row: (row.get("agent_subtype"), row.get("effect"), row.get("bonus_value_id"))
    if alias == "agent_subtype_subculture_overrides":
        return lambda row: (row.get("agent_subtype"), row.get("subculture"))
    if alias == "agent_subtype_civil_war_faction_overrides":
        return lambda row: (row.get("agent_subtype"), row.get("faction"))
    if alias == "land_units_to_unit_abilites_junctions":
        return _land_unit_ability_key
    if alias == "special_ability_to_special_ability_phase_junctions":
        return _special_ability_phase_link_key
    if alias == "special_ability_phase_stat_effects":
        return _special_ability_phase_stat_effect_key
    if alias == "special_ability_phase_attribute_effects":
        return _special_ability_phase_attribute_effect_key
    if alias == "special_ability_phase_displays":
        return _generic_key_or_id
    if alias == "special_ability_to_auto_deactivate_flags":
        return _special_ability_auto_deactivate_flag_key
    if alias == "special_ability_to_invalid_target_flags":
        return _special_ability_invalid_target_flag_key
    if alias == "special_ability_to_invalid_usage_flags":
        return _special_ability_invalid_usage_flag_key
    if alias in {"projectile_bombardments", "projectile_displays", "projectile_impacts"}:
        return _generic_key_or_id
    if alias == "main_units":
        return _main_unit_key
    if alias == "effects":
        return _effect_key
    if alias == "special_ability_phases":
        return "id"
    return "key"


def _equipment_variant_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any, Any, Any]:
    return (
        row.get("ceos_key"),
        row.get("game_mode"),
        row.get("armour"),
        row.get("primary_melee_weapon"),
        row.get("primary_missile_weapon"),
        row.get("mount"),
    )


def _frontend_character_ceo_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("frontend_character"),
        row.get("ceo"),
        row.get("reason"),
        row.get("threshold_points"),
    )


def _read_rows(
    session: RpfmPackSession,
    table_name: str,
    source_dbs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = session.read_table(table_name)
    path = session._resolve_table_path(table_name)
    source_dbs[path] = copy.deepcopy(session.decoded_db_by_path[path])
    for row in rows:
        row["_sourceTablePath"] = path
    if hasattr(session, "payload") and path.startswith(("db/", "ceo_db/")):
        folder = path.rsplit("/", 1)[0]
        for sibling_path in session.list_tables():
            if sibling_path == path or not sibling_path.startswith(f"{folder}/"):
                continue
            try:
                sibling_rows = session.read_table(sibling_path)
            except Exception:
                continue
            source_dbs[sibling_path] = copy.deepcopy(session.decoded_db_by_path[sibling_path])
            for row in sibling_rows:
                row["_sourceTablePath"] = sibling_path
            rows.extend(sibling_rows)
    return rows


def _source_table_path_for_rows(rows: list[dict[str, Any]], table_name: str) -> str:
    for row in rows:
        path = row.get("_sourceTablePath")
        if path:
            return str(path)
    raise ValueError(f"RPFM table not found in pack: {table_name}")


def _db_with_rows(source_db: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    db = copy.deepcopy(source_db)
    table = db["table"]
    fields = _rpfm_field_names(table)
    if not table["table_data"]:
        table["table_data"] = []
        return db
    template_row = table["table_data"][0]
    table["table_data"] = [
        [
            _encode_rpfm_cell(template_cell, row.get(field_name))
            for field_name, template_cell in zip(fields, template_row, strict=True)
        ]
        for row in rows
    ]
    return db


def _decoded_rows_from_db(source_db: dict[str, Any]) -> list[dict[str, Any]]:
    table = source_db["table"]
    fields = _rpfm_field_names(table)
    return [
        {
            field_name: _decode_rpfm_cell(value)
            for field_name, value in zip(fields, row, strict=False)
        }
        for row in table.get("table_data", [])
    ]


def _merge_source_table_rows(path: str, source_db: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [_clean_source_row(row) for row in _decoded_rows_from_db(source_db)]
    key_field = _table_key_for_path(path, source_db)
    if not key_field:
        return [*merged, *[_clean_source_row(row) for row in rows]]
    for row in rows:
        _upsert_plain_row(merged, key_field, _clean_source_row(row))
    return merged


def _upsert_plain_row(rows: list[dict[str, Any]], key_field: str | Any, row: dict[str, Any]) -> None:
    row_key = key_field(row) if callable(key_field) else row.get(key_field)
    for index, existing in enumerate(rows):
        existing_key = key_field(existing) if callable(key_field) else existing.get(key_field)
        if existing_key == row_key:
            rows[index] = row
            return
    rows.append(row)


def _table_key_for_path(path: str, source_db: dict[str, Any]) -> str | Any | None:
    normalized = path.replace("\\", "/")
    folder = normalized.rsplit("/", 1)[0] if "/" in normalized else normalized
    alias_by_folder = {
        "campaign_character_arts_tables": "campaign_character_arts",
        "campaign_character_art_sets_tables": "campaign_character_art_sets",
        "agent_uniforms_tables": "agent_uniforms",
        "character_generation_template_game_mode_details_tables": "character_generation_template_game_mode_details",
        "character_generation_templates_tables": "character_generation_templates",
        "character_generation_spawn_age_ranges_tables": "character_generation_spawn_age_ranges",
        "character_attributes_tables": "character_attributes",
        "character_attribute_sets_tables": "character_attribute_sets",
        "character_skill_node_sets_tables": "character_skill_node_sets",
        "character_skill_nodes_tables": "character_skill_nodes",
        "character_skill_level_to_effects_junctions_tables": "character_skill_level_to_effects_junctions",
        "retinues_tables": "retinues",
        "retinue_slot_initial_units_tables": "retinue_slot_initial_units",
        "cai_retinues_to_aspects_tables": "cai_retinues_to_aspects",
        "agent_subtypes_tables": "agent_subtypes",
        "cai_agent_subtypes_to_aspects_tables": "cai_agent_subtypes_to_aspects",
        "agent_subtype_loyalty_factor_junctions_tables": "agent_subtype_loyalty_factor_junctions",
        "effect_bonus_value_agent_subtype_loyalty_factor_junctions_tables": "effect_bonus_value_agent_subtype_loyalty_factor_junctions",
        "agent_subtype_weighted_selection_set_to_weights_tables": "agent_subtype_weighted_selection_set_to_weights",
        "campaign_group_member_criteria_agent_subtypes_tables": "campaign_group_member_criteria_agent_subtypes",
        "faction_agent_permitted_subtypes_tables": "faction_agent_permitted_subtypes",
        "ministerial_postion_valid_agent_subtypes_tables": "ministerial_postion_valid_agent_subtypes",
        "effect_bonus_value_agent_subtype_junctions_tables": "effect_bonus_value_agent_subtype_junctions",
        "agent_subtype_subculture_overrides_tables": "agent_subtype_subculture_overrides",
        "agent_subtype_civil_war_faction_overrides_tables": "agent_subtype_civil_war_faction_overrides",
        "land_units_tables": "land_units",
        "land_units_to_unit_abilites_junctions_tables": "land_units_to_unit_abilites_junctions",
        "unit_abilities_tables": "unit_abilities",
        "unit_special_abilities_tables": "unit_special_abilities",
        "special_ability_to_special_ability_phase_junctions_tables": "special_ability_to_special_ability_phase_junctions",
        "special_ability_phases_tables": "special_ability_phases",
        "special_ability_phase_stat_effects_tables": "special_ability_phase_stat_effects",
        "special_ability_phase_attribute_effects_tables": "special_ability_phase_attribute_effects",
        "special_ability_to_invalid_usage_flags_tables": "special_ability_to_invalid_usage_flags",
        "projectiles_tables": "projectiles",
        "main_units_tables": "main_units",
        "effects_tables": "effects",
        "frontend_character_ceos_tables": "frontend_character_ceos",
        "ceos_to_equipment_variants_tables": "equipment_variants_armours",
        "unit_armour_types_tables": "unit_armour_types",
    }
    for marker, alias in alias_by_folder.items():
        if marker in folder:
            return _dependency_key_for_alias(alias)
    fields = _rpfm_field_names(source_db["table"])
    if "key" in fields:
        return "key"
    if "id" in fields:
        return "id"
    return None


def _dedicated_armour_pool_for_clones(
    clones: list[CharacterClone],
    active_pack_paths: list[Path],
) -> DedicatedArmourPool | None:
    assignments = [
        clone.dedicated_armour
        for clone in clones
        if clone.dedicated_armour is not None
    ]
    if not assignments:
        return None
    pool_ids = {assignment.pool_id for assignment in assignments}
    if len(pool_ids) != 1:
        raise DedicatedArmourPoolError(
            "서로 다른 전용 갑옷 CEO 풀을 한 팩에 섞을 수 없습니다."
        )
    pools = load_dedicated_armour_pools(DEDICATED_ARMOUR_POOL_ROOTS)
    pool_id = next(iter(pool_ids))
    pool = next((item for item in pools if item.pool_id == pool_id), None)
    if pool is None:
        raise DedicatedArmourPoolError(
            f"전용 갑옷 CEO 풀을 찾지 못했습니다: {pool_id}"
        )
    status = resolve_pool_status([pool], active_pack_paths)
    if not status.available:
        raise DedicatedArmourPoolError(status.reason)
    validate_pool_assignments(pool, assignments)
    verify_pool_asset(pool)
    return pool


def _materialize_dedicated_armour_ccd(
    pool: DedicatedArmourPool | None,
    clones: list[CharacterClone],
    active_pack_paths: list[Path],
) -> Path | None:
    if pool is None:
        return None
    if pool.mode != "precompiled":
        raise DedicatedArmourPoolError(
            "런타임 동적 CCD 복제는 비활성화되었습니다. "
            "Assembly Kit로 미리 컴파일한 전용 갑옷 풀만 사용할 수 있습니다."
        )
    if pool.ccd_path is None:
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀 CCD 파일이 없습니다: {pool.pool_id}"
        )
    assignments = [
        clone.dedicated_armour
        for clone in clones
        if clone.dedicated_armour is not None
    ]
    if not assignments:
        return pool.ccd_path

    try:
        ccd = CeoCcd.from_path(pool.ccd_path)
        for assignment in assignments:
            rebase_dedicated_armour_ceo_as_regular(
                ccd,
                source_ceo_key=DEDICATED_ARMOUR_REGULAR_CEO_SOURCE,
                destination_ceo_key=assignment.armour_ceo_key,
            )
            rebase_dedicated_armour_initial_ceo(
                ccd,
                source_initial_ceo_key=assignment.source_initial_ceo_key,
                destination_initial_ceo_key=assignment.initial_ceo_key,
                source_armour_ceo_key=assignment.source_ceo_key,
                destination_armour_ceo_key=assignment.armour_ceo_key,
            )
        materialized = ccd.to_bytes()
        reopened = CeoCcd.from_bytes(materialized)
        for assignment in assignments:
            expected = [
                assignment.armour_ceo_key
                if key == assignment.source_ceo_key
                else key
                for key in initial_ceo_active_ceos(
                    reopened,
                    assignment.source_initial_ceo_key,
                )
            ]
            actual = initial_ceo_active_ceos(
                reopened,
                assignment.initial_ceo_key,
            )
            if actual != expected:
                raise DedicatedArmourPoolError(
                    "Dedicated armour initial CEO verification failed after "
                    f"serialization: {assignment.initial_ceo_key}"
                )
    except (OSError, ValueError) as error:
        raise DedicatedArmourPoolError(
            f"Failed to materialize dedicated armour CEO data: {pool.pool_id}"
        ) from error

    seed = "\n".join(
        (
            pool.pool_id,
            *(
                f"{assignment.slot_id}:{assignment.source_initial_ceo_key}:"
                f"{assignment.source_ceo_key}:{assignment.initial_ceo_key}:"
                f"{assignment.armour_ceo_key}"
                for assignment in assignments
            ),
        )
    ).encode("utf-8")
    TEMP_DEDICATED_ARMOUR_CCD_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = (
        TEMP_DEDICATED_ARMOUR_CCD_ROOT
        / f"{hashlib.sha256(seed).hexdigest()[:16]}_ceo_data.ccd"
    )
    output_path.write_bytes(materialized)
    return output_path

def _new_delta_pack(session: RpfmPackSession) -> str:
    response = session.client.send("NewPack")
    _raise_rpfm_error(response)
    target_key = response["data"]["String"]
    _raise_rpfm_error(session.client.send({"SetPackFileType": [target_key, "Mod"]}))
    return target_key


def _write_lua_text_file(session: RpfmPackSession, target_key: str, path: str, contents: str) -> None:
    file_name = path.rsplit("/", 1)[-1]
    normalized_path = _normalize_pack_path(path)
    TEMP_LUA_SCRIPT_ROOT.mkdir(parents=True, exist_ok=True)
    source_path = TEMP_LUA_SCRIPT_ROOT / f"{zlib.crc32(normalized_path.encode('utf-8')) & 0xffffffff:08x}_{file_name}"
    source_path.write_text(contents, encoding="utf-8", newline="\n")
    _raise_rpfm_error(session.client.send({
        "AddPackedFiles": [target_key, [str(source_path)], [{"File": normalized_path}], None]
    }))


def _write_binary_packed_file(
    session: RpfmPackSession,
    target_key: str,
    path: str,
    source_path: Path,
) -> None:
    normalized_path = _normalize_pack_path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Packed file source is missing: {source_path}")
    _raise_rpfm_error(session.client.send({
        "AddPackedFiles": [
            target_key,
            [str(source_path.resolve())],
            [{"File": normalized_path}],
            None,
        ]
    }))


def _write_loc_file(session: RpfmPackSession, target_key: str, path: str, rows: dict[str, str]) -> None:
    file_name = path.rsplit("/", 1)[-1].removesuffix(".loc")
    loc_db = _loc_db_with_rows(session, rows)
    _raise_rpfm_error(session.client.send({
        "NewPackedFile": [target_key, path, {"Loc": file_name}]
    }))
    _raise_rpfm_error(session.client.send({
        "SavePackedFileFromView": [target_key, path, {"Loc": loc_db}]
    }))


def _write_spawn_incident_tables(
    session: RpfmPackSession,
    target_key: str,
    clones: list[CharacterClone],
) -> int:
    spawn_clones = [
        clone
        for clone in clones
        if clone.spawn_event in {"campaign_start", "delayed_join"} and clone.template_overrides.get("subtype")
    ]
    if not spawn_clones:
        return 0

    template_path = (Path.cwd() / LEGACY_TEMPLATE_PACK).resolve()
    if not template_path.exists():
        return 0

    template_key = _open_pack_reusing_existing(session, template_path, {})

    source_paths = {
        "incidents": "db/incidents_tables/event",
        "payloads": "db/cdir_events_incident_payloads_tables/event",
        "options": "db/cdir_events_incident_option_junctions_tables/event",
    }
    source_dbs = {
        name: _decode_db_from_pack(session, template_key, path)
        for name, path in source_paths.items()
    }

    incidents_source = _rows_from_db(source_dbs["incidents"])
    payloads_source = _rows_from_db(source_dbs["payloads"])
    options_source = _rows_from_db(source_dbs["options"])

    located_source = _find_row(payloads_source, "payload_key", "LOCATED") or payloads_source[0]
    grouped_clones: dict[int, list[CharacterClone]] = {}
    for clone in spawn_clones:
        grouped_clones.setdefault(_spawn_turn_for_clone(clone), []).append(clone)

    incident_rows = []
    options = []
    payloads = []
    loc = {}
    for turn, turn_clones in sorted(grouped_clones.items()):
        incident_key = _incident_key_for_spawn_group(turn_clones, SPAWN_INCIDENT_EVENT_CATEGORY, turn)
        source_incident = incidents_source[0]
        incident_rows.append({
            **source_incident,
            "key": incident_key,
            "generate": True,
            "ui_image": source_incident.get("ui_image") or "3k_event_giving_jobs",
            "prioritised": True,
            "event_category": SPAWN_INCIDENT_EVENT_CATEGORY,
        })

        base_id = 1_820_000_000 + (zlib.crc32(incident_key.encode("utf-8")) % 100_000)
        options.extend(_spawn_incident_option_rows(options_source, incident_key, base_id, turn))
        payloads.append({
            **located_source,
            "id": base_id + 100,
            "incident_key": incident_key,
            "payload_key": "LOCATED",
            "value": "FACTION",
            "target_key": "default",
        })
        names = ", ".join(str(clone.display_name or "").strip() or clone.new_template_key for clone in turn_clones)
        loc[f"incidents_localised_title_{incident_key}"] = "신규 장수 합류"
        loc[f"incidents_localised_description_{incident_key}"] = f"{names} 장수가 플레이어 세력에 합류했습니다."

    _write_db_file(session, target_key, source_paths["incidents"], source_dbs["incidents"], incident_rows)
    _write_db_file(session, target_key, source_paths["options"], source_dbs["options"], options)
    _write_db_file(session, target_key, source_paths["payloads"], source_dbs["payloads"], payloads)
    _write_loc_file(
        session,
        target_key,
        "text/db/hby_mtu_pack_editor_event.loc",
        loc,
    )
    return 3


def _spawn_incident_option_rows(
    options_source: list[dict[str, Any]],
    incident_key: str,
    base_id: int,
    turn: int,
) -> list[dict[str, Any]]:
    source_by_key = {
        str(row.get("option_key") or ""): row
        for row in options_source
    }
    fallback = options_source[0] if options_source else {}
    specs = [
        ("CND_FIRST_ROUND", str(turn)),
        ("GEN_CND_SELF", ""),
        ("GEN_TARGET_FACTION", ""),
        ("CND_UNIQUE", ""),
        ("VAR_CHANCE", "50000"),
        ("CND_LAST_ROUND", "100"),
    ]
    rows = []
    for index, (option_key, value) in enumerate(specs):
        source_row = source_by_key.get(option_key, fallback)
        rows.append({
            **source_row,
            "id": base_id + index,
            "incident_key": incident_key,
            "option_key": option_key,
            "value": value,
            "target": "default",
        })
    return rows


def _decode_db_from_pack(session: RpfmPackSession, pack_key: str, path: str) -> dict[str, Any]:
    response = session.client.send({"DecodePackedFile": [pack_key, path, "PackFile"]})
    _raise_rpfm_error(response)
    data = response.get("data", {})
    if "DBRFileInfo" not in data:
        raise ValueError(f"RPFM did not decode '{path}' as a DB table.")
    return copy.deepcopy(data["DBRFileInfo"][0])


def _rows_from_db(db: dict[str, Any]) -> list[dict[str, Any]]:
    table = db["table"]
    fields = _rpfm_field_names(table)
    return [
        {
            field_name: _decode_rpfm_cell(value)
            for field_name, value in zip(fields, row, strict=False)
        }
        for row in table["table_data"]
    ]


def _write_db_file(
    session: RpfmPackSession,
    target_key: str,
    path: str,
    source_db: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    output_path = _delta_table_path(path)
    normalized_path = path.replace("\\", "/")
    write_rows = (
        _merge_source_table_rows(normalized_path, source_db, rows)
        if output_path == normalized_path
        else rows
    )
    delta_db = _db_with_rows(source_db, write_rows)
    table = delta_db["table"]
    _raise_rpfm_error(session.client.send({
        "NewPackedFile": [
            target_key,
            output_path,
            {"DB": [output_path, _schema_table_name_for_db_path(output_path, table), table["definition"]["version"]]},
        ]
    }))
    _raise_rpfm_error(session.client.send({
        "SavePackedFileFromView": [target_key, output_path, {"DB": delta_db}]
    }))


def _schema_table_name_for_db_path(path: str, table: dict[str, Any]) -> str:
    normalized = _normalize_pack_path(path)
    for part in normalized.split("/"):
        if part.endswith("_tables") and len(part) > len("_tables"):
            return part
    return str(table.get("table_name") or "")


def _delta_table_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "/" not in normalized:
        return f"!!!!!!!!!hby_mtu_pack_editor_{_safe_table_leaf(normalized)}"
    folder, leaf = normalized.rsplit("/", 1)
    if leaf.startswith("!!!!!!!!!hby_mtu_pack_editor"):
        return normalized
    return f"{folder}/!!!!!!!!!hby_mtu_pack_editor_{_safe_table_leaf(leaf)}"


def _safe_table_leaf(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in {"_", "-"}:
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "data"


def _incident_key_for_clones(clones: list[CharacterClone]) -> str:
    seed = "|".join(clone.new_template_key for clone in clones)
    return f"hby_mtu_pack_editor_spawn_{zlib.crc32(seed.encode('utf-8')):08x}"


def _incident_key_for_clone(clone: CharacterClone) -> str:
    seed = f"{clone.new_template_key}:{clone.spawn_event or ''}"
    return f"hby_mtu_pack_editor_spawn_{zlib.crc32(seed.encode('utf-8')):08x}"


def _incident_key_for_clone_category(clone: CharacterClone, category: str) -> str:
    return f"{_incident_key_for_clone(clone)}_{category}"


def _spawn_turn_for_clone(clone: CharacterClone) -> int:
    if clone.spawn_event != "delayed_join":
        return 0
    try:
        return max(0, int(float(clone.template_overrides.get("min_spawn_round") or 0)))
    except (TypeError, ValueError):
        return 0


def _incident_key_for_spawn_group(clones: list[CharacterClone], game_mode: str, turn: int) -> str:
    seed = "|".join(sorted(clone.new_template_key for clone in clones))
    seed = f"{seed}:{game_mode}:{turn}"
    return f"hby_mtu_pack_editor_spawn_{zlib.crc32(seed.encode('utf-8')):08x}_{game_mode}"


def _loc_db_with_rows(session: RpfmPackSession, rows: dict[str, str]) -> dict[str, Any]:
    loc_files = session.list_loc_files()
    if not loc_files:
        raise ValueError("Source pack has no loc file to use as a loc table template.")
    source: dict[str, Any] | None = None
    for loc_file in loc_files:
        response = session.client.send({"DecodePackedFile": [session.pack_key, loc_file, "PackFile"]})
        _raise_rpfm_error(response)
        candidate = copy.deepcopy(response["data"]["LocRFileInfo"][0])
        if candidate.get("table", {}).get("table_data"):
            source = candidate
            break
        if source is None:
            source = candidate
    if source is None:
        raise ValueError("Source pack has no loc file to use as a loc table template.")
    table = source["table"]
    fields = _rpfm_field_names(table)
    template_row = table["table_data"][0] if table["table_data"] else [
        _default_loc_template_cell(field_name)
        for field_name in fields
    ]
    table["table_data"] = [
        [
            _encode_rpfm_cell(template_cell, {"key": key, "text": text, "tooltip": True}.get(field_name))
            for field_name, template_cell in zip(fields, template_row, strict=True)
        ]
        for key, text in sorted(rows.items())
    ]
    return source


def _default_loc_template_cell(field_name: str) -> dict[str, Any]:
    if field_name == "tooltip":
        return {"Boolean": False}
    return {"StringU8": ""}


def _copy_image_assets(
    session: RpfmPackSession,
    target_key: str,
    items: list[Any],
    opened_sources: dict[str, str] | None = None,
) -> int:
    assets_by_source: dict[str, set[str]] = {}
    retargeted_assets: list[tuple[str, str, str]] = []
    for item in items:
        for asset in item.image_assets or []:
            packed_path = _normalize_pack_path(asset.get("path", ""))
            if not packed_path:
                continue
            if _is_duplicate_character_folder_path(packed_path):
                continue
            target_path = _normalize_pack_path(asset.get("targetPath", ""))
            if target_path and _is_duplicate_character_folder_path(target_path):
                continue
            source_path = str(asset.get("sourcePath") or session.pack_path)
            if target_path and target_path != packed_path:
                retargeted_assets.append((source_path, packed_path, target_path))
                continue
            assets_by_source.setdefault(source_path, set()).add(packed_path)

    copied = _copy_retargeted_image_assets(session, target_key, retargeted_assets)
    opened_sources = dict(opened_sources or {})
    opened_sources.setdefault(str(session.pack_path), session.pack_key)
    opened_sources.setdefault(str(session.pack_path.resolve()), session.pack_key)
    for source_path, packed_paths in assets_by_source.items():
        source_key = opened_sources.get(source_path)
        if source_key is None:
            resolved = str(Path(source_path).resolve())
            source_key = opened_sources.get(resolved)
        if source_key is None:
            resolved_path = Path(source_path).resolve()
            if resolved_path.is_file():
                source_key = _open_pack_reusing_existing(session, resolved_path, opened_sources)
                opened_sources[source_path] = source_key
                opened_sources[str(resolved_path)] = source_key
            else:
                copied += _copy_extracted_image_assets(session, target_key, sorted(packed_paths))
                continue

        paths = [{"File": path} for path in sorted(packed_paths)]
        if not paths:
            continue
        response = session.client.send({
            "AddPackedFilesFromPackFile": [target_key, source_key, paths]
        })
        try:
            _raise_rpfm_error(response)
        except Exception:
            copied += _copy_extracted_image_assets(session, target_key, sorted(packed_paths))
            continue
        copied += len(paths)
    return copied


def _copy_equipment_ceo_raw_assets(
    session: RpfmPackSession,
    target_key: str,
    items: list[Any],
    reference_paths: list[Path] | None = None,
    opened_sources: dict[str, str] | None = None,
) -> int:
    equipment_ceo_keys = _equipment_ceo_keys_for_raw_assets(items)
    if not equipment_ceo_keys or not hasattr(session, "client"):
        return 0

    opened_sources = dict(opened_sources or {})
    opened_sources.setdefault(str(session.pack_path), session.pack_key)
    opened_sources.setdefault(str(session.pack_path.resolve()), session.pack_key)

    copied = 0
    copied_paths: set[str] = set()
    source_paths = [Path(session.pack_path), *(reference_paths or [])]
    for source_path in source_paths:
        paths = _equipment_raw_asset_paths_from_source(source_path, equipment_ceo_keys)
        paths = [path for path in paths if path not in copied_paths]
        if not paths:
            continue
        source_key = _open_pack_reusing_existing(session, source_path, opened_sources)
        response = session.client.send({
            "AddPackedFilesFromPackFile": [
                target_key,
                source_key,
                [{"File": path} for path in paths],
            ]
        })
        _raise_rpfm_error(response)
        copied += len(paths)
        copied_paths.update(paths)
    return copied


def _equipment_ceo_keys_for_raw_assets(items: list[Any]) -> list[str]:
    keys: list[str] = []
    for item in items:
        for attr in ("equipment_ceo_keys", "default_equipment_ceo_keys"):
            for value in getattr(item, attr, ()) or ():
                text = str(value or "").strip()
                if text:
                    keys.append(text)
    return _unique_strings(keys)


def _equipment_raw_asset_paths_from_source(source_path: Path, equipment_ceo_keys: list[str]) -> list[str]:
    try:
        index = read_pfh_index(source_path.resolve())
    except Exception:
        return []
    files = {_normalize_pack_path(entry.path) for entry in index.entries}
    paths: set[str] = set()
    paths.update(_equipment_ancillary_icon_paths(files, equipment_ceo_keys))
    return sorted(paths)


def _equipment_ancillary_icon_paths(files: set[str], equipment_ceo_keys: list[str]) -> list[str]:
    needles = _equipment_icon_needles(equipment_ceo_keys)
    if not needles:
        return []
    matches = []
    for path in files:
        lower = path.lower()
        if not lower.startswith("ui/ancillaries/"):
            continue
        if not lower.endswith((".png", ".dds")):
            continue
        file_name = lower.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if any(needle and needle in file_name for needle in needles):
            matches.append(path)
    return sorted(matches)


def _equipment_icon_needles(equipment_ceo_keys: list[str]) -> list[str]:
    needles: set[str] = set()
    for key in equipment_ceo_keys:
        normalized = str(key or "").strip().lower()
        if not normalized:
            continue
        needles.add(normalized)
        for marker in ("_ancillary_armour_", "_ancilliary_armour_", "_ancillary_weapon_", "_ancilliary_weapon_"):
            if marker not in normalized:
                continue
            prefix, suffix = normalized.split(marker, 1)
            if suffix:
                needles.add(suffix)
                needles.add(f"{prefix}_ancillary_{suffix}")
                needles.add(f"{prefix}_ancilliary_{suffix}")
                if marker.endswith("_weapon_") and "bow" in suffix:
                    needles.add(f"{prefix}_ancillary_bow_{suffix}")
                    needles.add(f"{prefix}_ancilliary_bow_{suffix}")
    return sorted(needles, key=lambda value: (-len(value), value))


MODEL_REFERENCE_RE = re.compile(
    r"(?i)(?:variantmeshes[/\\]_variantmodels|commontextures|shaders)[^<>\s\"']+"
)
TEXT_MODEL_ASSET_SUFFIXES = (
    ".variantmeshdefinition",
    ".wsmodel",
    ".material",
    ".xml",
    ".shader",
)


def _copy_uniform_model_assets(
    session: RpfmPackSession,
    target_key: str,
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path],
    opened_sources: dict[str, str] | None = None,
) -> int:
    uniform_rows = _output_agent_uniform_rows(rows_by_table)
    if not uniform_rows or not hasattr(session, "client"):
        return 0

    opened_sources = dict(opened_sources or {})
    opened_sources.setdefault(str(session.pack_path), session.pack_key)
    opened_sources.setdefault(str(session.pack_path.resolve()), session.pack_key)
    index_cache: dict[str, Any] = {}
    paths_by_source: dict[Path, set[str]] = {}

    for table_path, uniform_row in uniform_rows:
        for source_path in _uniform_model_source_candidates(session, table_path, reference_paths):
            resolved_source = source_path.resolve()
            source_key = str(resolved_source).lower()
            try:
                index = index_cache.get(source_key)
                if index is None:
                    index = read_pfh_index(resolved_source)
                    index_cache[source_key] = index
            except Exception:
                continue
            definition_paths = _find_uniform_definition_paths(index, uniform_row)
            if not definition_paths:
                continue
            model_paths = _model_asset_closure(resolved_source, index, definition_paths)
            if model_paths:
                paths_by_source.setdefault(resolved_source, set()).update(model_paths)
                break

    copied = 0
    for source_path, packed_paths in paths_by_source.items():
        source_key = _open_pack_reusing_existing(session, source_path, opened_sources)
        paths = [{"File": path} for path in sorted(packed_paths)]
        if not paths:
            continue
        response = session.client.send({
            "AddPackedFilesFromPackFile": [target_key, source_key, paths]
        })
        _raise_rpfm_error(response)
        copied += len(paths)
    return copied


def _write_equipment_independent_model_assets(
    session: RpfmPackSession,
    target_key: str,
    rows_by_table: dict[str, list[dict[str, Any]]],
    reference_paths: list[Path],
) -> int:
    requested: dict[str, tuple[str, dict[str, str]]] = {}
    for table_path, uniform_row in _output_agent_uniform_rows(rows_by_table):
        model = _fixed_unique_model_for_uniform_row(uniform_row)
        if not model:
            continue
        requested[model["fixed_definition"]] = (table_path, model)
    if not requested:
        return 0

    source_paths: list[str] = []
    destination_paths: list[dict[str, str]] = []
    for fixed_definition, (table_path, model) in requested.items():
        if fixed_definition == model["source_definition"]:
            # The base-game definition is already a complete full-body VMD
            # with no equipment-injection slot.  The generated variant row can
            # safely reference it in place; duplicating a vanilla asset would
            # make the editor depend on the user's install path.
            continue
        source_definition_path = _normalize_pack_path(
            "variantmeshes/variantmeshdefinitions/"
            f"{model['source_definition']}.variantmeshdefinition"
        )
        target_definition_path = _normalize_pack_path(
            "variantmeshes/variantmeshdefinitions/"
            f"{fixed_definition}.variantmeshdefinition"
        )
        fixed_text: str | None = None
        for source_pack in _uniform_model_source_candidates(
            session,
            table_path,
            reference_paths,
        ):
            try:
                index = read_pfh_index(source_pack)
                entry = next(
                    entry
                    for entry in index.entries
                    if _normalize_pack_path(entry.path).lower() == source_definition_path.lower()
                )
                source_text = read_entry_bytes(source_pack, entry).decode("utf-8")
            except (OSError, StopIteration, UnicodeDecodeError, ValueError):
                continue
            fixed_text = _freeze_variant_mesh_body_slot(source_text)
            break
        if fixed_text is None:
            raise ValueError(
                "Source variant mesh definition not found for equipment-independent model: "
                f"{source_definition_path}"
            )

        TEMP_MODEL_ASSET_ROOT.mkdir(parents=True, exist_ok=True)
        local_path = TEMP_MODEL_ASSET_ROOT / f"{fixed_definition}.variantmeshdefinition"
        local_path.write_text(fixed_text, encoding="utf-8", newline="\n")
        source_paths.append(str(local_path))
        destination_paths.append({"File": target_definition_path})

    if not source_paths:
        return 0

    response = session.client.send({
        "AddPackedFiles": [target_key, source_paths, destination_paths, None]
    })
    _raise_rpfm_error(response)
    data = response.get("data", {})
    added = data.get("VecContainerPathOptionString", [destination_paths, None])[0]
    return len(added)


def _freeze_variant_mesh_body_slot(source_text: str) -> str:
    pattern = re.compile(
        r"(?im)^[ \t]*<SLOT\s+name=[\"']set_body[\"']\s*/>\s*\r?\n?"
    )
    body_slot_count = len(pattern.findall(source_text))
    if body_slot_count > 1:
        raise ValueError(
            "Variant mesh definition contains more than one set_body slot."
        )

    model_count = len(re.findall(
        r"<VARIANT_MESH\b[^>]*\bmodel\s*=",
        source_text,
        re.IGNORECASE,
    ))
    if model_count == 0:
        raise ValueError(
            "Variant mesh definition has no baked model geometry; removing set_body would hide the character."
        )

    # A zero-slot VMD is already equipment-independent and must be copied
    # unchanged.  For a removable injection slot, require either the regular
    # semantic body slot or a complete custom assembly (head plus torso).  The
    # latter covers MTU male definitions such as Zhang Xun without accepting a
    # head-only equipment wrapper.
    if body_slot_count == 0:
        return source_text

    has_semantic_body = bool(re.search(
        r"<SLOT\s+name=[\"']body[\"'][^>]*>\s*<VARIANT_MESH\b[^>]*\bmodel\s*=",
        source_text,
        re.IGNORECASE,
    ))
    has_head = bool(re.search(
        r"<SLOT\s+name=[\"']head[\"'][^>]*>\s*<VARIANT_MESH\b[^>]*\bmodel\s*=",
        source_text,
        re.IGNORECASE,
    ))
    has_torso = bool(re.search(
        r"<SLOT\s+name=[\"'](?:chest_armour|tunic_top|tunic_bottom|collar)[\"'][^>]*>"
        r"\s*<VARIANT_MESH\b[^>]*\bmodel\s*=",
        source_text,
        re.IGNORECASE,
    ))
    if not has_semantic_body and not (has_head and has_torso):
        raise ValueError(
            "Variant mesh definition has no complete baked body model; removing set_body would hide the character."
        )
    fixed_text = pattern.sub("", source_text, count=1)
    return fixed_text


def _fixed_unique_model_for_uniform_row(
    uniform_row: dict[str, Any],
) -> dict[str, str] | None:
    values = {
        str(uniform_row.get(field) or "")
        for field in (
            "uniform_name",
            "filename",
            "battle_filename",
            "campaign_porthole_filename",
        )
    }
    for model in EQUIPMENT_INDEPENDENT_UNIQUE_MODELS.values():
        if model["fixed_uniform"] in values or model["fixed_variant"] in values:
            return dict(model)
    return None


def _output_agent_uniform_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for table_path, table_rows in rows_by_table.items():
        if "/agent_uniforms_tables/" not in _normalize_pack_path(table_path):
            continue
        for row in table_rows:
            uniform_name = str(row.get("uniform_name") or "")
            if not uniform_name or uniform_name in seen:
                continue
            seen.add(uniform_name)
            rows.append((table_path, row))
    return rows


def _uniform_model_source_candidates(
    session: RpfmPackSession,
    table_path: str,
    reference_paths: list[Path],
) -> list[Path]:
    candidates: list[Path] = []
    source_for_table = getattr(session, "material_source_path_for_table", None)
    if callable(source_for_table):
        try:
            raw_source = str(source_for_table(table_path) or "")
        except Exception:
            raw_source = ""
        if raw_source:
            candidates.append(Path(raw_source))
    candidates.append(Path(session.pack_path))
    candidates.extend(reference_paths)

    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if not resolved.is_file() or _is_base_game_asset_pack(resolved):
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return result


def _is_base_game_asset_pack(path: Path) -> bool:
    name = path.name.lower()
    return (
        name == "mtu_reference_core.pack"
        or name == "database.pack"
        or name.startswith("data")
        or name.startswith("local_")
    )


def _find_uniform_definition_paths(index: Any, uniform_row: dict[str, Any]) -> list[str]:
    definition_paths = [
        entry.path
        for entry in index.entries
        if _normalize_pack_path(entry.path).lower().startswith("variantmeshes/variantmeshdefinitions/")
        and entry.path.lower().endswith(".variantmeshdefinition")
    ]
    by_lower = {path.lower(): path for path in definition_paths}
    by_basename = {
        _definition_stem(path): path
        for path in definition_paths
    }
    matches: list[str] = []
    for name in _uniform_model_name_candidates(uniform_row):
        for candidate in _definition_name_candidates(name):
            exact = by_lower.get(f"variantmeshes/variantmeshdefinitions/{candidate}.variantmeshdefinition")
            if exact:
                matches.append(exact)
            basename = by_basename.get(candidate)
            if basename:
                matches.append(basename)
    return _unique_strings(matches)


def _uniform_model_name_candidates(uniform_row: dict[str, Any]) -> list[str]:
    return _unique_strings([
        uniform_row.get("filename"),
        uniform_row.get("battle_filename"),
        uniform_row.get("campaign_porthole_filename"),
        uniform_row.get("campaign_politician_filename"),
        uniform_row.get("uniform_name"),
    ])


def _definition_name_candidates(name: Any) -> list[str]:
    raw = _definition_name_stem(str(name or ""))
    if not raw:
        return []
    candidates = [raw]
    for model in EQUIPMENT_INDEPENDENT_UNIQUE_MODELS.values():
        fixed_names = {
            model["fixed_uniform"].lower(),
            model["fixed_variant"].lower(),
            model["fixed_definition"].lower(),
        }
        if raw in fixed_names:
            candidates.append(model["source_definition"].lower())
    for prefix in (
        "3k_mtu_",
        "3k_main_",
        "3k_dlc04_",
        "3k_dlc05_",
        "3k_dlc06_",
        "3k_dlc07_",
        "3k_ytr_",
        "ep_",
    ):
        if raw.startswith(prefix):
            candidates.append(raw[len(prefix):])
    for candidate in list(candidates):
        if candidate.startswith("sad_"):
            sad_tail = candidate[len("sad_"):]
            candidates.append(sad_tail)
            candidates.append(f"tup_{sad_tail}")
            if sad_tail.startswith("hero_"):
                candidates.append(sad_tail[len("hero_"):])
            if sad_tail.startswith("lady_"):
                candidates.append(sad_tail[len("lady_"):])
    return _unique_strings(candidates)


def _definition_stem(path: str) -> str:
    return _definition_name_stem(Path(_normalize_pack_path(path)).name)


def _definition_name_stem(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
    if name.endswith(".variantmeshdefinition"):
        name = name[: -len(".variantmeshdefinition")]
    return name


def _model_asset_closure(source_path: Path, index: Any, definition_paths: list[str]) -> set[str]:
    entries_by_lower = {entry.path.lower(): entry for entry in index.entries}
    queued = list(definition_paths)
    copied: set[str] = set()
    while queued:
        path = _normalize_pack_path(queued.pop(0))
        key = path.lower()
        if key in copied:
            continue
        entry = entries_by_lower.get(key)
        if entry is None:
            continue
        copied.add(entry.path)
        if not key.endswith(TEXT_MODEL_ASSET_SUFFIXES):
            continue
        try:
            data = read_entry_bytes(source_path, entry)
        except Exception:
            continue
        text = data.decode("utf-8", errors="ignore")
        for referenced_path in _model_references_from_text(text):
            referenced_entry = entries_by_lower.get(referenced_path.lower())
            if referenced_entry is not None and referenced_entry.path.lower() not in copied:
                queued.append(referenced_entry.path)
    return copied


def _model_references_from_text(text: str) -> list[str]:
    refs = []
    for match in MODEL_REFERENCE_RE.finditer(text):
        ref = _normalize_pack_path(match.group(0).strip().rstrip(".,;:)"))
        if ref:
            refs.append(ref)
    return _unique_strings(refs)


def _copy_extracted_image_assets(
    session: RpfmPackSession,
    target_key: str,
    packed_paths: list[str],
) -> int:
    return _copy_extracted_image_asset_pairs(
        session,
        target_key,
        [(packed_path, packed_path) for packed_path in packed_paths],
    )


def _copy_extracted_image_asset_pairs(
    session: RpfmPackSession,
    target_key: str,
    path_pairs: list[tuple[str, str]],
) -> int:
    source_paths: list[str] = []
    dest_paths: list[dict[str, str]] = []
    missing: list[str] = []
    for source_packed_path, target_packed_path in path_pairs:
        source_packed_path = _normalize_pack_path(source_packed_path)
        target_packed_path = _normalize_pack_path(target_packed_path)
        extracted = _find_extracted_asset(source_packed_path)
        if extracted is None:
            missing.append(source_packed_path)
            continue
        source_paths.append(str(_prepare_image_asset_for_pack(session, extracted, target_packed_path)))
        dest_paths.append({"File": target_packed_path})
    if missing:
        raise ValueError(
            "Extracted image asset(s) not found. Refresh/extract reference assets first: "
            + ", ".join(missing[:5])
        )
    if not source_paths:
        return 0
    response = session.client.send({
        "AddPackedFiles": [target_key, source_paths, dest_paths, None]
    })
    _raise_rpfm_error(response)
    data = response.get("data", {})
    added = data.get("VecContainerPathOptionString", [dest_paths, None])[0]
    return len(added)


def _copy_retargeted_image_assets(
    session: RpfmPackSession,
    target_key: str,
    path_triples: list[tuple[str, str, str]],
) -> int:
    source_paths: list[str] = []
    dest_paths: list[dict[str, str]] = []
    missing: list[str] = []
    for source_path, source_packed_path, target_packed_path in path_triples:
        source_packed_path = _normalize_pack_path(source_packed_path)
        target_packed_path = _normalize_pack_path(target_packed_path)
        extracted = _find_extracted_asset(source_packed_path, source_path)
        if extracted is None:
            missing.append(source_packed_path)
            continue
        source_paths.append(str(_prepare_image_asset_for_pack(session, extracted, target_packed_path)))
        dest_paths.append({"File": target_packed_path})
    if missing:
        raise ValueError(
            "Extracted image asset(s) not found. Refresh/extract reference assets first: "
            + ", ".join(missing[:5])
        )
    if not source_paths:
        return 0
    response = session.client.send({
        "AddPackedFiles": [target_key, source_paths, dest_paths, None]
    })
    _raise_rpfm_error(response)
    data = response.get("data", {})
    added = data.get("VecContainerPathOptionString", [dest_paths, None])[0]
    return len(added)


def _copy_available_extracted_image_assets(
    session: RpfmPackSession,
    target_key: str,
    path_pairs: list[tuple[str, str]],
) -> tuple[int, list[str]]:
    source_paths: list[str] = []
    dest_paths: list[dict[str, str]] = []
    missing: list[str] = []
    for source_packed_path, target_packed_path in path_pairs:
        source_packed_path = _normalize_pack_path(source_packed_path)
        target_packed_path = _normalize_pack_path(target_packed_path)
        extracted = _find_extracted_asset(source_packed_path)
        if extracted is None:
            missing.append(source_packed_path)
            continue
        source_paths.append(str(_prepare_image_asset_for_pack(session, extracted, target_packed_path)))
        dest_paths.append({"File": target_packed_path})
    if not source_paths:
        return 0, missing
    response = session.client.send({
        "AddPackedFiles": [target_key, source_paths, dest_paths, None]
    })
    _raise_rpfm_error(response)
    data = response.get("data", {})
    added = data.get("VecContainerPathOptionString", [dest_paths, None])[0]
    return len(added), missing


def _prepare_image_asset_for_pack(
    session: RpfmPackSession,
    extracted: Path,
    target_packed_path: str,
) -> Path:
    return extracted


def _png_text_chunk(data: bytes, key: str) -> str | None:
    if not data.startswith(PNG_SIGNATURE):
        return None
    position = len(PNG_SIGNATURE)
    key_prefix = key.encode("latin1") + b"\x00"
    while position + 12 <= len(data):
        length = int.from_bytes(data[position:position + 4], "big")
        chunk_type = data[position + 4:position + 8]
        payload_start = position + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            return None
        payload = data[payload_start:payload_end]
        if chunk_type == b"tEXt" and payload.startswith(key_prefix):
            return payload[len(key_prefix):].decode("latin1", errors="replace")
        position = payload_end + 4
    return None


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def _find_extracted_asset(packed_path: str, source_path: str | None = None) -> Path | None:
    normalized = _normalize_pack_path(packed_path)
    parts = [part for part in normalized.split("/") if part]
    if not parts or not EXTRACTED_ASSET_ROOT.is_dir():
        return None
    if source_path:
        source_root = Path(source_path)
        if source_root.is_dir():
            for candidate_parts in _image_asset_candidate_parts(parts):
                candidate = source_root.joinpath(*candidate_parts)
                if candidate.is_file():
                    return candidate
    core_candidate = EXTRACTED_ASSET_ROOT / CORE_ASSET_SOURCE_ID
    if core_candidate.is_dir():
        for candidate_parts in _image_asset_candidate_parts(parts):
            candidate = core_candidate.joinpath(*candidate_parts)
            if candidate.is_file():
                return candidate
    for pack_dir in EXTRACTED_ASSET_ROOT.iterdir():
        if pack_dir.name != "hby_generated_character_sets":
            continue
        for candidate_parts in _image_asset_candidate_parts(parts):
            candidate = pack_dir.joinpath(*candidate_parts)
            if candidate.is_file():
                return candidate
    return None


def _image_asset_candidate_parts(parts: list[str]) -> list[list[str]]:
    candidates = [parts]
    lower_parts = [part.lower() for part in parts]
    try:
        characters_index = next(
            i for i, part in enumerate(lower_parts)
            if part == "characters" and i > 0 and lower_parts[i - 1] == "ui"
        )
    except StopIteration:
        return candidates
    panel_index = characters_index + 2
    if (
        panel_index < len(parts)
        and lower_parts[panel_index] in {"large_panel", "small_panel"}
        and "composites" not in lower_parts[characters_index + 2:panel_index + 1]
    ):
        candidates.append(parts[:panel_index] + ["composites"] + parts[panel_index:])
    return candidates


def _normalize_pack_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _is_duplicate_character_folder_path(path: str) -> bool:
    parts = [part for part in _normalize_pack_path(path).split("/") if part]
    try:
        index = next(
            i for i, part in enumerate(parts)
            if part == "characters" and i > 0 and parts[i - 1] == "ui"
        )
    except StopIteration:
        return False
    return (
        len(parts) > index + 2
        and parts[index + 1].lower() == parts[index + 2].lower()
    )


def _validate_clone_image_asset_targets(clones: list[CharacterClone]) -> None:
    warnings = _clone_image_asset_target_warnings(clones)
    if warnings:
        raise ValueError(warnings[0])


def _clone_image_asset_target_warnings(clones: list[CharacterClone]) -> list[str]:
    warnings: list[str] = []
    for clone in clones:
        art_tokens = {
            _art_image_token(value)
            for key, value in (clone.art_overrides or {}).items()
            if key in {"portrait", "card"}
            if isinstance(value, str)
        }
        art_tokens.discard("")
        if not art_tokens:
            continue
        for asset in clone.image_assets or []:
            target_path = _normalize_pack_path(asset.get("targetPath") or asset.get("path") or "")
            token = _image_asset_token(target_path)
            if token and token not in art_tokens:
                warnings.append(
                    f"Image asset target does not match art override token: "
                    f"{target_path} not in {sorted(art_tokens)}"
                )
    return warnings


def _image_asset_path_warnings(items: list[Any]) -> list[str]:
    warnings: list[str] = []
    for item in items:
        owner = getattr(item, "new_template_key", None) or getattr(item, "template_key", None) or ""
        for asset in item.image_assets or []:
            source_path = _normalize_pack_path(asset.get("path") or "")
            target_path = _normalize_pack_path(asset.get("targetPath") or asset.get("path") or "")
            if source_path.startswith(f"{IMAGE_ONLY_ASSET_PREFIX}/"):
                warnings.append(
                    f"Image-only reference path leaked into output source for {owner}: {source_path}"
                )
            if target_path.startswith(f"{IMAGE_ONLY_ASSET_PREFIX}/"):
                warnings.append(
                    f"Image-only reference path leaked into output target for {owner}: {target_path}"
                )
    return warnings


def _character_clone_integrity_warnings(
    clones: list[CharacterClone],
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
) -> list[str]:
    warnings: list[str] = []
    if not clones:
        return warnings
    all_rows = [row for rows in rows_by_table.values() for row in rows]
    templates = {str(row.get("key") or ""): row for row in all_rows if row.get("key")}
    art_sets = {str(row.get("art_set_id") or ""): row for row in all_rows if row.get("art_set_id")}
    ceo_initials = {
        str(row.get("key") or ""): row
        for table_path, rows in rows_by_table.items()
        if "/ceo_initial_datas_tables/" in _normalize_pack_path(table_path)
        for row in rows
        if row.get("key")
    }
    details_by_template: dict[str, list[dict[str, Any]]] = {}
    arts_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in all_rows:
        template_key = str(row.get("character_generation_template") or "")
        if template_key:
            details_by_template.setdefault(template_key, []).append(row)
        art_set = str(row.get("art_set_id") or "")
        if art_set and ("portrait" in row or "card" in row or "uniform" in row):
            arts_by_set.setdefault(art_set, []).append(row)

    for clone in clones:
        template = templates.get(clone.new_template_key)
        clone_subtype = str(
            (template or {}).get("subtype")
            or (clone.template_overrides or {}).get("subtype")
            or ""
        )
        clone_is_male = _coerce_bool(
            (template or {}).get("is_male", (clone.template_overrides or {}).get("is_male"))
        )
        clone_has_custom_art = bool(
            (
                (clone.art_overrides or {}).get("portrait")
                or (clone.art_overrides or {}).get("card")
            )
            and not (clone.art_overrides or {}).get("uniform")
            and (clone.image_assets or [])
        )
        clone_element = _element_from_subtype(clone_subtype)
        if (
            not clone_is_male
            and clone_has_custom_art
            and clone_element in UNSUPPORTED_GENERIC_FEMALE_ELEMENTS
        ):
            warnings.append(
                "Vanilla has no generic female campaign art family for "
                f"{clone_element}: {clone.new_template_key}. "
                "Use earth, metal, or water for equipment-independent female art."
            )
        if not template:
            warnings.append(f"Generated character template row missing: {clone.new_template_key}")
            continue
        forename = str(template.get("forename") or "")
        if clone.display_name and forename and f"names_name_{forename}" not in loc_rows:
            warnings.append(f"Generated character name loc missing: {clone.new_template_key} forename={forename}")
        art_set = str(template.get("art_set_override") or "")
        if art_set.startswith("image_only_"):
            warnings.append(f"Generated character uses image-only art set as DB art set: {clone.new_template_key} art_set={art_set}")
        if art_set and art_set not in art_sets:
            warnings.append(f"Generated character art set row missing: {clone.new_template_key} art_set={art_set}")
        if art_set and not arts_by_set.get(art_set):
            warnings.append(f"Generated character art rows missing: {clone.new_template_key} art_set={art_set}")
        details = details_by_template.get(clone.new_template_key, [])
        if not details:
            warnings.append(f"Generated character game mode detail rows missing: {clone.new_template_key}")
        for detail in details:
            initial_ceo = str(detail.get("initial_ceos") or "")
            if not initial_ceo:
                warnings.append(f"Generated character initial CEO missing: {clone.new_template_key}")
                continue
            ceo_row = ceo_initials.get(initial_ceo)
            if not ceo_row:
                warnings.append(
                    f"Generated character initial CEO row not copied into patch pack: "
                    f"{clone.new_template_key} initial_ceo={initial_ceo}"
                )
    return warnings


def _art_image_token(value: str) -> str:
    clean = _normalize_pack_path(value).strip("/")
    return clean.split("/")[0] if clean else ""


def _image_asset_token(path: str) -> str:
    parts = [part for part in _normalize_pack_path(path).split("/") if part]
    for index, part in enumerate(parts):
        if part == "characters" and index > 0 and parts[index - 1] == "ui" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _write_delta_diagnostics(
    output_path: Path,
    recipe: Recipe,
    rows_by_table: dict[str, list[dict[str, Any]]],
    loc_rows: dict[str, str],
    campaign_script: str | None,
    warnings: list[str] | None = None,
    *,
    ceo_set_entries: list[dict[str, Any]] | None = None,
    equipment_entries: list[dict[str, Any]] | None = None,
) -> None:
    diagnostics_path = output_path.with_suffix(".diagnostics.json")
    diagnostics = {
        "outputPack": str(output_path),
        "warnings": warnings or [],
        "workItems": [
            {
                "kind": work.get("kind"),
                "title": work.get("title"),
                "workNumber": work.get("workNumber"),
                "workSlug": work.get("workSlug"),
            }
            for work in recipe.work_items
        ],
        "tables": rows_by_table,
        "loc": loc_rows,
        "campaignScriptPath": CAMPAIGN_SPAWN_SCRIPT_PATH if campaign_script else "",
        "campaignScriptPaths": list(CAMPAIGN_SPAWN_SCRIPT_PATHS) if campaign_script else [],
        "campaignScript": campaign_script or "",
        "spawnEntries": _spawn_entries_for_clones(recipe.character_clones),
        "ceoSetEntries": (
            ceo_set_entries
            if ceo_set_entries is not None
            else _ceo_set_entries_for_characters(
                recipe.character_clones,
                recipe.character_patches,
            )
        ),
        "equipmentEntries": (
            equipment_entries
            if equipment_entries is not None
            else _equipment_entries_for_characters(
                recipe.character_clones,
                recipe.character_patches,
            )
        ),
        "dedicatedArmourAssignments": [
            {
                "template": clone.new_template_key,
                "poolId": clone.dedicated_armour.pool_id,
                "slotId": clone.dedicated_armour.slot_id,
                "sourceCeoKey": clone.dedicated_armour.source_ceo_key,
                "sourceInitialCeoKey": (
                    clone.dedicated_armour.source_initial_ceo_key
                ),
                "sourceArmourTypeKey": clone.dedicated_armour.source_armour_type_key,
                "sourceArmourValue": clone.dedicated_armour.source_armour_value,
                "armourCeoKey": clone.dedicated_armour.armour_ceo_key,
                "initialCeoKey": clone.dedicated_armour.initial_ceo_key,
                "armourTypeKey": clone.dedicated_armour.armour_type_key,
                "armourValue": clone.dedicated_armour.armour_value,
                "armourBonus": (
                    clone.dedicated_armour.armour_value
                    - clone.dedicated_armour.source_armour_value
                    if clone.dedicated_armour.source_armour_value is not None
                    else None
                ),
                "meleeDefenceBonus": clone.dedicated_armour.melee_defence_bonus,
                "meleeAttackBonus": clone.dedicated_armour.melee_attack_bonus,
                "meleeDamageBonus": clone.dedicated_armour.melee_damage_bonus,
                "apMeleeDamageBonus": clone.dedicated_armour.ap_melee_damage_bonus,
                "chargeBonus": clone.dedicated_armour.charge_bonus,
                "missileDefenceBonus": clone.dedicated_armour.missile_defence_bonus,
            }
            for clone in recipe.character_clones
            if clone.dedicated_armour is not None
        ],
        "imageAssets": [
            {
                "owner": getattr(item, "new_template_key", None) or getattr(item, "template_key", None),
                "path": asset.get("path"),
                "targetPath": asset.get("targetPath") or asset.get("path"),
                "sourcePath": asset.get("sourcePath"),
            }
            for item in [*recipe.character_clones, *recipe.character_patches]
            for asset in (item.image_assets or [])
        ],
    }
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _spawn_entries_for_clones(clones: list[CharacterClone]) -> list[dict[str, Any]]:
    spawn_clones = [
        clone
        for clone in clones
        if clone.spawn_event in {"campaign_start", "delayed_join"}
    ]
    grouped_clones: dict[int, list[CharacterClone]] = {}
    for clone in spawn_clones:
        grouped_clones.setdefault(_spawn_turn_for_clone(clone), []).append(clone)
    entries = []
    for clone in spawn_clones:
        subtype = _spawn_subtype_for_clone(clone)
        if not subtype:
            continue
        min_turn = _spawn_turn_for_clone(clone)
        save_seed = f"{clone.new_template_key}:{clone.spawn_event}:v{SPAWN_SCRIPT_SAVE_VERSION}".encode("utf-8")
        attempt_seed = f"{clone.new_template_key}:{clone.spawn_event}:attempt:v{SPAWN_SCRIPT_SAVE_VERSION}".encode("utf-8")
        incident_keys = [{
            "category": SPAWN_INCIDENT_EVENT_CATEGORY,
            "key": _incident_key_for_spawn_group(grouped_clones[min_turn], SPAWN_INCIDENT_EVENT_CATEGORY, min_turn),
        }]
        entries.append({
            "template": clone.new_template_key,
            "subtype": subtype,
            "event": clone.spawn_event,
            "turn": min_turn,
            "saveKey": f"hby_mtu_pack_editor_player_spawn_v{SPAWN_SCRIPT_SAVE_VERSION}_{zlib.crc32(save_seed) & 0xffffffff:08x}",
            "attemptKey": f"hby_mtu_pack_editor_player_spawn_attempt_v{SPAWN_SCRIPT_SAVE_VERSION}_{zlib.crc32(attempt_seed) & 0xffffffff:08x}",
            "incident": incident_keys[0]["key"],
            "incidents": incident_keys,
            "titleCeo": clone.title_ceo_key,
            "traitSetKey": clone.trait_set_key,
            "traitCeos": list(clone.trait_ceo_keys),
            "equipmentSetKey": clone.equipment_set_key,
            "equipmentCeos": list(clone.equipment_ceo_keys),
        })
    return entries


def _equipment_entries_for_characters(
    clones: list[CharacterClone],
    patches: list[CharacterPatch],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in [*clones, *patches]:
        template_key = getattr(item, "new_template_key", None) or getattr(item, "template_key", "")
        equipment_ceos = _unique_lua_ceo_keys(
            _runtime_armour_ceo_key(value) for value in getattr(item, "equipment_ceo_keys", ())
        )


        # The initial CEO chain remains authoritative. These defaults are only
        # granted to faction inventory as a non-equipping fallback when a
        # character-bound MTU CEO cannot create a second instance for a clone.
        default_equipment_ceos = _unique_lua_ceo_keys(
            _runtime_armour_ceo_key(value) for value in getattr(item, "default_equipment_ceo_keys", ())
        )
        grant_equipment_ceos = _unique_lua_ceo_keys([*equipment_ceos, *default_equipment_ceos])
        if not template_key or not grant_equipment_ceos:
            continue
        remove_ceos: list[str] = []
        equipment_set_key = getattr(item, "equipment_set_key", "") or ""
        save_seed = (
            f"{template_key}:{equipment_set_key}:"
            f"{','.join(equipment_ceos)}:{','.join(default_equipment_ceos)}:"
            f"{','.join(remove_ceos)}:equipment:v{EQUIPMENT_SCRIPT_SAVE_VERSION}"
        ).encode("utf-8")
        grant_seed = (
            f"{template_key}:{equipment_set_key}:"
            f"{','.join(grant_equipment_ceos)}:equipment-grant:v{EQUIPMENT_SCRIPT_SAVE_VERSION}"
        ).encode("utf-8")
        entries.append({
            "template": template_key,
            "saveKey": f"hby_mtu_pack_editor_equipment_v{EQUIPMENT_SCRIPT_SAVE_VERSION}_{zlib.crc32(save_seed) & 0xffffffff:08x}",
            "grantKey": f"hby_mtu_pack_editor_equipment_grant_v{EQUIPMENT_SCRIPT_SAVE_VERSION}_{zlib.crc32(grant_seed) & 0xffffffff:08x}",
            "equipmentSetKey": equipment_set_key,
            "equipmentCeos": equipment_ceos,
            "defaultEquipmentCeos": default_equipment_ceos,
            "grantEquipmentCeos": grant_equipment_ceos,
            "cleanupEquipmentCeos": [
                "3k_mtu_ancillary_lady_ma_yunlus_armour_unique"
            ] if "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique" in grant_equipment_ceos else [],
            "removeCeos": remove_ceos,
            "existingOnly": False,
            "bestEffort": False,
        })
    return entries


def _ceo_set_entries_for_characters(
    clones: list[CharacterClone],
    patches: list[CharacterPatch],
    *,
    source_ceo_defaults: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    source_ceo_defaults = source_ceo_defaults or {}
    for item in [*clones, *patches]:
        template_key = getattr(item, "new_template_key", None) or getattr(item, "template_key", "")
        raw_title_ceo_key = getattr(item, "title_ceo_key", "") or ""
        defaults = source_ceo_defaults.get(template_key) or {}
        if not raw_title_ceo_key:
            raw_title_ceo_key = str(defaults.get("titleCeoKey") or "")
        title_ceo_key = raw_title_ceo_key if _is_career_title_ceo_key(raw_title_ceo_key) else ""
        generic_title_ceos = () if not raw_title_ceo_key or title_ceo_key else (raw_title_ceo_key,)
        selected_trait_ceos = tuple(getattr(item, "trait_ceo_keys", ()))
        if not selected_trait_ceos and not getattr(item, "trait_set_key", None):
            selected_trait_ceos = tuple(defaults.get("traitCeoKeys") or ())
        add_ceos = _unique_lua_ceo_keys([
            *generic_title_ceos,
            *selected_trait_ceos,
        ])
        if not template_key or (not title_ceo_key and not add_ceos):
            continue
        remove_ceos = _unique_lua_ceo_keys([
            *getattr(item, "removable_title_ceo_keys", ()),
            *getattr(item, "removable_trait_ceo_keys", ()),
        ])
        trait_set_key = getattr(item, "trait_set_key", "") or ""
        equipment_set_key = getattr(item, "equipment_set_key", "") or ""
        save_seed = (
            f"{template_key}:{title_ceo_key}:{trait_set_key}:{equipment_set_key}:"
            f"{','.join(add_ceos)}:{','.join(remove_ceos)}:ceo_sets:v{CEO_SET_SCRIPT_SAVE_VERSION}"
        ).encode("utf-8")
        entries.append({
            "template": template_key,
            "saveKey": f"hby_mtu_pack_editor_ceo_sets_v{CEO_SET_SCRIPT_SAVE_VERSION}_{zlib.crc32(save_seed) & 0xffffffff:08x}",
            "titleCeoKey": title_ceo_key,
            "traitSetKey": trait_set_key,
            "equipmentSetKey": equipment_set_key,
            "addCeos": add_ceos,
            "removeCeos": remove_ceos,
        })
    return entries


def _source_initial_ceo_defaults_for_clones(
    clones: list[CharacterClone],
    active_pack_paths: list[Path],
) -> dict[str, dict[str, Any]]:
    dedicated_clones = [
        clone
        for clone in clones
        if clone.dedicated_armour is not None
    ]
    if not dedicated_clones:
        return {}

    effective = resolve_effective_ccd(active_pack_paths)
    if effective is None:
        raise DedicatedArmourPoolError(
            "전용 갑옷 기준 장수의 초기 특성을 읽을 campaigns/ceo_data.ccd가 없습니다."
        )
    try:
        index = read_pfh_index(effective.pack_path)
        ccd = CeoCcd.from_bytes(
            read_entry_bytes(
                effective.pack_path,
                find_entry(index, effective.packed_path),
            )
        )
    except (OSError, ValueError) as error:
        raise DedicatedArmourPoolError(
            "전용 갑옷 기준 장수의 초기 특성을 읽지 못했습니다: "
            f"{effective.pack_path}"
        ) from error

    result: dict[str, dict[str, Any]] = {}
    for clone in dedicated_clones:
        assignment = clone.dedicated_armour
        assert assignment is not None
        active_ceos = initial_ceo_active_ceos(
            ccd,
            assignment.source_initial_ceo_key,
        )
        title_ceo = next(
            (
                key
                for key in active_ceos
                if _is_career_title_ceo_key(key)
                and "_career_childhood_" not in key
            ),
            "",
        )
        trait_ceos = [
            key
            for key in active_ceos
            if "_ceo_trait_" in key
        ]
        if title_ceo or trait_ceos:
            result[clone.new_template_key] = {
                "titleCeoKey": title_ceo,
                "traitCeoKeys": trait_ceos,
            }
    return result


def _is_career_title_ceo_key(value: Any) -> bool:
    key = str(value or "").strip()
    return "_ceo_career_" in key


def _unique_lua_ceo_keys(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            raw_key = value.get("key") or value.get("ceoKey") or value.get("ceoNodeKey") or ""
        else:
            raw_key = value
        key = str(raw_key or "").strip()
        if not key or key == "[object Object]" or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _legacy_campaign_start_spawn_script(
    clones: list[CharacterClone],
    patches: list[CharacterPatch] | None = None,
) -> str | None:
    entries = _spawn_entries_for_clones(clones)
    ceo_entries = _ceo_set_entries_for_characters(clones, patches or [])
    equipment_entries = _equipment_entries_for_characters(clones, patches or [])

    if not entries and not ceo_entries and not equipment_entries:
        return None

    lines = [
        "-- Auto-generated by MTU Pack Editor.",
        "-- Creates generated characters once, then applies post-spawn CEO changes.",
        "local hby_mtu_player_spawn_characters = {",
    ]
    for entry in entries:
        lines.append(
            f'    {{ template = "{_lua_escape(entry["template"])}", subtype = "{_lua_escape(entry["subtype"])}", event = "{_lua_escape(entry["event"] or "")}", turn = {entry["turn"]}, save_key = "{_lua_escape(entry["saveKey"])}", attempt_key = "{_lua_escape(entry["attemptKey"])}", incident = "{_lua_escape(entry["incident"])}" }},'
        )
    lines.extend([
        "}",
        "",
        "local hby_mtu_ceo_set_characters = {",
    ])
    for entry in ceo_entries:
        lines.append(
            f'    {{ template = "{_lua_escape(entry["template"])}", save_key = "{_lua_escape(entry["saveKey"])}", title_ceo = "{_lua_escape(entry["titleCeoKey"])}", remove_ceos = {_lua_string_list(entry["removeCeos"])}, add_ceos = {_lua_string_list(entry["addCeos"])} }},'
        )
    lines.extend([
        "}",
        "",
        "local hby_mtu_equipment_characters = {",
    ])
    for entry in equipment_entries:
        lines.append(
            f'    {{ template = "{_lua_escape(entry["template"])}", save_key = "{_lua_escape(entry["saveKey"])}", grant_key = "{_lua_escape(entry["grantKey"])}", remove_ceos = {_lua_string_list(entry["removeCeos"])}, equipment_ceos = {_lua_string_list(entry["equipmentCeos"])}, default_equipment_ceos = {_lua_string_list(entry["defaultEquipmentCeos"])}, grant_equipment_ceos = {_lua_string_list(entry["grantEquipmentCeos"])}, cleanup_equipment_ceos = {_lua_string_list(entry["cleanupEquipmentCeos"])} }},'
        )
    lines.extend([
        "}",
        "",
        "local function hby_mtu_all_player_spawns_done()",
        "    for i = 1, #hby_mtu_player_spawn_characters do",
        "        local item = hby_mtu_player_spawn_characters[i]",
        "        if not cm:get_saved_value(item.save_key) then",
        "            return false",
        "        end",
        "    end",
        "    return true",
        "end",
        "",
        "local function hby_mtu_all_ceo_sets_done()",
        "    for i = 1, #hby_mtu_ceo_set_characters do",
        "        local item = hby_mtu_ceo_set_characters[i]",
        "        if not cm:get_saved_value(item.save_key) then",
        "            return false",
        "        end",
        "    end",
        "    return true",
        "end",
        "",
        "local function hby_mtu_all_equipment_sets_done()",
        "    for i = 1, #hby_mtu_equipment_characters do",
        "        local item = hby_mtu_equipment_characters[i]",
        "        if not cm:get_saved_value(item.save_key) then",
        "            return false",
        "        end",
        "    end",
        "    return true",
        "end",
        "",
        "local function hby_mtu_character_exists(template_key)",
        "    local ok, character = pcall(function() return cm:query_model():character_for_template(template_key) end)",
        "    if not ok or not character then",
        "        return false",
        "    end",
        "    local null_ok, is_null = pcall(function() return character:is_null_interface() end)",
        "    if null_ok and is_null then",
        "        return false",
        "    end",
        "    local dead_ok, is_dead = pcall(function() return character:is_dead() end)",
        "    return not (dead_ok and is_dead)",
        "end",
        "",
        "local function hby_mtu_faction_key(value)",
        "    if value then",
        "        local ok, name = pcall(function() return value:name() end)",
        '        if ok and type(name) == "string" and name ~= "" then',
        "            return name",
        "        end",
        "    end",
        '    if type(value) == "string" then',
        "        return value",
        "    end",
        '    return ""',
        "end",
        "",
        "local function hby_mtu_query_character_for_template(template_key)",
        "    local ok, character = pcall(function() return cm:query_model():character_for_template(template_key) end)",
        "    if not ok or not character then",
        "        return nil",
        "    end",
        "    local null_ok, is_null = pcall(function() return character:is_null_interface() end)",
        "    if null_ok and is_null then",
        "        return nil",
        "    end",
        "    local dead_ok, is_dead = pcall(function() return character:is_dead() end)",
        "    if dead_ok and is_dead then",
        "        return nil",
        "    end",
        "    return character",
        "end",
        "",
        "local function hby_mtu_prepare_spawned_character(template_key, faction_key)",
        "    local character = hby_mtu_query_character_for_template(template_key)",
        "    if not character then",
        '        output("MTU Pack Editor: generated character not ready: " .. tostring(template_key))',
        "        return false",
        "    end",
        "    local faction_ok, current_faction = pcall(function() return character:faction():name() end)",
        "    local leader_ok, is_leader = pcall(function() return character:is_faction_leader() end)",
        "    if faction_ok and current_faction and current_faction ~= faction_key and not (leader_ok and is_leader) then",
        "        local move_ok = pcall(function() cm:modify_character(character):move_to_faction_and_make_recruited(faction_key) end)",
        "        if not move_ok then",
        '            output("MTU Pack Editor: spawned character move failed: " .. tostring(template_key) .. " -> " .. tostring(faction_key))',
        "        end",
        "    end",
        "    return true",
        "end",
        "",
        "local function hby_mtu_spawn_modify_faction(faction_key)",
        "    faction_key = hby_mtu_faction_key(faction_key)",
        '    if not faction_key or faction_key == "" then',
        "        return nil",
        "    end",
        "    local modify_ok, modify_faction = pcall(function() return cm:modify_faction(faction_key) end)",
        "    if modify_ok and modify_faction then",
        "        return modify_faction",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_direct_spawn_character(faction_key, subtype_key, template_key)",
        "    if hby_mtu_query_character_for_template(template_key) then",
        '        return "exists"',
        "    end",
        "    local modify_faction = hby_mtu_spawn_modify_faction(faction_key)",
        "    if not modify_faction or not modify_faction.create_character_from_template then",
        '        output("MTU Pack Editor: MTU template spawn API not ready.")',
        '        return "failed"',
        "    end",
        "    local create_ok, result = pcall(function() return modify_faction:create_character_from_template(\"general\", subtype_key, template_key, false) end)",
        "    if not create_ok or result == false then",
        '        output("MTU Pack Editor: generated character spawn API failed: " .. tostring(template_key))',
        '        return "failed"',
        "    end",
        "    if hby_mtu_query_character_for_template(template_key) then",
        '        return "created"',
        "    end",
        '    return "pending"',
        "end",
        "",
        "local function hby_mtu_preflight_spawn_state(faction_key)",
        "    faction_key = hby_mtu_faction_key(faction_key)",
        '    if not faction_key or faction_key == "" then',
        "        return",
        "    end",
        "    for i = 1, #hby_mtu_player_spawn_characters do",
        "        local item = hby_mtu_player_spawn_characters[i]",
        "        if not cm:get_saved_value(item.save_key) then",
        "            local character = hby_mtu_query_character_for_template(item.template)",
        "            if character then",
        "                hby_mtu_prepare_spawned_character(item.template, faction_key)",
        "                cm:set_saved_value(item.save_key, true)",
        '                output("MTU Pack Editor: preflight locked generated character: " .. tostring(item.template))',
        "            end",
        "        end",
        "    end",
        "end",
        "",
        "local function hby_mtu_modify_character_for_template(template_key)",
        "    local ok, character = pcall(function() return cm:query_model():character_for_template(template_key) end)",
        "    if not ok or not character then",
        "        return nil",
        "    end",
        "    local null_ok, is_null = pcall(function() return character:is_null_interface() end)",
        "    if null_ok and is_null then",
        "        return nil",
        "    end",
        "    local dead_ok, is_dead = pcall(function() return character:is_dead() end)",
        "    if dead_ok and is_dead then",
        "        return nil",
        "    end",
        "    local modify_ok, modify_character = pcall(function() return cm:modify_character(character) end)",
        "    if modify_ok and modify_character then",
        "        return modify_character",
        "    end",
        "    local lookup_ok, lookup = pcall(function() return cm:char_lookup_str(character) end)",
        "    if lookup_ok and lookup then",
        "        modify_ok, modify_character = pcall(function() return cm:modify_character(lookup) end)",
        "        if modify_ok and modify_character then",
        "            return modify_character",
        "        end",
        "    end",
        "    local cqi_ok, cqi = pcall(function() return character:cqi() end)",
        "    if not cqi_ok or not cqi then",
        "        cqi_ok, cqi = pcall(function() return character:command_queue_index() end)",
        "    end",
        "    if cqi_ok and cqi then",
        "        modify_ok, modify_character = pcall(function() return cm:modify_character(cqi) end)",
        "        if modify_ok and modify_character then",
        "            return modify_character",
        "        end",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_remove_ceo(ceo_manager, ceo_key)",
        "    local ok, result = pcall(function() return ceo_manager:remove_ceos(ceo_key) end)",
        "    if ok and result ~= false then",
        "        return true",
        "    end",
        "    ok, result = pcall(function() return ceo_manager:remove_ceo(ceo_key) end)",
        "    return ok and result ~= false",
        "end",
        "",
        "local function hby_mtu_add_ceo(ceo_manager, ceo_key)",
        "    local ok, result = pcall(function() return ceo_manager:add_ceos(ceo_key) end)",
        "    if ok and result ~= false then",
        "        return true",
        "    end",
        "    ok, result = pcall(function() return ceo_manager:add_ceo(ceo_key) end)",
        "    return ok and result ~= false",
        "end",
        "",
        "local function hby_mtu_character_cqi(character)",
        "    if not character then",
        "        return nil",
        "    end",
        "    local ok, cqi = pcall(function() return character:cqi() end)",
        "    if ok and cqi then",
        "        return cqi",
        "    end",
        "    ok, cqi = pcall(function() return character:command_queue_index() end)",
        "    if ok and cqi then",
        "        return cqi",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_character_lookup(character)",
        "    if not character then",
        "        return nil",
        "    end",
        "    local ok, lookup = pcall(function() return cm:char_lookup_str(character) end)",
        "    if ok and lookup then",
        "        return lookup",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_modify_character_from_character(character)",
        "    if not character then",
        "        return nil",
        "    end",
        "    local ok, modify_character = pcall(function() return cm:modify_character(character) end)",
        "    if ok and modify_character then",
        "        return modify_character",
        "    end",
        "    local lookup = hby_mtu_character_lookup(character)",
        "    if lookup then",
        "        ok, modify_character = pcall(function() return cm:modify_character(lookup) end)",
        "        if ok and modify_character then",
        "            return modify_character",
        "        end",
        "    end",
        "    local cqi = hby_mtu_character_cqi(character)",
        "    if cqi then",
        "        ok, modify_character = pcall(function() return cm:modify_character(cqi) end)",
        "        if ok and modify_character then",
        "            return modify_character",
        "        end",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_ceo_manager_for_character(character)",
        "    local modify_character = hby_mtu_modify_character_from_character(character)",
        "    if not modify_character then",
        "        return nil",
        "    end",
        "    local ok, ceo_manager = pcall(function() return modify_character:ceo_management() end)",
        "    if ok and ceo_manager then",
        "        return ceo_manager",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_force_add_character_ceo(character, modify_character, ceo_manager, ceo_key)",
        "    if ceo_manager and hby_mtu_add_ceo(ceo_manager, ceo_key) then",
        "        return true",
        "    end",
        "    local lookup = hby_mtu_character_lookup(character)",
        "    if lookup then",
        "        local ok, result = pcall(function() return cm:force_add_ceo(lookup, ceo_key) end)",
        "        if ok and result ~= false then",
        "            return true",
        "        end",
        "    end",
        "    local cqi = hby_mtu_character_cqi(character)",
        "    if cqi then",
        "        local ok, result = pcall(function() return cm:force_add_ceo(cqi, ceo_key) end)",
        "        if ok and result ~= false then",
        "            return true",
        "        end",
        "    end",
        "    if character then",
        "        local ok, result = pcall(function() return cm:force_add_ceo(character, ceo_key) end)",
        "        if ok and result ~= false then",
        "            return true",
        "        end",
        "    end",
        "    if modify_character then",
        "        local manager_ok, fallback_manager = pcall(function() return modify_character:ceo_management() end)",
        "        if manager_ok and fallback_manager then",
        "            return hby_mtu_add_ceo(fallback_manager, ceo_key)",
        "        end",
        "    end",
        "    return false",
        "end",
        "",
        "local function hby_mtu_character_ceo_for_category(character, category_key, ceo_key)",
        "    if not character then",
        "        return nil, nil",
        "    end",
        "    local manager_ok, query_ceo_manager = pcall(function() return character:ceo_management() end)",
        "    if not manager_ok or not query_ceo_manager then",
        "        return nil, nil",
        "    end",
        "    local list_ok, ceo_list = pcall(function() return query_ceo_manager:all_ceos_for_category(category_key) end)",
        "    if not list_ok or not ceo_list then",
        "        return nil, nil",
        "    end",
        "    local count_ok, count = pcall(function() return ceo_list:num_items() end)",
        "    if not count_ok or not count then",
        "        return nil, nil",
        "    end",
        "    for index = 0, count - 1 do",
        "        local item_ok, ceo_node = pcall(function() return ceo_list:item_at(index) end)",
        "        if item_ok and ceo_node then",
        "            local data_ok, data_key = pcall(function() return ceo_node:ceo_data_key() end)",
        "            local node_ok, node_key = pcall(function() return ceo_node:current_node_key() end)",
        "            if data_ok and data_key and (not ceo_key or ceo_key == \"\" or data_key == ceo_key) then",
        "                if node_ok then",
        "                    return data_key, node_key",
        "                end",
        "                return data_key, nil",
        "            end",
        "        end",
        "    end",
        "    return nil, nil",
        "end",
        "",
        "local function hby_mtu_set_character_title(character, modify_character, ceo_manager, ceo_key)",
        "    if not ceo_key or ceo_key == \"\" then",
        "        return true",
        "    end",
        "    local category_key = \"3k_main_ceo_category_career\"",
        "    if not ceo_manager and modify_character then",
        "        local manager_ok, fallback_manager = pcall(function() return modify_character:ceo_management() end)",
        "        if manager_ok and fallback_manager then",
        "            ceo_manager = fallback_manager",
        "        end",
        "    end",
        "    if not ceo_manager then",
        "        return false",
        "    end",
        "    local old_ceo_key = hby_mtu_character_ceo_for_category(character, category_key, nil)",
        "    if old_ceo_key == ceo_key then",
        "        return true",
        "    end",
        "    if old_ceo_key and old_ceo_key ~= \"\" then",
        "        hby_mtu_remove_ceo(ceo_manager, old_ceo_key)",
        "    end",
        "    local added = hby_mtu_add_ceo(ceo_manager, ceo_key)",
        "    local result_ceo_key = hby_mtu_character_ceo_for_category(character, category_key, ceo_key)",
        "    return result_ceo_key == ceo_key or added",
        "end",
        "",
        "local function hby_mtu_modify_faction(faction_key)",
        "    faction_key = hby_mtu_faction_key(faction_key)",
        '    if not faction_key or faction_key == "" then',
        "        return nil",
        "    end",
        "    local modify_ok, modify_faction = pcall(function() return cm:modify_faction(faction_key) end)",
        "    if modify_ok and modify_faction then",
        "        return modify_faction",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_append_unique(list, value)",
        "    if not value or value == \"\" then",
        "        return",
        "    end",
        "    for i = 1, #list do",
        "        if list[i] == value then",
        "            return",
        "        end",
        "    end",
        "    table.insert(list, value)",
        "end",
        "",
        "local function hby_mtu_weapon_type_from_suffix(suffix)",
        "    local weapon_types = { \"bow\", \"spear\", \"sword\", \"axe\", \"halberd\", \"crossbow\", \"dao\", \"ji\", \"glaive\", \"mace\" }",
        "    suffix = tostring(suffix or \"\")",
        "    for i = 1, #weapon_types do",
        "        local weapon_type = weapon_types[i]",
        "        if suffix == weapon_type or string.sub(suffix, -string.len(weapon_type)) == weapon_type then",
        "            return weapon_type",
        "        end",
        "    end",
        "    return nil",
        "end",
        "",
        "local function hby_mtu_is_custom_ancillary_key(key)",
        "    key = string.lower(tostring(key or \"\"))",
        "    return string.sub(key, 1, 7) == \"3k_mtu_\" or string.sub(key, 1, 4) == \"hby_\" or string.find(key, \"_mtu_\", 1, true) ~= nil",
        "end",
        "",
        "local function hby_mtu_ancillary_key_candidates(ancillary_key)",
        "    local key = tostring(ancillary_key or \"\")",
        "    local candidates = {}",
        "    if not hby_mtu_is_custom_ancillary_key(key) then",
        "        hby_mtu_append_unique(candidates, key)",
        "        return candidates",
        "    end",
        "    local start_pos, end_pos = string.find(key, \"_ancillary_armour_\", 1, true)",
        "    if start_pos then",
        "        hby_mtu_append_unique(candidates, key)",
        "    end",
        "    start_pos, end_pos = string.find(key, \"_ancilliary_armour_\", 1, true)",
        "    if start_pos then",
        "        local prefix = string.sub(key, 1, start_pos - 1)",
        "        local suffix = string.sub(key, end_pos + 1)",
        "        hby_mtu_append_unique(candidates, key)",
        "        hby_mtu_append_unique(candidates, prefix .. \"_ancillary_armour_\" .. suffix)",
        "    end",
        "    start_pos, end_pos = string.find(key, \"_ancillary_weapon_\", 1, true)",
        "    if start_pos then",
        "        hby_mtu_append_unique(candidates, key)",
        "    end",
        "    start_pos, end_pos = string.find(key, \"_ancilliary_weapon_\", 1, true)",
        "    if start_pos then",
        "        local prefix = string.sub(key, 1, start_pos - 1)",
        "        local suffix = string.sub(key, end_pos + 1)",
        "        hby_mtu_append_unique(candidates, key)",
        "        hby_mtu_append_unique(candidates, prefix .. \"_ancillary_weapon_\" .. suffix)",
        "    end",
        "    if #candidates == 0 then",
        "        hby_mtu_append_unique(candidates, key)",
        "    end",
        "    return candidates",
        "end",
        "",
        "local function hby_mtu_add_ancillary_to_faction(faction_key, ancillary_key)",
        "    local candidates = hby_mtu_ancillary_key_candidates(ancillary_key)",
        "    local modify_faction = hby_mtu_modify_faction(faction_key)",
        "    if not modify_faction then",
        "        return false",
        "    end",
        "    local manager_ok, ceo_manager = pcall(function() return modify_faction:ceo_management() end)",
        "    if not manager_ok or not ceo_manager then",
        "        return false",
        "    end",
        "    for i = 1, #candidates do",
        "        local candidate_key = candidates[i]",
        "        if hby_mtu_add_ceo(ceo_manager, candidate_key) then",
        "            return true",
        "        end",
        "    end",
        "    return false",
        "end",
        "",
        "local function hby_mtu_apply_equipment_set(item, faction_key)",
        "    faction_key = hby_mtu_faction_key(faction_key)",
        '    if not faction_key or faction_key == "" then',
        "        return false",
        "    end",
        "    if item.save_key and cm:get_saved_value(item.save_key) then",
        "        return true",
        "    end",
        "    local grant_done = item.grant_key and cm:get_saved_value(item.grant_key)",
        "    local granted = true",
        "    if not grant_done then",
        "        local modify_faction = hby_mtu_modify_faction(faction_key)",
        "        if modify_faction then",
        "            local manager_ok, ceo_manager = pcall(function() return modify_faction:ceo_management() end)",
        "            if manager_ok and ceo_manager then",
        "                for i = 1, #(item.cleanup_equipment_ceos or {}) do",
        "                    hby_mtu_remove_ceo(ceo_manager, item.cleanup_equipment_ceos[i])",
        "                end",
        "            end",
        "        end",
        "        for i = 1, #(item.grant_equipment_ceos or {}) do",
        "            local ceo_key = item.grant_equipment_ceos[i]",
        "            if not hby_mtu_add_ancillary_to_faction(faction_key, ceo_key) then",
        '                output("MTU Pack Editor: failed to grant ancillary: " .. tostring(item.template) .. " -> " .. tostring(ceo_key))',
        "                granted = false",
        "            end",
        "        end",
        "        if not granted then",
        "            return false",
        "        end",
        "        if item.grant_key then",
        "            cm:set_saved_value(item.grant_key, true)",
        "        end",
        "    end",
        "    cm:set_saved_value(item.save_key, true)",
        '    output("MTU Pack Editor: granted equipment items: " .. tostring(item.template))',
        "    return true",
        "end",
        "",
        "local function hby_mtu_apply_equipment_sets(faction_key)",
        "    faction_key = hby_mtu_faction_key(faction_key)",
        '    if not faction_key or faction_key == "" then',
        "        return",
        "    end",
        "    for i = 1, #hby_mtu_equipment_characters do",
        "        local item = hby_mtu_equipment_characters[i]",
        "        hby_mtu_apply_equipment_set(item, faction_key)",
        "    end",
        "end",
        "",
        "local function hby_mtu_apply_ceo_set(item)",
        "    if cm:get_saved_value(item.save_key) then",
        "        return true",
        "    end",
        "    local character = hby_mtu_query_character_for_template(item.template)",
        "    local modify_character = hby_mtu_modify_character_for_template(item.template)",
        "    if not character then",
        '        output("MTU Pack Editor: CEO set target not ready: " .. tostring(item.template))',
        "        return false",
        "    end",
        "    local manager_ok, ceo_manager = false, nil",
        "    if modify_character then",
        "        manager_ok, ceo_manager = pcall(function() return modify_character:ceo_management() end)",
        "    end",
        "    if not manager_ok or not ceo_manager then",
        '        output("MTU Pack Editor: CEO manager unavailable: " .. tostring(item.template))',
        "    end",
        "    for i = 1, #(item.remove_ceos or {}) do",
        "        local ceo_key = item.remove_ceos[i]",
        "        if manager_ok and ceo_manager then",
        "            hby_mtu_remove_ceo(ceo_manager, ceo_key)",
        "        end",
        "    end",
        "    local applied = true",
        "    if item.title_ceo and item.title_ceo ~= \"\" then",
        "        if not hby_mtu_set_character_title(character, modify_character, ceo_manager, item.title_ceo) then",
        '            output("MTU Pack Editor: failed to set title CEO: " .. tostring(item.template) .. " -> " .. tostring(item.title_ceo))',
        "            applied = false",
        "        end",
        "    end",
        "    for i = 1, #(item.add_ceos or {}) do",
        "        local ceo_key = item.add_ceos[i]",
        "        if not hby_mtu_force_add_character_ceo(character, modify_character, ceo_manager, ceo_key) then",
        '            output("MTU Pack Editor: failed to add CEO: " .. tostring(item.template) .. " -> " .. tostring(ceo_key))',
        "            applied = false",
        "        end",
        "    end",
        "    if not applied then",
        "        return false",
        "    end",
        "    cm:set_saved_value(item.save_key, true)",
        '    output("MTU Pack Editor: applied CEO set: " .. tostring(item.template))',
        "    return true",
        "end",
        "",
        "local function hby_mtu_apply_ceo_sets()",
        "    for i = 1, #hby_mtu_ceo_set_characters do",
        "        local item = hby_mtu_ceo_set_characters[i]",
        "        if not cm:get_saved_value(item.save_key) then",
        "            hby_mtu_apply_ceo_set(item)",
        "        end",
        "    end",
        "end",
        "",
        "local function hby_mtu_register_special_character_templates()",
        "    if not ancillaries or not ancillaries.char_start_ancillaries_banned_character_templates then",
        "        return false",
        "    end",
        "    local banned = ancillaries.char_start_ancillaries_banned_character_templates",
        "    for i = 1, #hby_mtu_player_spawn_characters do",
        "        local template_key = hby_mtu_player_spawn_characters[i].template",
        "        local found = false",
        "        for j = 1, #banned do",
        "            if banned[j] == template_key then",
        "                found = true",
        "                break",
        "            end",
        "        end",
        "        if not found then",
        "            table.insert(banned, template_key)",
        "            output(\"MTU Pack Editor: registered special character template: \" .. tostring(template_key))",
        "        end",
        "    end",
        "    return true",
        "end",
        "",
        "local function hby_mtu_spawn_for_player(faction_key)",
        "    faction_key = hby_mtu_faction_key(faction_key)",
        '    if not faction_key or faction_key == "" then',
        '        output("MTU Pack Editor: no local player faction found.")',
        "        return",
        "    end",
        "    hby_mtu_register_special_character_templates()",
        "    hby_mtu_preflight_spawn_state(faction_key)",
        "    if hby_mtu_all_player_spawns_done() then",
        "        return",
        "    end",
        "",
        "    local turn_number = cm:turn_number() or 0",
        "    for i = 1, #hby_mtu_player_spawn_characters do",
        "        local item = hby_mtu_player_spawn_characters[i]",
        '        local can_spawn = item.event == "campaign_start" or turn_number >= item.turn',
        "        if not cm:get_saved_value(item.save_key) and can_spawn then",
        "            if hby_mtu_prepare_spawned_character(item.template, faction_key) then",
        '                output("MTU Pack Editor: generated character observed: " .. tostring(item.template))',
        "                cm:set_saved_value(item.save_key, true)",
        "            elseif not item.attempt_key or cm:get_saved_value(item.attempt_key) ~= turn_number then",
        "                if item.attempt_key then",
        "                    cm:set_saved_value(item.attempt_key, turn_number)",
        "                end",
        "                local spawn_result = hby_mtu_direct_spawn_character(faction_key, item.subtype, item.template)",
        '                if spawn_result == "created" or spawn_result == "exists" then',
        "                    hby_mtu_prepare_spawned_character(item.template, faction_key)",
        '                    output("MTU Pack Editor: generated character created: " .. tostring(item.template))',
        "                    cm:set_saved_value(item.save_key, true)",
        '                elseif spawn_result == "pending" then',
        '                    output("MTU Pack Editor: generated character spawn pending: " .. tostring(item.template))',
        "                else",
        '                    output("MTU Pack Editor: generated character spawn failed: " .. tostring(item.template))',
        "                    if item.attempt_key then",
        "                        cm:set_saved_value(item.attempt_key, false)",
        "                    end",
        "                end",
        "            else",
        '                output("MTU Pack Editor: generated character spawn already attempted this turn: " .. tostring(item.template))',
        "            end",
        "        end",
        "    end",
        "end",
        "",
        "function hby_mtu_pack_editor_player_spawn(faction_key)",
        "    hby_mtu_spawn_for_player(faction_key)",
        "    hby_mtu_apply_equipment_sets(faction_key)",
        "    hby_mtu_apply_ceo_sets()",
        "end",
        "",
        "-- Errors escaping this file's load or callbacks would abort every mod",
        "-- script queued after it (Korea addon, sandbox mode UI, ...), so all",
        "-- entry points stay guarded and never propagate.",
        "local hby_mtu_turn_start_listener_added = false",
        "",
        "local function hby_mtu_register_turn_start_listener()",
        "    if hby_mtu_turn_start_listener_added then",
        "        return",
        "    end",
        "    if not core or not core.add_listener then",
        "        return",
        "    end",
        "    hby_mtu_turn_start_listener_added = true",
        "    core:add_listener(",
        '        "hby_mtu_pack_editor_player_spawn_turn_start",',
        '        "FactionTurnStart",',
        "        function(context)",
        "            local cond_ok, wanted = pcall(function()",
        "                return context:faction():is_human() and (not hby_mtu_all_player_spawns_done() or not hby_mtu_all_equipment_sets_done() or not hby_mtu_all_ceo_sets_done())",
        "            end)",
        "            if not cond_ok then",
        "                return false",
        "            end",
        "            return wanted == true",
        "        end,",
        "        function(context)",
        "            local run_ok, run_error = pcall(function()",
        "                local faction_key = context:faction():name()",
        "                hby_mtu_spawn_for_player(faction_key)",
        "                hby_mtu_apply_equipment_sets(faction_key)",
        "                hby_mtu_apply_ceo_sets()",
        "            end)",
        "            if not run_ok then",
        '                output("MTU Pack Editor: turn start error: " .. tostring(run_error))',
        "            end",
        "        end,",
        "        true",
        "    )",
        "end",
        "",
        "if cm and cm.add_first_tick_callback then",
        "    cm:add_first_tick_callback(function()",
        "        local tick_ok, tick_error = pcall(function()",
        '            cm:set_saved_value("hby_mtu_player_spawn_listener_registered", true)',
        "            hby_mtu_register_turn_start_listener()",
        "            local faction_key = nil",
        "            local local_ok, local_value = pcall(function() return cm:get_local_faction() end)",
        "            if local_ok then",
        "                faction_key = hby_mtu_faction_key(local_value)",
        "            end",
        '            if not faction_key or faction_key == "" then',
        "                local_ok, local_value = pcall(function() return cm:get_local_faction(true) end)",
        "                if local_ok then",
        "                    faction_key = hby_mtu_faction_key(local_value)",
        "                end",
        "            end",
        "            hby_mtu_spawn_for_player(faction_key)",
        "            hby_mtu_apply_equipment_sets(faction_key)",
        "            hby_mtu_apply_ceo_sets()",
        "        end)",
        "        if not tick_ok then",
        '            output("MTU Pack Editor: first tick error: " .. tostring(tick_error))',
        "        end",
        "    end)",
        "end",
        "",
    ])
    return "\n".join(lines)


def _diagnostic_work_entries(clones: list[CharacterClone], patches: list[CharacterPatch]) -> list[dict[str, str]]:
    return [
        *({"template": clone.new_template_key, "kind": "new_character"} for clone in clones),
        *({"template": patch.template_key, "kind": "existing_character"} for patch in patches),
    ]


def _campaign_start_spawn_script(
    clones: list[CharacterClone],
    patches: list[CharacterPatch] | None = None,
) -> str | None:
    """Generate the guarded, minimal campaign runtime script.

    The older generator grew several speculative API fallbacks.  Keep the
    shipped Lua on CA's documented Three Kingdoms paths instead.
    """
    return build_campaign_start_script(
        _spawn_entries_for_clones(clones),
        _ceo_set_entries_for_characters(clones, patches or []),
        _equipment_entries_for_characters(clones, patches or []),
        work_entries=_diagnostic_work_entries(clones, patches or []),
        escape=_lua_escape,
        string_list=_lua_string_list,
    )


def _lua_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _lua_string_list(values: list[str]) -> str:
    return "{ " + ", ".join(f'"{_lua_escape(str(value))}"' for value in values if value) + " }"


def _name_id_for_clone(clone: CharacterClone, names: list[dict[str, Any]]) -> int:
    used = {str(row.get("id")) for row in names}
    seed = f"{clone.new_template_key}:{clone.display_name or ''}".encode("utf-8")
    value = 2_000_000_000 + (zlib.crc32(seed) % 100_000_000)
    while str(value) in used:
        value += 1
    return value


def _upsert_delta_row(
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_name: str,
    key_field: str | Any,
    row: dict[str, Any],
) -> None:
    rows = rows_by_table.setdefault(table_name, [])
    row_key = key_field(row) if callable(key_field) else row.get(key_field)
    for index, existing in enumerate(rows):
        existing_key = key_field(existing) if callable(key_field) else existing.get(key_field)
        if existing_key == row_key:
            rows[index] = row
            return
    rows.append(row)


def _upsert_delta_row_once(
    rows_by_table: dict[str, list[dict[str, Any]]],
    table_name: str,
    key_field: str | Any,
    row: dict[str, Any],
) -> bool:
    row_key = key_field(row) if callable(key_field) else row.get(key_field)
    target_family = _delta_table_family(table_name)
    for existing_table, rows in rows_by_table.items():
        if _delta_table_family(existing_table) != target_family:
            continue
        for existing in rows:
            existing_key = key_field(existing) if callable(key_field) else existing.get(key_field)
            if existing_key == row_key:
                return False
    _upsert_delta_row(rows_by_table, table_name, key_field, row)
    return True


def _delta_table_family(table_name: str) -> str:
    normalized = _normalize_pack_path(str(table_name or ""))
    if "/" not in normalized:
        return normalized
    folder = normalized.rsplit("/", 1)[0]
    return folder.rsplit("/", 1)[-1]


def _find_delta_row(
    rows_by_table: dict[str, list[dict[str, Any]]],
    key_field: str | Any,
    key: Any,
    table_name: str | None = None,
) -> dict[str, Any] | None:
    row_groups = [rows_by_table.get(table_name, [])] if table_name else rows_by_table.values()
    for rows in row_groups:
        for row in rows:
            row_key = key_field(row) if callable(key_field) else row.get(key_field)
            if row_key == key:
                return row
    return None


def _unique_numeric_delta_value(
    seed: str,
    rows: list[dict[str, Any]],
    field: str,
    minimum: int = 1_700_000_000,
    span: int = 300_000_000,
) -> int:
    used = {str(row.get(field)) for row in rows if row.get(field) not in (None, "")}
    value = minimum + (zlib.crc32(seed.encode("utf-8")) % span)
    while str(value) in used:
        value += 1
        if value >= minimum + span:
            value = minimum
    return value


def _clean_source_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not str(key).startswith("_source")}


def _find_required(rows: list[dict[str, Any]], key_field: str, key: str) -> dict[str, Any]:
    for row in rows:
        if row.get(key_field) == key:
            return row
    raise ValueError(f"Row not found: {key_field}={key}")


def _find_required_by(rows: list[dict[str, Any]], key_func: Any, key: str) -> dict[str, Any]:
    for row in rows:
        if str(key_func(row)) == str(key):
            return row
    raise ValueError(f"Row not found: {key}")


def _find_row(rows: list[dict[str, Any]], key_field: str, key: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get(key_field)) == str(key):
            return row
    return None


def _detail_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("character_generation_template"), row.get("game_mode")


def _art_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("art_set_id"),
        row.get("age"),
        row.get("is_female"),
        row.get("has_come_of_age"),
    )


def _attribute_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return _attribute_set_key(row), _attribute_override_key(row)


def _attribute_set_key(row: dict[str, Any]) -> str:
    for column in (
        "set_name",
        "attribute_set",
        "character_attribute_set",
        "character_attribute_set_key",
        "attribute_set_key",
        "set",
        "key",
    ):
        value = row.get(column)
        if value:
            return str(value)
    for value in row.values():
        text = str(value or "")
        if "_attribute_set_" in text or "attribute_set_" in text:
            return text
    return ""


def _with_attribute_set_key(row: dict[str, Any], set_key: str) -> dict[str, Any]:
    clean = _clean_source_row(dict(row))
    for column in (
        "set_name",
        "attribute_set",
        "character_attribute_set",
        "character_attribute_set_key",
        "attribute_set_key",
        "set",
        "key",
    ):
        value = clean.get(column)
        if value and ("attribute_set" in str(value) or column != "key"):
            clean[column] = set_key
            return clean
    clean["set_name"] = set_key
    return clean


def _attribute_override_key(row: dict[str, Any]) -> str:
    value = str(
        row.get("attribute_type")
        or row.get("attribute")
        or row.get("character_attribute")
        or row.get("attribute_key")
        or row.get("key")
        or ""
    ).lower()
    stat_key = _attribute_override_key_from_text(value)
    if stat_key:
        return stat_key
    for cell in row.values():
        stat_key = _attribute_override_key_from_text(str(cell or "").lower())
        if stat_key:
            return stat_key
    return value


def _attribute_override_key_from_text(value: str) -> str | None:
    if "attribute_set" in value:
        return None
    if "expertise" in value or "metal" in value:
        return "expertise"
    if "resolve" in value or "wood" in value:
        return "resolve"
    if "cunning" in value or "water" in value:
        return "cunning"
    if "instinct" in value or "fire" in value:
        return "instinct"
    if "authority" in value or "earth" in value:
        return "authority"
    return None


def _attribute_value_column(row: dict[str, Any]) -> str | None:
    for column in ("value", "attribute_value", "base_value", "initial_value", "starting_value", "amount"):
        if isinstance(row.get(column), (int, float)):
            return column
    skip_columns = {
        "set_name",
        "attribute_set",
        "character_attribute_set",
        "character_attribute_set_key",
        "attribute_set_key",
        "set",
        "key",
        "attribute_type",
        "attribute",
        "character_attribute",
        "attribute_key",
        "minimum_value",
        "maximum_value",
        "min_value",
        "max_value",
        "min",
        "max",
    }
    for column, value in row.items():
        if str(column).startswith("_") or column in skip_columns:
            continue
        if isinstance(value, (int, float)):
            return column
    return None


def _skill_link_key(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    return row.get("parent_key"), row.get("child_key"), row.get("link_type")


def _skill_effect_key(row: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("character_skill_key"),
        row.get("effect_key"),
        row.get("effect_scope"),
        row.get("level"),
    )


def _effect_bonus_value_id(row: dict[str, Any]) -> str:
    return str(
        row.get("bonus_value_id")
        or row.get("effect_bonus_value_id")
        or row.get("bonus_value")
        or ""
    )


def _effect_bonus_unit_ability(row: dict[str, Any]) -> str:
    return str(
        row.get("unit_ability")
        or row.get("ability")
        or row.get("unit_abilities")
        or row.get("unit_ability_key")
        or ""
    )


def _effect_bonus_value_unit_set_key(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    return _effect_bonus_value_id(row), row.get("effect") or row.get("effect_key"), row.get("unit_set")


def _effect_bonus_value_unit_ability_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return _effect_bonus_value_id(row), _effect_bonus_unit_ability(row)


def _retinue_aspect_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("retinue"), row.get("aspect")


def _retinue_slot_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("retinue"), row.get("slot_index")


def _land_unit_ability_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("land_unit"), row.get("ability")


def _special_ability_phase_link_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("special_ability"), row.get("order")


def _special_ability_phase_stat_effect_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("phase"), row.get("stat")


def _special_ability_phase_attribute_effect_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("phase"), row.get("attribute")


def _special_ability_auto_deactivate_flag_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("special_ability"), row.get("auto_deactivate_flag") or row.get("flag")


def _special_ability_invalid_target_flag_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("special_ability"), row.get("invalid_target_flag") or row.get("invalid_target") or row.get("flag")


def _special_ability_invalid_usage_flag_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("special_ability"), row.get("invalid_usage_flag")


def _generic_key_or_id(row: dict[str, Any]) -> str:
    return str(row.get("key") or row.get("id") or row.get("name") or "")


def _main_unit_key(row: dict[str, Any]) -> Any:
    return row.get("unit") if "unit" in row else row.get("key")


def _effect_key(row: dict[str, Any]) -> str:
    return str(row.get("key") or row.get("effect") or "")


def _raise_rpfm_error(response: dict[str, Any]) -> None:
    data = response.get("data")
    if isinstance(data, dict) and "Error" in data:
        raise ValueError(data["Error"])
