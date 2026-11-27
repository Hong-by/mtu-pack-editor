# 내장 참조 데이터 관리

사용자의 게임 경로는 실행 시 필요하지 않습니다. 프로그램은 배포 폴더의 재료 DB, 참조 팩, 칭호 설명, CEO 연결표를 사용합니다.

원본 갱신은 개발자가 수행합니다. `scripts/bundle_verified_reference_data.py`에 `--game-data`, `--mtu`, `--mtu-korean`을 명시하여 설치 원본을 가져옵니다. 이 스크립트는 실제 CCD의 CEO/초기 CEO/노드/효과 관계와 노드가 지정하는 번역 키를 읽습니다. 이름을 치환해서 CEO 키를 만들지 않습니다.

이후 `scripts/build_reference_core_pack.py`로 참조 팩을 갱신하고 프로그램을 다시 시작합니다. EXE 배포는 `scripts/build_windows_exe.ps1`로 새로 빌드해야 합니다. 기존 EXE는 소스 수정만으로 갱신되지 않습니다.

내장 파일:

- `work/internal_materials/vanilla_mtu/materials.v015.json`
- `work/packs/refs/mtu_vanilla_reference.pack`
- `tk_pack_builder/data/assembly_kit_title_effects.ko.json`: 파일명은 호환성을 위해 유지하며, 내용은 현재 게임에서 추출한 칭호 429개입니다.
- `tk_pack_builder/data/verified_ceo_registry.json`: 원본 CCD 해시와 검증된 관계를 함께 저장합니다.

2026-11-28 변경:

- 불완전한 월 템플릿과 관련 이름 번역 제거.
- MTU 칭호 40개 보충 및 기존 칭호 효과 교정.
- 사용자 요청으로 누락됐던 팔왕 칭호 6개는 지원 목록에서 제외. 팔왕 DLC 전체를 삭제하는 변경은 아닙니다.
- 한국어 번역을 내장 자료에 포함.
- 실제 키로 칭호를 선택하고, 없는 키를 제출하면 팩 생성을 중단.
- DB에 있는 스킬은 동명 수동 설명으로 덮지 않음.

수정 전 참조 자료는 `work/reference-data-before-fix-2026-11-28`에 보관했습니다. 기존 작업 대기열에 잘못된 칭호 키가 저장돼 있다면 프로그램을 다시 연 뒤 해당 칭호를 다시 선택해야 합니다.
