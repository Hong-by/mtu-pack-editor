# Three Kingdoms Custom Character Pack Builder CLI Prototype

UI 없이 `recipe.json + starter.pack -> output.pack` 흐름을 검증하는 CLI 프로토타입입니다.

현재 구현은 `MockPackAdapter`와 `RpfmAdapter`를 지원합니다. Mock `.pack`은 JSON envelope이고, RPFM 경로는 실행 중인 RPFM 서버에 붙어 실제 pack의 DB를 디코드한 뒤 숫자 cell만 수정해 저장합니다. 저장 방식은 Save As(`--output`)와 원본 저장(`--in-place`)을 분리합니다.

대상 게임은 **Total War: THREE KINGDOMS**로 고정합니다. RPFM game key는 `three_kingdoms`입니다.

## 사용법

웹 UI 실행:

```bash
python3 scripts/dev_server.py
```

브라우저에서 `http://127.0.0.1:8765`를 엽니다. 이 런처는 RPFM 서버(`127.0.0.1:45127`)와 웹 UI 서버(`127.0.0.1:8765`)를 함께 확인하고, 꺼져 있는 서버만 자동으로 켭니다.

macOS Finder에서 바로 실행하려면 프로젝트 루트의 `MTU Pack Editor.command`를 더블클릭합니다. 서버를 켠 뒤 기본 브라우저로 `http://127.0.0.1:8765`를 자동으로 엽니다.

터미널에서 브라우저까지 자동으로 열려면:

```bash
python3 scripts/dev_server.py --open-browser
```

웹 UI만 켜고 싶으면:

```bash
python3 scripts/dev_server.py --no-rpfm
```

웹 UI의 기본 저장 방식은 `패치 pack`입니다. 이 모드는 원본 MTU pack 전체를 복사하지 않고, 원본 모드는 별도로 켠다는 전제로 변경/신규 row만 담은 작은 `.pack`을 만듭니다. 원본 전체를 복사하는 방식은 저장 방식에서 `Save As 원본 복사`를 명시적으로 선택했을 때만 사용합니다.

```bash
python3 -m tk_pack_builder build \
  --recipe examples/recipe.effect-edit.json \
  --input examples/starter.pack \
  --output 출력팩/output.pack
```

원본 pack에 직접 저장:

```bash
python3 -m tk_pack_builder build \
  --recipe examples/recipe.effect-edit.json \
  --input examples/starter.pack \
  --in-place
```

검증만 실행:

```bash
python3 -m tk_pack_builder validate \
  --recipe examples/recipe.effect-edit.json \
  --input examples/starter.pack
```

Pack 분석:

```bash
python3 -m tk_pack_builder analyze --input examples/starter.pack
```

Adapter를 통해 특정 table row를 확인:

```bash
python3 -m tk_pack_builder read-table \
  --input examples/starter.pack \
  --table melee_weapons \
  --limit 5
```

RPFM 서버가 `127.0.0.1:45127`에서 실행 중이면 실제 pack도 읽기 전용으로 분석할 수 있습니다.

```bash
python3 -m tk_pack_builder --adapter rpfm analyze \
  --input /Users/hong/Downloads/my_hero.pack
```

실제 Total War PFH pack을 RPFM 연동 전에 읽기 전용으로 훑기:

```bash
python3 -m tk_pack_builder probe --input /Users/hong/Downloads/my_hero.pack --limit 80
```

실제 PFH index에서 내부 파일 경로, 크기, offset 확인:

```bash
python3 -m tk_pack_builder index \
  --input /Users/hong/Downloads/my_hero.pack \
  --contains ceos_to_equipment_variants \
  --limit 20
```

DB packed file의 schema-independent header 확인:

```bash
python3 -m tk_pack_builder db-header \
  --input /Users/hong/Downloads/my_hero.pack \
  --path db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_weapons
```

RPFM Spike 메모는 [docs/rpfm-spike.md](docs/rpfm-spike.md)를 참고하세요.

## 현재 범위

- 입력/출력은 모두 `.pack` 파일 기준입니다.
- 게임 설치 경로는 받지 않습니다.
- 대상 게임은 삼국지 토탈워(`three_kingdoms`)만 허용합니다.
- 새 장비 생성, 장비 복제, 신규 row 추가, row 삭제는 막습니다.
- 현재 pack 안에 존재하는 기존 장비가 참조하는 기존 stat row의 숫자 컬럼만 수정합니다.
- 지원 stat target:
  - `melee_weapon`: `melee_weapons`의 `damage`, `ap_damage`, `bonus_v_*`, `weapon_length` 등
  - `armour`: `unit_armour_types`의 `armour_value`
  - `projectile`: `projectiles`의 `damage`, `ap_damage`, `effective_range`, `base_reload_time` 등

## 현재 대상 Pack

작업 대상 모드팩은 `/Users/hong/Downloads/my_hero.pack`입니다. 파일 헤더는 `PFH5`인 실제 Total War pack이며, Mock Adapter가 직접 수정하지 않습니다. RPFM Adapter는 `--output`이면 새 `.pack`으로 저장하고, `--in-place`를 명시한 경우에만 원본 pack에 저장합니다.

Spike 결과, 장비 key에서 기본 stat row까지의 경로가 확인됐습니다.

- 무기 장비 → `ceos_to_equipment_variants_tables` → `melee_weapons_tables`
- 원거리 장비 → `ceos_to_equipment_variants_tables` → `missile_weapons_tables` → `projectiles_tables`
- 갑옷 장비 → `ceos_to_equipment_variants_tables` → `unit_armour_types_tables`

장비의 CEO effect bonus는 `campaigns/ceo_data.ccd` 쪽일 가능성이 있어 별도 과제로 남깁니다. 1차 기능은 일반 DB로 디코드 가능한 기본 공격력/방어력 stat 수정입니다.

검증된 실제 출력:

```bash
python3 -m tk_pack_builder --adapter rpfm build \
  --recipe examples/recipe.effect-edit.json \
  --input /Users/hong/Downloads/my_hero.pack \
  --output work/rpfm_builder_output.pack
```

실제 원본 pack에 직접 저장하려면 `--output` 대신 `--in-place`를 사용합니다. 이 모드는 원본 파일을 바꾸므로 백업 pack을 따로 둔 뒤 실행하는 것을 권장합니다.

원본 MTU pack을 별도 모드로 유지하고 변경분만 작은 패치 pack으로 만들려면:

```bash
python3 -m tk_pack_builder --adapter rpfm build \
  --recipe examples/recipe.character-clone.json \
  --input /Users/hong/Downloads/my_hero.pack \
  --output 출력팩/hby_character_delta.pack \
  --delta
```
