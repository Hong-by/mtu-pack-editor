# RPFM Adapter Spike

## 입력

- 사용자가 제공한 `/Users/hong/Downloads/rpfm-master.zip`
- zip 기준 커밋: `f59641d3a59c81f197794f4c7ded8882d24c8065`
- 대상 게임: Total War: THREE KINGDOMS
- RPFM game key: `three_kingdoms`
- 현재 대상 pack: `/Users/hong/Downloads/my_hero.pack`

## 확인한 구조

zip에는 Rust workspace와 다음 후보가 포함되어 있다.

- `rpfm_lib`: pack, table, loc 같은 핵심 파일 처리 라이브러리 후보
- `rpfm_ui`: Qt 기반 데스크톱 UI
- `docs/server`: RPFM server, websocket, MCP 문서
- `test_files/*.pack`: pack 읽기/쓰기 검증에 쓸 수 있는 샘플

`Cargo.toml` 기준 workspace version은 `5.0.3`이고 멤버에 `rpfm_lib`, `rpfm_server`, `rpfm_ui`가 포함되어 있다. `rpfm_lib/src/files/pack`, `rpfm_lib/src/files/table`, `rpfm_lib/src/files/loc`가 직접 연동 후보이며, `rpfm_lib/src/games/supported_games.rs`와 schema 계층도 함께 초기화해야 할 가능성이 높다.

`supported_games.rs`에서 삼국지 토탈워는 `KEY_THREE_KINGDOMS = "three_kingdoms"`로 정의되어 있고, schema 파일명은 `schema_3k.ron`, dependency cache 파일명은 `3k.pak2`다.

`/Users/hong/Downloads/my_hero.pack`는 헤더가 `PFH5`이고 크기는 약 956MB다. 문자열 probe 기준 다음 계열이 확인됐다.

- `db\character_generation_templates_tables\_mtu_characters`
- `db\character_generation_template_game_mode_details_tables\_mtu_characters`
- `db\ceo_initial_datas_tables\_mtu_characters_ceo`
- `db\ceos_to_equipment_variants_tables\_mtu_characters_ceo_armours`
- `db\ceos_to_equipment_variants_tables\_mtu_characters_ceo_mounts`
- `db\ceos_to_equipment_variants_tables\_mtu_characters_ceo_weapons`
- `db\effect_bonus_value_ids_unit_sets_tables\_mtu_characters_effects`
- `db\effects_tables\_mtu_characters_skills_effects`
- `db\melee_weapons_tables\_mtu_characters_weapons`
- `db\missile_weapons_tables\_mtu_characters_weapons`
- `db\projectiles_tables\_mtu_characters_weapons`
- `db\unit_armour_types_tables\_mtu_characters_skills_abilities`
- `text\mtu_text\*.loc`
- `ui\ancillaries\...`

서버 문서 기준 `rpfm_server`는 기본적으로 `127.0.0.1:45127`에 바인딩하고 `/ws` WebSocket 및 `/mcp` endpoint를 제공한다. WebSocket 명령에는 `OpenPackFiles`, `GetPackFileDataForTreeView`, `DecodePackedFile`, `SavePackedFileFromView`, `SavePackAs`, `GetTablesByTableName` 등이 있어 CLI Adapter의 1차 Spike 대상으로 적합하다.

## Adapter 판단

프로토타입에서는 `PackAdapter` 경계를 먼저 만들었다.

필요 인터페이스:

```text
open_pack(filePath)
list_tables()
read_table(tableName)
replace_table(tableName, rows)
list_loc_files()
read_loc(locPath)
upsert_loc_rows(locPath, rows)
list_files()
save_as_pack(outputPath)
save_pack()
```

RPFM 실제 연동은 두 갈래로 검증한다.

1. `rpfm_lib` 직접 연동
   - 장점: 로컬 CLI에 가장 깔끔하게 내장 가능
   - 리스크: Rust crate API와 schema/profile 초기화 요구사항 확인 필요
2. `rpfm_server` 연동
   - 장점: 이미 문서화된 서버 프로토콜이 있어 외부 프로세스 Adapter로 감쌀 수 있음
   - 리스크: 배포, 프로세스 관리, session lifecycle이 CLI에 추가됨

## 실제 Spike 결과

`rpfm_server`를 빌드하고 WebSocket 경로를 검증했다. zip 원본의 workspace는 Qt UI 하위 모듈이 없어 `rpfm_ui_common`, `rpfm_ui` 멤버를 제외한 뒤 `cargo build -p rpfm_server`로 서버만 빌드했다.

서버 실행:

```bash
cd work/rpfm-master
./target/debug/rpfm_server
```

검증된 호출:

1. `SetGameSelected(["three_kingdoms", false])`
2. `OpenPackFiles(["/Users/hong/Downloads/my_hero.pack"])`
3. `GetPackFileDataForTreeView(pack_key)`
4. `DecodePackedFile([pack_key, path, "PackFile"])`

처음에는 DB 디코드가 `"Missing or invalid extra data provided: \"schema\""`로 실패했다. `CheckSchemaUpdates`/`UpdateSchemas`를 실행해 `work/rpfm-master/schemas/schema_3k.ron`을 받은 뒤 DB 디코드가 성공했다.

확인된 pack 정보:

- magic: `PFH5`
- pack type: `Mod`
- 파일 수: lightweight PFH index 기준 `3460`, RPFM tree 기준 `3457`
- RPFM game key: `three_kingdoms`

디코드 성공 예:

- `db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_weapons`
  - row count: `36`
  - 주요 field: `ceos_key`, `primary_melee_weapon`, `primary_missile_weapon`, `shield`, `game_mode`
- `db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_armours`
  - row count: `37`
- `db/effect_bonus_value_ids_unit_sets_tables/_mtu_characters_effects`
  - row count: `2`
  - field: `bonus_value_id`, `effect`, `unit_set`
- `db/character_skill_level_to_effects_junctions_tables/_mtu_characters_skills`
  - row count: `330`
  - field: `character_skill_key`, `effect_key`, `effect_scope`, `level`, `value`
- `db/special_ability_phase_stat_effects_tables/_mtu_characters_skills_abilities`
  - row count: `218`
  - field: `phase`, `value`, `stat`, `how`
- `db/melee_weapons_tables/_mtu_characters_weapons`
  - row count: `24`
  - numeric stat field: `damage`, `ap_damage`, `bonus_v_cavalry`, `bonus_v_large`, `bonus_v_infantry`, `weapon_length`, `melee_attack_interval`
- `db/unit_armour_types_tables/_mtu_characters_skills_abilities`
  - row count: `37`
  - numeric stat field: `armour_value`
- `db/projectiles_tables/_mtu_characters_weapons`
  - row count: `6`
  - numeric stat field: `damage`, `ap_damage`, `effective_range`, `base_reload_time`, `shots_per_volley`

`campaigns/ceo_data.ccd`는 `DecodePackedFile` 응답이 `Unknown`이다. RPFM 소스의 `BuildCeo` 경로는 pack의 CEO DB를 Assembly Kit XML로 export하고 BOB로 `ceo_data.ccd`를 다시 만드는 방식이라, 이번 CLI 조건인 “게임 경로를 받지 않고 `.pack`만 처리”와 맞지 않는다.

## 장비 기본 Stat 경로

이번 1차 기능 대상은 CEO effect bonus가 아니라 장비가 참조하는 기존 stat row의 숫자 컬럼이다. 이 경로는 RPFM 서버로 구조화 디코드가 된다.

- 근접 무기:
  - `ceos_to_equipment_variants_tables._mtu_characters_ceo_weapons.ceos_key`
  - `primary_melee_weapon`
  - `melee_weapons_tables._mtu_characters_weapons.key`
  - `damage`, `ap_damage` 등 숫자 컬럼
- 원거리 무기:
  - `ceos_to_equipment_variants_tables._mtu_characters_ceo_weapons.ceos_key`
  - `primary_missile_weapon`
  - `missile_weapons_tables._mtu_characters_weapons.default_projectile`
  - `projectiles_tables._mtu_characters_weapons.key`
  - `damage`, `ap_damage`, `effective_range` 등 숫자 컬럼
- 갑옷:
  - `ceos_to_equipment_variants_tables._mtu_characters_ceo_armours.ceos_key`
  - `armour`
  - `unit_armour_types_tables._mtu_characters_skills_abilities.key`
  - `armour_value`

## 현재 결론

`MockPackAdapter`로 `recipe.json + starter.pack -> output.pack` 전체 흐름은 완성했다. `RpfmAdapter`도 실제 RPFM 서버에 붙어 삼국지 토탈워 pack을 열고, DB payload의 타입 태그를 보존한 채 숫자 cell을 수정하고, `SavePackedFileFromView` + `SavePackAs`로 새 pack을 저장하는 단계까지 검증했다. 원본 저장은 별도 `--in-place` 플래그로만 열며 RPFM의 `SavePack` 명령을 사용한다.

실제 출력 검증:

- 입력: `/Users/hong/Downloads/my_hero.pack`
- 출력: `work/rpfm_builder_output.pack`
- recipe: `examples/recipe.effect-edit.json`
- 결과:
  - `melee_weapons/3k_mtu_general_2h175_comet_spear_unique.damage = 25`
  - `unit_armour_types/3k_mtu_hero_chen_jiu_unique.armour_value = 70`
  - `projectiles/3k_mtu_hero_bow_hawk_unique.ap_damage = 900`

남은 Spike 순서:

1. 더 많은 stat column 조합에 대한 regression recipe 추가
2. output pack을 게임/RPFM GUI에서 수동 로드 확인
3. 필요하면 `ceo_data.ccd` 기반 CEO effect bonus 수정 가능성 조사

CEO effect bonus까지 필요해지면 `rpfm_lib`의 ESF/CCD 처리나 별도 CCD parser를 작은 Rust/Python harness로 작성하고, 추출한 `campaigns/ceo_data.ccd` 복사본을 대상으로 다음이 가능한지 확인한다.

- CEO/equipment key 검색
- effect key/value 검색
- 단일 numeric value patch
- raw 재인코딩
- pack 내부 `campaigns/ceo_data.ccd` 교체

이 검증이 통과하면 `RpfmAdapter` 구현만 교체하고 Recipe/Validation/CLI는 유지한다.
