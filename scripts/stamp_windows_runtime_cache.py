from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tk_pack_builder import __version__
from tk_pack_builder.portable_cache import inventory, map_paths


def stamp_runtime_cache(app_dir, source_root=ROOT):
    app_dir = Path(app_dir).resolve()
    prefix = Path(source_root).resolve().as_posix().rstrip('/') + '/'
    def relocate(text):
        normalized = text.replace('\\', '/')
        if normalized.lower().startswith(prefix.lower()):
            return '@APP@/' + normalized[len(prefix):]
        marker = '/work/assets/'
        position = normalized.lower().find(marker)
        if position >= 0:
            return '@APP@/work/assets/' + normalized[position + len(marker):]
        return text
    for profile, folder in [('vanilla-mtu-v1', 'vanilla_mtu'), ('190', '190'), ('190-korea', '190-korea')]:
        directory = app_dir / 'work/internal_materials' / folder
        path = directory / 'materials.v015.summary.json'
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        resources = {p.relative_to(app_dir).as_posix(): p.stat().st_size for p in directory.glob('*.json') if p != path}
        output = {'portable': {'version': __version__, 'profile': profile, 'assets': inventory(app_dir, profile), 'resources': resources}, 'summary': map_paths(payload['summary'], relocate)}
        path.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app-dir', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    args = parser.parse_args()
    stamp_runtime_cache(args.app_dir, args.source_root)
