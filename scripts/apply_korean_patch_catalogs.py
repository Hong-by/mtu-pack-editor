"""Refresh packaged display catalogs using the bundled Gathering Korean patch."""
import copy
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tk_pack_builder.korean_patch import translations
from scripts.build_assembly_kit_ui_catalogs import clean_ui_text, effect_text


def translate_entry(entry, loc):
    result = copy.deepcopy(entry)
    key = entry.get('key', '')
    mappings = {
        'title': 'ceo_nodes_title_', 'description': 'ceo_nodes_description_',
    } if 'title' in entry else {
        'name': 'character_skills_localised_name_',
        'description': 'character_skills_localised_description_',
    }
    for field, prefix in mappings.items():
        if prefix + key in loc:
            result[field] = clean_ui_text(loc[prefix + key])
    for effect in result.get('effectRows', []):
        effect_key = effect.get('effectKey', '')
        loc_key = 'effects_description_' + effect_key
        if loc_key not in loc or effect.get('abilities'):
            continue
        old = effect.get('text', '')
        # Use the patch directly, without the formatter's unrelated fallback map.
        text = effect_text('patch_' + effect_key, {'description': loc[loc_key]}, {}, effect.get('value'))
        new = (text + ' ' + effect.get('scope', '')).strip()
        effect['name'] = clean_ui_text(loc[loc_key])
        effect['text'] = new
        if old:
            result['effects'] = [line.replace(old, new) for line in result.get('effects', [])]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, help='Explicit Korean localisation pack to import')
    args = parser.parse_args()
    if args.pack:
        from tk_pack_builder.adapters import adapter_for
        from tk_pack_builder.web_runtime import _ensure_rpfm_server
        from tk_pack_builder.korean_patch import PATCH_PATH
        _ensure_rpfm_server()
        session = adapter_for('rpfm').open_pack(args.pack.resolve())
        rows = {}
        try:
            for name in sorted(session.list_loc_files(), reverse=True):
                rows.update(session.read_loc(name))
        finally:
            session.close()
        PATCH_PATH.write_text(json.dumps({
            'source': args.pack.name, 'sha256': hashlib.sha256(args.pack.read_bytes()).hexdigest(),
            'rows': rows,
        }, ensure_ascii=False), encoding='utf-8')
        translations.cache_clear()
    loc = translations()
    paths = list((ROOT / 'tk_pack_builder/data').glob('assembly_kit_*_effects.ko.json'))
    paths += list((ROOT / 'work/internal_materials').glob('*/assembly_kit_title_effects.ko.json'))
    report = []
    for path in paths:
        before = json.loads(path.read_text(encoding='utf-8'))
        after = [translate_entry(entry, loc) for entry in before]
        changes = sum(a != b for a, b in zip(before, after))
        if changes:
            path.write_text(json.dumps(after, ensure_ascii=False), encoding='utf-8')
        report.append({'path': str(path.relative_to(ROOT)), 'changed': changes})
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
