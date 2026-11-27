"""Verified, bundled CEO relationships. No runtime game-directory access."""
from functools import lru_cache
import json
from pathlib import Path
from .source_profiles import resource

REGISTRY_PATH = Path(__file__).resolve().parent / 'data' / 'verified_ceo_registry.json'

def registry():
    path = resource(REGISTRY_PATH, 'verified_ceo_registry.json')
    return _registry(str(path), path.stat().st_mtime_ns)

@lru_cache(maxsize=6)
def _registry(path, stamp):
    return json.loads(Path(path).read_text(encoding='utf-8'))

registry.cache_clear = _registry.cache_clear

def resolve_title(*, initial='', node='', title=''):
    data = registry()
    excluded = set(data['excludedTitleKeys'])
    if title in data['ceoKeys'] and '_ceo_career_' in title and title not in excluded:
        return title
    if node in data['nodeToTitle']:
        return data['nodeToTitle'][node]
    candidates = data['initialToTitles'].get(initial, [])
    if len(candidates) == 1 and candidates[0] not in excluded:
        return candidates[0]
    return ''

def title_node(title):
    nodes = registry()['titleToNodes'].get(title, [])
    return nodes[0] if nodes else ''

def require_known_title(value):
    if value and (value not in registry()['ceoKeys'] or '_ceo_career_' not in value or value in registry()['excludedTitleKeys']):
        raise ValueError(f'내장 바닐라·MTU 자료에서 확인되지 않은 칭호입니다: {value}. 칭호를 다시 선택하세요.')

def validate_recipe_titles(recipe):
    for item in [*recipe.character_clones, *recipe.character_patches]:
        require_known_title(item.title_ceo_key)
        for key in item.removable_title_ceo_keys:
            require_known_title(key)
    if recipe.work_items:
        from .recipe import recipe_from_dict
        for work in recipe.work_items:
            validate_recipe_titles(recipe_from_dict(work.get('recipe') or {}))
