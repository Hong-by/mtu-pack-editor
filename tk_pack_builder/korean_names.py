from __future__ import annotations


KOREAN_CHARACTER_NAMES = {
    "3k_dlc04_template_historical_luo_jun_xiaoyuan_wood": "나준",
    "3k_dlc05_template_generated_lady_zhang_jinglan_hero_metal": "장정란",
    "3k_main_template_historical_chunyu_qiong_hero_fire": "순우경",
    "3k_main_template_historical_dong_bai_hero_metal": "동백",
    "3k_main_template_historical_hua_xin_hero_water": "화흠",
    "3k_main_template_historical_huang_zu_hero_wood": "황조",
    "3k_main_template_historical_lady_cai_yan_hero_water": "채염",
    "3k_main_template_historical_shen_pei_hero_water": "심배",
    "3k_mtu_template_ancestral_ma": "마씨",
    "3k_mtu_template_historical_chen_jiu_hero_wood": "진구",
    "3k_mtu_template_historical_dong_min_hero_earth": "동민",
    "3k_mtu_template_historical_jian_yong_hero_metal": "간옹",
    "3k_mtu_template_historical_lady_dong_peishan_hero_earth": "동패산",
    "3k_mtu_template_historical_lady_feng_hero_earth": "풍부인",
    "3k_mtu_template_historical_lady_gongsun_jinting_hero_water": "공손금정",
    "3k_mtu_template_historical_lady_guan_yinping_hero_wood": "관은병",
    "3k_mtu_template_historical_lady_lu_ji_hero_wood": "여희",
    "3k_mtu_template_historical_lady_lu_zheng_hero_water": "여정",
    "3k_mtu_template_historical_lady_ma_lanli_hero_metal": "마란리",
    "3k_mtu_template_historical_lady_wang_liting_hero_metal": "왕리정",
    "3k_mtu_template_historical_lady_wu_minyu_hero_earth": "오민옥",
    "3k_mtu_template_historical_qu_gong_hero_wood": "국공",
    "3k_mtu_template_historical_yan_xiang_hero_water": "염상",
    "3k_mtu_template_historical_zhang_bao_hero_fire": "장보",
    "3k_mtu_template_historical_zhang_xun_hero_earth": "장훈",
    "3k_mtu_template_historical_trieu_quocdat_hero_earth": "조국달",
    "3k_mtu_template_historical_wu_anguo_hero_wood": "무안국",
    "3k_mtu_template_historical_lady_zhu_beng_hero_wood": "축붕",
    "3k_mtu_template_historical_lady_du_hero_earth": "두부인",
    "3k_mtu_template_historical_lady_trieu_hero_wood": "조구",
    "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire": "장성채",
    "3k_mtu_template_historical_lady_ma_yunlu_hero_metal": "마운록",
    "3k_mtu_template_historical_lady_buyeo_wol_hero_water": "부여월",
    "3k_mtu_template_historical_lady_yuan_anyang_hero_water": "원안양",
    "3k_mtu_template_historical_lady_zou_yuan_hero_water": "추원",
}


def korean_character_name(template_key: str) -> str | None:
    return KOREAN_CHARACTER_NAMES.get(template_key)
