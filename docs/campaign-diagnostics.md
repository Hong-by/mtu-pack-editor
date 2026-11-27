# 캠페인 종료 진단 로그

생성기가 새로 저장하는 팩의 캠페인 Lua에는 `[HBY_DIAG v1]` 로그가 포함된다.
기존 팩에는 자동으로 적용되지 않는다. 새로 저장한 팩을 게임에 복사해야 한다.

- `kind=new_character`: 신규 장수 생성 작업.
- `kind=existing_character`: 기존 장수 수정 작업.
- `template`: 해당 장수의 정확한 템플릿 키.
- `stage`, `status=before/after`: 호출 직전과 반환 직후.
- `pcall_ok=false`: Lua 오류가 잡힌 경우. `true`는 호출이 반환했다는 뜻이며 게임 기능 성공 보증은 아니다.
- `detail`: 변경하는 CEO·장비·칭호 키 또는 호출 반환 상태.

파일 쓰기가 허용되는 환경에서는 게임 실행 작업 디렉터리의
`hby_mtu_pack_editor_diagnostic.log`에 매 줄 추가하고 flush/close한다.
동시에 게임의 `output()`에도 기록한다. 파일 쓰기가 막혀도 기존 처리는 계속한다.
이 PC의 일반 실행 작업 디렉터리는 게임 설치 폴더이며, 실행 방식에 따라 달라질 수 있다.
각 실행은 `script_load begin`부터 구분한다. 로그는 덮어쓰지 않는다.

주요 단계:

| 단계 | 의미 |
| --- | --- |
| `script_load` | 생성된 스크립트 로딩 시작·완료 |
| `work_manifest` | DB만 수정한 작업까지 포함한 작업 목록 |
| `first_tick` | 첫 캠페인 콜백 진입·반환 |
| `hby_character.call_1` | 장수 템플릿 조회 |
| `hby_spawn_one.call_1` | 신규 장수 생성 API 호출 |
| `hby_prepare_character.call_3` | 필요한 경우 세력 이동 |
| `hby_add_ancillary_to_faction.call_3` | 세력 창고에 장비 지급 |
| `hby_apply_ceos.call_1` | 장수 CEO 변경 관리자 조회 |
| `hby_character_ceo_for_category.call_1/2` | 칭호 조회 관리자·카테고리 목록 접근 |
| `hby_remove_ceo.call_1` / `hby_add_ceo.call_1` | 개별 CEO 제거·추가 |
| `work_step returned` | 해당 작업 함수 반환(성공 여부와 별개) |

`before` 이후 대응하는 `after`가 없으면 해당 호출 도중 종료됐을 가능성을 좁힐 수 있다.
로그 자체가 생성되지 않으면 DB 로딩 중 종료, 팩 미적용, 로깅 제한 등을 구분해야 한다.
DB 로딩은 이 Lua보다 먼저 이루어지므로 DB만 수정한 장수의 로딩 단계별 추적은 지원하지 않는다.
네이티브 프로세스 충돌은 Lua `pcall`로 복구할 수 없다. 이 변경은 진단용이며 충돌 해결 패치가 아니다.

검사: `python -m unittest tests.test_campaign_diagnostics tests.test_delta_builder_material_rows`.
진단 실행 테스트에는 선택적 테스트 의존성 `lupa`의 Lua 5.1 런타임을 사용한다.
게임에서는 아직 재현 검증하지 않았다.
