from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tk_pack_builder.adapters import adapter_for


KOREAN_UNIT_NAMES = {
    "3k_ytr_unit_earth_virtuous_noblemen": "현월기",
    "ep_unit_water_qi_crossbowmen": "비노",
    "3k_ytr_unit_metal_arm_of_the_supreme_peace": "철화위",
    "3k_dlc04_unit_fire_tyrant_slayers": "홍련기",
    "3k_dlc04_unit_metal_chosen_of_the_eight_immortals": "검희",
    "ep_unit_wood_qi_guardsmen": "창랑",
    "3k_dlc07_unit_water_northern_mounted_archers": "북궁기",
    "3k_ytr_unit_water_archery_masters": "비연궁",
    "ep_unit_water_archers_of_jing": "형궁희",
    "3k_dlc04_unit_fire_righteous_vanguards": "화선기",
    "3k_dlc04_unit_wood_gallants_of_the_people": "월창",
    "3k_dlc04_unit_earth_messengers_of_heaven": "천월기",
    "3k_ytr_unit_metal_scholar_warriors": "문검랑",
    "3k_ytr_unit_metal_youxia": "유검희",
}


LITERAL_UNIT_NAMES = {
    "3k_ytr_unit_earth_virtuous_noblemen": "고결한 귀족 여성들",
    "ep_unit_water_qi_crossbowmen": "제나라 쇠뇌병 여성",
    "3k_ytr_unit_metal_arm_of_the_supreme_peace": "태평의 팔",
    "3k_dlc04_unit_fire_tyrant_slayers": "폭군을 죽이는 자들 여성",
    "3k_dlc04_unit_metal_chosen_of_the_eight_immortals": "팔선에게 선택받은 자들",
    "ep_unit_wood_qi_guardsmen": "제나라 경비병 여성",
    "3k_dlc07_unit_water_northern_mounted_archers": "북방 기마 궁수 여성",
    "3k_ytr_unit_water_archery_masters": "궁술의 대가들",
    "ep_unit_water_archers_of_jing": "형주의 궁수들 여성",
    "3k_dlc04_unit_fire_righteous_vanguards": "의로운 선봉대 여성",
    "3k_dlc04_unit_wood_gallants_of_the_people": "백성의 용사들",
    "3k_dlc04_unit_earth_messengers_of_heaven": "하늘의 사자들",
    "3k_ytr_unit_metal_scholar_warriors": "학자 전사들",
    "3k_ytr_unit_metal_youxia": "유협 여성",
}


PHONETIC_UNIT_NAMES = {
    "3k_ytr_unit_earth_virtuous_noblemen": "버추어스 노블우먼",
    "ep_unit_water_qi_crossbowmen": "치 크로스보우맨",
    "3k_ytr_unit_metal_arm_of_the_supreme_peace": "암 오브 더 슈프림 피스",
    "3k_dlc04_unit_fire_tyrant_slayers": "타이런트 슬레이어스",
    "3k_dlc04_unit_metal_chosen_of_the_eight_immortals": "초즌 오브 디 에이트 임모털스",
    "ep_unit_wood_qi_guardsmen": "치 가즈맨",
    "3k_dlc07_unit_water_northern_mounted_archers": "노던 마운티드 아처스",
    "3k_ytr_unit_water_archery_masters": "아처리 마스터스",
    "ep_unit_water_archers_of_jing": "아처스 오브 징",
    "3k_dlc04_unit_fire_righteous_vanguards": "라이처스 뱅가즈",
    "3k_dlc04_unit_wood_gallants_of_the_people": "갤런츠 오브 더 피플",
    "3k_dlc04_unit_earth_messengers_of_heaven": "메신저스 오브 헤븐",
    "3k_ytr_unit_metal_scholar_warriors": "스칼라 워리어스",
    "3k_ytr_unit_metal_youxia": "유샤",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export editable unit stats from a pack.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pack_path = args.input.resolve()
    output_path = args.output.resolve()
    csv_path = output_path.with_suffix(".csv")

    session = adapter_for("rpfm").open_pack(pack_path)
    try:
        tables = session.list_tables()
        land_path = _single(tables, "db/land_units_tables/")
        main_path = _single(tables, "db/main_units_tables/")
        land_rows = {str(row["key"]): row for row in session.read_table(land_path)}
        main_rows = session.read_table(main_path)

        loc_rows: dict[str, str] = {}
        for loc_path in session.list_loc_files():
            try:
                loc_rows.update(session.read_loc(loc_path))
            except ValueError:
                pass
    finally:
        session.close()

    rows = []
    for main in sorted(main_rows, key=lambda row: (str(row.get("ui_unit_group_land")), str(row.get("unit")))):
        key = str(main.get("land_unit") or main.get("unit") or "")
        land = land_rows.get(key, {})
        rows.append(
            {
                "unit": key,
                "korean_name": KOREAN_UNIT_NAMES.get(key, ""),
                "literal_name": LITERAL_UNIT_NAMES.get(key, ""),
                "phonetic_name": PHONETIC_UNIT_NAMES.get(key, ""),
                "name": _loc_name(loc_rows, key),
                "card": _card_name(str(main.get("unit_card") or "")),
                "category": land.get("category", ""),
                "class": land.get("class", ""),
                "recruitment_cost": main.get("recruitment_cost", ""),
                "upkeep_cost": main.get("upkeep_cost", ""),
                "multiplayer_cost": main.get("multiplayer_cost", ""),
                "create_time": main.get("create_time", ""),
                "tier": main.get("tier", ""),
                "melee_attack": land.get("melee_attack", ""),
                "melee_defence": land.get("melee_defence", ""),
                "charge_bonus": land.get("charge_bonus", ""),
                "morale": land.get("morale", ""),
                "primary_ammo": land.get("primary_ammo", ""),
                "accuracy": land.get("accuracy", ""),
                "armour": land.get("armour", ""),
                "shield": land.get("shield", ""),
                "primary_melee_weapon": land.get("primary_melee_weapon", ""),
                "primary_missile_weapon": land.get("primary_missile_weapon", ""),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(csv_path, rows)
    _write_markdown(output_path, pack_path, rows)
    print(output_path)
    print(csv_path)
    print(f"{len(rows)} units")
    return 0


def _single(tables: list[str], prefix: str) -> str:
    matches = [table for table in tables if table.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"Expected one table for {prefix}, got {matches}")
    return matches[0]


def _loc_name(loc_rows: dict[str, str], unit: str) -> str:
    for key in (
        f"land_units_onscreen_name_{unit}",
        f"main_units_onscreen_name_{unit}",
        f"units_onscreen_name_{unit}",
        f"land_units_screen_name_{unit}",
    ):
        if key in loc_rows:
            return loc_rows[key]
    return ""


def _card_name(path: str) -> str:
    if not path:
        return ""
    return path.split("/")[-1].removesuffix("_lady")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, pack_path: Path, rows: list[dict[str, object]]) -> None:
    headers = [
        "#",
        "유닛 key",
        "한글 이름",
        "직역 이름",
        "음차 이름",
        "표시명",
        "카드명",
        "분류",
        "모집비",
        "유지비",
        "멀티비",
        "모집턴",
        "티어",
        "근공",
        "근방",
        "돌격",
        "사기",
        "탄약",
        "명중",
        "갑옷",
        "방패",
    ]
    lines = [
        "# mj_women_unit_all_in_one 유닛 수치 정리",
        "",
        f"- 원본 pack: `{pack_path}`",
        f"- 유닛 수: {len(rows)}",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for index, row in enumerate(rows, 1):
        values = [
            index,
            row["unit"],
            row["korean_name"],
            row["literal_name"],
            row["phonetic_name"],
            row["name"],
            row["card"],
            f"{row['category']}/{row['class']}",
            row["recruitment_cost"],
            row["upkeep_cost"],
            row["multiplayer_cost"],
            row["create_time"],
            row["tier"],
            row["melee_attack"],
            row["melee_defence"],
            row["charge_bonus"],
            row["morale"],
            row["primary_ammo"],
            row["accuracy"],
            row["armour"],
            row["shield"],
        ]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")

    lines.extend(["", "## 무기 참조", "", "| 유닛 key | 근접무기 | 원거리무기 |", "| --- | --- | --- |"])
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    row["unit"],
                    row["primary_melee_weapon"],
                    row["primary_missile_weapon"],
                )
            )
            + " |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cell(value: object) -> str:
    return str(value).replace("|", "/")


if __name__ == "__main__":
    raise SystemExit(main())
