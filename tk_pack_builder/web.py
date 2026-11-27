from __future__ import annotations

import json
import mimetypes
import os
import re
import time
import hashlib
import threading
import traceback
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from .adapters import adapter_for
from .analyzer import analyze_pack
from .builder import build_pack
from .character_clone import CHARACTER_TABLE_ALIASES, resolve_character_table_name
from . import delta_builder as delta_builder_module
from .dedicated_armour_pool import (
    DedicatedArmourPool,
    DedicatedArmourPoolError,
    DedicatedArmourPoolStatus,
    load_dedicated_armour_pools,
    ordered_active_ccd_pack_paths,
    resolve_pool_status,
    validate_pool_assignments,
    verify_pool_asset,
)
from .internal_materials import MaterialPackSession
from .source_profiles import current as current_profile, resource as profile_resource, profiled, BASE as BASE_PROFILE
from .source_policy import PROFILE, REFERENCE_PACK, supported_source, require_supported_sources, require_clean_references, require_clean_pack
from .korea_addon import korea_character_metadata, korea_display_name_hint
from .korean_names import korean_character_name
from .pack_cache import PackCache
from .recipe import Recipe, recipe_from_dict
from .stat_tables import TABLE_ALIASES
from .validation import allow_reference_backed_clone_sources, has_errors, messages_to_dicts, validate
from .web_runtime import _close_session, _ensure_rpfm_server


ROOT = Path(os.environ.get("TK_PACK_EDITOR_ROOT", Path(__file__).resolve().parents[1])).resolve()
STATIC_ROOT = ROOT / "web"
WEB_STATIC_SUFFIXES = {".css", ".html", ".js"}
PACK_CACHE = PackCache(ROOT / "work" / "pack_cache.sqlite3")
_BUILD_LOCK = threading.Lock()
REFERENCE_SNAPSHOT = ROOT / "work" / "reference_snapshot.json"
REFERENCE_SNAPSHOT_VERSION = 26
OPEN_PAYLOAD_CACHE_SCHEMA_VERSION = 27
INTERNAL_CHARACTER_CATALOG = ROOT / "work" / "internal_dbs" / "character_catalog.json"
INTERNAL_MATERIALS_PATH = ROOT / "work" / "internal_materials" / "vanilla_mtu" / "materials.v015.json"
INTERNAL_ASSET_MANIFEST = ROOT / "work" / "internal_materials" / "vanilla_mtu" / "asset_manifest.v015.json"
INTERNAL_MATERIAL_SUMMARY = ROOT / "work" / "internal_materials" / "vanilla_mtu" / "materials.v015.summary.json"
PACKAGED_ASSEMBLY_KIT_TITLE_EFFECT_CATALOG = (
    Path(__file__).resolve().parent / "data" / "assembly_kit_title_effects.ko.json"
)
PACKAGED_ASSEMBLY_KIT_SKILL_EFFECT_CATALOG = (
    Path(__file__).resolve().parent / "data" / "assembly_kit_skill_effects.ko.json"
)
EXTRACTED_ASSET_ROOT = ROOT / "work" / "assets"
DEDICATED_ARMOUR_POOL_ROOTS = (
    Path(__file__).resolve().parent / "data" / "dedicated_armour_pools",
    ROOT / "work" / "dedicated_armour_pools",
)
# Only Assembly Kit/BOB-precompiled CCD pools whose exact hash matches the
# active CEO data are exposed. Runtime CCD mutation remains forbidden.
DEDICATED_ARMOUR_ENGINE_ENABLED = True
IMAGE_ONLY_ASSET_PREFIX = "__image_only_reference__"
_ROMANIZED_NAME_LOOKUP_CACHE: dict[tuple[int, int], dict[str, str]] = {}

COMMON_TITLE_ROLE_ALIASES = {
    "clerk": "agent",
    "merchant": "envoy",
}

COMMON_TITLE_ROLE_ORDER = {
    "agent": 1,
    "envoy": 2,
    "general": 3,
    "governor": 4,
    "minister": 5,
    "villager": 6,
}

COMMON_TITLE_CATALOG: dict[tuple[str, str], dict[str, Any]] = {
    ("metal", "agent"): {
        "label": "사무원",
        "effects": ["전문성 +15", "건설 시간 -2턴(세력 전체)"],
    },
    ("metal", "envoy"): {
        "label": "장인",
        "effects": ["전문성 +15, 결의 +5", "산업 수입 +15%(해당 군현)"],
    },
    ("metal", "general"): {
        "label": "도공",
        "effects": ["전문성 +15", "산업 수입 +10%(해당 군현)"],
    },
    ("metal", "governor"): {
        "label": "건설자",
        "effects": ["전문성 +15", "비축 물자 +5, 건설 비용 -10%(해당 군현)"],
    },
    ("metal", "minister"): {
        "label": "양조장 주인",
        "effects": ["전문성 +15, 본능 +5", "상업 수입 +10%(해당 군현)"],
    },
    ("metal", "villager"): {
        "label": "옥 조각가",
        "effects": ["전문성 +15", "상업 및 산업 수입 +5%(해당 군현)"],
    },
    ("wood", "agent"): {
        "label": "소작농",
        "effects": ["결의 +15", "농업 수입 +15%(해당 군현)"],
    },
    ("wood", "envoy"): {
        "label": "벌목꾼",
        "effects": ["결의 +15, 전문성 +5", "농업 수입 +10%(해당 군현)"],
    },
    ("wood", "general"): {
        "label": "어부",
        "effects": ["결의 +15", "식량 생산 +25%(해당 군현)"],
    },
    ("wood", "governor"): {
        "label": "사냥꾼",
        "effects": ["결의 +15, 본능 +5", "군사 보급품 +5(인접 군현)"],
    },
    ("wood", "minister"): {
        "label": "광부",
        "effects": ["결의 +15", "산업 수입 +10%(해당 군현)"],
    },
    ("wood", "villager"): {
        "label": "석공",
        "effects": ["결의 +15", "건설 비용 -10%(해당 군현)"],
    },
    ("water", "agent"): {
        "label": "학자",
        "effects": ["지략 +15", "캐릭터 경험치 +10%(세력 전체)"],
    },
    ("water", "envoy"): {
        "label": "서기",
        "effects": ["지략 +15, 권위 +5", "행정 장관(태수) 제한 +1(세력 전체)"],
    },
    ("water", "general"): {
        "label": "스승",
        "effects": ["지략 +15", "충원 +2%(조정 임명 시 세력 전체)"],
    },
    ("water", "governor"): {
        "label": "철학자",
        "effects": ["지략 +15", "연구 속도 +10%(세력 전체)"],
    },
    ("water", "minister"): {
        "label": "천문학자",
        "effects": ["지략 +15, 결의 +5", "군사 보급품 +5(세력 전체)"],
    },
    ("water", "villager"): {
        "label": "점술가",
        "effects": ["지략 +15", "만족도 +4(세력 전체)"],
    },
    ("fire", "agent"): {
        "label": "약탈자",
        "effects": ["본능 +15", "전후 포획 전리품 +10%(지휘 군대)"],
    },
    ("fire", "envoy"): {
        "label": "무법자",
        "effects": ["본능 +15, 결의 +5", "적 군대 약탈 수입 +15%(지휘 군대)"],
    },
    ("fire", "general"): {
        "label": "도적",
        "effects": ["본능 +15", "적 영토에서의 군사 보급품 +10(지휘 군대)"],
    },
    ("fire", "governor"): {
        "label": "용병",
        "effects": ["본능 +15, 권위 +5", "적 격퇴 수입 +15%(지휘 군대)"],
    },
    ("fire", "minister"): {
        "label": "밀수꾼",
        "effects": ["본능 +15", "상업 수입 +10%(해당 군현)"],
    },
    ("fire", "villager"): {
        "label": "해적",
        "effects": ["본능 +15, 전문성 +5", "습격 수입 +15%(지휘 군대)"],
    },
    ("earth", "agent"): {
        "label": "소지주",
        "effects": ["권위 +15, 결의 +5", "농업 수입 +10%(해당 군현)"],
    },
    ("earth", "envoy"): {
        "label": "상인",
        "effects": ["권위 +15", "상업 수입 +15%(해당 군현)"],
    },
    ("earth", "general"): {
        "label": "귀족",
        "effects": ["권위 +15", "만족도 +4(세력 전체)"],
    },
    ("earth", "governor"): {
        "label": "세금 징수원",
        "effects": ["권위 +15", "세금 징수령 효과 +20%(해당 군현)"],
    },
    ("earth", "minister"): {
        "label": "수송관",
        "effects": ["권위 +15, 지략 +5", "군대 이동 거리 +5%(지휘 군대)"],
    },
    ("earth", "villager"): {
        "label": "가신",
        "effects": ["권위 +15", "수행원(부대) 모집 비용 -10%(지휘 군대)"],
    },
}
DEFAULT_GAME_DATA_DIRS = [
    Path(os.environ["TK_PACK_EDITOR_GAME_DATA_DIR"])
    for _ in [0]
    if os.environ.get("TK_PACK_EDITOR_GAME_DATA_DIR")
] + [
    ROOT / "work" / "packs" / "refs",
    Path("E:/SteamLibrary/steamapps/common/Total War THREE KINGDOMS/data"),
    Path("C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data"),
]
DEFAULT_GAME_LOCAL_PACKS = ("local_kr.pack", "local_en.pack")

SKILL_TABLE_ALIASES = {
    "character_skill_node_sets": [
        "character_skill_node_sets",
        "db/character_skill_node_sets_tables/_mtu_characters",
    ],
    "character_skill_nodes": [
        "character_skill_nodes",
        "db/character_skill_nodes_tables/_mtu_characters",
    ],
    "character_skill_node_links": [
        "character_skill_node_links",
        "db/character_skill_node_links_tables/_mtu_characters",
    ],
    "character_skill_level_to_effects_junctions": [
        "character_skill_level_to_effects_junctions",
        "db/character_skill_level_to_effects_junctions_tables/_mtu_characters_skills",
    ],
    "effects": [
        "effects",
        "db/effects_tables/_mtu_characters_skills_effects",
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
    "land_units_to_unit_abilites_junctions": [
        "land_units_to_unit_abilites_junctions",
        "db/land_units_to_unit_abilites_junctions_tables/_mtu_characters_skills_abilities_land_units",
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
        "db/projectiles_tables/data__",
    ],
}

RETINUE_TABLE_ALIASES = {
    "retinues": [
        "retinues",
        "db/retinues_tables/data__",
        "db/retinues_tables/unit",
    ],
    "retinue_slot_initial_units": [
        "retinue_slot_initial_units",
        "db/retinue_slot_initial_units_tables/data__",
        "db/retinue_slot_initial_units_tables/unit",
    ],
    "cai_retinues_to_aspects": [
        "cai_retinues_to_aspects",
        "db/cai_retinues_to_aspects_tables/data__",
    ],
}

TRAIT_SET_PRESETS = [
    {
        "key": "warrior",
        "label": "용장",
        "items": ["차분함", "용감함", "우애적", "단호함", "명예로움", "완강함", "강한 힘"],
    },
    {
        "key": "vanguard",
        "label": "선봉장",
        "items": ["위협적", "두려움", "활기참", "겸손함", "집요함", "직설적", "맹렬함"],
    },
    {
        "key": "commander",
        "label": "지휘관",
        "items": ["사람을 휘어잡는 매력", "순종적", "야심참", "열성적", "두려움", "겸허함", "상냥함"],
    },
    {
        "key": "sentinel",
        "label": "감시자",
        "items": ["창의적임", "충직함", "인내심이 강함", "방심하지 않음", "강인함", "원칙주의자", "뛰어남"],
    },
    {
        "key": "strategist",
        "label": "모사",
        "items": ["교활함", "뛰어남", "현명함", "통찰력 있음", "종잡을 수 없음", "영리함", "겸허함"],
    },
    {
        "key": "heir",
        "label": "후계자",
        "items": ["쾌활함", "동정적임", "창의적임", "원칙주의자", "신념이 굳셈", "믿음직함", "사람을 휘어잡는 매력"],
    },
    {
        "key": "general",
        "label": "장군",
        "items": ["호위장군", "수하팔부", "백성의 수호자", "백성의 군주", "백성의 치유사", "유능한 장군", "환관"],
    },
]

EQUIPMENT_SET_PRESETS = [
    {
        "key": "sentinel",
        "label": "감시자 세트",
        "items": ["전쟁용 검", "거장의 가죽갑옷", "전문 교관", "산해경", "회색 종마"],
    },
    {
        "key": "warrior",
        "label": "용장 세트",
        "items": ["황실 호위병의 극", "강철각", "전문 교관", "산해경", "갈색 종마"],
    },
    {
        "key": "strategist",
        "label": "모사 세트",
        "items": ["천상의 검", "점쟁이 예복", "공학자", "황실 활", "흑색 종마"],
    },
    {
        "key": "vanguard",
        "label": "선봉장 세트",
        "items": ["가보 창", "용장의 가죽갑옷", "전문 교관", "산해경", "적색 종마"],
    },
    {
        "key": "commander",
        "label": "지휘관 세트",
        "items": ["전쟁도끼", "품위있는 의복", "전문 교관", "산해경", "백색 종마"],
    },
    {
        "key": "industry_administrator",
        "label": "산업 태수 세트",
        "items": ["공두", "수탉 석상"],
    },
    {
        "key": "commerce_administrator",
        "label": "상업 태수 세트",
        "items": ["옥 조각가", "주례"],
    },
    {
        "key": "agriculture_administrator",
        "label": "농업 태수 세트",
        "items": ["주 고문관", "옥 낫"],
    },
]

TRAIT_SET_KEY_OVERRIDES = {
    "강인함": "3k_ytr_ceo_trait_personality_land_powerful",
    "강한 힘": "3k_main_ceo_trait_physical_strong",
    "겸손함": "3k_main_ceo_trait_personality_humble",
    "겸허함": "3k_main_ceo_trait_personality_modest",
    "교활함": "3k_main_ceo_trait_personality_cunning",
    "두려움": "3k_ytr_ceo_trait_physical_feared",
    "뛰어남": "3k_main_ceo_trait_personality_brilliant",
    "단호함": "3k_main_ceo_trait_personality_determined",
    "동정적임": "3k_ytr_ceo_trait_personality_people_compassionate",
    "맹렬함": "3k_main_ceo_trait_personality_fiery",
    "명예로움": "3k_main_ceo_trait_personality_honourable",
    "믿음직함": "3k_ytr_ceo_trait_personality_trustworthy",
    "방심하지 않음": "3k_ytr_ceo_trait_personality_land_alert",
    "백성의 군주": "3k_ytr_ceo_trait_physical_leader_of_people",
    "백성의 수호자": "3k_ytr_ceo_trait_physical_protector_of_people",
    "백성의 치유사": "3k_ytr_ceo_trait_physical_healer_of_people",
    "사람을 휘어잡는 매력": "3k_main_ceo_trait_personality_charismatic",
    "상냥함": "3k_ytr_ceo_trait_personality_people_amiable",
    "수하팔부": "3k_main_ceo_trait_physical_sui_knight",
    "순종적": "3k_main_ceo_trait_personality_dutiful",
    "신념이 굳셈": "3k_ytr_ceo_trait_personality_stalwart",
    "야심참": "3k_main_ceo_trait_personality_ambitious",
    "열성적": "3k_ytr_ceo_trait_personality_land_aspiring",
    "영리함": "3k_main_ceo_trait_personality_clever",
    "완강함": "3k_ytr_ceo_trait_personality_strong_willed",
    "용감함": "3k_main_ceo_trait_personality_brave",
    "우애적": "3k_main_ceo_trait_personality_fraternal",
    "원칙주의자": "3k_main_ceo_trait_personality_disciplined",
    "위협적": "3k_main_ceo_trait_personality_intimidating",
    "유능한 장군": "3k_main_ceo_trait_physical_wei_elite_general",
    "인내심이 강함": "3k_main_ceo_trait_personality_patient",
    "종잡을 수 없음": "3k_main_ceo_trait_personality_elusive",
    "직설적": "3k_main_ceo_trait_personality_direct",
    "집요함": "3k_ytr_ceo_trait_personality_relentless",
    "차분함": "3k_ytr_ceo_trait_personality_heaven_tranquil",
    "창의적임": "3k_ytr_ceo_trait_personality_heaven_creative",
    "충직함": "3k_main_ceo_trait_personality_loyal",
    "쾌활함": "3k_ytr_ceo_trait_personality_people_cheerful",
    "통찰력 있음": "3k_main_ceo_trait_personality_perceptive",
    "현명함": "3k_ytr_ceo_trait_personality_heaven_wise",
    "호위장군": "3k_main_ceo_trait_physical_shu_tiger_general",
    "환관": "3k_main_ceo_trait_physical_eunuch",
    "활기참": "3k_main_ceo_trait_personality_energetic",
}

EQUIPMENT_SET_KEY_OVERRIDES = {
    "가보 창": "3k_main_ancillary_weapon_two_handed_spear_exceptional",
    "갈색 종마": "3k_main_ancillary_mount_brown_stallion",
    "강철각": "3k_main_ancillary_armour_heavy_armour_wood_extraordinary",
    "거장의 가죽갑옷": "3k_main_ancillary_armour_medium_armour_metal_extraordinary",
    "공두": "3k_main_ancillary_follower_foreman",
    "공학자": "3k_main_ancillary_follower_engineer",
    "산해경": "3k_main_ancillary_accessory_book_of_mountains_and_seas",
    "수탉 석상": "3k_main_ancillary_accessory_stone_rooster",
    "옥 낫": "3k_main_ancillary_accessory_jade_sickle",
    "옥 조각가": "3k_main_ancillary_follower_jade_sculptor",
    "용장의 가죽갑옷": "3k_main_ancillary_armour_medium_armour_fire_extraordinary",
    "전문 교관": "3k_main_ancillary_follower_professional_instuctor",
    "전쟁도끼": "3k_main_ancillary_weapon_one_handed_axe_exceptional",
    "전쟁용 검": "3k_main_ancillary_weapon_double_edged_sword_exceptional",
    "점쟁이 예복": "3k_main_ancillary_armour_strategist_light_armour_water_extraordinary",
    "주 고문관": "3k_main_ancillary_follower_provincial_advisor",
    "주례": "3k_main_ancillary_accessory_rites_of_zhou",
    "천상의 검": "3k_main_ancillary_weapon_ceremonial_sword_exceptional",
    "품위있는 의복": "3k_main_ancillary_armour_light_armour_earth_extraordinary",
    "황실 호위병의 극": "3k_main_ancillary_weapon_halberd_exceptional",
    "황실 활": "3k_main_ancillary_weapon_composite_bow_exceptional",
    "회색 종마": "3k_main_ancillary_mount_grey_stallion",
    "흑색 종마": "3k_main_ancillary_mount_black_stallion",
    "백색 종마": "3k_main_ancillary_mount_white_stallion",
    "적색 종마": "3k_main_ancillary_mount_red_stallion",
}

_SKILL_PHRASE_LABELS: dict[str, str] = {
    "stone_bulwark": "석벽",
    "stone_wall": "석벽",
    "earth_steadfastness": "땅의 부동심",
    "heart_of_the_earth": "땅의 부동심",
    "nature_friend": "자연의 벗",
    "friend_of_nature": "자연의 벗",
    "composure": "침착",
    "intensity": "격렬",
    "mobility": "기동",
    "meditation": "명상",
    "zeal": "열의",
    "perception": "통찰",
    "flexibility": "유연",
    "clarity": "명료",
    "dignity": "품위",
    "nobility": "고귀",
    "understanding": "이해심",
    "stability": "안정",
    "scholarship": "학식",
    "precision": "정밀",
    "intuition": "직감",
    "resourcefulness": "수완",
    "judgement": "판단",
    "judgment": "판단",
    "patience": "인내",
    "endurance": "인내",
    "reach": "도달",
    "vengeance": "복수",
    "bodyguard": "호위",
    "adamant_resolve": "금강 같은 결의",
    "tenacity_of_steel": "강철 같은 끈기",
    "tempered_deflection": "단련된 회피",
    "binding_fury": "속박하는 분노",
    "abundance": "풍부",
    "wisdom": "지혜",
    "consideration": "배려",
    "earthen_rampart": "흙벽",
    "trust": "신뢰",
    "wisdom_of_the_river": "강의 지혜",
    "stifling_deluge": "숨막히는 격류",
    "poison_volley": "독화살 일제 사격",
    "venomous_shot": "맹독 사격",
    "flames_of_the_phoenix": "봉황의 불꽃",
    "phoenix": "불사조의 불꽃",
    "final_rush": "최후의 돌격",
    "passion": "열정",
    "nature_s_ally": "자연의 벗",
    "natures_ally": "자연의 벗",
    "fervour": "열광",
    "heart_seeker": "심장 추적자",
    "tolerance": "관용",
    "harmony": "조화",
    "finesse": "기교",
    "insight": "식견",
    "purity": "순수",
    "inspiration": "고무",
    "resolve_unwavering": "흔들림 없는 결의",
    "patience_rewarded": "보상받은 인내",
    "guile": "기만",
    "guerrilla_deployment": "유격 배치",
    "fury": "격노",
    "bravery": "용맹",
    "majesty": "위엄",
}


_LABEL_SKIP_TOKENS = {
    "3k",
    "main",
    "mtu",
    "dlc04",
    "dlc05",
    "dlc06",
    "dlc07",
    "ytr",
    "ep",
    "template",
    "historical",
    "generated",
    "ancestral",
    "hero",
    "general",
    "character",
    "records",
    "record",
    "data",
    "node",
    "career",
    "ceo",
    "initial",
    "set",
    "sets",
    "key",
    "keys",
    "override",
    "source",
    "profile",
    "effect",
    "effects",
    "stat",
    "stats",
    "mod",
    "modifier",
    "localised",
    "localized",
    "title",
    "description",
}

_LABEL_TOKEN_TRANSLATIONS = {
    "earth": "토",
    "fire": "화",
    "wood": "목",
    "water": "수",
    "metal": "금",
    "expertise": "전문성",
    "resolve": "결의",
    "cunning": "책략",
    "instinct": "본능",
    "authority": "권위",
    "male": "남성",
    "female": "여성",
    "lady": "여성",
    "woman": "여성",
    "women": "여성",
    "f": "여성",
    "m": "남성",
    "model": "모델",
    "art": "이미지",
    "image": "이미지",
    "skill": "스킬",
    "skillset": "스킬셋",
    "skills": "스킬",
    "attribute": "능력치",
    "attributes": "능력치",
    "subtype": "오행",
    "age": "연령",
    "spawn": "등장",
    "range": "범위",
    "retinue": "부대",
    "unit": "부대",
    "units": "부대",
    "land": "지상",
    "melee": "근접",
    "missile": "사격",
    "weapon": "무기",
    "weapons": "무기",
    "armour": "방어구",
    "armor": "방어구",
    "defense": "방어",
    "defence": "방어",
    "attack": "공격",
    "damage": "피해",
    "ap": "관통",
    "projectile": "투사체",
    "audio": "오디오",
    "voice": "음성",
    "voiceover": "음성",
    "actor": "배우",
    "generic": "기본",
    "unique": "유니크",
    "dummy": "더미",
    "leader": "지도자",
    "king": "왕",
    "queen": "왕후",
    "emperor": "황제",
    "empress": "황후",
    "lord": "군주",
    "governor": "태수",
    "administrator": "태수",
    "minister": "관료",
    "commander": "지휘관",
    "champion": "용장",
    "strategist": "책사",
    "vanguard": "선봉장",
    "sentinel": "감시자",
    "agent": "첩보원",
    "envoy": "사절",
    "villager": "향촌 인물",
    "legendary": "전설",
    "non": "비",
    "deployable": "배치 가능",
    "satisfaction": "만족도",
    "morale": "사기",
    "movement": "이동거리",
    "replenishment": "충원",
    "supplies": "보급품",
    "charge": "돌격",
    "fatigue": "피로",
    "ambush": "매복",
    "income": "수입",
    "food": "식량",
    "diplomacy": "외교",
    "ability": "능력",
    "unlock": "해금",
    "enable": "사용 가능",
    "campaign": "캠페인",
    "battle": "전투",
    "faction": "세력",
    "army": "군단",
    "all": "전체",
    "local": "지역",
    "own": "아군",
    "enemy": "적",
    "bonus": "보너스",
    "cost": "비용",
    "construction": "건설",
    "research": "연구",
    "corruption": "부패",
    "population": "인구",
}

_ELEMENT_LABELS = {
    "earth": "토",
    "fire": "화",
    "wood": "목",
    "water": "수",
    "metal": "금",
}

_TITLE_STAT_ELEMENT_TERMS = {
    "전문성": "metal",
    "expertise": "metal",
    "결의": "wood",
    "resolve": "wood",
    "본능": "fire",
    "instinct": "fire",
    "지략": "water",
    "책략": "water",
    "cunning": "water",
    "권위": "earth",
    "authority": "earth",
}

_CHARACTER_TOKEN_LABELS = {
    "cao_cao": "조조",
    "cao_pi": "조비",
    "cao_ren": "조인",
    "cao_sang": "조상",
    "chen_gong": "진궁",
    "cheng_pu": "정보",
    "dian_wei": "전위",
    "diao_chan": "초선",
    "dong_bai": "동백",
    "dong_zhuo": "동탁",
    "fa_zheng": "법정",
    "gan_ning": "감녕",
    "gao_shun": "고순",
    "gongsun_zan": "공손찬",
    "guan_yu": "관우",
    "guo_jia": "곽가",
    "han_sui": "한수",
    "huang_zhong": "황충",
    "huang_zu": "황조",
    "jia_xu": "가후",
    "kong_rong": "공융",
    "lady_bian": "변부인",
    "bian": "변부인",
    "lady_cai_yan": "채염",
    "cai_yan": "채염",
    "lady_da_qiao": "대교",
    "da_qiao": "대교",
    "lady_diao_chan": "초선",
    "lady_sun_shangxiang": "손상향",
    "sun_shangxiang": "손상향",
    "lady_xiao_qiao": "소교",
    "xiao_qiao": "소교",
    "lady_zheng_jiang": "정강",
    "zheng_jiang": "정강",
    "liu_bei": "유비",
    "liu_biao": "유표",
    "liu_chong": "유총",
    "liu_yan": "유언",
    "liu_yao": "유요",
    "liu_zhang": "유장",
    "lu_bu": "여포",
    "lu_su": "노숙",
    "ma_chao": "마초",
    "ma_teng": "마등",
    "ma_yunlu": "마운록",
    "pang_tong": "방통",
    "pei_yuanshao": "배원소",
    "sima_ai": "사마애",
    "sima_jiong": "사마경",
    "sima_liang": "사마량",
    "sima_lun": "사마륜",
    "sima_wei": "사마위",
    "sima_yi": "사마의",
    "sima_ying": "사마영",
    "sima_yong": "사마옹",
    "sima_yue": "사마월",
    "sun_ce": "손책",
    "sun_jian": "손견",
    "sun_quan": "손권",
    "taishi_ci": "태사자",
    "wang_lang": "왕랑",
    "wei_yan": "위연",
    "wen_chou": "문추",
    "xiahou_dun": "하후돈",
    "xiahou_yuan": "하후연",
    "xu_chu": "허저",
    "xu_huang": "서황",
    "xun_you": "순유",
    "xun_yu": "순욱",
    "yan_baihu": "엄백호",
    "yan_liang": "안량",
    "yuan_shao": "원소",
    "yuan_shu": "원술",
    "zhang_bao": "장포",
    "zhang_fei": "장비",
    "zhang_liao": "장료",
    "zhang_yan": "장연",
    "zhao_yun": "조운",
    "zhou_yu": "주유",
    "zhuge_liang": "제갈량",
    "gogukcheon": "고남무",
    "go_gyesu": "고계수",
    "go_baekgo": "고백고",
    "go_balgi": "고발기",
    "go_yeonu": "고연우",
    "go_su": "고수",
    "eul_paso": "을파소",
    "go_yeon_hwa": "고연화",
    "geum_ryeong": "금령",
    "no_ri_ko": "노리코",
    "seol_hwa": "설화",
    "so_ma": "소마",
    "yeon_jiwoo": "연지우",
    "yu_hyerin": "유혜린",
    "yun_i_seo": "윤이서",
    "chae_rin": "채린",
    "hwa_ryeong": "화령",
}

_SYLLABLE_TOKEN_TRANSLATIONS = {
    "cao": "조",
    "liu": "유",
    "sun": "손",
    "zhang": "장",
    "wang": "왕",
    "yuan": "원",
    "ma": "마",
    "lu": "여",
    "guan": "관",
    "zhou": "주",
    "zhao": "조",
    "xiao": "소",
    "qiao": "교",
    "cai": "채",
    "yan": "염",
    "lan": "란",
    "lanlan": "란란",
    "jing": "정",
    "jie": "제",
    "yue": "월",
    "fang": "방",
    "min": "민",
    "yu": "우",
}


def _elapsed(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 4)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), WebHandler)
    print(f"Three Kingdoms Pack Builder UI: http://{host}:{port}", flush=True)
    server.serve_forever()


def _log_api_build_error(error: BaseException) -> None:
    log_path = ROOT / "work" / "api-build-error.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] /api/build failed\n")
        handle.write("".join(traceback.format_exception(type(error), error, error.__traceback__)))


def _static_web_file(path: str) -> str | None:
    if path == "/":
        return "index.html"
    if not path.startswith("/"):
        return None
    name = path[1:]
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return None
    candidate = STATIC_ROOT / name
    if candidate.suffix.lower() not in WEB_STATIC_SUFFIXES:
        return None
    if not candidate.is_file():
        return None
    return name


class WebHandler(BaseHTTPRequestHandler):
    server_version = "TKPackBuilderWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        static_name = _static_web_file(path)
        if static_name is not None:
            self._serve_static(static_name)
            return
        if path == "/api/health":
            self._send_json({"ok": True})
            return
        if path == "/api/asset":
            self._serve_pack_asset(parse_qs(parsed.query))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/api/open":
                self._send_json(open_pack_payload(payload))
                return
            if self.path == "/api/validate":
                self._send_json(validate_payload(payload))
                return
            if self.path == "/api/build":
                self._send_json(build_payload(payload))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as error:
            if self.path == "/api/build":
                _log_api_build_error(error)
            self._send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            if self.path == "/api/build":
                _log_api_build_error(error)
            self._send_json({"ok": False, "error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_static(self, name: str) -> None:
        path = STATIC_ROOT / name
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_pack_asset(self, query: dict[str, list[str]]) -> None:
        input_path = query.get("inputPath", [""])[0]
        requested_packed_path = query.get("path", [""])[0]
        if not input_path or not requested_packed_path:
            self.send_error(HTTPStatus.BAD_REQUEST, "inputPath and path are required")
            return
        packed_path = _real_packed_asset_path(requested_packed_path)
        pack_path = _resolve_user_path(input_path)
        extracted = _extracted_asset_path(pack_path, requested_packed_path)
        if extracted.is_file():
            content_type = mimetypes.guess_type(extracted.name)[0] or "application/octet-stream"
            self._send_bytes(extracted.read_bytes(), content_type, cache_hit=True)
            return
        extracted_any = _find_extracted_asset(requested_packed_path) or _find_extracted_asset(packed_path)
        if extracted_any is not None:
            content_type = mimetypes.guess_type(extracted_any.name)[0] or "application/octet-stream"
            self._send_bytes(extracted_any.read_bytes(), content_type, cache_hit=True)
            return
        cached = PACK_CACHE.get_asset(pack_path, packed_path)
        if cached is not None:
            content_type, data = cached
            _write_extracted_asset(extracted, data)
            self._send_bytes(data, content_type, cache_hit=True)
            return

        session = None
        try:
            _ensure_rpfm_server()
            if not pack_path.is_file():
                fallback_pack = _fallback_pack_path(pack_path)
                if fallback_pack is not None:
                    pack_path = fallback_pack
                    extracted = _extracted_asset_path(pack_path, requested_packed_path)
                    if extracted.is_file():
                        content_type = mimetypes.guess_type(extracted.name)[0] or "application/octet-stream"
                        self._send_bytes(extracted.read_bytes(), content_type, cache_hit=True)
                        return
            session = adapter_for("rpfm").open_pack(pack_path)
            data = session.read_file_bytes(packed_path)
        except Exception as error:
            self.send_error(HTTPStatus.NOT_FOUND, str(error))
            return
        finally:
            if session is not None:
                _close_session(session)
        content_type = mimetypes.guess_type(packed_path)[0] or "application/octet-stream"
        PACK_CACHE.put_asset(pack_path, packed_path, content_type, data)
        _write_extracted_asset(extracted, data)
        self._send_bytes(data, content_type, cache_hit=False)

    def _send_bytes(self, data: bytes, content_type: str, cache_hit: bool = False) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "private, max-age=3600")
        self.send_header("x-pack-cache", "hit" if cache_hit else "miss")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _extracted_asset_path(pack_path: Path, packed_path: str) -> Path:
    pack_id = hashlib.sha1(str(pack_path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:12]
    clean_parts = [
        part
        for part in packed_path.replace("\\", "/").split("/")
        if part and part not in {".", ".."}
    ]
    return EXTRACTED_ASSET_ROOT / pack_id / Path(*clean_parts)


def _source_scoped_asset_path(source_path: Path, packed_path: str) -> str:
    source_id = hashlib.sha1(str(source_path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:12]
    normalized = packed_path.replace("\\", "/")
    return f"{IMAGE_ONLY_ASSET_PREFIX}/{source_id}/{normalized}"


def _real_packed_asset_path(packed_path: str) -> str:
    normalized = packed_path.replace("\\", "/")
    prefix = f"{IMAGE_ONLY_ASSET_PREFIX}/"
    if not normalized.startswith(prefix):
        return normalized
    parts = normalized.split("/", 2)
    return parts[2] if len(parts) >= 3 else normalized


def _write_extracted_asset(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.stat().st_size != len(data):
        path.write_bytes(data)


def _find_extracted_asset(packed_path: str) -> Path | None:
    clean_parts = [
        part
        for part in packed_path.replace("\\", "/").split("/")
        if part and part not in {".", ".."}
    ]
    if not clean_parts or not EXTRACTED_ASSET_ROOT.is_dir():
        return None
    suffix = Path(*clean_parts)
    for pack_dir in EXTRACTED_ASSET_ROOT.iterdir():
        candidate = pack_dir / suffix
        if candidate.is_file():
            return candidate
    return None


def _fallback_pack_path(pack_path: Path) -> Path | None:
    candidates = [
        ROOT / "work" / "packs" / pack_path.name,
        ROOT / "work" / "packs" / "refs" / pack_path.name,
        ROOT / "work" / "packs" / "my_hero.pack",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _dedicated_armour_pool_status(
    payload: dict[str, Any],
) -> DedicatedArmourPoolStatus:
    if not DEDICATED_ARMOUR_ENGINE_ENABLED:
        return DedicatedArmourPoolStatus(
            available=False,
            reason=(
                "전용 갑옷 복제 기능은 실제 게임 시작 충돌이 확인되어 "
                "안전을 위해 비활성화되었습니다."
            ),
            active_ccd=None,
            pool=None,
        )
    try:
        pools = load_dedicated_armour_pools(DEDICATED_ARMOUR_POOL_ROOTS)
    except DedicatedArmourPoolError as error:
        return DedicatedArmourPoolStatus(
            available=False,
            reason=f"전용 갑옷 슬롯 풀을 읽지 못했습니다: {error}",
            active_ccd=None,
            pool=None,
        )
    input_path = payload.get("inputPath")
    source_pack = _resolve_user_path(input_path) if input_path else None
    pack_paths = ordered_active_ccd_pack_paths(
        source_pack,
        _reference_pack_paths(payload),
    )
    status = resolve_pool_status(pools, pack_paths)
    if status.available and status.pool is not None:
        try:
            verify_pool_asset(status.pool)
        except DedicatedArmourPoolError as error:
            return DedicatedArmourPoolStatus(
                available=False,
                reason=str(error),
                active_ccd=status.active_ccd,
                pool=None,
            )
    return status


def _validated_dedicated_armour_pool(
    payload: dict[str, Any],
    recipe: Recipe,
) -> DedicatedArmourPool | None:
    # Armour edits are implemented as generated-character-only hidden skill
    # effects. They no longer consume a precompiled CEO/CCD armour slot.
    return None


@profiled
def open_pack_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if current_profile() != BASE_PROFILE:
        summary = _load_internal_material_summary()
        return {"ok": True, "analysis": {}, "characters": {
            "pack": summary, "vanilla": {"available": False}, "referencePacks": []},
            "cache": {"hit": True}, "timings": {}}
    started_at = time.perf_counter()
    timings: dict[str, float] = {}
    input_path = payload.get("inputPath")
    include_vanilla = bool(payload.get("includeVanilla"))
    reference_paths = _reference_pack_paths(payload)
    if not input_path:
        raise ValueError("inputPath is required.")
    pack_path = _resolve_user_path(input_path)
    uses_core_reference = _uses_core_reference_pack(reference_paths)
    asset_cache_token = _local_asset_cache_token()
    reference_cache_token = _reference_cache_token(reference_paths)
    internal_material_token = _internal_material_cache_token()
    open_cache_token = _open_payload_cache_token(
        asset_cache_token,
        reference_cache_token,
        internal_material_token,
    )
    if not payload.get("forceRefresh"):
        cache_started = time.perf_counter()
        cached = PACK_CACHE.get_open_payload(pack_path, include_vanilla, reference_paths, open_cache_token) if pack_path.exists() else None
        timings["cacheLookup"] = _elapsed(cache_started)
        if cached is not None:
            _enrich_korea_addon_character_data(cached.get("characters", {}))
            _normalize_character_data_runtime_equipment_keys(cached.get("characters"))
            cached["dedicatedArmour"] = _dedicated_armour_pool_status(payload).to_dict()
            cached["timings"] = {**timings, "total": _elapsed(started_at)}
            cached["assetCacheToken"] = asset_cache_token
            cached["openCacheToken"] = open_cache_token
            return cached
        snapshot_started = time.perf_counter()
        snapshot = _load_reference_snapshot(
            asset_cache_token,
            reference_cache_token,
            internal_material_token,
            pack_path=pack_path,
            include_vanilla=include_vanilla,
        )
        timings["snapshotLookup"] = _elapsed(snapshot_started)
        if snapshot is not None:
            snapshot["dedicatedArmour"] = _dedicated_armour_pool_status(payload).to_dict()
            snapshot["timings"] = {**timings, "total": _elapsed(started_at)}
            snapshot["assetCacheToken"] = asset_cache_token
            snapshot["openCacheToken"] = open_cache_token
            return snapshot

    open_started = time.perf_counter()
    session = _open_session(payload)
    timings["openSession"] = _elapsed(open_started)
    try:
        analyze_started = time.perf_counter()
        analysis = analyze_pack(session).to_dict()
        timings["analyze"] = _elapsed(analyze_started)
        read_started = time.perf_counter()
        character_data = read_character_data(
            session,
            include_vanilla=include_vanilla,
            reference_paths=reference_paths,
            adapter_name=payload.get("adapter", "auto"),
        )
        timings["readCharacterData"] = _elapsed(read_started)
        enrich_started = time.perf_counter()
        _enrich_korea_addon_character_data(character_data)
        timings["enrich"] = _elapsed(enrich_started)
        cache_write_started = time.perf_counter()
        PACK_CACHE.put_open_payload(pack_path, include_vanilla, analysis, character_data, reference_paths, open_cache_token)
        _write_reference_snapshot(
            analysis,
            character_data,
            asset_cache_token,
            reference_cache_token,
            internal_material_token,
            pack_path=pack_path,
            include_vanilla=include_vanilla,
        )
        timings["cacheWrite"] = _elapsed(cache_write_started)
        timings["total"] = _elapsed(started_at)
        return {
            "ok": True,
            "analysis": analysis,
            "characters": character_data,
            "dedicatedArmour": _dedicated_armour_pool_status(payload).to_dict(),
            "cache": {
                "hit": False,
                "path": str(PACK_CACHE.db_path),
            },
            "assetCacheToken": asset_cache_token,
            "openCacheToken": open_cache_token,
            "timings": timings,
        }
    finally:
        _close_session(session)


def _local_asset_cache_token() -> str:
    roots = [
        EXTRACTED_ASSET_ROOT / "hby_generated_character_sets",
        EXTRACTED_ASSET_ROOT / "17309a40b912",
    ]
    if current_profile() != BASE_PROFILE:
        roots.append(EXTRACTED_ASSET_ROOT / "profile_190")
    if current_profile() == '190-korea':
        roots.append(EXTRACTED_ASSET_ROOT / "profile_korea")
    count = 0
    latest_mtime_ns = 0
    total_size = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            count += 1
            latest_mtime_ns = max(latest_mtime_ns, stat.st_mtime_ns)
            total_size += stat.st_size
    return f"portrait-assets:{count}:{latest_mtime_ns}:{total_size}"


def _is_extracted_asset_scan_root(path: Path) -> bool:
    name = path.name.lower()
    if name == "codex_generated":
        return False
    return not (
        "backup" in name
        or name.startswith("before_")
        or "_before_" in name
    )


def _reference_cache_token(reference_paths: list[Path]) -> str:
    parts: list[str] = []
    for path in reference_paths:
        try:
            resolved = path.resolve()
            stat = resolved.stat()
            parts.append(f"{resolved}|{stat.st_mtime_ns}|{stat.st_size}")
        except OSError:
            parts.append(f"{path}|missing")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _file_cache_fingerprint(path: Path) -> dict[str, Any]:
    try:
        resolved = path.resolve()
        stat = resolved.stat()
    except OSError:
        return {
            "path": str(path),
            "missing": True,
        }
    return {
        "path": str(resolved),
        "mtimeNs": stat.st_mtime_ns,
        "sizeBytes": stat.st_size,
    }


def _file_cache_key(paths: list[Path]) -> str:
    payload = [_file_cache_fingerprint(path) for path in paths]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _open_payload_cache_token(
    asset_cache_token: str,
    reference_cache_token: str,
    internal_material_token: dict[str, Any],
) -> str:
    payload = {
        "version": OPEN_PAYLOAD_CACHE_SCHEMA_VERSION,
        "assetCacheToken": asset_cache_token,
        "referenceCacheToken": reference_cache_token,
        "internalMaterialToken": internal_material_token,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _pack_snapshot_fingerprint(pack_path: Path | None, include_vanilla: bool) -> dict[str, Any]:
    if pack_path is None:
        return {}
    try:
        resolved = pack_path.resolve()
        stat = resolved.stat()
    except OSError:
        return {
            "inputPath": str(pack_path),
            "missing": True,
            "includeVanilla": bool(include_vanilla),
        }
    return {
        "inputPath": str(resolved),
        "mtimeNs": stat.st_mtime_ns,
        "sizeBytes": stat.st_size,
        "includeVanilla": bool(include_vanilla),
    }


def _load_reference_snapshot(
    asset_cache_token: str = "",
    reference_cache_token: str = "",
    internal_material_token: dict[str, Any] | None = None,
    *,
    pack_path: Path | None = None,
    include_vanilla: bool = False,
) -> dict[str, Any] | None:
    if not profile_resource(REFERENCE_SNAPSHOT, "reference_snapshot.json").is_file():
        return None
    with profile_resource(REFERENCE_SNAPSHOT, "reference_snapshot.json").open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schemaVersion") != REFERENCE_SNAPSHOT_VERSION:
        return None
    if payload.get("assetCacheToken", "") != asset_cache_token:
        return None
    if payload.get("referenceCacheToken", "") != reference_cache_token:
        return None
    if payload.get("internalMaterialToken") != (internal_material_token or _internal_material_cache_token()):
        return None
    if pack_path is not None and payload.get("inputPack") != _pack_snapshot_fingerprint(pack_path, include_vanilla):
        return None
    characters = payload.get("characters", {})
    _enrich_korea_addon_character_data(characters)
    _normalize_character_data_runtime_equipment_keys(characters)
    return {
        "ok": True,
        "analysis": payload.get("analysis", {}),
        "characters": characters,
        "cache": {
            "hit": True,
            "type": "reference_snapshot",
            "path": str(profile_resource(REFERENCE_SNAPSHOT, "reference_snapshot.json")),
        },
    }


def _enrich_korea_addon_character_data(character_data: dict[str, Any]) -> None:
    enrichment_token = _character_enrichment_token()
    if character_data.get("_mtuEnrichmentToken") == enrichment_token:
        return
    _merge_internal_material_character_summary(character_data)
    for summary in _iter_character_summaries(character_data):
        for character in summary.get("characters", []):
            _clear_stale_korea_metadata(character)
    _normalize_character_data_runtime_equipment_keys(character_data)
    character_data["_mtuEnrichmentToken"] = enrichment_token


def _apply_korea_addon_metadata_to_characters(character_data: dict[str, Any]) -> None:
    for summary in _iter_character_summaries(character_data):
        for character in summary.get("characters", []):
            if not isinstance(character, dict):
                continue
            key = str(character.get("key", ""))
            metadata = korea_character_metadata(key) or {}
            if not metadata:
                _clear_stale_korea_metadata(character)
                continue
            display_name_hint = str(metadata.get("koreaDisplayNameHint") or "")
            if display_name_hint:
                character["displayName"] = display_name_hint
                character["label"] = display_name_hint
            character.update(metadata)
            if display_name_hint:
                character["koreaDisplayNameHint"] = display_name_hint


KOREA_METADATA_FIELDS = {
    "isKoreaAddon",
    "koreaFactionKey",
    "koreaFaction",
    "koreaFactionLabel",
    "koreaRole",
    "koreaSubtype",
    "koreaSourceScript",
    "koreaDisplayNameHint",
    "koreaRosterHidden",
    "koreaHiddenReason",
}


def _clear_stale_korea_metadata(character: dict[str, Any]) -> None:
    for field in KOREA_METADATA_FIELDS:
        character.pop(field, None)


def _character_enrichment_token() -> str:
    payload = {
        "version": 14,
        "internalMaterialToken": _internal_material_cache_token(),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _normalize_character_data_runtime_equipment_keys(character_data: Any) -> None:
    if not isinstance(character_data, dict):
        return
    for summary in _iter_character_summaries(character_data):
        characters = summary.get("characters")
        if not isinstance(characters, list):
            continue
        for character in characters:
            if not isinstance(character, dict):
                continue
            _normalize_character_runtime_equipment_keys(character)


def _normalize_character_runtime_equipment_keys(character: dict[str, Any]) -> None:
    stats = character.get("combatStats")
    if not isinstance(stats, dict):
        return
    armour_ceo = _runtime_armour_ceo_key(stats.get("armourCeo"))
    if armour_ceo:
        stats["armourCeo"] = armour_ceo


def _merge_internal_material_character_summary(character_data: dict[str, Any]) -> None:
    target_summary = character_data.get("pack")
    if not isinstance(target_summary, dict) or not profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json").is_file():
        return
    try:
        internal_summary = _load_internal_material_summary()
    except Exception:
        return

    target_characters = target_summary.setdefault("characters", [])
    if not isinstance(target_characters, list):
        return
    target_by_key = {
        str(character.get("key", "")).lower(): character
        for character in target_characters
        if isinstance(character, dict)
    }
    for character in internal_summary.get("characters", []):
        if not isinstance(character, dict):
            continue
        character = _sanitize_stale_korea_character(character)
        key = str(character.get("key", "")).lower()
        if not key:
            continue
        if key in target_by_key:
            _merge_internal_material_character(target_by_key[key], character)
        else:
            target_characters.append(character)
            target_by_key[key] = character
    target_summary["characters"] = _dedupe_characters_by_key(target_characters)
    _merge_summary_supporting_rows(target_summary, internal_summary)
    _repair_image_only_character_labels(target_summary)


def _merge_internal_material_character(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    incoming = _sanitize_stale_korea_character(incoming)
    for field, value in incoming.items():
        if field == "combatStats":
            target[field] = _merge_combat_stats_preserving_target(
                target.get(field) if isinstance(target.get(field), dict) else {},
                value if isinstance(value, dict) else {},
            )
            continue
        if field in {"details", "templateRow"} and _has_useful_value(target.get(field)):
            continue
        if field in {"displayName", "label", "forename"} and _is_bad_display_hint(value):
            if _has_useful_value(target.get(field)):
                continue
        if _has_useful_value(value) or not _has_useful_value(target.get(field)):
            target[field] = value


def _merge_combat_stats_preserving_target(
    target_stats: dict[str, Any],
    incoming_stats: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(incoming_stats)
    for key, value in target_stats.items():
        if _has_useful_value(value) or not _has_useful_value(merged.get(key)):
            merged[key] = value
    return merged


def _has_useful_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _sanitize_stale_korea_character(character: dict[str, Any]) -> dict[str, Any]:
    if current_profile() != BASE_PROFILE:
        return character
    if not _has_stale_korea_metadata(character):
        return character
    sanitized = dict(character)
    _clear_stale_korea_metadata(sanitized)
    fallback_name = _fallback_display_name_for_stale_korea_character(sanitized)
    if fallback_name:
        sanitized["displayName"] = fallback_name
        sanitized["label"] = fallback_name
    else:
        sanitized.pop("displayName", None)
        sanitized.pop("label", None)
    return sanitized


def _has_stale_korea_metadata(character: dict[str, Any]) -> bool:
    key = str((character.get("templateRow") or {}).get("key") or character.get("key") or "")
    if korea_character_metadata(key):
        return False
    return any(field in character for field in KOREA_METADATA_FIELDS)


def _fallback_display_name_for_stale_korea_character(character: dict[str, Any]) -> str:
    key = str((character.get("templateRow") or {}).get("key") or character.get("key") or "")
    korean_name = korean_character_name(key)
    if korean_name:
        return korean_name
    token = _character_token_from_template(key)
    if token:
        return token.replace("_", " ")
    title_label = str((character.get("titleInfo") or {}).get("label") or "").strip()
    if title_label:
        return title_label
    return _friendly_character_label(key)


BAD_DISPLAY_HINTS = {
    "잘못된힌트",
    "잘못된 힌트",
    "wronghint",
    "wrong hint",
    "badhint",
    "bad hint",
    "invalidhint",
    "invalid hint",
}


def _is_bad_display_hint(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = re.sub(r"[\s_\-]+", "", text.casefold())
    return normalized in {
        re.sub(r"[\s_\-]+", "", hint.casefold())
        for hint in BAD_DISPLAY_HINTS
    }


def _repair_image_only_character_labels(summary: dict[str, Any]) -> None:
    characters = summary.get("characters", [])
    art_sets = summary.get("artSets", [])
    if not isinstance(characters, list) or not isinstance(art_sets, list):
        return
    art_labels = {
        str(art_set.get("key") or "").lower(): str(art_set.get("label") or "").strip()
        for art_set in art_sets
        if isinstance(art_set, dict) and art_set.get("key")
    }
    for character in characters:
        if not isinstance(character, dict):
            continue
        if not (character.get("virtualImageOnly") or character.get("imageOnly")):
            continue
        current = str(character.get("displayName") or character.get("label") or "").strip()
        if current and not _is_bad_display_hint(current):
            continue
        art_key = str(character.get("artSet") or character.get("key") or "").lower()
        replacement = art_labels.get(art_key, "")
        if not replacement or _is_bad_display_hint(replacement):
            replacement = _image_only_character_label_fallback(character)
        if not replacement or _is_bad_display_hint(replacement):
            continue
        character["displayName"] = replacement
        character["label"] = replacement
        if _is_bad_display_hint(character.get("forename")) or not character.get("forename"):
            character["forename"] = replacement


def _image_only_character_label_fallback(character: dict[str, Any]) -> str:
    for field in ("portrait", "card"):
        value = str(character.get(field) or "").strip()
        if value:
            return _friendly_image_character_label(value)
    for field in ("portraitImagePath", "cardImagePath"):
        value = str(character.get(field) or "").replace("\\", "/").strip("/")
        if not value:
            continue
        parts = [part for part in value.split("/") if part]
        if "characters" in parts:
            index = parts.index("characters")
            if index + 1 < len(parts):
                return _friendly_image_character_label(parts[index + 1])
        stem = Path(value).stem
        if stem:
            return _friendly_image_character_label(stem)
    key = str(character.get("artSet") or character.get("key") or "").strip()
    return _friendly_character_label(key)


def _load_internal_material_summary() -> dict[str, Any]:
    cache_key = json.dumps(_internal_material_cache_token(), ensure_ascii=False, sort_keys=True)
    return _load_internal_material_summary_for_cache_key(cache_key)


@lru_cache(maxsize=2)
def _load_internal_material_summary_for_cache_key(_cache_key: str) -> dict[str, Any]:
    cached = _read_internal_material_summary_cache()
    if cached is not None:
        return cached

    session = _open_compact_internal_material_session(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json"))
    tables = _read_internal_material_reference_tables(session)
    asset_files = session.list_files()
    asset_sources: dict[str, str] = {}
    known_assets = set(asset_files)
    _merge_internal_asset_manifest(asset_files, asset_sources, known_assets)
    _merge_extracted_asset_inventory(asset_files, asset_sources, known_assets)
    summary = summarize_character_tables(
        tables,
        _read_all_loc_text(session),
        asset_files,
        asset_sources,
        include_skill_trees=True,
    )
    _write_internal_material_summary_cache(summary)
    return summary


def _open_compact_internal_material_session(path: Path) -> MaterialPackSession:
    session = MaterialPackSession.open(path)
    try:
        from scripts.build_reference_core_pack import select_loc_files, select_tables
    except Exception:
        return session
    try:
        tables = select_tables(session.payload)
        loc_files = select_loc_files(session.payload, tables)
        for path, table in session.payload.get("tables", {}).items():
            if path.split('/')[1] in {"start_pos_characters_tables", "start_pos_factions_tables"}:
                tables[path] = table
        for path, loc in session.payload.get("loc", {}).items():
            for key, value in loc.get("rows", {}).items():
                if key.startswith("factions_screen_name_"):
                    loc_files.setdefault(path, {})[key] = value
    except Exception:
        return session
    compact_payload = {
        "baseline": session.payload.get("baseline"),
        "tables": tables,
        "loc": {
            loc_path: {"rows": rows}
            for loc_path, rows in loc_files.items()
        },
        "assets": {},
    }
    return MaterialPackSession(path, compact_payload)


def _internal_material_cache_token() -> dict[str, Any]:
    from .title_registry import REGISTRY_PATH
    from .korean_patch import PATCH_PATH
    catalog_paths = _title_effect_catalog_paths()
    skill_catalog_paths = _skill_effect_catalog_paths()
    paths = [
        profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json"),
        Path(__file__),
        Path(__file__).with_name("image_catalog.py"),
        INTERNAL_ASSET_MANIFEST,
        PATCH_PATH,
        *catalog_paths,
        *skill_catalog_paths,
        profile_resource(REGISTRY_PATH, "verified_ceo_registry.json"),
    ]
    return {
        "version": 34,
        "sourceProfile": current_profile(),
        "localAssets": _local_asset_cache_token(),
        "sources": {
            str(path): _file_cache_fingerprint(path)
            for path in paths
            if path.is_file()
        },
    }


def _read_internal_material_summary_cache() -> dict[str, Any] | None:
    if not profile_resource(INTERNAL_MATERIAL_SUMMARY, "materials.v015.summary.json").is_file():
        return None
    try:
        with profile_resource(INTERNAL_MATERIAL_SUMMARY, "materials.v015.summary.json").open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("portable"):
        from .portable_cache import load_portable_summary
        summary = load_portable_summary(payload, ROOT, current_profile())
        if isinstance(summary, dict):
            _write_internal_material_summary_cache(summary)
            return _sanitize_summary_stale_korea_metadata(summary)
    if payload.get("cache") != _internal_material_cache_token():
        return None
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None
    return _sanitize_summary_stale_korea_metadata(summary)


def _write_internal_material_summary_cache(summary: dict[str, Any]) -> None:
    summary = _sanitize_summary_stale_korea_metadata(summary)
    try:
        profile_resource(INTERNAL_MATERIAL_SUMMARY, "materials.v015.summary.json").parent.mkdir(parents=True, exist_ok=True)
        with profile_resource(INTERNAL_MATERIAL_SUMMARY, "materials.v015.summary.json").open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "cache": _internal_material_cache_token(),
                    "summary": summary,
                },
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
    except OSError:
        return


def _sanitize_summary_stale_korea_metadata(summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return summary
    characters = summary.get("characters")
    if not isinstance(characters, list):
        return summary
    cleaned = [
        _sanitize_stale_korea_character(character) if isinstance(character, dict) else character
        for character in characters
    ]
    if cleaned == characters:
        return summary
    sanitized = dict(summary)
    sanitized["characters"] = cleaned
    return sanitized


def _iter_character_summaries(character_data: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    pack_summary = character_data.get("pack")
    if isinstance(pack_summary, dict):
        summaries.append(pack_summary)
    vanilla = character_data.get("vanilla", {})
    vanilla_summary = vanilla.get("summary") if isinstance(vanilla, dict) else None
    if isinstance(vanilla_summary, dict):
        summaries.append(vanilla_summary)
    for report in character_data.get("referencePacks", []):
        if isinstance(report, dict) and isinstance(report.get("summary"), dict):
            summaries.append(report["summary"])
    return summaries


def _merge_auxiliary_catalog_characters(character_data: dict[str, Any]) -> None:
    # AW image-only packs do not contain the full in-game composite portrait set,
    # so keep them out of the editor catalog instead of offering broken choices.
    return


@lru_cache(maxsize=1)
def _load_internal_character_catalog_pack() -> dict[str, Any] | None:
    if not INTERNAL_CHARACTER_CATALOG.is_file():
        return None
    try:
        with INTERNAL_CHARACTER_CATALOG.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    summary = payload.get("characters", {}).get("pack")
    return summary if isinstance(summary, dict) else None


def _is_aw_image_only_character(character: dict[str, Any]) -> bool:
    if not (character.get("virtualImageOnly") or character.get("imageOnly")):
        return False
    text = " ".join(
        str(character.get(field, ""))
        for field in [
            "sourceTag",
            "referenceSourcePath",
            "portraitImageSourcePath",
            "cardImageSourcePath",
            "portraitImagePath",
            "cardImagePath",
            "sourcePackName",
            "sourceIdentity",
            "key",
        ]
    ).lower()
    return any(token in text for token in ["aw-design", "aw addon", "aw_", "aw-"])


def _dedupe_characters_by_key(characters: list[Any]) -> list[Any]:
    by_key: dict[str, dict[str, Any]] = {}
    key_order: list[str] = []
    passthrough: list[Any] = []
    for character in characters:
        if not isinstance(character, dict):
            passthrough.append(character)
            continue
        key = str(character.get("key", "")).lower()
        if not key:
            passthrough.append(character)
            continue
        if key not in by_key:
            key_order.append(key)
        by_key[key] = character
    return passthrough + [by_key[key] for key in key_order]


def _merge_summary_supporting_rows(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in [
        "artSets",
        "ageRanges",
        "initialCeos",
        "retinues",
        "attributeSets",
        "titleCatalog",
        "skillSets",
        "subtypes",
        "landUnits",
        "mainUnits",
        "retinueSlotInitialUnits",
    ]:
        _merge_list_by_key(target, source, field)
    _merge_skill_tree_summary(target, source)
    for field in ["artRowsBySet", "attributeStatsBySet", "locKeys"]:
        target_dict = target.setdefault(field, {})
        source_dict = source.get(field, {})
        if isinstance(target_dict, dict) and isinstance(source_dict, dict):
            for key, value in source_dict.items():
                target_dict.setdefault(key, value)


def _merge_skill_tree_summary(target: dict[str, Any], source: dict[str, Any]) -> None:
    target_trees = target.setdefault("skillTrees", {})
    source_trees = source.get("skillTrees", {})
    if not isinstance(target_trees, dict) or not isinstance(source_trees, dict):
        return

    target_romance = target_trees.setdefault("romance", [])
    source_romance = source_trees.get("romance", [])
    if isinstance(target_romance, list) and isinstance(source_romance, list):
        by_key = {
            str(tree.get("key") or ""): tree
            for tree in target_romance
            if isinstance(tree, dict) and tree.get("key")
        }
        for tree in source_romance:
            if not isinstance(tree, dict):
                continue
            key = str(tree.get("key") or "")
            if key and key not in by_key:
                target_romance.append(tree)
                by_key[key] = tree
        target_romance.sort(key=lambda item: str(item.get("key") or "") if isinstance(item, dict) else "")
        target_trees["nodeCount"] = sum(
            len(tree.get("nodes") or [])
            for tree in target_romance
            if isinstance(tree, dict)
        )

    target_index = target_trees.setdefault("skillIndex", {})
    source_index = source_trees.get("skillIndex", {})
    if isinstance(target_index, dict) and isinstance(source_index, dict):
        for key, value in source_index.items():
            existing = target_index.get(key)
            if not isinstance(existing, dict):
                target_index[key] = value
                continue
            if not isinstance(value, dict):
                continue
            _merge_localized_skill_index_entry(existing, value)
        _add_catalog_skill_index_entries(target_index)


def _merge_localized_skill_index_entry(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Overlay fresher Korean metadata without replacing the real DB skill row."""
    for field in ("name", "description", "effectSummary"):
        incoming = str(source.get(field) or "").strip()
        current = str(target.get(field) or "").strip()
        if incoming and (
            not current
            or (_contains_hangul(incoming) and not _contains_hangul(current))
            or (
                field == "effectSummary"
                and _has_raw_english_effect_name(current)
                and not _has_raw_english_effect_name(incoming)
            )
        ):
            target[field] = source[field]

    for field in ("effectRows", "effectDataSource", "element", "source", "owner"):
        incoming = source.get(field)
        if incoming not in (None, "", [], {}) and target.get(field) in (None, "", [], {}):
            target[field] = incoming

    if source.get("exclusive"):
        target["exclusive"] = True


def _merge_list_by_key(target: dict[str, Any], source: dict[str, Any], field: str) -> None:
    target_rows = target.setdefault(field, [])
    source_rows = source.get(field, [])
    if not isinstance(target_rows, list) or not isinstance(source_rows, list):
        return
    existing = {
        _row_identity(row): row
        for row in target_rows
        if isinstance(row, dict) and _row_identity(row)
    }
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        identity = _row_identity(row)
        if not identity:
            continue
        if identity in existing:
            if _catalog_source_rank(row) > _catalog_source_rank(existing[identity]):
                existing[identity].update(row)
            continue
        target_rows.append(row)
        existing[identity] = row


def _row_identity(row: dict[str, Any]) -> str:
    if row.get("retinue") and row.get("slotIndex") is not None:
        return f"{row.get('retinue')}:{row.get('slotIndex')}"
    for field in [
        "key",
        "artSet",
        "art_set_id",
        "ageRange",
        "initialCeo",
        "ceoNodeKey",
        "retinue",
        "attributeSet",
        "skillSet",
        "subtype",
        "landUnitKey",
        "mainUnitKey",
    ]:
        value = row.get(field)
        if value:
            return str(value)
    return ""


def _catalog_source_rank(row: dict[str, Any] | None) -> int:
    if not row:
        return 0
    explicit_rank = row.get("sourceRank") if "sourceRank" in row else row.get("_sourceRank")
    if explicit_rank not in {None, ""}:
        try:
            return int(explicit_rank)
        except (TypeError, ValueError):
            pass
    text = " ".join(
        str(row.get(field, "") or "").lower()
        for field in (
            "_sourceTablePath",
            "_referenceSourcePath",
            "_externalImageSetSourcePath",
            "sourceTablePath",
            "referenceSourcePath",
            "sourcePackName",
            "sourceTag",
            "key",
            "art_set_id",
            "attributeSet",
            "ceoNodeKey",
        )
    )
    if "hby_" in text or "hby " in text:
        return 95
    if (
        "3k_mtu" in text
        or "_mtu_characters" in text
        or "/_mtu" in text
        or "\\_mtu" in text
        or "tables/_mtu" in text
    ):
        return 90
    if (
        "!!ironic_addon_korea" in text
        or "190expande_korea_addon" in text
        or "korea_addon" in text
        or "korea_tweak" in text
        or "korea_generics" in text
        or "ironic_korea" in text
        or "ironic_culture_korea" in text
        or "korean_unique" in text
        or "korean_unque" in text
        or "3k_mod_template_historical_" in text
    ):
        return 80
    if "190_expanded" in text or "190 expanded" in text:
        return 70
    if "ironic_" in text or "/ironic" in text or "\\ironic" in text:
        return 60
    if "database.pack" in text or "/data__" in text or "\\data__" in text or "tables/data__" in text:
        return 10
    if "/data" in text or "\\data" in text or "data.pack" in text:
        return 15
    if "3k_main" in text or "3k_dlc" in text or "3k_ytr" in text or "ep_" in text:
        return 30
    if row.get("_referenceSourcePath") or row.get("referenceSourcePath") or row.get("_sourceTablePath"):
        return 50
    return 100


def _catalog_source_tag(row: dict[str, Any] | None) -> str:
    rank = _catalog_source_rank(row)
    if rank >= 95:
        return "MY"
    if rank >= 90:
        return "MTU"
    text = " ".join(
        str((row or {}).get(field, "") or "").lower()
        for field in ("_sourceTablePath", "_referenceSourcePath", "sourceTablePath", "referenceSourcePath")
    )
    if "database.pack" in text or "/data" in text or "\\data" in text:
        return "DATA"
    if rank >= 70:
        return "KR"
    if (row or {}).get("_referenceSourcePath") or (row or {}).get("referenceSourcePath"):
        return "REF"
    return "PACK"


def _dedupe_catalog_entries(
    rows: list[dict[str, Any]],
    key_func: Any,
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = key_func(row)
        if not key:
            continue
        if key not in by_key:
            by_key[key] = row
            order.append(key)
            continue
        if _catalog_source_rank(row) > _catalog_source_rank(by_key[key]):
            by_key[key] = row
    return [by_key[key] for key in order]


def _title_catalog_score(row: dict[str, Any]) -> tuple[int, int, int, int]:
    label = str(row.get("label") or "")
    return (
        1 if _contains_hangul(label) else 0,
        1 if row.get("effectSummary") or row.get("effects") else 0,
        1 if row.get("description") else 0,
        _catalog_source_rank(row),
    )


def _normalize_common_title_role(role: str) -> str:
    normalized = str(role or "").strip().lower()
    return COMMON_TITLE_ROLE_ALIASES.get(normalized, normalized)


def _common_title_match_from_text(value: Any) -> tuple[str, str] | None:
    text = str(value or "").lower()
    if not text or "legendary" in text or "generic_bandit" in text or "nanman" in text:
        return None
    role_pattern = r"(agent|clerk|envoy|general|governor|minister|merchant|villager)"
    element_pattern = r"(metal|wood|water|fire|earth)"
    patterns = (
        rf"generic_[mf]_{element_pattern}_{role_pattern}(?:$|[^a-z0-9])",
        rf"template_generic_{element_pattern}_{role_pattern}_normal_[mf]_hero",
        rf"korea_template_generic_{element_pattern}_{role_pattern}_normal_[mf]_hero",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        element = match.group(1)
        role = _normalize_common_title_role(match.group(2))
        if (element, role) in COMMON_TITLE_CATALOG:
            return element, role
    return None


def _common_title_info_for_values(*values: Any) -> dict[str, Any]:
    for value in values:
        match = _common_title_match_from_text(value)
        if not match:
            continue
        element, role = match
        info = COMMON_TITLE_CATALOG.get((element, role))
        if not info:
            continue
        effects = [str(item) for item in info.get("effects") or [] if str(item)]
        return {
            "canonicalTitleGroup": f"common_title:{element}:{role}",
            "title": info.get("label") or "",
            "label": info.get("label") or "",
            "effects": effects,
            "effectSummary": " / ".join(effects),
            "effectTitle": info.get("label") or "",
            "element": element,
            "elements": [element],
            "commonTitleRole": role,
            "commonTitleRoleOrder": COMMON_TITLE_ROLE_ORDER.get(role, 0),
            "titleSourceKind": "common",
        }
    return {}


def _title_catalog_character_has_game_mode_details(character: dict[str, Any]) -> bool:
    return any(
        isinstance(detail, dict) and bool(detail.get("gameMode"))
        for detail in character.get("details") or []
    )


def _generated_template_pool_text(
    character: dict[str, Any],
    title_info: dict[str, Any],
    label: Any,
    key: Any,
) -> str:
    template_row = character.get("templateRow") or {}
    values = [
        key,
        label,
        title_info.get("ceoNodeKey"),
        title_info.get("initialCeoKey"),
        title_info.get("locTitleKey"),
        character.get("key"),
        character.get("displayName"),
        character.get("label"),
        character.get("subtype"),
        character.get("artSet"),
        character.get("sourceIdentity"),
        character.get("referenceSourcePath"),
        template_row.get("key"),
        template_row.get("art_set_override"),
        template_row.get("_sourceTablePath"),
        template_row.get("_referenceSourcePath"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def _looks_like_generated_title_pool_label(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    if re.search(r"\bxianbei\b.*\b(generic|castellan|colonel|aristocrat|matriarch|wrangler|lancer|marauder)\b", text):
        return True
    if re.search(r"\bxianbei\s+기본\b", text):
        return True
    if re.search(r"\b(generic\s+)?(castellan|colonel)\b", text):
        return True
    return bool(re.search(r"\b0?\d\b.*\b0?\d\b$", text) and ("generic" in text or "xianbei" in text))


def _is_generated_template_pool_title_candidate(
    character: dict[str, Any],
    title_info: dict[str, Any],
    label: Any,
    key: Any,
    common_title_info: dict[str, Any],
) -> bool:
    if common_title_info:
        return False
    text = _generated_template_pool_text(character, title_info, label, key)
    if not text:
        return False
    if any(
        marker in text
        for marker in (
            "generic_nomads",
            "xianbei_template_generic",
            "template_generic_castellan",
            "template_generic_colonel",
            "generic_castellan",
            "generic_colonel",
        )
    ):
        return True
    if _looks_like_generated_title_pool_label(label):
        return True
    if not _title_catalog_character_has_game_mode_details(character):
        return bool(re.search(r"\b(generic|scripted|dummy|placeholder|castellan|colonel)\b", text))
    return bool(
        not _contains_hangul(str(label or ""))
        and re.search(r"\b(generic|scripted|template|dummy|placeholder|xianbei|castellan|colonel)\b", text)
    )


def _merge_title_catalog_entry(
    base: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key in (
        "description",
        "hasDescription",
        "effects",
        "effectSummary",
        "effectTitle",
        "ownerKey",
        "ownerName",
        "initialCeoKey",
        "ceoNodeKey",
        "titleCeoKey",
        "element",
        "elements",
        "locTitleKey",
        "descriptionKey",
        "referenceSourcePath",
        "sourceTablePath",
        "sourceRank",
        "sourceTag",
        "canonicalTitleGroup",
        "commonTitleRole",
        "commonTitleRoleOrder",
        "titleSourceKind",
    ):
        if not merged.get(key) and fallback.get(key):
            merged[key] = fallback[key]
    return merged


def _dedupe_title_catalog_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("canonicalTitleGroup") or row.get("key") or "")
        if not key:
            continue
        if key not in by_key:
            by_key[key] = row
            order.append(key)
            continue
        existing = by_key[key]
        if _title_catalog_score(row) > _title_catalog_score(existing):
            by_key[key] = _merge_title_catalog_entry(row, existing)
        else:
            by_key[key] = _merge_title_catalog_entry(existing, row)
    return [by_key[key] for key in order]


def _build_attribute_set_catalog(
    detail_rows: list[dict[str, Any]],
    tables: dict[str, list[dict[str, Any]]],
    stats_by_set: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in tables.get("character_attribute_sets", []):
        key = _attribute_set_key(row)
        if not key:
            continue
        candidates.append(
            {
                "key": key,
                "label": _localized_label(key, context="attribute"),
                "stats": stats_by_set.get(key, {}),
                "referenceSourcePath": row.get("_referenceSourcePath") or "",
                "sourceTablePath": row.get("_sourceTablePath") or "",
                "sourceRank": _catalog_source_rank(row),
                "sourceTag": _catalog_source_tag(row),
            }
        )
    for row in tables.get("character_attributes", []):
        key = _attribute_set_key(row)
        if not key:
            continue
        candidates.append(
            {
                "key": key,
                "label": _localized_label(key, context="attribute"),
                "stats": stats_by_set.get(key, {}),
                "referenceSourcePath": row.get("_referenceSourcePath") or "",
                "sourceTablePath": row.get("_sourceTablePath") or "",
                "sourceRank": _catalog_source_rank(row),
                "sourceTag": _catalog_source_tag(row),
            }
        )
    for row in detail_rows:
        key = str(row.get("attribute_set") or "")
        if not key:
            continue
        candidates.append(
            {
                "key": key,
                "label": _localized_label(key, context="attribute"),
                "stats": stats_by_set.get(key, {}),
                "referenceSourcePath": row.get("_referenceSourcePath") or "",
                "sourceTablePath": row.get("_sourceTablePath") or "",
                "sourceRank": 2,
                "sourceTag": "USE",
            }
        )
    for key, stats in stats_by_set.items():
        candidates.append(
            {
                "key": key,
                "label": _localized_label(key, context="attribute"),
                "stats": stats,
                "sourceRank": 1,
                "sourceTag": "DEFAULT",
            }
        )
    deduped = _dedupe_catalog_entries(candidates, key_func=lambda item: str(item.get("key") or ""))
    # UI equivalence includes bounds and all attributes, not only the five visible
    # base values. Preserve mode-specific resolve_records/resolve keys in recipes.
    rows_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in tables.get("character_attributes", []):
        key = _attribute_set_key(row)
        if key:
            rows_by_set.setdefault(key, []).append(row)
    for item in deduped:
        rows = rows_by_set.get(item["key"], [])
        comparison = []
        for row in rows:
            comparison.append({
                "type": "resolve" if row.get("attribute_type") == "resolve_records" else row.get("attribute_type"),
                "base": row.get("base_value"),
                "min": row.get("min_range"),
                "max": row.get("max_range"),
            })
        if comparison and all(row["type"] and row["base"] is not None for row in comparison):
            unique = {json.dumps(row, sort_keys=True) for row in comparison}
            item["equivalenceKey"] = json.dumps(sorted(unique))
        item["gameMode"] = (
            "historical" if item["key"].endswith("_records")
            else "romance" if item["key"].endswith("_romance") else ""
        )
    return sorted(deduped, key=lambda item: (str(item.get("label") or ""), str(item.get("key") or "")))


def _build_title_catalog(characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .title_registry import resolve_title
    candidates: list[dict[str, Any]] = []
    effects_by_title, _effect_entries = _load_title_effect_catalog()
    for character in characters:
        if not isinstance(character, dict):
            continue
        title_info = character.get("titleInfo") or {}
        if not isinstance(title_info, dict):
            continue
        verified_title = resolve_title(initial=title_info.get('initialCeoKey', ''),
                                       node=title_info.get('ceoNodeKey', ''),
                                       title=title_info.get('titleCeoKey', ''))
        if not verified_title:
            continue
        key = str(title_info.get("ceoNodeKey") or title_info.get("initialCeoKey") or "")
        if not key:
            continue
        label = _localized_label(title_info.get("label"), key, context="title")
        effect_info = _title_effect_for_key_or_label(
            effects_by_title,
            label,
            key,
            title_info.get("ceoNodeKey"),
            title_info.get("initialCeoKey"),
            title_info.get("locTitleKey"),
        )
        common_title_info = _common_title_info_for_values(
            key,
            title_info.get("ceoNodeKey"),
            title_info.get("locTitleKey"),
            character.get("key"),
            character.get("displayName"),
            character.get("label"),
        )
        if common_title_info:
            label = str(common_title_info.get("label") or label)
            if not effect_info:
                effect_info = common_title_info
        if _is_generated_template_pool_title_candidate(character, title_info, label, key, common_title_info):
            continue
        title_context = " ".join(
            str(value or "")
            for value in (
                label,
                key,
                title_info.get("description"),
                title_info.get("ceoNodeKey"),
                title_info.get("initialCeoKey"),
                character.get("subtype"),
            )
        )
        elements = effect_info.get("elements") or _title_elements_from_effect_lines([title_context]) or _title_elements_from_text(title_context)
        candidates.append(
            {
                "key": key,
                "label": label,
                "description": title_info.get("description") or "",
                "hasDescription": bool(title_info.get("description")),
                "effects": effect_info.get("effects") or [],
                "effectSummary": effect_info.get("effectSummary") or "",
                "effectTitle": effect_info.get("title") or "",
                "effectRows": effect_info.get("effectRows") or [],
                "effectDataSource": effect_info.get("sourceKind") or "",
                "ownerKey": common_title_info.get("canonicalTitleGroup") or character.get("key") or "",
                "ownerName": "기본 칭호" if common_title_info else character.get("displayName") or character.get("label") or "",
                "initialCeoKey": title_info.get("initialCeoKey") or "",
                "ceoNodeKey": title_info.get("ceoNodeKey") or "",
                "titleCeoKey": verified_title,
                "element": elements[0] if elements else "",
                "elements": elements,
                "locTitleKey": title_info.get("locTitleKey") or "",
                "descriptionKey": title_info.get("descriptionKey") or "",
                "referenceSourcePath": character.get("referenceSourcePath") or "",
                "sourceTablePath": (character.get("templateRow") or {}).get("_sourceTablePath") or "",
                "sourceRank": _catalog_source_rank(character.get("templateRow") or character),
                "sourceTag": _catalog_source_tag(character.get("templateRow") or character),
                "canonicalTitleGroup": common_title_info.get("canonicalTitleGroup") or "",
                "commonTitleRole": common_title_info.get("commonTitleRole") or "",
                "commonTitleRoleOrder": common_title_info.get("commonTitleRoleOrder") or 0,
                "titleSourceKind": common_title_info.get("titleSourceKind") or "",
            }
        )
    deduped = _dedupe_title_catalog_entries(candidates)
    return sorted(deduped, key=lambda item: (str(item.get("ownerName") or ""), str(item.get("label") or "")))




def _title_effect_lookup_key(value: Any) -> str:
    return re.sub(r"[\s·:;.,/()\[\]{}'\"-]+", "", str(value or "")).lower()


def _title_effect_lookup_variants(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    clean = raw.replace("ceo_nodes_title_", "").replace("ceo_nodes_description_", "")
    candidates = [raw, clean]
    if "_ceo_node_career_" in clean:
        career = clean.replace("_ceo_node_career_", "_ceo_career_").removesuffix("_01")
        candidates.extend([career, career.replace("_ceo_career_historical_", "_ceo_initial_data_character_historical_")])
    if "_ceo_career_historical_" in clean:
        candidates.extend([
            f"{clean.replace('_ceo_career_', '_ceo_node_career_')}_01",
            clean.replace("_ceo_career_historical_", "_ceo_initial_data_character_historical_"),
        ])
    if "_ceo_initial_data_character_historical_" in clean:
        career = clean.replace("_ceo_initial_data_character_historical_", "_ceo_career_historical_")
        candidates.extend([career, f"{career.replace('_ceo_career_', '_ceo_node_career_')}_01"])
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _title_effect_lookup_key(candidate)
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _title_effect_for_key_or_label(
    effects_by_title: dict[str, dict[str, Any]],
    label: Any,
    *keys: Any,
) -> dict[str, Any]:
    effect_info = _title_effect_for_keys(effects_by_title, *keys)
    if effect_info:
        return effect_info
    label_effect_info = effects_by_title.get(_title_effect_lookup_key(label)) or {}
    if label_effect_info and (label_effect_info.get("key") or label_effect_info.get("keys")):
        return {}
    return label_effect_info


def _title_effect_for_keys(
    effects_by_title: dict[str, dict[str, Any]],
    *keys: Any,
) -> dict[str, Any]:
    for key in keys:
        for lookup_key in _title_effect_lookup_variants(key):
            effect_info = effects_by_title.get(lookup_key)
            if effect_info:
                return effect_info
    return {}


def _load_title_effect_catalog() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    return _load_title_effect_catalog_for_cache_key(_file_cache_key(_title_effect_catalog_paths()))


def _title_effect_catalog_paths() -> list[Path]:
    if current_profile() != BASE_PROFILE:
        return [profile_resource(PACKAGED_ASSEMBLY_KIT_TITLE_EFFECT_CATALOG, "assembly_kit_title_effects.ko.json")]
    catalog_paths = []
    if PACKAGED_ASSEMBLY_KIT_TITLE_EFFECT_CATALOG.is_file():
        catalog_paths.append(PACKAGED_ASSEMBLY_KIT_TITLE_EFFECT_CATALOG)
    return catalog_paths


@lru_cache(maxsize=8)
def _load_title_effect_catalog_for_cache_key(_cache_key: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_title: dict[str, dict[str, Any]] = {}
    cleaned: list[dict[str, Any]] = []
    for catalog_path in _title_effect_catalog_paths():
        try:
            rows = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            entry = _title_effect_entry_from_row(row)
            if not entry:
                continue
            for lookup_key in _title_effect_entry_lookup_keys(entry):
                existing = by_title.get(lookup_key)
                if existing and _title_effect_entry_priority(existing) > _title_effect_entry_priority(entry):
                    continue
                by_title[lookup_key] = entry
            cleaned.append(entry)
    return by_title, cleaned


_load_title_effect_catalog.cache_clear = _load_title_effect_catalog_for_cache_key.cache_clear  # type: ignore[attr-defined]


def _title_effect_entry_from_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    title = str(row.get("title") or "").strip()
    effects = row.get("effects") or []
    if not title or not isinstance(effects, list):
        return {}
    effect_lines = [str(item).strip() for item in effects if str(item).strip()]
    key = str(row.get("key") or row.get("ceoKey") or "").strip()
    extra_keys = row.get("keys") or row.get("aliases") or []
    if not isinstance(extra_keys, list):
        extra_keys = []
    elements = _title_elements_from_effect_lines(effect_lines) or _title_elements_from_text(
        " ".join(str(row.get(field) or "") for field in ("category", "title", "key", "ceoKey"))
    )
    return {
        "title": title,
        "key": key,
        "keys": [str(item).strip() for item in extra_keys if str(item).strip()],
        "owner": str(row.get("owner") or "").strip(),
        "category": str(row.get("category") or "").strip(),
        "element": elements[0] if elements else "",
        "elements": elements,
        "effects": effect_lines,
        "effectSummary": " / ".join(effect_lines),
        "description": str(row.get("description") or "").strip(),
        "sourceKind": str(row.get("sourceKind") or "").strip(),
        "effectRows": row.get("effectRows") if isinstance(row.get("effectRows"), list) else [],
    }


def _title_effect_entry_priority(entry: dict[str, Any]) -> int:
    if entry.get("sourceKind") == "verified_game":
        return 200
    if entry.get("sourceKind") == "assembly_kit":
        return 100
    return 0


def _title_effect_entry_lookup_keys(entry: dict[str, Any]) -> list[str]:
    values = [entry.get("title"), entry.get("key"), *(entry.get("keys") or [])]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for lookup_key in _title_effect_lookup_variants(value):
            if lookup_key and lookup_key not in seen:
                seen.add(lookup_key)
                result.append(lookup_key)
    return result


def _is_background_title_key(value: Any) -> bool:
    key = str(value or "").strip().lower()
    return key.startswith("bg_") and "character_background" in key


def _title_elements_from_effect_lines(effect_lines: list[str]) -> list[str]:
    weights: dict[str, float] = {}
    positions: dict[str, int] = {}
    order: list[str] = []
    cursor = 0
    for line in effect_lines:
        for label, element in _TITLE_STAT_ELEMENT_TERMS.items():
            pattern = rf"(?<![가-힣A-Za-z]){re.escape(label)}\s*([+-]\s*\d+(?:\.\d+)?)?"
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                if element not in order:
                    order.append(element)
                positions[element] = min(positions.get(element, cursor + match.start()), cursor + match.start())
                raw_value = (match.group(1) or "").replace(" ", "")
                try:
                    value = abs(float(raw_value)) if raw_value else 1.0
                except ValueError:
                    value = 1.0
                weights[element] = max(weights.get(element, 0.0), value)
        cursor += len(line) + 1
    return sorted(order, key=lambda element: (-weights.get(element, 0.0), positions.get(element, 0)))


def _title_elements_from_text(value: Any) -> list[str]:
    text = str(value or "").lower()
    role_to_element = {
        "commander": "earth",
        "지휘관": "earth",
        "sentinel": "metal",
        "감시자": "metal",
        "champion": "wood",
        "용장": "wood",
        "vanguard": "fire",
        "선봉장": "fire",
        "strategist": "water",
        "모사": "water",
    }
    elements: list[str] = []
    for token, element in role_to_element.items():
        if token in text and element not in elements:
            elements.append(element)
    return elements


def _background_title_label_from_text(value: Any) -> str:
    _, entries = _load_title_effect_catalog()
    lookup_values = set(_title_effect_lookup_variants(value))
    for entry in entries:
        if not _is_background_title_key(entry.get("key")):
            continue
        if lookup_values.intersection(_title_effect_entry_lookup_keys(entry)):
            return str(entry.get("title") or "")
    return ""


def _write_reference_snapshot(
    analysis: dict[str, Any],
    characters: dict[str, Any],
    asset_cache_token: str = "",
    reference_cache_token: str = "",
    internal_material_token: dict[str, Any] | None = None,
    *,
    pack_path: Path | None = None,
    include_vanilla: bool = False,
) -> None:
    profile_resource(REFERENCE_SNAPSHOT, "reference_snapshot.json").parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": REFERENCE_SNAPSHOT_VERSION,
        "createdAt": time.time(),
        "assetCacheToken": asset_cache_token,
        "referenceCacheToken": reference_cache_token,
        "internalMaterialToken": internal_material_token or _internal_material_cache_token(),
        "inputPack": _pack_snapshot_fingerprint(pack_path, include_vanilla),
        "analysis": analysis,
        "characters": characters,
    }
    with profile_resource(REFERENCE_SNAPSHOT, "reference_snapshot.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


@profiled
def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    require_clean_references(payload.get("recipe", {}))
    _reference_pack_paths(payload)
    if payload.get("useInternalMaterials"):
        material_path = _resolve_user_path(payload.get("materialPath") or "")
        session = MaterialPackSession.open(material_path)
        try:
            recipe = recipe_from_dict(payload.get("recipe", {}))
            messages = validate(session, recipe, payload.get("outputPath"))
            message_dicts = messages_to_dicts(messages)
            try:
                _validated_dedicated_armour_pool(payload, recipe)
            except DedicatedArmourPoolError as error:
                message_dicts.append(
                    {
                        "level": "error",
                        "code": "invalid_dedicated_armour_pool",
                        "message": str(error),
                    }
                )
            return {
                "ok": not any(item.get("level") == "error" for item in message_dicts),
                "messages": message_dicts,
            }
        finally:
            _close_session(session)
    session = _open_session(payload)
    try:
        recipe = recipe_from_dict(payload.get("recipe", {}))
        messages = validate(session, recipe, payload.get("outputPath"))
        if _reference_pack_paths(payload):
            messages = allow_reference_backed_clone_sources(messages)
        message_dicts = messages_to_dicts(messages)
        try:
            _validated_dedicated_armour_pool(payload, recipe)
        except DedicatedArmourPoolError as error:
            message_dicts.append(
                {
                    "level": "error",
                    "code": "invalid_dedicated_armour_pool",
                    "message": str(error),
                }
            )
        return {
            "ok": not any(item.get("level") == "error" for item in message_dicts),
            "messages": message_dicts,
        }
    finally:
        _close_session(session)


def _build_response(messages: list[dict[str, Any]], output_path: Path | None = None) -> dict[str, Any]:
    has_error = any(message.get("level") == "error" for message in messages)
    if not has_error:
        detail = f"경로: {output_path}" if output_path is not None else ""
        messages = [{"level": "success", "code": "pack_written", "message": "팩 생성 완료", "detail": detail}]
    return {
        "ok": not has_error,
        "messages": messages or [{"level": "success", "code": "pack_written", "message": "팩 생성 완료"}],
    }


@profiled
def build_payload(payload: dict[str, Any]) -> dict[str, Any]:
    with _BUILD_LOCK:
        return _build_payload_unlocked(payload)


def _build_payload_unlocked(payload: dict[str, Any]) -> dict[str, Any]:
    require_clean_references(payload.get("recipe", {}))
    _reference_pack_paths(payload)
    if payload.get("useInternalMaterials"):
        if not payload.get("delta"):
            raise ValueError("Internal materials build is only available for patch pack output.")
        recipe = recipe_from_dict(payload.get("recipe", {}))
        _validated_dedicated_armour_pool(payload, recipe)
        output_path = _resolve_user_path(payload["outputPath"]) if payload.get("outputPath") else None
        if output_path is None:
            raise ValueError("Patch pack output path is required.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        material_path = _resolve_user_path(payload.get("materialPath") or "")
        source_session = MaterialPackSession.open(material_path)
        writer_session = _open_session(payload)
        previous_core = delta_builder_module.CORE_ASSET_SOURCE_ID
        if payload.get("coreAssetSourceId"):
            delta_builder_module.CORE_ASSET_SOURCE_ID = str(payload["coreAssetSourceId"])
        try:
            reference_paths = _build_reference_pack_paths(payload, recipe)
            build_messages = delta_builder_module.build_delta_pack_from_materials(
                source_session,
                writer_session,
                recipe,
                output_path,
                reference_paths,
            )
        finally:
            delta_builder_module.CORE_ASSET_SOURCE_ID = previous_core
            _close_session(writer_session)
            _close_session(source_session)
        verify_messages = _verify_saved_pack_image_chain(output_path, recipe) if payload.get("verifyAfterSave") else []
        return _build_response([*build_messages, *verify_messages], output_path)
        return {
            "ok": True,
            "messages": [{"level": "success", "code": "pack_written", "message": "팩 생성 완료"}],
        }
    session = _open_session(payload)
    try:
        recipe = recipe_from_dict(payload.get("recipe", {}))
        _validated_dedicated_armour_pool(payload, recipe)
        output_path = _resolve_user_path(payload["outputPath"]) if payload.get("outputPath") else None
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        reference_paths = _build_reference_pack_paths(payload, recipe)
        build_messages = build_pack(
            session,
            recipe,
            output_path,
            in_place=bool(payload.get("inPlace")),
            delta=bool(payload.get("delta")),
            reference_paths=reference_paths,
        )
        target_path = Path(payload["inputPath"]) if payload.get("inPlace") else output_path
        verify_messages = _verify_saved_pack_image_chain(target_path, recipe) if target_path and payload.get("verifyAfterSave") else []
        return _build_response([*build_messages, *verify_messages], target_path)
        return {
            "ok": True,
            "messages": [{"level": "success", "code": "pack_written", "message": "팩 생성 완료"}],
        }
    finally:
        _close_session(session)


def _verify_saved_pack_image_chain(pack_path: Path | None, recipe: Recipe) -> list[dict[str, Any]]:
    if pack_path is None or not pack_path.exists():
        return []
    expectations = _image_chain_expectations(recipe)
    if not expectations:
        return []

    session = adapter_for("rpfm").open_pack(pack_path)
    try:
        files = {path.replace("\\", "/") for path in session.list_files()}
        table_paths = set(session.list_tables())
    finally:
        _close_session(session)

    messages: list[dict[str, Any]] = []
    for expected in expectations:
        label = expected["label"]
        owner = expected["owner"]
        for table_kind, table_prefix in (
            ("장수 템플릿", "db/character_generation_templates_tables/"),
            ("아트셋", "db/campaign_character_art_sets_tables/"),
            ("이미지 연결", "db/campaign_character_arts_tables/"),
        ):
            if not any(path.startswith(table_prefix) for path in table_paths):
                messages.append({
                    "level": "error",
                    "code": "missing_image_chain_table",
                    "message": f"{label} 이미지의 {table_kind} DB가 누락되었습니다.",
                    "detail": f"owner={owner}, table={table_prefix}",
                })
                break
        for path in sorted(expected["paths"]):
            if path not in files:
                slot = _image_slot_label(path)
                messages.append({
                    "level": "error",
                    "code": "missing_image_asset",
                    "message": f"{label} 이미지의 {slot}가 누락되었습니다.",
                    "detail": path,
                })
    if messages:
        return messages
    return [{
        "level": "success",
        "code": "image_chain_verified",
        "message": f"이미지 체인 검증 완료: {len(expectations)}명",
    }]


def _image_chain_expectations(recipe: Recipe) -> list[dict[str, Any]]:
    title_by_owner = _recipe_work_title_by_owner(recipe)
    items: list[dict[str, Any]] = []
    for patch in recipe.character_patches:
        paths = _expected_image_paths(patch.art_overrides or {}, patch.image_assets or [])
        if paths:
            owner = patch.template_key
            items.append({
                "owner": owner,
                "label": _display_label(title_by_owner.get(owner) or patch.display_name or owner),
                "paths": paths,
            })
    for clone in recipe.character_clones:
        paths = _expected_image_paths(clone.art_overrides or {}, clone.image_assets or [])
        if paths:
            owner = clone.new_template_key
            items.append({
                "owner": owner,
                "label": _display_label(title_by_owner.get(owner) or clone.display_name or owner),
                "paths": paths,
            })
    return items


def _expected_image_paths(art_overrides: dict[str, Any], image_assets: list[dict[str, str]]) -> set[str]:
    paths = {
        _normalize_pack_asset_path(asset.get("targetPath") or asset.get("path") or "")
        for asset in image_assets
    }
    paths.discard("")
    return paths


def _normalize_pack_asset_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip("/")


def _image_slot_label(path: str) -> str:
    lower = path.lower()
    if "/stills/unitcards/" in lower:
        return "unitcard"
    if "/stills/halfbody_large/" in lower:
        return "halfbody_large"
    if "/stills/halfbody_small/" in lower:
        return "halfbody_small"
    if "/composites/large_panel/" in lower:
        return "large_panel"
    if "/composites/small_panel/" in lower:
        return "small_panel"
    if "/composites/" in lower:
        return "composite"
    return "이미지 파일"


def _recipe_work_title_by_owner(recipe: Recipe) -> dict[str, str]:
    titles: dict[str, str] = {}
    for work in recipe.work_items or []:
        title = str(work.get("title") or "").strip()
        if not title:
            continue
        work_recipe = work.get("recipe") or {}
        for patch in work_recipe.get("characterPatches", []) or []:
            key = patch.get("templateKey")
            if key:
                titles[str(key)] = title
        for clone in work_recipe.get("characterCloneRecipes", []) or []:
            key = clone.get("newTemplateKey")
            if key:
                titles[str(key)] = title
    return titles


def _display_label(value: str) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+(수정|생성)$", "", text) or "선택한 장수"


def read_character_data(
    session: Any,
    include_vanilla: bool = False,
    reference_paths: list[Path] | None = None,
    adapter_name: str = "mock",
) -> dict[str, Any]:
    timings: dict[str, Any] = {}
    started = time.perf_counter()
    step = time.perf_counter()
    tables = _read_character_tables(session, "pack")
    timings["readTables"] = _elapsed(step)
    step = time.perf_counter()
    loc_text = _read_all_loc_text(session)
    timings["readLoc"] = _elapsed(step)
    step = time.perf_counter()
    asset_files = session.list_files()
    timings["listPrimaryFiles"] = _elapsed(step)
    asset_sources: dict[str, str] = {}
    step = time.perf_counter()
    reference_paths = reference_paths or []
    uses_core_reference = _uses_core_reference_pack(reference_paths)
    merge_reference_paths = reference_paths
    reference_report = _merge_reference_packs(
        tables,
        loc_text,
        asset_files,
        asset_sources,
        merge_reference_paths,
        adapter_name,
        session.pack_path,
    )
    internal_report = None if uses_core_reference else _merge_internal_materials(tables, loc_text, asset_files, asset_sources)
    if internal_report:
        reference_report.append(internal_report)
    if uses_core_reference:
        local_asset_report = _merge_local_extracted_assets(asset_files, asset_sources)
        if local_asset_report:
            reference_report.append(local_asset_report)
    timings["mergeReferences"] = _elapsed(step)
    step = time.perf_counter()
    pack_summary = summarize_character_tables(
        tables,
        loc_text,
        asset_files,
        asset_sources,
        include_skill_trees=True,
    )
    timings["summarizePack"] = _elapsed(step)
    timings["total"] = _elapsed(started)
    data = {
        "pack": pack_summary,
        "vanilla": {"available": False, "error": None, "summary": None},
        "referencePacks": reference_report,
        "timings": timings,
    }
    if include_vanilla:
        try:
            vanilla_tables = _read_character_tables(session, "vanilla")
            data["vanilla"] = {
                "available": True,
                "error": None,
                "summary": summarize_character_tables(vanilla_tables, loc_text, []),
            }
        except ValueError as error:
            data["vanilla"] = {"available": False, "error": str(error), "summary": None}
    return data


def summarize_character_tables(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str] | None = None,
    asset_files: list[str] | None = None,
    asset_sources: dict[str, str] | None = None,
    *,
    include_skill_trees: bool = False,
) -> dict[str, Any]:
    loc_text = loc_text or {}
    asset_files = asset_files or []
    asset_sources = asset_sources or {}
    asset_index = _build_asset_index(asset_files)
    details_by_template: dict[str, list[dict[str, Any]]] = {}
    for row in tables["character_generation_template_game_mode_details"]:
        details_by_template.setdefault(str(row.get("character_generation_template", "")), []).append(row)

    art_rows_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in tables["campaign_character_arts"]:
        art_rows_by_set.setdefault(str(row.get("art_set_id", "")), []).append(row)
    external_art_set_ids = {
        str(row.get("art_set_id", ""))
        for row in tables["campaign_character_arts"]
        if row.get("art_set_id") and _is_bfg_reference(str(row.get("_referenceSourcePath") or row.get("_externalImageSetSourcePath") or ""))
    }

    art_sets = []
    known_art_set_ids: set[str] = set()
    for row in tables["campaign_character_art_sets"]:
        art_set_id = row.get("art_set_id")
        if not art_set_id:
            continue
        known_art_set_ids.add(str(art_set_id))
        art_rows = art_rows_by_set.get(str(art_set_id), [])
        if not art_rows:
            continue
        primary_art = _primary_art_row(art_rows)
        art_set_label = _friendly_art_set_label(str(art_set_id), loc_text)
        reference_source = str(
            row.get("_referenceSourcePath")
            or row.get("_externalImageSetSourcePath")
            or primary_art.get("_referenceSourcePath")
            or primary_art.get("_externalImageSetSourcePath")
            or ""
        )
        external_image_set = _is_bfg_reference(reference_source) or str(art_set_id) in external_art_set_ids
        if external_image_set and not reference_source:
            reference_source = "BFG_Astral.pack"
        portrait_path = str(primary_art.get("portrait") or "").strip("/")
        card_path = str(primary_art.get("card") or "").strip("/")
        portrait_image_path = _find_art_portrait(asset_index, portrait_path, card_path)
        card_image_path = _find_character_image(asset_index, card_path, "unitcards")
        if _is_image_only_reference(asset_sources.get(portrait_image_path or "", "")):
            portrait_image_path = None
        if _is_image_only_reference(asset_sources.get(card_image_path or "", "")):
            card_image_path = None
        image_assets = [] if external_image_set else _non_image_only_reference_assets(
            _character_image_assets(asset_index, asset_sources, portrait_path, card_path)
        )
        art_sets.append(
            {
                "key": art_set_id,
                "label": art_set_label,
                "rowCount": len(art_rows),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "uniformLabel": _friendly_model_set_label(primary_art.get("uniform"), art_set_label),
                "isMale": row.get("is_male"),
                "referenceSourcePath": reference_source,
                "externalImageSet": external_image_set,
                "portraitImagePath": portrait_image_path,
                "portraitImageSourcePath": asset_sources.get(portrait_image_path or ""),
                "cardImagePath": card_image_path,
                "cardImageSourcePath": asset_sources.get(card_image_path or ""),
                "imageAssets": image_assets,
                "rows": art_rows,
                "sourceTablePath": row.get("_sourceTablePath") or primary_art.get("_sourceTablePath") or "",
                "sourceRank": _catalog_source_rank(row) or _catalog_source_rank(primary_art),
                "sourceTag": _catalog_source_tag(row or primary_art),
            }
        )
    for art_set_id, art_rows in sorted(art_rows_by_set.items()):
        if not art_set_id or art_set_id in known_art_set_ids:
            continue
        primary_art = _primary_art_row(art_rows)
        art_set_label = _friendly_art_set_label(str(art_set_id), loc_text)
        reference_source = str(primary_art.get("_referenceSourcePath") or primary_art.get("_externalImageSetSourcePath") or "")
        external_image_set = _is_bfg_reference(reference_source) or str(art_set_id) in external_art_set_ids
        if external_image_set and not reference_source:
            reference_source = "BFG_Astral.pack"
        portrait_path = str(primary_art.get("portrait") or "").strip("/")
        card_path = str(primary_art.get("card") or "").strip("/")
        portrait_image_path = _find_art_portrait(asset_index, portrait_path, card_path)
        card_image_path = _find_character_image(asset_index, card_path, "unitcards")
        if _is_image_only_reference(asset_sources.get(portrait_image_path or "", "")):
            portrait_image_path = None
        if _is_image_only_reference(asset_sources.get(card_image_path or "", "")):
            card_image_path = None
        image_assets = [] if external_image_set else _non_image_only_reference_assets(
            _character_image_assets(asset_index, asset_sources, portrait_path, card_path)
        )
        art_sets.append(
            {
                "key": art_set_id,
                "label": art_set_label,
                "rowCount": len(art_rows),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "uniformLabel": _friendly_model_set_label(primary_art.get("uniform"), art_set_label),
                "isMale": next((row.get("is_male") for row in tables["campaign_character_art_sets"] if row.get("art_set_id") == art_set_id), None),
                "referenceSourcePath": reference_source,
                "virtual": True,
                "externalImageSet": external_image_set,
                "portraitImagePath": portrait_image_path,
                "portraitImageSourcePath": asset_sources.get(portrait_image_path or ""),
                "cardImagePath": card_image_path,
                "cardImageSourcePath": asset_sources.get(card_image_path or ""),
                "imageAssets": image_assets,
                "rows": art_rows,
                "sourceTablePath": primary_art.get("_sourceTablePath") or "",
                "sourceRank": _catalog_source_rank(primary_art),
                "sourceTag": _catalog_source_tag(primary_art),
            }
        )

    age_ranges = [
        {
            "key": row.get("key"),
            "label": _localized_label(row.get("key"), context="age"),
            "birthYear": row.get("birth_year"),
            "minSpawnYearRound": row.get("min_spawn_year_round"),
            "maxSpawnYearRound": row.get("max_spawn_year_round"),
            "row": row,
        }
        for row in tables["character_generation_spawn_age_ranges"]
        if row.get("key")
    ]

    initial_ceos = [
        {
            "key": row.get("key"),
            "label": _localized_label(row.get("key"), context="initial_ceo"),
            "row": row,
        }
        for row in tables["ceo_initial_datas"]
        if row.get("key")
    ]
    combat_stats_by_initial_ceo = _combat_stats_by_initial_ceo(tables)
    attribute_stats_by_set = _attribute_stats_by_set(tables)
    land_units = {str(row.get("key")): row for row in tables.get("land_units", []) if row.get("key")}
    main_units = _main_units_by_unit_record(tables)
    retinue_initial_units = _retinue_initial_unit_records(tables)

    art_set_summary_by_key = {str(row.get("key") or ""): row for row in art_sets}
    characters = []
    for template in tables["character_generation_templates"]:
        from .source_policy import EXCLUDED_TEMPLATE_KEYS
        if template.get('key') in EXCLUDED_TEMPLATE_KEYS:
            continue
        key = str(template.get("key", ""))
        korea_metadata = {}
        reference_source = template.get("_referenceSourcePath")
        display_name = _character_display_name(template, loc_text)
        korea_name_hint = str(korea_metadata.get("koreaDisplayNameHint") or "")
        if korea_name_hint:
            display_name = korea_name_hint
        details = sorted(
            [
                {
                    "gameMode": detail.get("game_mode", ""),
                    "retinue": detail.get("retinue"),
                    "attributeSet": detail.get("attribute_set"),
                    "skillSet": detail.get("skill_set_override"),
                    "initialCeos": detail.get("initial_ceos"),
                    "row": detail,
                }
                for detail in details_by_template.get(key, [])
            ],
            key=lambda item: str(item["gameMode"]),
        )
        art_set = str(template.get("art_set_override") or "")
        art_rows = art_rows_by_set.get(art_set, [])
        primary_art = _primary_art_row(art_rows)
        art_set_summary = art_set_summary_by_key.get(art_set, {})
        combat_stats = _combat_stats_for_details(details, combat_stats_by_initial_ceo) or {}
        combat_stats.update(_unit_stats_for_details(key, details, land_units, retinue_initial_units, main_units))
        title_info = _title_info_for_character(template, details, loc_text)
        characters.append(
            {
                "key": key,
                "displayName": display_name,
                "label": display_name or _friendly_character_label(key),
                "forename": template.get("forename"),
                "familyName": template.get("family_name"),
                "clanName": template.get("clan_name"),
                "subtype": template.get("subtype"),
                "weight": template.get("weight"),
                "artSet": template.get("art_set_override"),
                "ageRange": template.get("spawn_age_range"),
                "minSpawnRound": template.get("min_spawn_round"),
                "maxSpawnRound": template.get("max_spawn_round"),
                "portrait": primary_art.get("portrait"),
                "card": primary_art.get("card"),
                "uniform": primary_art.get("uniform"),
                "isMale": template.get("is_male"),
                "voiceoverActor": template.get("voiceover_actor"),
                "portraitImagePath": art_set_summary.get("portraitImagePath"),
                "portraitImageSourcePath": art_set_summary.get("portraitImageSourcePath"),
                "cardImagePath": art_set_summary.get("cardImagePath"),
                "cardImageSourcePath": art_set_summary.get("cardImageSourcePath"),
                "imageAssets": art_set_summary.get("imageAssets", []),
                "combatStats": combat_stats,
                "attributeStats": _attribute_stats_for_details(details, attribute_stats_by_set),
                "titleInfo": title_info,
                "templateRow": template,
                "details": details,
                "source": "reference" if reference_source else "pack",
                "referenceSourcePath": reference_source,
                **korea_metadata,
            }
        )

    _attach_roster_factions(characters, tables, loc_text)
    _append_image_only_characters(characters, art_sets, asset_index, asset_sources)
    from .image_catalog import annotate_image_catalog
    annotate_image_catalog(art_sets, characters)
    detail_rows = tables["character_generation_template_game_mode_details"]
    skill_trees = (
        _summarize_skill_trees(tables, loc_text, characters)
        if include_skill_trees
        else {"romance": [], "nodeCount": 0, "skillIndex": {}}
    )
    art_sets = _dedupe_catalog_entries(
        art_sets,
        key_func=lambda item: str(item.get("key") or ""),
    )
    attribute_set_catalog = _build_attribute_set_catalog(detail_rows, tables, attribute_stats_by_set)
    title_catalog = _build_title_catalog(characters)
    trait_sets = _build_ceo_set_catalog(TRAIT_SET_PRESETS, loc_text, "trait")
    equipment_sets = _build_ceo_set_catalog(EQUIPMENT_SET_PRESETS, loc_text, "equipment")
    sorted_characters = sorted(characters, key=lambda item: (item["displayName"] or item["key"], item["key"]))
    return {
        "characters": sorted_characters,
        "artSets": sorted(art_sets, key=lambda item: str(item["key"])),
        "modelSets": sorted(
            [
                {
                    "key": item.get("key"),
                    "label": item.get("label"),
                    "uniform": item.get("uniform"),
                    "uniformLabel": item.get("uniformLabel"),
                    "isMale": item.get("isMale"),
                    "referenceSourcePath": item.get("referenceSourcePath"),
                    "sourceTablePath": item.get("sourceTablePath"),
                    "sourceRank": item.get("sourceRank"),
                    "sourceTag": item.get("sourceTag"),
                }
                for item in art_sets
                if item.get("key") and item.get("uniform") and not item.get("imageOnly") and not item.get("virtual")
            ],
            key=lambda item: (str(item.get("label") or ""), str(item.get("key") or "")),
        ),
        "artRowsBySet": {
            key: len(rows)
            for key, rows in sorted(art_rows_by_set.items())
        },
        "ageRanges": sorted(age_ranges, key=lambda item: str(item["key"])),
        "initialCeos": sorted(initial_ceos, key=lambda item: str(item["key"])),
        "retinues": _unique_options(row.get("retinue") for row in detail_rows),
        "landUnits": _unique_options(row.get("key") for row in tables.get("land_units", [])),
        "mainUnits": [
            {
                "unit": row.get("unit") or row.get("key"),
                "landUnit": row.get("land_unit"),
                "sourceTablePath": row.get("_sourceTablePath") or "",
                "sourceRank": _catalog_source_rank(row),
                "sourceTag": _catalog_source_tag(row),
            }
            for row in tables.get("main_units", [])
            if (row.get("unit") or row.get("key")) and row.get("land_unit")
        ],
        "retinueSlotInitialUnits": [
            {
                "retinue": row.get("retinue"),
                "slotIndex": row.get("slot_index"),
                "initialUnitRecord": row.get("initial_unit_record"),
                "sourceTablePath": row.get("_sourceTablePath") or "",
                "sourceRank": _catalog_source_rank(row),
                "sourceTag": _catalog_source_tag(row),
            }
            for row in tables.get("retinue_slot_initial_units", [])
            if row.get("retinue") and row.get("initial_unit_record")
        ],
        "attributeSets": attribute_set_catalog,
        "attributeSetCatalog": attribute_set_catalog,
        "attributeStatsBySet": attribute_stats_by_set,
        "titleCatalog": title_catalog,
        "traitSets": trait_sets,
        "equipmentSets": equipment_sets,
        "skillSets": _unique_options(row.get("skill_set_override") for row in detail_rows),
        "skillTrees": skill_trees,
        "subtypes": _unique_options(row.get("subtype") for row in tables["character_generation_templates"]),
    }


def _attach_roster_factions(characters, tables, loc_text):
    factions = {str(row.get("ID")): str(row.get("faction") or "")
                for row in tables.get("start_pos_factions", [])}
    by_template = {}
    for row in tables.get("start_pos_characters", []):
        faction = factions.get(str(row.get("faction")), "")
        template = str(row.get("template") or "")
        if faction and template:
            by_template.setdefault(template, set()).add(faction)
    for character in characters:
        character["rosterFactions"] = [
            {"key": key, "label": loc_text.get("factions_screen_name_" + key) or key}
            for key in sorted(by_template.get(character.get("key"), set()))
        ]


def _build_ceo_set_catalog(
    presets: list[dict[str, Any]],
    loc_text: dict[str, str],
    kind: str,
) -> list[dict[str, Any]]:
    lookup = _ceo_node_lookup_by_title(loc_text)
    overrides = TRAIT_SET_KEY_OVERRIDES if kind == "trait" else EQUIPMENT_SET_KEY_OVERRIDES
    catalog: list[dict[str, Any]] = []
    for preset in presets:
        items = []
        for label in preset.get("items", []):
            override_key = overrides.get(str(label))
            if override_key:
                candidates = [override_key]
                key = override_key
                source = "sheet"
            else:
                candidates = sorted(
                    lookup.get(_ceo_title_lookup_key(label), []),
                    key=lambda key: _ceo_node_rank(key, kind),
                )
                key = candidates[0] if candidates else ""
                source = "loc" if key else ""
            items.append({
                "label": label,
                "key": key,
                "resolved": bool(key),
                "candidateCount": len(candidates),
                "source": source,
            })
        ceo_keys: list[str] = []
        seen_ceo_keys: set[str] = set()
        for item in items:
            key = str(item.get("key") or "").strip()
            if not key or key in seen_ceo_keys:
                continue
            seen_ceo_keys.add(key)
            ceo_keys.append(key)
        catalog.append({
            "key": preset.get("key"),
            "label": preset.get("label"),
            "kind": kind,
            "items": items,
            "ceoKeys": ceo_keys,
            "missingItems": [item["label"] for item in items if not item.get("key")],
            "available": len(ceo_keys) == len(items),
        })
    return catalog


def _ceo_node_lookup_by_title(loc_text: dict[str, str]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    prefix = "ceo_nodes_title_"
    for loc_key, label in loc_text.items():
        loc_key_text = str(loc_key or "")
        if not loc_key_text.startswith(prefix):
            continue
        label_text = str(label or "").strip()
        node_key = loc_key_text[len(prefix):]
        if not label_text or not node_key:
            continue
        lookup.setdefault(_ceo_title_lookup_key(label_text), []).append(node_key)
    return lookup


def _ceo_title_lookup_key(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().casefold())


def _ceo_node_rank(node_key: str, kind: str) -> tuple[int, int, str]:
    normalized = str(node_key or "").lower()
    score = 0
    if kind == "trait" and "_trait_" not in normalized:
        score += 100
    if kind == "equipment" and "_ancillary_" not in normalized and "_ancilliary_" not in normalized:
        score += 100
    if normalized.startswith("3k_main_"):
        score += 0
    elif normalized.startswith("3k_ytr_"):
        score += 5
    elif normalized.startswith("3k_dlc"):
        score += 10
    else:
        score += 20
    return score, len(normalized), normalized


def _append_image_only_characters(
    characters: list[dict[str, Any]],
    art_sets: list[dict[str, Any]],
    asset_index: dict[str, Any],
    asset_sources: dict[str, str],
) -> None:
    existing_image_paths = {
        str(character.get("portraitImagePath") or "").lower()
        for character in characters
        if character.get("portraitImagePath")
    }
    existing_character_keys = {str(character.get("key") or "") for character in characters}
    existing_art_keys = {str(art_set.get("key") or "") for art_set in art_sets}
    image_paths = sorted(
        [
            path for path in asset_index.get("files", [])
            if "/stills/halfbody_large/" in path.lower()
            and path.lower().endswith(".png")
            and "/large/" not in path.lower()
            and "/" not in path.lower().split("/stills/halfbody_large/", 1)[1]
        ],
        key=lambda path: (
            0 if Path(path).stem.lower() == path.lower().split("/stills/halfbody_large/", 1)[0].rsplit("/", 1)[-1] else 1,
            path.lower(),
        ),
    )
    seen_image_folders: set[str] = set()
    for path in image_paths:
        real_path = _real_packed_asset_path(path)
        lower = real_path.lower()
        marker = "/stills/halfbody_large/"
        if lower.startswith("ui/characters/krc_artsets/"):
            # Shared transparent equipment layers are not standalone portraits.
            # Character-specific KRC sets are supplied by the art table above.
            continue
        if lower in existing_image_paths:
            if not _is_image_only_reference(asset_sources.get(path, "")):
                continue
        if _is_non_character_image_path(real_path.lower()):
            continue
        folder = real_path[: lower.index(marker)]
        folder_key = folder.lower()
        source_path = asset_sources.get(path, "")
        source_folder_key = f"{source_path}|{folder_key}"
        if source_folder_key in seen_image_folders:
            continue
        seen_image_folders.add(source_folder_key)
        image_key = folder.removeprefix("ui/characters/").strip("/")
        if not image_key:
            continue
        card_path = _find_character_image(asset_index, image_key, "unitcards")
        label = _friendly_image_character_label(_image_label_key(image_key, real_path))
        source_slug = _image_only_source_slug(source_path)
        art_key = f"image_only_{source_slug}_{image_key}".replace("/", "_")
        image_assets = _character_image_assets(asset_index, asset_sources, image_key, image_key)
        if art_key not in existing_art_keys:
            art_sets.append({
                "key": art_key,
                "label": label,
                "rowCount": 0,
                "portrait": image_key,
                "card": image_key,
                "uniform": "",
                "uniformLabel": "모델 없음",
                "referenceSourcePath": source_path,
                "virtual": True,
                "imageOnly": True,
                "externalImageSet": False,
                "portraitImagePath": path,
                "portraitImageSourcePath": source_path,
                "cardImagePath": card_path,
                "cardImageSourcePath": asset_sources.get(card_path or ""),
                "imageAssets": image_assets,
                "rows": [],
                "sourcePackName": Path(source_path).name if source_path else "",
                "sourceIdentity": _image_only_source_identity(source_path, image_key, card_path),
            })
            existing_art_keys.add(art_key)
        character_key = f"image_only_{source_slug}_{image_key}".replace("/", "_")
        if character_key in existing_character_keys:
            character_key = f"{character_key}_{hashlib.sha1(path.encode('utf-8')).hexdigest()[:8]}".replace("/", "_")
        characters.append({
            "key": character_key,
            "displayName": label,
            "label": label,
            "forename": label,
            "familyName": "",
            "clanName": "",
            "subtype": "",
            "weight": 100,
            "artSet": art_key,
            "ageRange": "",
            "minSpawnRound": 0,
            "maxSpawnRound": 999,
            "voiceoverActor": "",
            "portrait": image_key,
            "card": image_key,
            "uniform": "",
            "uniformLabel": "모델 없음",
            "details": [],
            "combatStats": {},
            "attributeStats": {},
            "titleInfo": {},
            "templateRow": {},
            "source": "reference",
            "referenceSourcePath": source_path,
            "virtualImageOnly": True,
            "portraitImagePath": path,
            "portraitImageSourcePath": source_path,
            "cardImagePath": card_path,
            "cardImageSourcePath": asset_sources.get(card_path or ""),
            "imageAssets": image_assets,
            "sourcePackName": Path(source_path).name if source_path else "",
            "sourceIdentity": _image_only_source_identity(source_path, image_key, card_path),
        })
        existing_image_paths.add(lower)
        existing_character_keys.add(character_key)


def _image_only_source_slug(source_path: str) -> str:
    name = Path(source_path).stem if source_path else "unknown"
    slug = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:8]
    return f"{slug or 'unknown'}_{digest}"


def _image_only_source_identity(source_path: str, portrait_key: str, card_path: str | None) -> str:
    source_name = Path(source_path).name if source_path else "unknown"
    card_key = ""
    if card_path:
        normalized = card_path.replace("\\", "/")
        marker = "/unitcards/"
        if marker in normalized:
            card_key = normalized.split(marker, 1)[1].rsplit("/", 1)[0]
    parts = [source_name, portrait_key]
    if card_key and card_key != portrait_key:
        parts.append(card_key)
    return " 쨌 ".join(part for part in parts if part)


def _non_image_only_reference_assets(assets: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        asset for asset in assets
        if not _is_image_only_reference(asset.get("sourcePath", ""))
    ]


def _is_non_character_image_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if re.search(r"(^|[_\-/])(?:\d{1,2}yo|baby|child|children|kid|kids|infant|toddler)(?:[_\-/]|$)", normalized):
        return True
    child_tokens = {"baby", "child", "children", "kid", "kids", "infant", "toddler"}
    non_character_tokens = {
        "ancillary",
        "ancillaries",
        "armour",
        "armor",
        "weapon",
        "weapons",
        "mount",
        "mounts",
        "horse",
        "horses",
        "accessory",
        "accessories",
        "aura",
        "banner",
        "banners",
        "common",
        "face",
        "faces",
        "generic",
        "prop",
        "props",
        "shared",
        "ui_composite_scene",
    }
    return any(
        part in child_tokens
        or bool(child_tokens.intersection(part.replace("-", "_").split("_")))
        or bool(non_character_tokens.intersection(part.replace("-", "_").split("_")))
        or part.startswith(("baby_", "child_", "kid_", "infant_", "toddler_"))
        or part.endswith(("_baby", "_child", "_kid", "_infant", "_toddler"))
        for part in parts
    )


def _friendly_image_character_label(image_key: str) -> str:
    lower = image_key.lower()
    imported_labels = {
        "hby_hero_special_import_silver_gaze": "[신규] 은발 백금 의상 여성",
        "hby_hero_special_import_blue_gold_general": "[신규] 흑발 청금 갑옷 여장수",
        "hby_hero_special_import_purple": "[신규] 보라 의상 여성",
        "hby_hero_special_import_red_general": "[신규] 적금 갑옷 여장수",
    }
    if lower in imported_labels:
        return imported_labels[lower]
    known = {
        "diao_chan": "珥덉꽑",
        "lu_bu": "?ы룷",
    }
    for token, label in known.items():
        if token in lower:
            return label
    label = _friendly_character_label(image_key)
    for prefix in ("lb special ", "special "):
        if label.startswith(prefix):
            label = label[len(prefix):]
    return label


def _image_label_key(image_key: str, image_path: str) -> str:
    normalized = image_key.replace("\\", "/").strip("/")
    lower = normalized.lower()
    stem = Path(image_path).stem
    folder_leaf = normalized.rsplit("/", 1)[-1] if normalized else ""
    generic_folder_tokens = (
        "add_unique",
        "artsets",
        "generic_arts",
        "composites",
        "faces",
        "baby",
    )
    if "/" in normalized or any(token in lower for token in generic_folder_tokens):
        return stem
    if stem and stem.lower() != folder_leaf.lower() and stem.lower().startswith(("3k_", "sad_", "mod_")):
        return stem
    return image_key


def _summarize_skill_trees(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
    characters: list[dict[str, Any]],
) -> dict[str, Any]:
    node_sets = {str(row.get("key")): row for row in tables.get("character_skill_node_sets", []) if row.get("key")}
    nodes_by_set: dict[str, list[dict[str, Any]]] = {}
    node_by_key: dict[str, dict[str, Any]] = {}
    for row in tables.get("character_skill_nodes", []):
        set_key = str(row.get("character_skill_node_set_key") or "")
        key = str(row.get("key") or "")
        if not set_key or not key:
            continue
        nodes_by_set.setdefault(set_key, []).append(row)
        node_by_key[key] = row

    links_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in tables.get("character_skill_node_links", []):
        parent = str(row.get("parent_key") or "")
        child = str(row.get("child_key") or "")
        node = node_by_key.get(parent) or node_by_key.get(child)
        set_key = str(node.get("character_skill_node_set_key") or "") if node else ""
        if set_key:
            links_by_set.setdefault(set_key, []).append(row)

    effects_by_skill: dict[str, list[dict[str, Any]]] = {}
    ability_summaries = _material_ability_effect_summaries(tables, loc_text)
    effects = {str(row.get("key")): row for row in tables.get("effects", []) if row.get("key")}
    for row in tables.get("character_skill_level_to_effects_junctions", []):
        skill_key = str(row.get("character_skill_key") or "")
        if not skill_key:
            continue
        effect_key = str(row.get("effect_key") or "")
        effect_row = effects.get(effect_key, {})
        effects_by_skill.setdefault(skill_key, []).append({
            "effectKey": effect_key,
            "name": _effect_label(effect_key, effect_row, loc_text),
            "scope": row.get("effect_scope"),
            "level": row.get("level"),
            "value": row.get("value"),
            "abilitySummary": ability_summaries.get(effect_key, ""),
        })

    owners_by_skill: dict[str, list[dict[str, str]]] = {}
    for character in characters:
        for detail in character.get("details", []):
            if detail.get("gameMode") != "romance":
                continue
            skill_set = str(detail.get("skillSet") or "")
            if not skill_set:
                continue
            owners_by_skill.setdefault(skill_set, []).append({
                "key": str(character.get("key") or ""),
                "name": str(character.get("label") or character.get("displayName") or character.get("key") or ""),
            })

    skill_index: dict[str, dict[str, Any]] = {}
    trees = []
    for set_key, rows in sorted(nodes_by_set.items()):
        owners = owners_by_skill.get(set_key, [])
        if not owners:
            continue
        nodes = []
        for row in _prefer_romance_skill_tree_rows(rows):
            skill_key = str(row.get("character_skill_key") or "")
            effects_for_skill = effects_by_skill.get(skill_key, [])
            if skill_key not in skill_index:
                skill_index[skill_key] = _skill_index_entry(skill_key, loc_text, effects_for_skill)
            skill_info = skill_index[skill_key]
            skill_info["sources"].append({
                "setKey": set_key,
                "nodeKey": str(row.get("key") or ""),
                "owners": owners,
            })
            nodes.append(_skill_node_summary(row, loc_text, effects_for_skill, skill_info))
        trees.append({
            "key": set_key,
            "name": _skill_set_label(set_key, node_sets.get(set_key), loc_text),
            "owners": owners,
            "nodes": sorted(nodes, key=lambda item: (item["position"]["x"], item["position"]["y"], item["key"])),
            "links": [
                {
                    "parent": row.get("parent_key"),
                    "child": row.get("child_key"),
                    "type": row.get("link_type"),
                }
                for row in links_by_set.get(set_key, [])
            ],
        })
    _add_catalog_skill_index_entries(skill_index)
    return {
        "romance": trees,
        "nodeCount": sum(len(tree["nodes"]) for tree in trees),
        "skillIndex": dict(sorted(skill_index.items(), key=lambda item: (item[1]["name"], item[0]))),
    }


def _prefer_romance_skill_tree_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_position: dict[tuple[Any, Any], dict[str, Any]] = {}
    ordered_positions: list[tuple[Any, Any]] = []
    for row in rows:
        position = _skill_node_position(row)
        key = (position.get("x"), position.get("y"))
        current = by_position.get(key)
        if current is None:
            ordered_positions.append(key)
            by_position[key] = row
            continue
        if _skill_tree_node_mode_rank(row) > _skill_tree_node_mode_rank(current):
            by_position[key] = row
    return [by_position[key] for key in ordered_positions if key in by_position]


def _skill_tree_node_mode_rank(row: dict[str, Any]) -> int:
    text = f"{row.get('key') or ''} {row.get('character_skill_key') or ''}".lower()
    if "romance" in text:
        return 3
    if "historical" in text:
        return 1
    return 2


def _skill_node_summary(
    row: dict[str, Any],
    loc_text: dict[str, str],
    effects: list[dict[str, Any]],
    skill_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = str(row.get("key") or "")
    skill_info = skill_info or {}
    return {
        "key": key,
        "skillKey": row.get("character_skill_key"),
        "setKey": row.get("character_skill_node_set_key"),
        "name": skill_info.get("name") or _skill_node_label(key, row, loc_text),
        "description": skill_info.get("description") or "",
        "icon": row.get("icon") or row.get("icon_path") or row.get("onscreen_name"),
        "position": _skill_node_position(row),
        "tier": _first_present(row, ("tier", "required_level", "level", "min_level")),
        "row": row,
        "effects": effects,
        "effectSummary": skill_info.get("effectSummary") or _effect_summary(effects),
    }


def _skill_index_entry(skill_key: str, loc_text: dict[str, str], effects: list[dict[str, Any]]) -> dict[str, Any]:
    name = _skill_name_for_key(skill_key, loc_text)
    catalog = _catalog_skill_effect_info(skill_key, name)
    description = _skill_description_for_key(skill_key, loc_text)
    if description and not _contains_hangul(description):
        description = ""
    return {
        "key": skill_key,
        "name": catalog.get("name") or name,
        "description": description or catalog.get("description") or "",
        "effects": effects,
        "effectSummary": catalog.get("effectSummary") or _effect_summary(effects),
        "effectRows": catalog.get("effectRows") or [],
        "effectDataSource": catalog.get("sourceKind") or "",
        "element": catalog.get("element") or _skill_element(skill_key),
        "source": catalog.get("source") or _skill_source_label(skill_key),
        "owner": catalog.get("owner") or "",
        "exclusive": bool(catalog.get("exclusive")),
        "sources": [],
    }


def _skill_name_for_key(skill_key: str, loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"character_skills_localised_name_{skill_key}",
        f"character_skills_name_{skill_key}",
        f"character_skill_names_{skill_key}",
    ):
        if loc_text.get(loc_key):
            label = loc_text[loc_key]
            catalog = _catalog_skill_effect_info(label, skill_key)
            if catalog:
                return catalog.get("name") or label
            if _contains_hangul(label):
                return label
            # A real localized name is safer than a guessed class/element label.
            return label
    catalog = _catalog_skill_effect_info(skill_key)
    return catalog.get("name") or _friendly_skill_key(skill_key)


def _skill_description_for_key(skill_key: str, loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"character_skills_localised_description_{skill_key}",
        f"character_skills_description_{skill_key}",
    ):
        if loc_text.get(loc_key):
            return loc_text[loc_key]
    return ""


def _skill_element(skill_key: str) -> str:
    value = skill_key.lower()
    for element in ("earth", "fire", "wood", "water", "metal"):
        if f"_{element}_" in value or value.endswith(f"_{element}"):
            return element
    return ""


def _skill_source_label(skill_key: str) -> str:
    value = str(skill_key or "").lower()
    if value.startswith("3k_mtu") or "_mtu_" in value:
        return "MTU"
    if value.startswith("3k_dlc") or "_dlc" in value or value.startswith("ep_") or "_ep_" in value:
        return "DLC"
    if value.startswith("3k_ytr") or "_ytr_" in value:
        return "DLC"
    if value.startswith("3k_main"):
        return "바닐라"
    return ""


def _contains_hangul(value: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in str(value or ""))


def _has_raw_english_effect_name(value: Any) -> bool:
    return bool(
        re.search(
            r"\b(?:skill|effect|ability)[ _-]+[a-z][a-z0-9 _-]*\s+[+-]?\d",
            str(value or ""),
            flags=re.IGNORECASE,
        )
    )


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(value or ""))


def _normalize_label_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _load_skill_effect_catalog() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    catalog_paths = _skill_effect_catalog_paths()
    return _load_skill_effect_catalog_for_cache_key(_file_cache_key(catalog_paths))


def _skill_effect_catalog_paths() -> list[Path]:
    if current_profile() != BASE_PROFILE:
        return []  # Use this profile's actual DB effects, not baseline overrides.
    paths: list[Path] = []
    if PACKAGED_ASSEMBLY_KIT_SKILL_EFFECT_CATALOG.is_file():
        paths.append(PACKAGED_ASSEMBLY_KIT_SKILL_EFFECT_CATALOG)
    return paths


@lru_cache(maxsize=8)
def _load_skill_effect_catalog_for_cache_key(_cache_key: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_key: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for catalog_path in _skill_effect_catalog_paths():
        try:
            rows = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            entry = _skill_effect_entry_from_row(row)
            if not entry:
                continue
            entries.append(entry)
            for lookup_key in _skill_effect_lookup_keys(entry):
                by_key.setdefault(lookup_key, entry)
    return by_key, entries


_load_skill_effect_catalog.cache_clear = _load_skill_effect_catalog_for_cache_key.cache_clear  # type: ignore[attr-defined]


def _catalog_effect_label(effect_key: str) -> str:
    labels = _load_effect_label_catalog_for_cache_key(
        _file_cache_key(_skill_effect_catalog_paths())
    )
    return labels.get(str(effect_key or ""), "")


@lru_cache(maxsize=8)
def _load_effect_label_catalog_for_cache_key(_cache_key: str) -> dict[str, str]:
    _by_key, entries = _load_skill_effect_catalog()
    labels: dict[str, str] = {}
    for entry in entries:
        for row in entry.get("effectRows") or []:
            if not isinstance(row, dict):
                continue
            effect_key = str(row.get("effectKey") or "")
            name = _clean_game_ui_text(row.get("name"))
            if effect_key and name and _contains_hangul(name):
                labels.setdefault(effect_key, name)
    return labels


def _skill_effect_entry_from_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    key = str(row.get("key") or "").strip()
    name = str(row.get("name") or "").strip()
    raw_effects = row.get("effects") or []
    if isinstance(raw_effects, list):
        effect_lines = [str(item).strip() for item in raw_effects if str(item).strip()]
    else:
        effect_lines = [str(raw_effects).strip()] if str(raw_effects).strip() else []
    effect_summary = str(row.get("effectSummary") or " / ".join(effect_lines)).strip()
    if not key or not name:
        return {}
    aliases = row.get("aliases") or []
    if not isinstance(aliases, list):
        aliases = []
    return {
        "key": key,
        "name": name,
        "description": str(row.get("description") or "").strip(),
        "effectSummary": effect_summary,
        "element": str(row.get("element") or _skill_element(key) or "").strip(),
        "source": str(row.get("source") or "").strip(),
        "owner": str(row.get("owner") or "").strip(),
        "exclusive": bool(row.get("exclusive")),
        "aliases": [str(item).strip() for item in aliases if str(item).strip()],
        "effects": effect_lines,
        "effectRows": row.get("effectRows") if isinstance(row.get("effectRows"), list) else [],
        "sourceKind": str(row.get("sourceKind") or "").strip(),
    }


def _skill_effect_lookup_variants(value: Any) -> list[str]:
    normalized = _normalize_label_key(value)
    if not normalized:
        return []
    variants = [
        normalized,
        re.sub(r"^(?:3k_(?:main|dlc\d+|mtu)_)?(?:character_)?(?:skill|skills|ability)_", "", normalized),
        re.sub(r"^(?:3k_(?:main|dlc\d+|mtu)_)?(?:skill_node|skill_nodes|character_skill_node)_", "", normalized),
        re.sub(r"^(?:3k_(?:main|dlc\d+|mtu)_)?skill_special_(?:active|passive)_", "", normalized),
    ]
    result: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        if variant and variant not in seen:
            seen.add(variant)
            result.append(variant)
    return result


def _skill_effect_lookup_keys(entry: dict[str, Any]) -> list[str]:
    values = [entry.get("key"), entry.get("name"), entry.get("owner"), *(entry.get("aliases") or [])]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for lookup_key in _skill_effect_lookup_variants(value):
            if lookup_key and lookup_key not in seen:
                seen.add(lookup_key)
                result.append(lookup_key)
    return result


def _catalog_skill_effect_info(*values: Any) -> dict[str, Any]:
    by_key, entries = _load_skill_effect_catalog()
    candidates: list[str] = []
    for value in values:
        candidates.extend(_skill_effect_lookup_variants(value))
    selected: dict[str, Any] = {}
    for candidate in candidates:
        if candidate in by_key:
            selected = by_key[candidate]
            break
    # Never match a parent/prefix skill: MTU skills such as fire_blood_flower
    # otherwise inherit the unrelated vanilla fire (Vanguard) entry.
    return selected


def _add_catalog_skill_index_entries(skill_index: dict[str, dict[str, Any]]) -> None:
    # The catalog is descriptive metadata, not a DB source.  Older builds added
    # every catalog key as a selectable skill even when the key did not exist in
    # character_skill_nodes/character_skill_level_to_effects_junctions.  Writing
    # one of those synthetic keys into a cloned node produced a skill with none
    # of its required DB relations and could crash campaigns with several
    # generated characters.
    #
    # Only enrich skills that were discovered from real source rows.  This keeps
    # the Korean names/effect summaries while guaranteeing that every UI choice
    # has an actual DB key behind it.
    for key, existing in skill_index.items():
        entry = _catalog_skill_effect_info(key, existing.get("name"))
        if not entry:
            continue
        for field in ("name", "description", "effectSummary", "element", "source", "owner"):
            incoming = entry.get(field)
            current = existing.get(field)
            if incoming and (
                not current
                or (
                    field in {"name", "description", "effectSummary"}
                    and _contains_hangul(str(incoming))
                    and not _contains_hangul(str(current))
                )
                or (
                    field == "effectSummary"
                    and _has_raw_english_effect_name(current)
                    and not _has_raw_english_effect_name(incoming)
                )
            ):
                existing[field] = incoming
        if entry.get("effectRows") and not existing.get("effectRows"):
            existing["effectRows"] = entry["effectRows"]
        if entry.get("sourceKind") and not existing.get("effectDataSource"):
            existing["effectDataSource"] = entry["sourceKind"]
        existing["exclusive"] = bool(existing.get("exclusive") or entry.get("exclusive"))
        existing["catalogMetadata"] = True


def _label_tokens(value: Any) -> list[str]:
    return [
        token
        for token in _normalize_label_key(value).split("_")
        if token and token not in _LABEL_SKIP_TOKENS
    ]


def _joined_character_token(tokens: list[str]) -> str:
    best = ""
    for start in range(len(tokens)):
        for end in range(len(tokens), start, -1):
            candidate = "_".join(tokens[start:end])
            if candidate in _CHARACTER_TOKEN_LABELS and len(candidate) > len(best):
                best = candidate
    return best


def _character_template_candidates_from_label(value: str) -> list[str]:
    candidates = [value]
    token_sources = [
        _character_token_from_template(value),
        _character_token_from_initial_ceo(value),
        _character_token_from_art_or_model_key(value),
    ]
    seen_tokens: set[str] = set()
    for token in token_sources:
        token = str(token or "").strip("_")
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        for prefix in ("3k_main", "3k_mtu", "3k_dlc04", "3k_dlc05", "3k_dlc06", "3k_dlc07", "ep", "3k_ytr", "3k_mod", "ironic"):
            for element in ("earth", "fire", "metal", "water", "wood"):
                candidates.append(f"{prefix}_template_historical_{token}_hero_{element}")
                candidates.append(f"{prefix}_template_historical_lady_{token}_hero_{element}")
            candidates.append(f"{prefix}_template_historical_{token}")
            candidates.append(f"{prefix}_template_historical_lady_{token}")
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _korean_character_label_from_key(value: Any, loc_text: dict[str, str] | None = None) -> str:
    text = str(value or "")
    if not text:
        return ""

    for candidate in _character_template_candidates_from_label(text):
        mapped_name = korean_character_name(candidate)
        if mapped_name and _contains_hangul(mapped_name):
            return mapped_name
        if loc_text:
            loc_name = _display_name_from_key(candidate, loc_text)
            if loc_name and _contains_hangul(loc_name):
                return loc_name

    tokens = _label_tokens(text)
    joined = _joined_character_token(tokens)
    if joined:
        return _CHARACTER_TOKEN_LABELS[joined]
    return ""


def _element_label_from_text(value: Any) -> str:
    normalized = f"_{_normalize_label_key(value)}_"
    for element, label in _ELEMENT_LABELS.items():
        if f"_{element}_" in normalized:
            return label
    return ""


def _generic_title_label_from_text(value: Any) -> str:
    normalized = f"_{_normalize_label_key(value)}_"
    if "_generic_" not in normalized:
        return ""
    gender = ""
    if "_generic_f_" in normalized or "_female_" in normalized:
        gender = "여성"
    elif "_generic_m_" in normalized or "_male_" in normalized:
        gender = "남성"
    element = _element_label_from_text(value)
    role_labels = {
        "agent": "첩보원",
        "commander": "지휘관",
        "envoy": "사절",
        "general": "장군",
        "governor": "태수",
        "legendary": "전설",
        "minister": "관료",
        "strategist": "책사",
        "villager": "향촌 인물",
    }
    role = next((label for token, label in role_labels.items() if f"_{token}_" in normalized), "")
    return " ".join(part for part in (gender, element, role) if part)


def _translate_token_sequence(tokens: list[str]) -> str:
    if not tokens:
        return ""
    result: list[str] = []
    index = 0
    while index < len(tokens):
        matched = ""
        matched_label = ""
        for end in range(len(tokens), index, -1):
            candidate = "_".join(tokens[index:end])
            if candidate in _CHARACTER_TOKEN_LABELS:
                matched = candidate
                matched_label = _CHARACTER_TOKEN_LABELS[candidate]
                break
            if candidate in _SKILL_PHRASE_LABELS:
                matched = candidate
                matched_label = _SKILL_PHRASE_LABELS[candidate]
                break
        if matched:
            result.append(matched_label)
            index += len(matched.split("_"))
            continue
        token = tokens[index]
        if token in _LABEL_TOKEN_TRANSLATIONS:
            label = _LABEL_TOKEN_TRANSLATIONS[token]
            if not result or result[-1] != label:
                result.append(label)
        elif token.isdigit():
            result.append(token)
        elif len(token) > 1:
            result.append(_SYLLABLE_TOKEN_TRANSLATIONS.get(token, token))
        index += 1
    return " ".join(part for part in result if part).strip()


def _korean_label_from_text(
    value: Any,
    *,
    key: Any = "",
    context: str = "generic",
    loc_text: dict[str, str] | None = None,
) -> str:
    text = str(value or "").strip()
    if text and _contains_hangul(text):
        return text

    key_text = str(key or "").strip()
    source = " ".join(part for part in (text, key_text) if part)
    element_label = _element_label_from_text(source)
    if context == "attribute" and element_label:
        return f"{element_label} 기본 능력치"
    if context == "subtype" and element_label:
        return f"{element_label} 장수 타입"
    if context == "skill_set" and element_label:
        return f"{element_label} 스킬셋"
    if context == "title":
        background_label = _background_title_label_from_text(source)
        if background_label:
            return background_label
        generic_label = _generic_title_label_from_text(source)
        if generic_label:
            return generic_label
        translated = _translate_token_sequence(_label_tokens(source))
        if translated and _contains_hangul(translated):
            return translated

    return ""


def _localized_label(value: Any, key: Any = "", *, context: str = "generic", loc_text: dict[str, str] | None = None) -> str:
    label = _korean_label_from_text(value, key=key, context=context, loc_text=loc_text)
    if label:
        return label
    return _korean_label_from_text(key, context=context, loc_text=loc_text) or str(value or key or "")


def _translate_skill_name_text(value: str) -> str:
    return _localized_label(value, context="skill")


def _friendly_skill_key(skill_key: str) -> str:
    return _localized_label(skill_key, context="skill")


def _skill_node_position(row: dict[str, Any]) -> dict[str, int | float]:
    x = _number_or_none(_first_present(row, ("x", "ui_x", "column", "indent", "position_x", "tree_position_x")))
    y = _number_or_none(_first_present(row, ("y", "ui_y", "row", "tier", "position_y", "tree_position_y")))
    return {"x": x if x is not None else 0, "y": y if y is not None else 0}


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row.get(key) not in {None, ""}:
            return row.get(key)
    return None


def _skill_set_label(key: str, row: dict[str, Any] | None, loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"character_skill_node_sets_name_{key}",
        f"character_skill_node_set_name_{key}",
        f"character_skillsets_name_{key}",
    ):
        if loc_text.get(loc_key):
            return _localized_label(loc_text[loc_key], key, context="skill_set", loc_text=loc_text)
    if row:
        for field in ("onscreen_name", "name", "loc_key"):
            value = row.get(field)
            if value and loc_text.get(str(value)):
                return _localized_label(loc_text[str(value)], key, context="skill_set", loc_text=loc_text)
            if value:
                return _localized_label(str(value), key, context="skill_set", loc_text=loc_text)
    return _localized_label(key, context="skill_set", loc_text=loc_text)


def _skill_node_label(key: str, row: dict[str, Any], loc_text: dict[str, str]) -> str:
    skill_key = str(row.get("character_skill_key") or "")
    for loc_key in (
        f"character_skills_localised_name_{skill_key}",
        f"character_skills_name_{skill_key}",
        f"character_skill_names_{skill_key}",
        f"character_skills_localised_name_{key}",
        f"character_skill_nodes_name_{key}",
        f"character_skill_node_name_{key}",
        f"character_skills_name_{key}",
    ):
        if loc_text.get(loc_key):
            return _localized_label(loc_text[loc_key], key, context="skill", loc_text=loc_text)
    for field in ("onscreen_name", "name", "loc_key"):
        value = row.get(field)
        if value and loc_text.get(str(value)):
            return _localized_label(loc_text[str(value)], key, context="skill", loc_text=loc_text)
        if value:
            return _localized_label(str(value), key, context="skill", loc_text=loc_text)
    return _localized_label(key, context="skill", loc_text=loc_text)


def _effect_label(key: str, row: dict[str, Any], loc_text: dict[str, str]) -> str:
    for loc_key in (
        f"effects_description_{key}",
        f"effects_localised_description_{key}",
        f"effects_localised_title_{key}",
        f"effects_name_{key}",
    ):
        if loc_text.get(loc_key):
            label = _clean_game_ui_text(loc_text[loc_key])
            if _contains_hangul(label):
                return label
            catalog_label = _catalog_effect_label(key)
            if catalog_label:
                return catalog_label
            return _clean_game_ui_text(_localized_label(label, key, context="effect", loc_text=loc_text))
    catalog_label = _catalog_effect_label(key)
    if catalog_label:
        return catalog_label
    for field in ("description", "onscreen_name", "name", "icon"):
        value = row.get(field)
        if value and loc_text.get(str(value)):
            label = _clean_game_ui_text(loc_text[str(value)])
            if _contains_hangul(label):
                return label
            return _clean_game_ui_text(_localized_label(label, key, context="effect", loc_text=loc_text))
        if value and field != "icon":
            return _clean_game_ui_text(_localized_label(str(value), key, context="effect", loc_text=loc_text))
    return _clean_game_ui_text(_friendly_effect_key(key))


def _friendly_effect_key(key: str) -> str:
    direct = _korean_label_from_text(key, context="effect")
    if direct and _contains_hangul(direct):
        return direct
    value = str(key or "")
    lower = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lower).strip("_")
    normalized = re.sub(r"^(?:3k_(?:main|dlc\d+|mtu)_)?(?:effect|effects|enable|unlock|skill|ability)_", "", normalized)
    if normalized in _SKILL_PHRASE_LABELS:
        return _SKILL_PHRASE_LABELS[normalized]
    for phrase_key, label in _SKILL_PHRASE_LABELS.items():
        if phrase_key in normalized or phrase_key in lower:
            return label
    translated = _translate_token_sequence(_label_tokens(normalized or lower))
    if translated and _contains_hangul(translated):
        return translated
    return _friendly_key(value)

def _visible_effect_label(effect: dict[str, Any]) -> str:
    key = str(effect.get("effectKey") or "")
    name = str(effect.get("name") or "")
    label = name if name and not name.lower().startswith("effect ") else _friendly_effect_key(key)
    label = _clean_game_ui_text(label)
    if label and not _contains_hangul(label):
        label = _friendly_effect_key(key)
    label = _clean_game_ui_text(label)
    lower = f"{key} {label}".lower()
    if "ai_hint" in lower or "ai hint" in lower:
        return ""
    return label.strip()


def _effect_summary(effects: list[dict[str, Any]]) -> str:
    useful_effects = [effect for effect in effects if _visible_effect_label(effect)]
    if not useful_effects:
        return "효과 정보 없음"
    pieces = []
    for effect in useful_effects[:4]:
        ability_summary = _clean_game_ui_text(effect.get("abilitySummary"))
        if ability_summary:
            pieces.append(ability_summary)
            continue
        label = _visible_effect_label(effect)
        value = effect.get("value")
        suffix = f" {value:+g}" if isinstance(value, (int, float)) else f" {value}" if value not in {None, ""} else ""
        pieces.append(_clean_game_ui_text(f"{label}{suffix}"))
    if len(useful_effects) > 4:
        pieces.append(f"외 {len(useful_effects) - 4}개")
    return " · ".join(pieces)


_MATERIAL_ABILITY_STAT_LABELS = {
    "scalar_charge_speed": "돌격 속도",
    "scalar_speed": "이동 속도",
    "stat_melee_attack_interval": "근접 공격 간격",
    "stat_morale": "사기",
    "stat_melee_defence": "근접 방어",
    "stat_spotting_forest": "숲 탐지 거리",
    "stat_spotting_range_min_modifier": "최소 탐지 거리",
    "stat_spotting_scrub": "관목 탐지 거리",
    "stat_visibility_sight": "시야 거리",
    "stat_melee_damage_ap": "관통 무기 피해",
    "stat_melee_damage_base": "일반 무기 피해",
}

_MATERIAL_ABILITY_PERCENT_MULTIPLIERS = {
    "scalar_charge_speed",
    "scalar_speed",
}


def _material_ability_effect_summaries(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
) -> dict[str, str]:
    grants = [
        row
        for row in tables.get("effect_bonus_value_unit_ability_junctions", [])
        if str(row.get("bonus_value_id") or "").lower() == "enable"
        and row.get("effect")
        and row.get("unit_ability")
    ]
    if not grants:
        return {}

    ability_rows = _preferred_material_rows(tables.get("unit_abilities", []), "key")
    special_rows = _preferred_material_rows(tables.get("unit_special_abilities", []), "key")
    phase_rows = _preferred_material_rows(tables.get("special_ability_phases", []), "id")

    phase_links: dict[str, list[tuple[int, str]]] = {}
    seen_phase_links: set[tuple[str, str]] = set()
    for row in sorted(
        tables.get("special_ability_to_special_ability_phase_junctions", []),
        key=lambda item: (_catalog_source_rank(item), _number_or_zero(item.get("order"))),
        reverse=True,
    ):
        ability_key = str(row.get("special_ability") or "")
        phase_key = str(row.get("phase") or "")
        identity = (ability_key, phase_key)
        if not ability_key or not phase_key or identity in seen_phase_links:
            continue
        seen_phase_links.add(identity)
        phase_links.setdefault(ability_key, []).append(
            (int(_number_or_zero(row.get("order"))), phase_key)
        )

    stat_rows_by_phase = _material_rows_by_field(
        tables.get("special_ability_phase_stat_effects", []),
        "phase",
        ("phase", "stat", "how", "value"),
    )
    attribute_rows_by_phase = _material_rows_by_field(
        tables.get("special_ability_phase_attribute_effects", []),
        "phase",
        ("phase", "attribute", "attribute_type"),
    )

    summaries_by_ability: dict[str, str] = {}
    for ability_key in sorted({str(row.get("unit_ability") or "") for row in grants}):
        phases = [
            phase_rows[phase_key]
            for _, phase_key in sorted(phase_links.get(ability_key, []))
            if phase_key in phase_rows
        ]
        summaries_by_ability[ability_key] = _material_ability_summary(
            ability_key,
            ability_rows.get(ability_key, {}),
            special_rows.get(ability_key, {}),
            phases,
            stat_rows_by_phase,
            attribute_rows_by_phase,
            loc_text,
        )

    result: dict[str, str] = {}
    for row in grants:
        effect_key = str(row.get("effect") or "")
        ability_key = str(row.get("unit_ability") or "")
        summary = summaries_by_ability.get(ability_key, "")
        if effect_key and summary:
            result[effect_key] = summary
    return result


def _preferred_material_rows(
    rows: list[dict[str, Any]],
    key_field: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=_catalog_source_rank):
        key = str(row.get(key_field) or "")
        if key:
            result[key] = row
    return result


def _material_rows_by_field(
    rows: list[dict[str, Any]],
    group_field: str,
    identity_fields: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[Any, ...]] = set()
    for row in sorted(rows, key=_catalog_source_rank, reverse=True):
        group = str(row.get(group_field) or "")
        identity = tuple(row.get(field) for field in identity_fields)
        if not group or identity in seen:
            continue
        seen.add(identity)
        result.setdefault(group, []).append(row)
    return result


def _material_ability_summary(
    ability_key: str,
    ability_row: dict[str, Any],
    special_row: dict[str, Any],
    phases: list[dict[str, Any]],
    stat_rows_by_phase: dict[str, list[dict[str, Any]]],
    attribute_rows_by_phase: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
) -> str:
    name = _first_localized_text(
        loc_text,
        (
            f"unit_abilities_onscreen_name_{ability_key}",
            f"unit_ability_types_localised_description_{ability_key}",
        ),
    ) or _friendly_effect_key(ability_key)
    ability_type = _first_localized_text(
        loc_text,
        (f"unit_ability_types_onscreen_name_{ability_key}",),
    ).replace("발동시", "발동 시")
    if not ability_type:
        ability_type = "상시 강화" if _truthy_value(special_row.get("passive")) else "발동 시 강화"

    details: list[str] = []
    if ability_type:
        details.append(ability_type)
    target = _material_ability_target_text(special_row)
    if target:
        details.append(target)

    phase_details: list[str] = []
    for index, phase in enumerate(phases, start=1):
        phase_key = str(phase.get("id") or "")
        mechanics = [
            text
            for text in (
                *(
                    _material_ability_stat_text(row, loc_text)
                    for row in stat_rows_by_phase.get(phase_key, [])
                ),
                *(
                    _material_ability_attribute_text(row, loc_text)
                    for row in attribute_rows_by_phase.get(phase_key, [])
                ),
                *_material_phase_mechanics(phase),
            )
            if text
        ]
        mechanics = _dedupe_text(mechanics)
        duration = _numeric_value(phase.get("duration"))
        duration_text = (
            f"{_format_ui_number(duration)}초"
            if duration is not None and duration > 0
            else ""
        )
        if len(phases) > 1:
            heading = f"{index}단계"
            if duration_text:
                heading += f"({duration_text})"
            phase_details.append(
                f"{heading}: {', '.join(mechanics)}" if mechanics else heading
            )
        else:
            if duration_text and not _truthy_value(special_row.get("passive")):
                details.append(f"지속 {duration_text}")
            phase_details.extend(mechanics)

    details.extend(phase_details)
    recharge = max(
        [
            value
            for value in (
                _numeric_value(special_row.get("recharge_time")),
                *(_numeric_value(phase.get("recharge_time")) for phase in phases),
            )
            if value is not None and value > 0
        ],
        default=None,
    )
    if recharge is not None and not _truthy_value(special_row.get("passive")):
        details.append(f"재사용 대기시간 {_format_ui_number(recharge)}초")
    hp_cost = _numeric_value(special_row.get("hp_cost"))
    if hp_cost is not None and hp_cost > 0:
        suffix = "%" if _truthy_value(special_row.get("hp_cost_is_percentage")) else ""
        details.append(f"체력 비용 {_format_ui_number(hp_cost)}{suffix}")

    details = _dedupe_text(details)
    summary = f"능력: {name}"
    if details:
        summary += " — " + " · ".join(details)
    return summary


def _material_ability_stat_text(
    row: dict[str, Any],
    loc_text: dict[str, str],
) -> str:
    stat_key = str(row.get("stat") or "")
    value = _numeric_value(row.get("value"))
    if not stat_key or value is None:
        return ""
    label = _MATERIAL_ABILITY_STAT_LABELS.get(stat_key) or _first_localized_text(
        loc_text,
        (
            f"unit_stat_localisations_onscreen_name_{stat_key}",
            f"unit_stat_localisations_abbreviated_name_{stat_key}",
        ),
    )
    if not label:
        label = _friendly_effect_key(stat_key)
    how = str(row.get("how") or "").lower()
    if how == "mult":
        if stat_key in _MATERIAL_ABILITY_PERCENT_MULTIPLIERS:
            percent = (value - 1.0) * 100.0
            return f"{label} {_format_signed_ui_number(percent)}%"
        return f"{label} ×{_format_ui_number(value)}"
    return f"{label} {_format_signed_ui_number(value)}"


def _material_ability_attribute_text(
    row: dict[str, Any],
    loc_text: dict[str, str],
) -> str:
    attribute = str(row.get("attribute") or "")
    if not attribute:
        return ""
    label = _first_localized_text(
        loc_text,
        (
            f"unit_attributes_imued_effect_text_{attribute}",
            f"unit_attributes_bullet_text_{attribute}",
        ),
    ) or _friendly_effect_key(attribute)
    if str(row.get("attribute_type") or "").lower() == "negative":
        return f"{label} 제거"
    return label


def _material_phase_mechanics(phase: dict[str, Any]) -> list[str]:
    result: list[str] = []
    fatigue = _numeric_value(phase.get("fatigue_change_ratio"))
    if fatigue not in (None, 0):
        result.append(f"피로 변화 {_format_signed_ui_number(fatigue)}")
    damage = _numeric_value(phase.get("damage_amount"))
    if damage not in (None, 0):
        result.append(f"피해 {_format_signed_ui_number(damage)}")
    heal = _numeric_value(phase.get("heal_amount"))
    if heal not in (None, 0):
        result.append(f"회복량 {_format_signed_ui_number(heal)}")
    if _truthy_value(phase.get("unbreakable")):
        result.append("불굴")
    if _truthy_value(phase.get("cant_move")):
        result.append("이동 불가")
    if _truthy_value(phase.get("freeze_fatigue")):
        result.append("피로 고정")
    return result


def _material_ability_target_text(special_row: dict[str, Any]) -> str:
    if not special_row:
        return ""
    effect_range = _numeric_value(special_row.get("effect_range"))
    if effect_range is None or effect_range <= 0:
        effect_range = _numeric_value(special_row.get("target_intercept_range"))
    range_text = (
        f"{_format_ui_number(effect_range)}m"
        if effect_range is not None and effect_range > 0
        else ""
    )
    affect_self = _truthy_value(special_row.get("affect_self"))
    target_friends = _truthy_value(special_row.get("target_friends"))
    friendly_count = _numeric_value(special_row.get("num_effected_friendly_units"))
    if target_friends:
        count = (
            f" {int(friendly_count)}개 부대"
            if friendly_count is not None and friendly_count > 0
            else ""
        )
        within = f" ({range_text} 이내)" if range_text else ""
        return f"지정 아군{count}{within}"
    affects_friendlies = friendly_count is not None and friendly_count != 0
    if range_text and affects_friendlies:
        return (
            f"자신 및 반경 {range_text} 내 아군"
            if affect_self
            else f"반경 {range_text} 내 아군"
        )
    if affect_self:
        return "자신"
    return ""


def _first_localized_text(
    loc_text: dict[str, str],
    keys: tuple[str, ...],
) -> str:
    for key in keys:
        value = _clean_game_ui_text(loc_text.get(key))
        if value:
            return value
    return ""


def _number_or_zero(value: Any) -> float:
    return _numeric_value(value) or 0.0


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _truthy_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _format_ui_number(value: float) -> str:
    return f"{value:g}"


def _format_signed_ui_number(value: float) -> str:
    return f"{value:+g}"


def _dedupe_text(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _clean_game_ui_text(value)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _clean_game_ui_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = re.sub(r"\[\[/?[a-z0-9_:\-]+(?:\s+[^\]]*)?\]\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"%\+?n%?", "", text, flags=re.IGNORECASE)
    text = text.replace("\\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text.strip(" ·-")


def _combat_stats_by_initial_ceo(tables: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    weapon_ceos = {
        str(row.get("ceos_key")): row
        for row in tables.get("equipment_variants_weapons", [])
        if row.get("ceos_key")
    }
    armour_ceos = {
        str(row.get("ceos_key")): row
        for row in tables.get("equipment_variants_armours", [])
        if row.get("ceos_key")
    }
    melee_weapons = {str(row.get("key")): row for row in tables.get("melee_weapons", [])}
    missile_weapons = {str(row.get("key")): row for row in tables.get("missile_weapons", [])}
    projectiles = {str(row.get("key")): row for row in tables.get("projectiles", [])}
    armour_types = {str(row.get("key")): row for row in tables.get("unit_armour_types", [])}

    initial_keys = {
        str(row.get("key") or "")
        for row in tables.get("ceo_initial_datas", [])
        if row.get("key")
    }
    initial_keys.update(
        str(row.get("initial_ceos") or "")
        for row in tables.get("character_generation_template_game_mode_details", [])
        if row.get("initial_ceos")
    )

    stats: dict[str, dict[str, Any]] = {}
    for initial_key in sorted(initial_keys):
        if not initial_key:
            continue
        name_tokens = _equipment_tokens_from_initial_ceo(initial_key)
        weapon = _best_equipment_variant(name_tokens, weapon_ceos, "weapon")
        armour = _best_equipment_variant(name_tokens, armour_ceos, "armour")
        weapon_row = melee_weapons.get(str((weapon or {}).get("primary_melee_weapon") or ""))
        missile_weapon_row = missile_weapons.get(str((weapon or {}).get("primary_missile_weapon") or ""))
        projectile_row = projectiles.get(str((missile_weapon_row or {}).get("default_projectile") or ""))
        armour_row = armour_types.get(str((armour or {}).get("armour") or ""))
        if weapon_row or missile_weapon_row or projectile_row or armour_row:
            stats[initial_key] = {
                "weaponCeo": (weapon or {}).get("ceos_key"),
                "weaponStatKey": (weapon or {}).get("primary_melee_weapon"),
                "weaponDamage": _number_or_none((weapon_row or {}).get("damage")),
                "weaponApDamage": _number_or_none((weapon_row or {}).get("ap_damage")),
                "weaponType": (weapon_row or {}).get("melee_weapon_type"),
                "missileWeaponStatKey": (weapon or {}).get("primary_missile_weapon"),
                "projectileStatKey": (missile_weapon_row or {}).get("default_projectile"),
                "projectileDamage": _number_or_none((projectile_row or {}).get("damage")),
                "projectileApDamage": _number_or_none((projectile_row or {}).get("ap_damage")),
                "projectileRange": _number_or_none((projectile_row or {}).get("effective_range")),
                "armourCeo": _runtime_armour_ceo_key((armour or {}).get("ceos_key")) if armour_row else None,
                "armourStatKey": (armour or {}).get("armour") if armour_row else None,
                "armourAudioType": (armour_row or {}).get("audio_type"),
                "armourFromReference": bool(
                    (armour or {}).get("_referenceSourcePath")
                    or (armour_row or {}).get("_referenceSourcePath")
                ),
                "baseAttack": _sum_numeric(weapon_row, ("damage", "ap_damage")),
                "baseDefense": _number_or_none((armour_row or {}).get("armour_value")),
            }
    return stats


def _runtime_armour_ceo_key(value: Any) -> str | None:
    key = str(value or "").strip()
    if not key:
        return None
    return key


def _combat_stats_for_details(
    details: list[dict[str, Any]],
    stats_by_initial_ceo: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") != game_mode:
                continue
            stats = stats_by_initial_ceo.get(str(detail.get("initialCeos") or ""))
            if stats:
                return stats
    for detail in details:
        stats = stats_by_initial_ceo.get(str(detail.get("initialCeos") or ""))
        if stats:
            return stats
    return None


def _raw_character_token_from_initial_ceo(initial_key: str) -> str:
    token = initial_key
    for marker in (
        "ceo_initial_data_character_historical_",
        "ceo_initial_data_character_romance_",
        "ceo_initial_data_character_",
        "initial_data_character_historical_",
        "initial_data_character_romance_",
        "initial_data_character_",
    ):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    return token


def _character_token_from_initial_ceo(initial_key: str) -> str:
    return _raw_character_token_from_initial_ceo(initial_key).removeprefix("lady_")


def _equipment_tokens_from_initial_ceo(initial_key: str) -> list[str]:
    raw = _raw_character_token_from_initial_ceo(initial_key)
    tokens = [raw]
    if raw.startswith("lady_"):
        tokens.append(raw.removeprefix("lady_"))
    return [token for token in tokens if token]


def _title_info_for_character(
    template: dict[str, Any],
    details: list[dict[str, Any]],
    loc_text: dict[str, str],
) -> dict[str, Any]:
    initial_key = _preferred_initial_ceo(details)
    from .title_registry import resolve_title, title_node
    verified_title = resolve_title(initial=initial_key)
    template_key = str(template.get("key", ""))
    initial_token = _character_token_from_initial_ceo(initial_key) if initial_key else ""
    template_token = _character_token_from_template(template_key)
    token = template_token if _is_generic_initial_ceo_token(initial_token) else (initial_token or template_token)
    source_key = template_key if token == template_token else (initial_key or template_key)
    candidates = _title_candidate_keys(token, source_key, template_key)
    matched, title_text = _best_title_loc_candidate(candidates, loc_text)
    matched = matched or (candidates[0] if candidates else "")
    if not initial_key:
        verified_title = resolve_title(node=matched)
    if verified_title:
        matched = title_node(verified_title) or matched
    description = _loc_description_for_ceo_node(matched, loc_text) or ""
    _frontend_name, frontend_title = _frontend_character_description_parts(template_key, loc_text)
    effects_by_title, _effect_entries = _load_title_effect_catalog()
    keyed_effect_info = _title_effect_for_keys(
        effects_by_title,
        matched,
        initial_key,
        f"ceo_nodes_title_{matched}" if matched else "",
        f"ceo_nodes_description_{matched}" if matched else "",
        template_key,
    )
    description = str(keyed_effect_info.get('description') or description)
    label = (
        _usable_title_label(keyed_effect_info.get("title"))
        or _usable_title_label(title_text)
        or _usable_title_label(frontend_title)
        or _usable_title_label(_friendly_title_label(matched or template_key))
        or "칭호 미확인"
    )
    return {
        "status": "verified" if verified_title else "unavailable",
        "titleCeoKey": verified_title,
        "effectSummary": keyed_effect_info.get('effectSummary', ''),
        "label": label,
        "description": description,
        "hasDescription": bool(description),
        "ceoNodeKey": matched,
        "initialCeoKey": initial_key,
        "locTitleKey": f"ceo_nodes_title_{matched}" if matched else "",
        "descriptionKey": f"ceo_nodes_description_{matched}" if matched else "",
        "source": "campaigns/ceo_data.ccd",
        "note": "" if verified_title else "내장 자료에서 지원하는 칭호 연결이 없습니다.",
    }


def _is_generic_initial_ceo_token(token: str) -> bool:
    return token.startswith(("generic_m_", "generic_f_"))


def _best_title_loc_candidate(
    candidates: list[str],
    loc_text: dict[str, str],
) -> tuple[str, str]:
    fallback_key = ""
    fallback_text = ""
    for key in candidates:
        title_text = _loc_title_for_ceo_node(key, loc_text) or ""
        if not title_text:
            continue
        if _usable_title_label(title_text):
            return key, title_text
        if not fallback_key:
            fallback_key = key
            fallback_text = title_text
    return fallback_key, fallback_text


def _usable_title_label(value: Any) -> str:
    text = _clean_game_ui_text(str(value or "").strip())
    if not text or _is_bad_display_hint(text) or _looks_like_mixed_name_title_label(text):
        return ""
    if _contains_hangul(text):
        return text
    return ""


def _looks_like_mixed_name_title_label(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lower = text.lower()
    if not re.search(r"[a-z]", lower):
        return False
    if re.search(r"\b([a-z]{2,})\b.*\b\1\b", lower):
        return True
    if _contains_hangul(text) and re.search(r"\b[a-z]{2,}\b", lower) and re.search(r"\b\d{1,2}\b$", lower):
        return True
    return bool(_contains_hangul(text) and re.search(r"\b[a-z]{2,}\b", lower) and len(text.split()) <= 5)


def _preferred_initial_ceo(details: list[dict[str, Any]]) -> str:
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") == game_mode and detail.get("initialCeos"):
                return str(detail.get("initialCeos"))
    for detail in details:
        if detail.get("initialCeos"):
            return str(detail.get("initialCeos"))
    return ""


def _title_candidate_keys(token: str, source_key: str = "", template_key: str = "") -> list[str]:
    if not token:
        return []
    normalized = token.removeprefix("lady_")
    tokens = [normalized]
    if token != normalized:
        tokens.append(token)
    prefixes = _title_prefix_candidates(source_key, template_key)
    candidates = []
    for prefix in prefixes:
        for item in tokens:
            candidates.append(f"{prefix}_ceo_node_career_historical_{item}_01")
    return candidates


def _title_prefix_candidates(source_key: str, template_key: str = "") -> tuple[str, ...]:
    preferred: list[str] = []
    text = str(source_key or "")
    template_text = str(template_key or "")
    for prefix in ("3k_dlc05", "3k_dlc04", "3k_dlc06", "3k_dlc07", "3k_ytr", "ep", "3k_main"):
        if text.startswith(f"{prefix}_") or f"_{prefix}_" in text:
            preferred.append(prefix)
    if korea_character_metadata(template_text) or template_text.startswith(("3k_mod_template_", "ironic_template_")):
        # Korea add-on characters reuse vanilla/EP initial CEO keys but override
        # their loc rows. Preserve the reused prefix before trying MTU aliases.
        preferred = preferred or ["3k_main"]
    if "3k_mtu" not in preferred:
        preferred.append("3k_mtu")
    for prefix in ("3k_mtu", "3k_dlc05", "3k_dlc04", "3k_dlc06", "3k_dlc07", "3k_ytr", "ep", "3k_main"):
        if prefix not in preferred:
            preferred.append(prefix)
    return tuple(preferred)


def _loc_title_for_ceo_node(ceo_node_key: str, loc_text: dict[str, str]) -> str | None:
    if not ceo_node_key:
        return None
    return _resolve_loc_text(loc_text.get(f"ceo_nodes_title_{ceo_node_key}"), loc_text)


def _loc_description_for_ceo_node(ceo_node_key: str, loc_text: dict[str, str]) -> str | None:
    if not ceo_node_key:
        return None
    return _resolve_loc_text(loc_text.get(f"ceo_nodes_description_{ceo_node_key}"), loc_text)


def _resolve_loc_text(value: str | None, loc_text: dict[str, str], depth: int = 0) -> str | None:
    if not value:
        return None
    if depth >= 3:
        return value
    match = re.fullmatch(r"\{\{tr:([^}]+)\}\}", value.strip())
    if not match:
        return value
    resolved = loc_text.get(match.group(1))
    if not resolved:
        return value
    return _resolve_loc_text(resolved, loc_text, depth + 1) or resolved


def _friendly_title_label(ceo_node_key: str) -> str:
    if not ceo_node_key:
        return "칭호 미확인"
    value = ceo_node_key
    for marker in ("_ceo_node_career_historical_", "_ceo_node_career_generated_"):
        if marker in value:
            value = value.split(marker, 1)[1]
            break
    return _localized_label(value.removesuffix("_01"), ceo_node_key, context="title")


def _best_equipment_variant(
    name_tokens: str | list[str],
    variants_by_ceo: dict[str, dict[str, Any]],
    equipment_kind: str,
) -> dict[str, Any] | None:
    tokens = [name_tokens] if isinstance(name_tokens, str) else list(name_tokens or [])
    tokens = [token for token in tokens if token]
    if not tokens:
        return None
    candidates = []
    for ceo_key, row in variants_by_ceo.items():
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
    return sorted(candidates)[0][4]


def _equipment_variant_match_rank(row: dict[str, Any], normalized_ceo_key: str, token: str) -> int | None:
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


def _equipment_variant_token_matches(normalized_ceo_key: str, token: str) -> bool:
    token = str(token or "").lower()
    if not token:
        return False
    if len(token) >= 4 and token in normalized_ceo_key:
        return True
    parts = [part for part in re.split(r"[^a-z0-9]+", normalized_ceo_key) if part]
    return any(part == token or part == f"{token}s" for part in parts)


def _sum_numeric(row: dict[str, Any] | None, columns: tuple[str, ...]) -> int | float | None:
    if not row:
        return None
    values = [_number_or_none(row.get(column)) for column in columns]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(numeric_values)


def _number_or_none(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _read_character_tables(session: Any, source: str) -> dict[str, list[dict[str, Any]]]:
    tables = {}
    for alias in CHARACTER_TABLE_ALIASES:
        table_name = resolve_character_table_name(session, alias) if source == "pack" else _resolve_source_table(session, alias, source)
        tables[alias] = session.read_table(table_name, source)
    for alias in (
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
        "main_units",
    ):
        try:
            table_name = _resolve_stat_table(session, alias, source)
            tables[alias] = session.read_table(table_name, source)
        except ValueError:
            tables[alias] = []
    for alias in RETINUE_TABLE_ALIASES:
        try:
            table_name = _resolve_retinue_table(session, alias, source)
            tables[alias] = session.read_table(table_name, source)
        except ValueError:
            tables[alias] = []
    for alias in SKILL_TABLE_ALIASES:
        try:
            table_name = _resolve_skill_table(session, alias, source)
            tables[alias] = session.read_table(table_name, source)
        except ValueError:
            tables[alias] = []
    return tables


def _merge_reference_packs(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
    asset_files: list[str],
    asset_sources: dict[str, str],
    reference_paths: list[Path],
    adapter_name: str,
    primary_pack_path: Path,
) -> list[dict[str, Any]]:
    report = []
    known_assets = set(asset_files)
    for reference_path in reference_paths:
        reference_started = time.perf_counter()
        resolved = reference_path.expanduser()
        if _is_aw_reference(resolved):
            report.append({
                "path": str(resolved),
                "ok": False,
                "error": "skipped_aw_image_pack",
                "seconds": _elapsed(reference_started),
            })
            continue
        if _skip_bfg_resource_pack_for_fast_open(resolved):
            report.append({
                "path": str(resolved),
                "ok": False,
                "error": "skipped_bfg_resource_pack",
                "seconds": _elapsed(reference_started),
            })
            continue
        if not resolved.exists():
            report.append({"path": str(resolved), "ok": False, "error": "file_not_found", "seconds": _elapsed(reference_started)})
            continue
        if resolved.resolve() == primary_pack_path.resolve():
            report.append({"path": str(resolved), "ok": False, "error": "same_as_input_pack", "seconds": _elapsed(reference_started)})
            continue
        session = None
        before_counts = {alias: len(rows) for alias, rows in tables.items()}
        try:
            step = time.perf_counter()
            actual_adapter = _detect_adapter(resolved) if adapter_name == "auto" else adapter_name
            if actual_adapter == "rpfm":
                _ensure_rpfm_server()
            session = adapter_for(actual_adapter).open_pack(resolved)
            open_seconds = _elapsed(step)
            step = time.perf_counter()
            reference_tables = {} if _is_image_only_reference(resolved) else _read_reference_tables(session)
            table_seconds = _elapsed(step)
            step = time.perf_counter()
            for alias, rows in reference_tables.items():
                if alias == "campaign_character_arts":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("art_set_id", "age", "portrait", "card", "uniform"),
                        str(resolved),
                    )
                elif alias == "character_generation_template_game_mode_details":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("character_generation_template", "game_mode"),
                        str(resolved),
                    )
                elif alias == "character_skill_node_links":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("parent_key", "child_key", "link_type"),
                        str(resolved),
                    )
                elif alias == "character_skill_level_to_effects_junctions":
                    _append_missing_rows_by_fields(
                        tables.setdefault(alias, []),
                        rows,
                        ("character_skill_key", "effect_key", "effect_scope", "level"),
                        str(resolved),
                    )
                elif alias == "character_attribute_sets":
                    _append_missing_rows_by_key(
                        tables.setdefault(alias, []),
                        rows,
                        _attribute_set_key,
                        str(resolved),
                    )
                elif alias == "character_attributes":
                    _append_missing_rows_by_key(
                        tables.setdefault(alias, []),
                        rows,
                        lambda row: (_attribute_set_key(row), _attribute_stat_key(row) or ""),
                        str(resolved),
                    )
                else:
                    _append_missing_rows(
                        tables.setdefault(alias, []),
                        rows,
                        _key_field_for_alias(alias),
                        str(resolved),
                    )
            for key, text in _read_all_loc_text(session).items():
                loc_text.setdefault(key, text)
            loc_seconds = _elapsed(step)
            step = time.perf_counter()
            added_assets = 0
            image_only_reference = _is_image_only_reference(resolved)
            for asset_path in session.list_files():
                stored_asset_path = _source_scoped_asset_path(resolved, asset_path) if image_only_reference else asset_path
                if stored_asset_path in known_assets:
                    continue
                if not image_only_reference and asset_path in known_assets:
                    continue
                asset_files.append(stored_asset_path)
                known_assets.add(stored_asset_path)
                asset_sources[stored_asset_path] = str(resolved)
                added_assets += 1
            asset_seconds = _elapsed(step)
            added = {
                alias: len(tables.get(alias, [])) - before_counts.get(alias, 0)
                for alias in reference_tables
            }
            row_counts = {alias: len(rows) for alias, rows in reference_tables.items()}
            report.append({
                "path": str(resolved),
                "ok": True,
                "tables": sorted(reference_tables),
                "rowCounts": row_counts,
                "addedRows": {key: value for key, value in added.items() if value},
                "addedAssets": added_assets,
                "seconds": _elapsed(reference_started),
                "timings": {
                    "open": open_seconds,
                    "tablesAndRows": table_seconds,
                    "loc": loc_seconds,
                    "assets": asset_seconds,
                },
            })
        except Exception as error:
            report.append({"path": str(resolved), "ok": False, "error": str(error), "seconds": _elapsed(reference_started)})
        finally:
            if session is not None:
                _close_session(session)
    return report


def _merge_internal_materials(
    tables: dict[str, list[dict[str, Any]]],
    loc_text: dict[str, str],
    asset_files: list[str],
    asset_sources: dict[str, str],
) -> dict[str, Any] | None:
    if not profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json").is_file():
        return None
    started = time.perf_counter()
    known_assets = set(asset_files)
    before_counts = {alias: len(rows) for alias, rows in tables.items()}
    try:
        session = MaterialPackSession.open(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json"))
        reference_tables = _read_internal_material_reference_tables(session)
        for alias, rows in reference_tables.items():
            if alias == "campaign_character_arts":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("art_set_id", "age", "portrait", "card", "uniform"),
                    str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
                )
            elif alias == "character_generation_template_game_mode_details":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("character_generation_template", "game_mode"),
                    str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
                )
            elif alias == "character_skill_node_links":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("parent_key", "child_key", "link_type"),
                    str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
                )
            elif alias == "character_skill_level_to_effects_junctions":
                _append_missing_rows_by_fields(
                    tables.setdefault(alias, []),
                    rows,
                    ("character_skill_key", "effect_key", "effect_scope", "level"),
                    str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
                )
            elif alias == "character_attribute_sets":
                _append_missing_rows_by_key(
                    tables.setdefault(alias, []),
                    rows,
                    _attribute_set_key,
                    str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
                )
            elif alias == "character_attributes":
                _append_missing_rows_by_key(
                    tables.setdefault(alias, []),
                    rows,
                    lambda row: (_attribute_set_key(row), _attribute_stat_key(row) or ""),
                    str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
                )
            else:
                _append_missing_rows(
                    tables.setdefault(alias, []),
                    rows,
                    _key_field_for_alias(alias),
                    str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
                )
        for key, text in _read_all_loc_text(session).items():
            loc_text[key] = text
        added_assets = _merge_internal_asset_manifest(asset_files, asset_sources, known_assets)
        added_assets += _merge_extracted_asset_inventory(asset_files, asset_sources, known_assets)
        added = {
            alias: len(tables.get(alias, [])) - before_counts.get(alias, 0)
            for alias in reference_tables
        }
        return {
            "path": str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
            "ok": True,
            "internalMaterials": True,
            "tables": sorted(reference_tables),
            "rowCounts": {alias: len(rows) for alias, rows in reference_tables.items()},
            "addedRows": {key: value for key, value in added.items() if value},
            "addedAssets": added_assets,
            "seconds": _elapsed(started),
        }
    except Exception as error:
        return {
            "path": str(profile_resource(INTERNAL_MATERIALS_PATH, "materials.v015.json")),
            "ok": False,
            "internalMaterials": True,
            "error": str(error),
            "seconds": _elapsed(started),
        }


def _merge_internal_asset_manifest(
    asset_files: list[str],
    asset_sources: dict[str, str],
    known_assets: set[str],
) -> int:
    if not INTERNAL_ASSET_MANIFEST.is_file():
        return 0
    try:
        with INTERNAL_ASSET_MANIFEST.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return 0
    assets = manifest.get("assets", {})
    if not isinstance(assets, dict):
        return 0
    added = 0
    for packed_path, info in assets.items():
        if not packed_path or packed_path in known_assets:
            continue
        if _is_aw_asset_path(str(packed_path)):
            continue
        if not supported_source(str(info.get("sourcePack") or info.get("sourcePath") or "")):
            continue
        if not _internal_manifest_asset_is_available(str(packed_path), info):
            continue
        asset_files.append(str(packed_path))
        known_assets.add(str(packed_path))
        source = ""
        if isinstance(info, dict):
            source = str(info.get("sourcePack") or info.get("sourcePath") or "")
        asset_sources[str(packed_path)] = source or str(INTERNAL_ASSET_MANIFEST)
        added += 1
    return added


def _internal_manifest_asset_is_available(packed_path: str, info: Any) -> bool:
    if not isinstance(info, dict):
        return False
    source = str(info.get("sourcePack") or info.get("sourcePath") or "").strip()
    if source and Path(source).is_file():
        return True
    extracted_path = str(info.get("extractedPath") or "").strip()
    if extracted_path and Path(extracted_path).is_file():
        return True
    source_id = str(info.get("sourceId") or "").strip()
    if source_id:
        candidate = EXTRACTED_ASSET_ROOT / source_id / _normalize_pack_asset_path(packed_path)
        if candidate.is_file():
            return True
    return False


def _merge_extracted_asset_inventory(
    asset_files: list[str],
    asset_sources: dict[str, str],
    known_assets: set[str],
) -> int:
    if not EXTRACTED_ASSET_ROOT.is_dir():
        return 0
    added = 0
    pack_dirs = sorted(
        (
            path for path in EXTRACTED_ASSET_ROOT.iterdir()
            if path.is_dir() and path.name in ({"17309a40b912", "hby_generated_character_sets"}
                | ({"profile_190"} if current_profile() != BASE_PROFILE else set())
                | ({"profile_korea"} if current_profile() == '190-korea' else set()))
        ),
        key=lambda path: ({"hby_generated_character_sets": 0, "profile_korea": 1, "profile_190": 2}.get(path.name, 3), path.name.lower()),
    )
    for pack_dir in pack_dirs:
        for path in pack_dir.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.relative_to(pack_dir).as_posix()
            if not suffix.lower().startswith("ui/characters/"):
                continue
            if not suffix.lower().endswith((".png", ".jpg", ".jpeg", ".dds")):
                continue
            if _is_aw_asset_path(suffix):
                continue
            if suffix in known_assets:
                continue
            asset_files.append(suffix)
            known_assets.add(suffix)
            asset_sources[suffix] = str(pack_dir)
            added += 1
    return added


def _merge_local_extracted_assets(
    asset_files: list[str],
    asset_sources: dict[str, str],
) -> dict[str, Any] | None:
    started = time.perf_counter()
    known_assets = set(asset_files)
    added_assets = _merge_extracted_asset_inventory(asset_files, asset_sources, known_assets)
    if not added_assets:
        return None
    return {
        "path": str(EXTRACTED_ASSET_ROOT),
        "ok": True,
        "localAssets": True,
        "addedAssets": added_assets,
        "seconds": _elapsed(started),
    }


def _read_internal_material_reference_tables(session: Any) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    table_list = session.list_tables()
    aliases: dict[str, list[str]] = {
        **CHARACTER_TABLE_ALIASES,
        **{alias: TABLE_ALIASES.get(alias, [alias]) for alias in TABLE_ALIASES},
        **RETINUE_TABLE_ALIASES,
        **SKILL_TABLE_ALIASES,
        "character_attribute_sets": [
            "db/character_attribute_sets_tables/data__",
            "db/character_attribute_sets_tables/data",
        ],
        "character_attributes": [
            "db/character_attributes_tables/data__",
            "db/character_attributes_tables/data",
        ],
        "frontend_character_ceos": [
            "db/frontend_character_ceos_tables/_mtu_characters_ceo",
            "db/frontend_character_ceos_tables/data__",
            "db/frontend_character_ceos_tables/data",
        ],
        "agent_uniforms": [
            "db/agent_uniforms_tables/_mtu_characters",
            "db/agent_uniforms_tables/data__",
            "db/agent_uniforms_tables/data",
        ],
    }
    wanted_aliases = {
        "start_pos_characters",
        "start_pos_factions",
        *CHARACTER_TABLE_ALIASES,
        "campaign_character_art_sets",
        "campaign_character_arts",
        "agent_uniforms",
        "character_attribute_sets",
        "character_attributes",
        "frontend_character_ceos",
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
        "main_units",
        *RETINUE_TABLE_ALIASES,
        *SKILL_TABLE_ALIASES,
    }
    for alias in wanted_aliases:
        rows: list[dict[str, Any]] = []
        for table_path in _all_reference_table_paths(table_list, alias, aliases.get(alias, [alias])):
            try:
                rows.extend(
                    {
                        **row,
                        "_sourceTablePath": table_path,
                        "_sourceRank": _catalog_source_rank({"_sourceTablePath": table_path, **row}),
                    }
                    for row in session.read_table(table_path)
                )
            except ValueError:
                continue
        if rows:
            tables[alias] = rows
    return tables


def _all_reference_table_paths(table_list: list[str], alias: str, candidates: list[str]) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for candidate in candidates:
        if candidate in table_list and candidate not in seen:
            paths.append(candidate)
            seen.add(candidate)
    folder = (
        "/ceos_to_equipment_variants_tables/"
        if alias in {"equipment_variants_weapons", "equipment_variants_armours"}
        else f"/{alias}_tables/"
    )
    for path in sorted(table_list):
        if folder in path and path not in seen:
            paths.append(path)
            seen.add(path)
    return paths


def _skip_reference_pack_for_fast_open(path: Path) -> bool:
    return False


def _is_data_pack(path: Path) -> bool:
    return path.name.lower().startswith("data") or path.name.lower() in {"database.pack"}


def _is_aw_reference(path: Path | str) -> bool:
    if not path:
        return False
    return Path(path).name.lower().startswith(("aw-", "aw ", "aw_"))


def _is_aw_asset_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/aw_" in normalized or normalized.startswith("aw_") or "/characters/aw_" in normalized


def _is_lshz_reference(path: Path | str) -> bool:
    if not path:
        return False
    return Path(path).name.lower().startswith("lshz_")


def _is_image_only_reference(path: Path | str) -> bool:
    return _is_aw_reference(path) or _is_lshz_reference(path)


def _skip_bfg_resource_pack_for_fast_open(path: Path) -> bool:
    name = path.name.lower()
    return name == "bfg_astral.pack"


def _is_bfg_pack(path: Path) -> bool:
    return path.name.lower().startswith("bfg_")


def _is_bfg_reference(path: str) -> bool:
    return Path(path).name.lower().startswith("bfg_") if path else False


def _read_reference_tables(session: Any) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    table_list = session.list_tables("pack")
    aliases: dict[str, list[str]] = {
        **CHARACTER_TABLE_ALIASES,
        **{alias: TABLE_ALIASES.get(alias, [alias]) for alias in TABLE_ALIASES},
        **SKILL_TABLE_ALIASES,
        "character_attribute_sets": [
            "db/character_attribute_sets_tables/data__",
            "db/character_attribute_sets_tables/data",
        ],
        "character_attributes": [
            "db/character_attributes_tables/data__",
            "db/character_attributes_tables/data",
        ],
        "frontend_character_ceos": [
            "db/frontend_character_ceos_tables/_mtu_characters_ceo",
            "db/frontend_character_ceos_tables/data__",
            "db/frontend_character_ceos_tables/data",
        ],
        "agent_uniforms": [
            "db/agent_uniforms_tables/_mtu_characters",
            "db/agent_uniforms_tables/data__",
            "db/agent_uniforms_tables/data",
        ],
    }
    wanted_aliases = {
        *CHARACTER_TABLE_ALIASES,
        "campaign_character_art_sets",
        "campaign_character_arts",
        "agent_uniforms",
        "character_attribute_sets",
        "character_attributes",
        "frontend_character_ceos",
        "equipment_variants_weapons",
        "equipment_variants_armours",
        "melee_weapons",
        "missile_weapons",
        "projectiles",
        "unit_armour_types",
        "land_units",
        "main_units",
        *SKILL_TABLE_ALIASES,
    }
    for alias in wanted_aliases:
        rows: list[dict[str, Any]] = []
        for table_path in _all_reference_table_paths(table_list, alias, aliases.get(alias, [alias])):
            try:
                rows.extend(
                    {
                        **row,
                        "_sourceTablePath": table_path,
                        "_sourceRank": _catalog_source_rank({"_sourceTablePath": table_path, **row}),
                    }
                    for row in session.read_table(table_path)
                )
            except ValueError:
                continue
        if rows:
            tables[alias] = rows
    return tables


def _read_data_pack_reference_tables(session: Any) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for alias in ("character_attribute_sets", "character_attributes"):
        try:
            table_name = _resolve_reference_character_table(session, alias)
            tables[alias] = session.read_table(table_name)
        except ValueError:
            continue
    return tables


def _append_missing_rows(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    key_field: str,
    reference_path: str,
) -> None:
    existing = {row.get(key_field): row for row in target if row.get(key_field) is not None}
    for row in source:
        key = row.get(key_field)
        if key is None:
            continue
        incoming = _reference_row(row, reference_path)
        current = existing.get(key)
        if current is None:
            target.append(incoming)
            existing[key] = incoming
            continue
        _merge_reference_row(current, incoming, reference_path)


def _append_missing_rows_by_fields(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    fields: tuple[str, ...],
    reference_path: str,
) -> None:
    existing = {
        tuple(row.get(field) for field in fields): row
        for row in target
    }
    for row in source:
        key = tuple(row.get(field) for field in fields)
        incoming = _reference_row(row, reference_path)
        if key in existing:
            if _is_bfg_reference(reference_path):
                existing[key].setdefault("_externalImageSetSourcePath", reference_path)
            _merge_reference_row(existing[key], incoming, reference_path)
            continue
        target.append(incoming)
        existing[key] = target[-1]


def _append_missing_rows_by_key(
    target: list[dict[str, Any]],
    source: list[dict[str, Any]],
    key_func: Any,
    reference_path: str,
) -> None:
    existing = {key_func(row): row for row in target if key_func(row)}
    for row in source:
        key = key_func(row)
        if not key:
            continue
        incoming = _reference_row(row, reference_path)
        current = existing.get(key)
        if current is None:
            target.append(incoming)
            existing[key] = incoming
            continue
        _merge_reference_row(current, incoming, reference_path)


def _reference_row(row: dict[str, Any], reference_path: str) -> dict[str, Any]:
    prepared = {**row}
    prepared.setdefault("_referenceSourcePath", reference_path)
    if "_sourceRank" not in prepared and "sourceRank" not in prepared:
        prepared["_sourceRank"] = _catalog_source_rank(prepared)
    return prepared


def _merge_reference_row(current: dict[str, Any], incoming: dict[str, Any], reference_path: str) -> None:
    if _is_bfg_reference(reference_path):
        current.setdefault("_externalImageSetSourcePath", reference_path)
    if _reference_row_should_replace(current, incoming):
        current.clear()
        current.update(incoming)


def _reference_row_should_replace(current: dict[str, Any], incoming: dict[str, Any]) -> bool:
    current_rank = _catalog_source_rank(current)
    incoming_rank = _catalog_source_rank(incoming)
    if incoming_rank != current_rank:
        return incoming_rank > current_rank
    current_path = str(current.get("_sourceTablePath") or current.get("sourceTablePath") or "")
    incoming_path = str(incoming.get("_sourceTablePath") or incoming.get("sourceTablePath") or "")
    return incoming_path < current_path


def _key_field_for_alias(alias: str) -> str:
    if alias == "campaign_character_art_sets":
        return "art_set_id"
    if alias in {"equipment_variants_weapons", "equipment_variants_armours"}:
        return "ceos_key"
    if alias == "main_units":
        return "unit"
    return "key"


def _unit_stats_for_details(
    template_key: str,
    details: list[dict[str, Any]],
    land_units: dict[str, dict[str, Any]],
    retinue_initial_units: dict[str, list[str]] | None = None,
    main_units: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    retinue_initial_units = retinue_initial_units or {}
    main_units = main_units or {}
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") != game_mode:
                continue
            retinue_key = str(detail.get("retinue") or "")
            stats = _unit_stats_for_retinue(retinue_key, land_units, retinue_initial_units, main_units)
            if stats:
                return stats
    for detail in details:
        retinue_key = str(detail.get("retinue") or "")
        stats = _unit_stats_for_retinue(retinue_key, land_units, retinue_initial_units, main_units)
        if stats:
            return stats
    name_token = _character_token_from_template(template_key)
    row = _best_land_unit(name_token, land_units)
    if row:
        return _unit_stats_from_row(row)
    return {}


def _main_units_by_unit_record(tables: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    by_unit: dict[str, dict[str, Any]] = {}
    for row in tables.get("main_units", []):
        unit_key = str(row.get("unit") or row.get("key") or "")
        land_unit_key = str(row.get("land_unit") or "")
        if unit_key and land_unit_key and unit_key not in by_unit:
            by_unit[unit_key] = row
    return by_unit


def _retinue_initial_unit_records(tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    rows = sorted(
        tables.get("retinue_slot_initial_units", []),
        key=lambda row: (
            str(row.get("retinue") or ""),
            _slot_index_sort_key(row.get("slot_index")),
            str(row.get("initial_unit_record") or ""),
        ),
    )
    by_retinue: dict[str, list[str]] = {}
    for row in rows:
        retinue_key = str(row.get("retinue") or "")
        unit_key = str(row.get("initial_unit_record") or "")
        if not retinue_key or not unit_key:
            continue
        units = by_retinue.setdefault(retinue_key, [])
        if unit_key not in units:
            units.append(unit_key)
    return by_retinue


def _slot_index_sort_key(value: Any) -> tuple[int, str]:
    number = _number_or_none(value)
    if number is not None:
        return (0, str(number).zfill(8))
    return (1, str(value or ""))


def _unit_stats_for_retinue(
    retinue_key: str,
    land_units: dict[str, dict[str, Any]],
    retinue_initial_units: dict[str, list[str]],
    main_units: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not retinue_key:
        return {}
    unit_keys = _unit_key_candidates(retinue_key, retinue_initial_units.get(retinue_key, []))
    for unit_key in unit_keys:
        row = _land_unit_row_for_unit_record(unit_key, land_units, main_units)
        if row:
            return _unit_stats_from_row(row, retinue_key)
    return {}


def _unit_key_candidates(retinue_key: str, initial_unit_records: list[str]) -> list[str]:
    candidates: list[str] = []
    for key in [retinue_key, *initial_unit_records]:
        for candidate in _land_unit_key_variants(key):
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _land_unit_key_variants(key: str) -> list[str]:
    text = str(key or "")
    variants = [text] if text else []
    for element in ("earth", "fire", "metal", "water", "wood"):
        generic_then_element = f"_generic_{element}"
        element_then_generic = f"_{element}_generic"
        if generic_then_element in text:
            variants.append(text.replace(generic_then_element, element_then_generic))
        if element_then_generic in text:
            variants.append(text.replace(element_then_generic, generic_then_element))
    return variants


def _land_unit_row_for_unit_record(
    unit_key: str,
    land_units: dict[str, dict[str, Any]],
    main_units: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    row = land_units.get(unit_key)
    if row:
        return row
    main_unit = main_units.get(unit_key)
    if not main_unit:
        return None
    land_unit_key = str(main_unit.get("land_unit") or "")
    if not land_unit_key:
        return None
    return land_units.get(land_unit_key)


def _unit_stats_from_row(row: dict[str, Any], source_retinue_key: str = "") -> dict[str, Any]:
    return {
        "landUnitKey": row.get("key"),
        "sourceRetinueKey": source_retinue_key,
        "unitMeleeAttack": _number_or_none(row.get("melee_attack")),
        "unitMeleeDefence": _number_or_none(row.get("melee_defence")),
        "unitChargeBonus": _number_or_none(row.get("charge_bonus")),
        "unitDismountedMeleeAttack": _number_or_none(row.get("dismounted_melee_attack")),
        "unitDismountedChargeBonus": _number_or_none(row.get("dismounted_charge_bonus")),
        "unitMorale": _number_or_none(row.get("morale")),
        "unitPrimaryAmmo": _number_or_none(row.get("primary_ammo")),
        "unitCategory": row.get("category"),
        "unitClass": row.get("class"),
        "unitFromReference": bool(row.get("_referenceSourcePath")),
        "unitReferenceSource": row.get("_referenceSourcePath"),
    }


def _attribute_stats_by_set(tables: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    ranks: dict[tuple[str, str], int] = {}
    for row in tables.get("character_attributes", []):
        set_key = _attribute_set_key(row)
        if not set_key:
            continue
        attr_key = _attribute_stat_key(row)
        value = _attribute_stat_value(row)
        if not attr_key or value is None:
            continue
        identity = (set_key, attr_key)
        rank = _catalog_source_rank(row)
        if identity in ranks and rank < ranks[identity]:
            continue
        grouped.setdefault(set_key, {})[attr_key] = value
        ranks[identity] = rank
    for set_key, stats in _DEFAULT_ATTRIBUTE_STATS_BY_SET.items():
        grouped.setdefault(set_key, dict(stats))
    return grouped


_ATTRIBUTE_STAT_PRESETS = {
    "balanced": {"expertise": 40, "resolve": 40, "cunning": 40, "instinct": 40, "authority": 40},
    "earth": {"expertise": 45, "resolve": 30, "cunning": 40, "instinct": 35, "authority": 50},
    "fire": {"expertise": 40, "resolve": 35, "cunning": 30, "instinct": 50, "authority": 45},
    "metal": {"expertise": 50, "resolve": 40, "cunning": 45, "instinct": 30, "authority": 35},
    "water": {"expertise": 35, "resolve": 45, "cunning": 50, "instinct": 40, "authority": 30},
    "wood": {"expertise": 30, "resolve": 50, "cunning": 35, "instinct": 45, "authority": 40},
    "healer": {"expertise": 30, "resolve": 45, "cunning": 35, "instinct": 50, "authority": 40},
    "scholar": {"expertise": 50, "resolve": 40, "cunning": 30, "instinct": 35, "authority": 45},
    "veteran": {"expertise": 35, "resolve": 50, "cunning": 45, "instinct": 40, "authority": 30},
}


def _build_default_attribute_stats_by_set() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for element in ("earth", "fire", "metal", "water", "wood"):
        for suffix in ("records", "romance"):
            result[f"3k_main_attribute_set_general_{element}_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS[element])
            result[f"3k_dlc06_attribute_set_general_nanman_{element}_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS[element])
    for suffix in ("records", "romance"):
        result[f"3k_dlc06_attribute_set_general_nanman_balanced_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS["balanced"])
        for role in ("healer", "scholar", "veteran"):
            result[f"3k_ytr_attribute_set_general_{role}_{suffix}"] = dict(_ATTRIBUTE_STAT_PRESETS[role])
    return result


_DEFAULT_ATTRIBUTE_STATS_BY_SET = _build_default_attribute_stats_by_set()


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


def _attribute_stats_for_details(
    details: list[dict[str, Any]],
    stats_by_set: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    for game_mode in ("historical", "romance"):
        for detail in details:
            if detail.get("gameMode") != game_mode:
                continue
            stats = stats_by_set.get(str(detail.get("attributeSet") or ""))
            if stats:
                return stats
    for detail in details:
        stats = stats_by_set.get(str(detail.get("attributeSet") or ""))
        if stats:
            return stats
    return {}


def _attribute_stat_key(row: dict[str, Any]) -> str | None:
    value = str(
        row.get("attribute_type")
        or row.get("attribute")
        or row.get("character_attribute")
        or row.get("attribute_key")
        or row.get("key")
        or ""
    ).lower()
    stat_key = _attribute_stat_key_from_text(value)
    if stat_key:
        return stat_key
    for cell in row.values():
        stat_key = _attribute_stat_key_from_text(str(cell or "").lower())
        if stat_key:
            return stat_key
    return None


def _attribute_stat_key_from_text(value: str) -> str | None:
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


def _attribute_stat_value(row: dict[str, Any]) -> int | float | None:
    for column in ("value", "attribute_value", "base_value", "initial_value", "starting_value", "amount"):
        value = row.get(column)
        if isinstance(value, (int, float)):
            return value
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
            return value
    return None


def _character_token_from_template(template_key: str) -> str:
    token = template_key
    for marker in ("template_historical_", "template_ancestral_"):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    for suffix in ("_hero_earth", "_hero_fire", "_hero_metal", "_hero_water", "_hero_wood"):
        token = token.removesuffix(suffix)
    return token.removeprefix("lady_")


def _best_land_unit(
    name_token: str,
    land_units: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not name_token:
        return None
    candidates = []
    for key, row in land_units.items():
        normalized = key.lower()
        if name_token.lower() not in normalized:
            continue
        priority = 0 if "_general_" in normalized else 1
        candidates.append((priority, key.count("_"), key, row))
    if not candidates:
        return None
    return sorted(candidates)[0][3]


def _read_all_loc_text(session: Any) -> dict[str, str]:
    texts: dict[str, str] = {}
    for loc_path in sorted(session.list_loc_files(), key=_loc_merge_priority):
        try:
            texts.update(session.read_loc(loc_path))
        except (NotImplementedError, ValueError):
            continue
    from .korean_patch import overlay
    return overlay(texts)


def _loc_merge_priority(loc_path: str) -> tuple[int, str]:
    text = str(loc_path or "").replace("\\", "/").lower()
    if "mtu_pack_editor/merged_korean" in text:
        return (5, text)
    if "mtu_pack_editor/ceo_node_titles_from_game" in text:
        return (4, text)
    if "ironic_addon_korea" in text or "korea" in text or "190expande_korea_addon" in text:
        return (3, text)
    if "localisation__" in text or "local_kr" in text:
        return (2, text)
    return (1, text)


def _character_display_name(template: dict[str, Any], loc_text: dict[str, str]) -> str | None:
    key = str(template.get("key", ""))

    frontend_name, _frontend_title = _frontend_character_description_parts(key, loc_text)
    if frontend_name:
        return frontend_name

    korean_name = korean_character_name(key)
    if korean_name:
        return korean_name

    parts = [
        _name_text(template.get("family_name"), loc_text),
        _name_text(template.get("forename"), loc_text),
        _name_text(template.get("other_name"), loc_text),
    ]
    id_text = "".join(part for part in parts if part)
    key_text = _display_name_from_key(key, loc_text)
    return id_text or key_text


def _frontend_character_description_parts(template_key: str, loc_text: dict[str, str]) -> tuple[str, str]:
    key = str(template_key or "").strip()
    if not key or not loc_text:
        return "", ""
    prefixes = [
        f"frontend_faction_leader_unique_characters_localised_description_{key}",
        f"frontend_characters_localised_description_{key}",
    ]
    values: list[str] = []
    for prefix in prefixes:
        for suffix in ("_190", "_194", "_200", ""):
            value = loc_text.get(f"{prefix}{suffix}")
            if value:
                values.append(str(value))
    if not values:
        for loc_key, value in loc_text.items():
            loc_key_text = str(loc_key or "")
            if any(loc_key_text.startswith(prefix) for prefix in prefixes):
                values.append(str(value))
                break
    for value in values:
        lines = _frontend_description_lines(value)
        if len(lines) >= 2:
            return lines[0], lines[1]
        if lines:
            return lines[0], ""
    return "", ""


def _frontend_description_lines(value: str) -> list[str]:
    text = str(value or "").replace("\\\\n", "\n").replace("\\n", "\n")
    text = re.sub(r"\{\{tr:[^}]+\}\}", "", text)
    text = re.sub(r"\[\[/?(?:b|i|col:[^\]]+)\]\]", "", text)
    text = re.sub(r"\[\[/?[^\]]+\]\]", "", text)
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("장군 유형:")
    ]


def _name_text(value: Any, loc_text: dict[str, str]) -> str | None:
    if value in {None, "", 0, "0"}:
        return None
    name_id = str(value)
    return (
        loc_text.get(f"names_alt_name_{name_id}")
        or loc_text.get(f"names_name_{name_id}")
    )


def _display_name_from_key(template_key: str, loc_text: dict[str, str]) -> str | None:
    tokens = _name_tokens_from_template_key(template_key)
    if not tokens:
        return None

    roman_to_alt = _romanized_name_lookup(loc_text)
    resolved: list[str] = []
    index = 0
    while index < len(tokens):
        two = "".join(tokens[index:index + 2]).lower()
        if index + 1 < len(tokens) and two in roman_to_alt:
            resolved.append(roman_to_alt[two])
            index += 2
            continue
        one = tokens[index].lower()
        if one in roman_to_alt:
            resolved.append(roman_to_alt[one])
        index += 1
    return "".join(resolved) or None


def _name_tokens_from_template_key(template_key: str) -> list[str]:
    marker = "_template_"
    if marker in template_key:
        template_key = template_key.split(marker, 1)[1]
    tokens = [
        token
        for token in template_key.split("_")
        if token not in {
            "3k",
            "main",
            "mtu",
            "dlc04",
            "dlc05",
            "template",
            "historical",
            "generated",
            "lady",
            "hero",
            "earth",
            "fire",
            "metal",
            "water",
            "wood",
        }
    ]
    return tokens


def _romanized_name_lookup(loc_text: dict[str, str]) -> dict[str, str]:
    cache_key = (id(loc_text), len(loc_text))
    cached = _ROMANIZED_NAME_LOOKUP_CACHE.get(cache_key)
    if cached is not None:
        return cached
    lookup: dict[str, str] = {}
    for key, romanized in loc_text.items():
        if not key.startswith("names_name_"):
            continue
        name_id = key.removeprefix("names_name_")
        alt = loc_text.get(f"names_alt_name_{name_id}")
        if romanized and alt:
            lookup[_normalize_romanized_name(romanized)] = alt
    if len(_ROMANIZED_NAME_LOOKUP_CACHE) > 4:
        _ROMANIZED_NAME_LOOKUP_CACHE.clear()
    _ROMANIZED_NAME_LOOKUP_CACHE[cache_key] = lookup
    return lookup


def _normalize_romanized_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _friendly_key(value: str) -> str:
    translated = _korean_label_from_text(value)
    if translated and translated != str(value or ""):
        return translated
    marker_words = {
        "3k",
        "main",
        "mtu",
        "template",
        "historical",
        "hero",
        "general",
        "character",
    }
    words = [word for word in value.split("_") if word and word not in marker_words]
    return " ".join(words[-4:]) if words else value


def _friendly_character_label(value: str) -> str:
    translated = _korean_character_label_from_key(value) or _korean_label_from_text(value)
    if translated and translated != str(value or ""):
        return translated
    tokens = _name_tokens_from_template_key(value)
    return " ".join(tokens) if tokens else _friendly_key(value)


def _friendly_art_set_label(value: str, loc_text: dict[str, str] | None = None) -> str:
    return _localized_label(value, context="art", loc_text=loc_text) or str(value or "")


def _friendly_model_set_label(value: Any, fallback_name: str) -> str:
    model_key = str(value or "")
    if not model_key:
        return fallback_name
    if fallback_name:
        return f"{fallback_name} 모델"
    return model_key


def _korean_name_from_art_or_model_key(value: str, loc_text: dict[str, str]) -> str | None:
    token = _character_token_from_art_or_model_key(value)
    if not token:
        return None
    prefixes = _key_prefix_candidates(value)
    element_suffixes = ["earth", "fire", "metal", "water", "wood"]
    candidates: list[str] = []
    for prefix in prefixes:
        candidates.extend(
            f"{prefix}_template_historical_{token}_hero_{element}"
            for element in element_suffixes
        )
        candidates.append(f"{prefix}_template_historical_{token}")
    for candidate in candidates:
        korean_name = korean_character_name(candidate)
        if korean_name:
            return korean_name
        display_name = _display_name_from_key(candidate, loc_text)
        if display_name:
            return display_name
    return None


def _key_prefix_candidates(value: str) -> list[str]:
    parts = value.split("_")
    candidates = []
    if len(parts) >= 2 and parts[0] == "3k":
        candidates.append("_".join(parts[:2]))
    if parts and parts[0] in {"ep"}:
        candidates.append(parts[0])
    for prefix in ["3k_main", "3k_mtu", "3k_dlc04", "3k_dlc05", "3k_dlc06", "3k_dlc07", "3k_ytr", "ep"]:
        if prefix not in candidates:
            candidates.append(prefix)
    return candidates


def _character_token_from_art_or_model_key(value: str) -> str:
    token = value
    for marker in (
        "_art_set_historical_",
        "_art_set_generated_",
        "_hero_skin_",
        "_general_",
        "_template_historical_",
    ):
        if marker in token:
            token = token.split(marker, 1)[1]
            break
    for suffix in (
        "_general",
        "_hero",
        "_earth",
        "_fire",
        "_metal",
        "_water",
        "_wood",
    ):
        token = token.removesuffix(suffix)
    return token.strip("_")


def _primary_art_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    adult_rows = [row for row in rows if row.get("has_come_of_age") is True]
    if adult_rows:
        return sorted(adult_rows, key=lambda row: (-_catalog_source_rank(row), int(row.get("age") or 999)))[0]
    non_baby_rows = [
        row for row in rows
        if str(row.get("portrait", "")).strip("/") not in {"baby", "child_01_male", "child_03_male", "child_01_female"}
    ]
    candidates = non_baby_rows if non_baby_rows else rows
    return sorted(candidates, key=lambda row: (-_catalog_source_rank(row), int(row.get("age") or 999)))[0]


def _build_asset_index(asset_files: list[str]) -> dict[str, Any]:
    normalized_files = [path.replace("\\", "/") for path in asset_files]
    lower_to_path: dict[str, str] = {}
    priority: dict[str, int] = {}
    stills_by_name: dict[tuple[str, str], list[str]] = {}
    for index, path in enumerate(normalized_files):
        lower = path.lower()
        lower_to_path.setdefault(lower, path)
        priority.setdefault(lower, index)
        if "/stills/" in lower and lower.endswith(".png"):
            parts = lower.rsplit("/", 1)
            name = parts[-1].removesuffix(".png") if parts else ""
            kind = lower.split("/stills/", 1)[1].split("/", 1)[0]
            stills_by_name.setdefault((name, kind), []).append(path)
    return {
        "files": normalized_files,
        "lower_to_path": lower_to_path,
        "priority": priority,
        "stills_by_name": stills_by_name,
        "prefix_cache": {},
    }


def _find_art_portrait(asset_index, portrait_key, card_key):
    # KRC is a shared layered-portrait folder: its root stills are transparent
    # armour layers, while the card token identifies the actual character face.
    if str(portrait_key).strip('/').lower() == 'krc_artsets':
        for size in ('', 'large/'):
            path = f'ui/characters/KRC_artsets/stills/halfbody_large/faces/{size}{card_key}.png'
            found = asset_index['lower_to_path'].get(path.lower())
            if found:
                return found
        return None
    return _find_character_panel_image(asset_index, portrait_key) or _find_character_image(asset_index, portrait_key, 'halfbody_large')


def _find_character_image(asset_index: dict[str, Any], image_key: str, image_kind: str) -> str | None:
    if not image_key:
        return None
    asset_files = asset_index["files"]
    normalized = image_key.strip("/")
    image_name = normalized.rsplit("/", 1)[-1]
    preferred = [
        f"ui/characters/{normalized}/stills/{image_kind}/{normalized}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/large/{normalized}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/{image_name}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/large/{image_name}.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/norm.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/happy.png",
        f"ui/eventpics/{image_name}.png",
    ]
    if image_name.startswith("ep_"):
        preferred.append(f"ui/eventpics/ep_event_{image_name.removeprefix('ep_')}.png")
    assets_by_lower = asset_index["lower_to_path"]
    for path in preferred:
        found = assets_by_lower.get(path.lower())
        if found:
            return found
    still_matches = asset_index["stills_by_name"].get((image_name.lower(), image_kind.lower()), [])
    if still_matches:
        return sorted(still_matches, key=lambda path: (
            _character_still_priority(path, image_kind),
            asset_index["priority"].get(path.lower(), 10**9),
        ))[0]
    folder_candidates = _image_folder_candidates(normalized)
    for folder in folder_candidates:
        found = _find_character_image_in_folder(asset_index, folder, image_kind)
        if found:
            return found
    composite_prefixes = _character_composite_prefixes(normalized)
    for prefix in composite_prefixes:
        candidates = [
            path
            for path in _asset_files_for_prefix(asset_index, prefix)
            if "/large_panel/" in path.lower()
            and path.lower().endswith(("/norm.png", "/happy.png", "/angry.png", "/noanim.png"))
        ]
        if candidates:
            return sorted(candidates, key=lambda path: (*_character_preview_priority(path), asset_index["priority"].get(path.lower(), 10**9)))[0]
    if "/" in normalized:
        return None
    return _find_character_image_in_folder(asset_index, normalized, image_kind)


def _find_character_panel_image(asset_index: dict[str, Any], image_key: str) -> str | None:
    if not image_key:
        return None
    normalized = image_key.strip("/").removesuffix("/")
    image_name = normalized.rsplit("/", 1)[-1]
    preferred = [
        f"ui/characters/{normalized}/composites/large_panel/norm/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/norm.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/normal.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/happy.png",
        f"ui/characters/{normalized}/composites/large_panel/angry/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/angry/angry.png",
    ]
    assets_by_lower = asset_index["lower_to_path"]
    for path in preferred:
        found = assets_by_lower.get(path.lower())
        if found:
            return found
    for folder in _image_folder_candidates(normalized):
        candidates = [
            path
            for path in _asset_files_for_prefix(asset_index, f"ui/characters/{folder.lower()}/")
            if "/composites/large_panel/" in path.lower()
            and path.lower().endswith(("/noanim.png", "/norm.png", "/normal.png", "/happy.png", "/angry.png"))
        ]
        if candidates:
            return sorted(candidates, key=lambda path: (*_character_preview_priority(path), asset_index["priority"].get(path.lower(), 10**9)))[0]
    if image_name != normalized:
        return _find_character_panel_image(asset_index, image_name)
    return None


def _image_folder_candidates(value: str) -> list[str]:
    normalized = str(value or "").replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    candidates: list[str] = []
    if not parts:
        return candidates
    lower_parts = [part.lower() for part in parts]
    if "characters" in lower_parts:
        index = lower_parts.index("characters")
        if len(parts) > index + 1:
            candidates.append(parts[index + 1])
    if "stills" in lower_parts:
        index = lower_parts.index("stills")
        if index > 0:
            candidates.append(parts[index - 1])
    if len(parts) == 1:
        candidates.append(parts[0])
    return list(dict.fromkeys(candidate.strip("/") for candidate in candidates if candidate))


def _find_character_image_in_folder(asset_index: dict[str, Any], folder: str, image_kind: str) -> str | None:
    normalized = str(folder or "").strip("/").lower()
    if not normalized:
        return None
    matches = [
        path for path in _asset_files_for_prefix(asset_index, f"ui/characters/{normalized}/")
        if path.lower().startswith(f"ui/characters/{normalized}/")
        and (
            f"/stills/{image_kind.lower()}/" in path.lower()
            or "/composites/large_panel/norm/" in path.lower()
            or "/composites/large_panel/happy/" in path.lower()
        )
        and path.lower().endswith(".png")
    ]
    return sorted(matches, key=lambda path: (
        _character_still_priority(path, image_kind),
        asset_index["priority"].get(path.lower(), 10**9),
    ))[0] if matches else None


def _character_still_priority(path: str, image_kind: str) -> int:
    lower = path.lower().replace("\\", "/")
    marker = f"/stills/{image_kind.lower()}/"
    if marker in lower:
        tail = lower.split(marker, 1)[1]
        if "/" not in tail:
            return 0
        if tail.startswith("large/"):
            return 1
        return 5
    if "/composites/large_panel/norm/" in lower:
        return 2
    if "/composites/large_panel/happy/" in lower:
        return 3
    return 4


def _asset_files_for_prefix(asset_index: dict[str, Any], prefix: str) -> list[str]:
    normalized_prefix = prefix.lower()
    cache = asset_index["prefix_cache"]
    if normalized_prefix not in cache:
        cache[normalized_prefix] = [
            path for path in asset_index["files"]
            if path.lower().startswith(normalized_prefix)
        ]
    return cache[normalized_prefix]


def _character_composite_prefixes(normalized_key: str) -> list[str]:
    parts = [part for part in normalized_key.lower().strip("/").split("/") if part]
    prefixes: list[str] = []
    if len(parts) >= 2:
        first, second = parts[0], parts[1]
        gender = second if second in {"female", "male"} else None
        element = first.split("_", 1)[0]
        if gender and element in {"earth", "fire", "metal", "water", "wood"}:
            if first == "water_strategist":
                prefixes.append(f"ui/characters/water_strategist_ban/{gender}/")
            prefixes.append(f"ui/characters/{first}/{gender}/")
            prefixes.append(f"ui/characters/{element}/{gender}/")
    if parts:
        prefixes.append(f"ui/characters/{parts[0]}/")
    return prefixes


def _character_preview_priority(path: str) -> tuple[int, str]:
    lower = path.lower()
    if "/large_panel/norm/norm.png" in lower:
        return (0, lower)
    if "/large_panel/happy/happy.png" in lower:
        return (1, lower)
    if "/large_panel/angry/angry.png" in lower:
        return (2, lower)
    return (3, lower)


def _character_image_assets(
    asset_index: dict[str, Any],
    asset_sources: dict[str, str],
    portrait_key: str,
    card_key: str,
) -> list[dict[str, str]]:
    asset_files = asset_index["files"]
    exact_prefixes: list[str] = []
    for key, kind in ((portrait_key, "halfbody_large"), (card_key, "unitcards")):
        preview_path = _find_character_image(asset_index, str(key or ""), kind)
        character_prefix = _character_asset_prefix_from_path(preview_path or "")
        if character_prefix:
            exact_prefixes.append(character_prefix)
        composite_prefix = _composite_asset_prefix_from_path(preview_path or "")
        if composite_prefix:
            exact_prefixes.append(composite_prefix)

    folders = []
    for key in (portrait_key, card_key):
        for folder in _image_folder_candidates(str(key or "")):
            if folder and folder not in folders:
                folders.append(folder)

    assets = []
    seen = set()
    prefixes = exact_prefixes or [f"ui/characters/{folder.lower()}/" for folder in folders]
    for prefix in dict.fromkeys(prefixes):
        for path in _asset_files_for_prefix(asset_index, prefix):
            normalized_path = path
            lower_path = normalized_path.lower()
            if normalized_path in seen:
                continue
            if _is_duplicate_character_folder_path(normalized_path):
                continue
            if not lower_path.startswith(prefix):
                continue
            if not lower_path.endswith((".png", ".jpg", ".jpeg", ".dds")):
                continue
            assets.append({
                "path": normalized_path,
                "sourcePath": asset_sources.get(path, asset_sources.get(normalized_path, "")),
            })
            seen.add(normalized_path)
    return sorted(assets, key=lambda item: item["path"])


def _is_duplicate_character_folder_path(path: str) -> bool:
    parts = [part for part in path.replace("\\", "/").strip("/").split("/") if part]
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


def _composite_asset_prefix_from_path(path: str) -> str | None:
    lower = path.replace("\\", "/").lower()
    marker = "/large_panel/"
    if marker in lower and "/composites/" in lower:
        return lower.split(marker, 1)[0] + "/"
    marker = "/small_panel/"
    if marker in lower and "/composites/" in lower:
        return lower.split(marker, 1)[0] + "/"
    return None


def _character_asset_prefix_from_path(path: str) -> str | None:
    normalized = path.replace("\\", "/").strip("/")
    lower = normalized.lower()
    if not lower.startswith("ui/characters/"):
        return None
    for marker in ("/composites/", "/stills/"):
        index = lower.find(marker)
        if index >= 0:
            return normalized[:index].lower() + "/"
    return None


def _unique_options(values: Any) -> list[dict[str, str]]:
    seen: set[str] = set()
    options: list[dict[str, str]] = []
    for value in values:
        if value in {None, "", 0, "0"}:
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        options.append({"key": key, "label": _localized_label(key)})
    return sorted(options, key=lambda item: item["label"])


def _resolve_source_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in CHARACTER_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    raise ValueError(f"Required character table is missing in {source}: {alias}")


def _resolve_stat_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    generic_prefix = (
        "db/ceos_to_equipment_variants_tables/"
        if alias in {"equipment_variants_weapons", "equipment_variants_armours"}
        else f"db/{alias}_tables/"
    )
    matches = sorted(table for table in tables if table.startswith(generic_prefix))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preferred = [
            table for table in matches
            if "/data__" in table or table.endswith(f"/{alias}") or table.endswith(f"/_{alias}")
        ]
        if len(preferred) == 1:
            return preferred[0]
        return matches[0]
    raise ValueError(f"Required stat table is missing in {source}: {alias}")


def _resolve_retinue_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in RETINUE_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    matches = sorted(table for table in tables if table.startswith(f"db/{alias}_tables/"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preferred = [
            table for table in matches
            if "/data__" in table or table.endswith(f"/{alias}") or table.endswith(f"/_{alias}")
        ]
        if len(preferred) == 1:
            return preferred[0]
        return matches[0]
    raise ValueError(f"Required retinue table is missing in {source}: {alias}")


def _resolve_skill_table(session: Any, alias: str, source: str) -> str:
    tables = set(session.list_tables(source))
    for candidate in SKILL_TABLE_ALIASES[alias]:
        if candidate in tables:
            return candidate
    matches = sorted(table for table in tables if table.startswith(f"db/{alias}_tables/"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preferred = [
            table for table in matches
            if "/_mtu" in table or "/data__" in table or "/data_" in table
        ]
        return preferred[0] if preferred else matches[0]
    raise ValueError(f"Required skill table is missing in {source}: {alias}")


def _resolve_reference_character_table(session: Any, alias: str) -> str:
    tables = set(session.list_tables("pack"))
    for candidate in CHARACTER_TABLE_ALIASES.get(alias, [alias]):
        if candidate in tables:
            return candidate
    matches = sorted(table for table in tables if table.startswith(f"db/{alias}_tables/"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preferred = [
            table for table in matches
            if "/_mtu" in table or "/data__" in table
        ]
        return preferred[0] if preferred else matches[0]
    raise ValueError(f"Required reference character table is missing: {alias}")


def _open_session(payload: dict[str, Any]) -> Any:
    input_path = payload.get("inputPath")
    if not input_path:
        raise ValueError("inputPath is required.")
    pack_path = _resolve_user_path(input_path)
    adapter_name = payload.get("adapter", "auto")
    if adapter_name == "auto":
        adapter_name = _detect_adapter(pack_path)
    if adapter_name == "rpfm":
        require_clean_pack(pack_path)
        _ensure_rpfm_server()
    return adapter_for(adapter_name).open_pack(pack_path)


def _reference_pack_paths(payload: dict[str, Any]) -> list[Path]:
    if current_profile() != BASE_PROFILE:
        return []
    raw_paths = payload.get("referencePackPaths") or []
    if isinstance(raw_paths, str):
        raw_paths = [line.strip() for line in raw_paths.splitlines()]
    paths = []
    for raw_path in raw_paths:
        if not raw_path:
            continue
        paths.append(_resolve_user_path(raw_path))
    core_reference = ROOT / "work" / "packs" / "refs" / REFERENCE_PACK
    if not paths and core_reference.is_file():
        paths.append(core_reference)
    require_supported_sources(paths)
    paths.extend(default_game_local_pack_paths())
    paths = _dedupe_paths(paths)
    return [
        path
        for _, path in sorted(
            enumerate(paths),
            key=lambda item: (_reference_pack_priority(item[1]), item[0]),
        )
    ]


def _build_reference_pack_paths(
    payload: dict[str, Any],
    recipe: Recipe,
) -> list[Path]:
    paths = _reference_pack_paths(payload)
    if not any(
        any(
            int(value)
            for value in (
                clone.armour_bonus,
                clone.melee_defence_bonus,
                clone.melee_attack_bonus,
                clone.melee_damage_bonus,
                clone.ap_melee_damage_bonus,
                clone.charge_bonus,
                clone.missile_defence_bonus,
            )
        )
        for clone in recipe.skill_set_clones
    ):
        return paths
    if any(path.name.lower() == "database.pack" for path in paths):
        return paths

    candidates: list[Path] = []
    input_path = payload.get("inputPath")
    if input_path:
        try:
            candidates.append(_resolve_user_path(input_path).parent / "database.pack")
        except (OSError, ValueError):
            pass
    candidates.extend(root / "database.pack" for root in DEFAULT_GAME_DATA_DIRS)
    candidates.append(ROOT / "work" / "packs" / "refs" / "database.pack")
    database_path = next((path.resolve() for path in candidates if path.is_file()), None)
    if database_path is None:
        raise ValueError(
            "방어력 보정 스킬을 생성할 바닐라 database.pack을 찾지 못했습니다. "
            "게임 data 폴더의 database.pack 경로를 참조 pack 목록에 추가해주세요."
        )
    paths.append(database_path)
    paths = _dedupe_paths(paths)
    return [
        path
        for _, path in sorted(
            enumerate(paths),
            key=lambda item: (_reference_pack_priority(item[1]), item[0]),
        )
    ]


def _uses_core_reference_pack(reference_paths: list[Path]) -> bool:
    return any(path.name.lower() == REFERENCE_PACK for path in reference_paths)


def _reference_core_material_report(reference_paths: list[Path]) -> dict[str, Any] | None:
    core_path = next((path for path in reference_paths if path.name.lower() == REFERENCE_PACK), None)
    if core_path is None:
        return None
    return {
        "path": str(core_path),
        "ok": True,
        "internalMaterials": True,
        "skipped": True,
        "reason": "mtu_reference_core.pack already contains the merged material/reference rows.",
        "seconds": 0.0,
    }


def _reference_pack_priority(path: Path) -> int:
    name = path.name.lower()
    if name == REFERENCE_PACK:
        return -3
    if name == "local_kr.pack":
        return -2
    if name.startswith("local_"):
        return -1
    if name.startswith("bfg_"):
        return 0
    if name.startswith("data") or name == "database.pack":
        return 1
    if name.startswith("lshz_"):
        return 2
    if name.startswith(("aw-", "aw ")):
        return 3
    return 4


def default_game_local_pack_paths() -> list[Path]:
    paths: list[Path] = []
    for root in DEFAULT_GAME_DATA_DIRS:
        for pack_name in DEFAULT_GAME_LOCAL_PACKS:
            path = root / pack_name
            if path.is_file():
                paths.append(path.resolve())
    return _dedupe_paths(paths)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _detect_adapter(pack_path: Path) -> str:
    try:
        with pack_path.open("rb") as handle:
            prefix = handle.read(64).lstrip()
    except FileNotFoundError:
        raise ValueError(f"Pack file not found: {pack_path}")
    if prefix.startswith(b"{"):
        return "mock"
    return "rpfm"


def _resolve_user_path(raw_path: Any) -> Path:
    text = str(raw_path).strip().strip('"')
    text = text.replace("\u00a5", "\\").replace("\u20a9", "\\")
    if os.name == "nt":
        normalized = text.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() == "users" and ":" not in parts[0]:
            home_parts = Path.home().parts
            if len(home_parts) >= 2 and home_parts[-2].lower() == "users":
                return Path.home().joinpath(*parts[2:])
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="tk-pack-builder-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
