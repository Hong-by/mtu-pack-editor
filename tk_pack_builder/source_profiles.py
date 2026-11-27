"""Request-local source selection. Bundles are imported by maintainers, never auto-discovered."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import json
import os

BASE = 'vanilla-mtu-v1'
PROFILES = {BASE: '바닐라·MTU', '190': '바닐라·MTU·190 Expanded', '190-korea': '바닐라·MTU·190 Expanded·한반도'}
ROOT = Path(os.environ.get('TK_PACK_EDITOR_ROOT', Path(__file__).resolve().parents[1])).resolve()
_active = ContextVar('source_profile', default=BASE)

def current():
    return _active.get()

def directory(profile=None):
    return ROOT / 'work/internal_materials' / ('vanilla_mtu' if (profile or current()) == BASE else (profile or current()))

def resource(default, name):
    return default if current() == BASE else directory() / name

@contextmanager
def using(profile):
    if profile not in PROFILES:
        raise ValueError('알 수 없는 데이터 구성입니다: ' + str(profile))
    token = _active.set(profile)
    try:
        yield
    finally:
        _active.reset(token)

def profiled(function):
    @wraps(function)
    def wrapped(payload):
        profile = payload.get('sourceProfile', BASE)
        with using(profile):
            request = dict(payload)
            if function.__name__ != 'open_pack_payload':
                for work in (payload.get('recipe') or {}).get('workItems', []):
                    if work.get('sourceProfile', BASE) != profile:
                        raise ValueError('다른 모드 구성에서 만든 작업이 보류되었습니다: ' + str(work.get('title', '작업')) + '. 원래 구성을 적용하거나 현재 자료로 작업을 다시 추가하세요.')
            if profile != BASE:
                folder = directory()
                for name in ('materials.v015.json', 'verified_ceo_registry.json', 'assembly_kit_title_effects.ko.json'):
                    if not (folder / name).is_file():
                        raise ValueError(f'{PROFILES[profile]} 내장 자료가 없습니다. 자료가 포함된 배포본을 사용하세요.')
                request['materialPath'] = str(folder / 'materials.v015.json')
                request['referencePackPaths'] = []
                if function.__name__ != 'open_pack_payload' and not request.get('useInternalMaterials'):
                    raise ValueError('추가 모드 구성은 패치 pack 저장을 사용하세요.')
            result = function(request)
            result['sourceProfile'] = profile
            result['sourceProfileLabel'] = PROFILES[profile]
            return result
    return wrapped
