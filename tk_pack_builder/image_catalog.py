"""Validate selectable portrait sets without deleting their legacy keys."""
from functools import lru_cache
from pathlib import Path
import hashlib
import io
import json
import re
from PIL import Image

KINDS = ('bobbleheads', 'halfbody_large', 'halfbody_small', 'mini', 'unitcards')

@lru_cache(maxsize=50000)
def _file_info(path, size, mtime):
    data = Path(path).read_bytes()
    im = Image.open(io.BytesIO(data))
    im.load()
    return hashlib.sha256(data).hexdigest(), im.convert('RGBA').getchannel('A').getextrema()[1]

def annotate_image_catalog(art_sets, characters):
    for item in art_sets:
        assets = item.get('imageAssets') or []
        paths = {a['path'].replace('\\', '/').lower(): a for a in assets}
        declared = str(item.get('card') or '').strip('/').split('/')[-1]
        units = [a for p, a in paths.items() if re.search(r'/stills/unitcards/(?:faces/)?(?:large/)?[^/]+\.png$', p)
                 and (Path(p).stem == declared.lower() or not re.search(r'ancillary|ancilliary|/empty\.png$', p))]
        names = {Path(a['path']).stem.lower(): Path(a['path']).stem for a in units}
        virtual = item.get('imageOnly') or item.get('virtual')
        card = names.get(declared.lower(), '')
        if not card and virtual and len(names) == 1:
            card = next(iter(names.values()))
        # Never interpret a composite filename (noanim/norm) as the card key.
        if card:
            unit = next((a for a in units if Path(a['path']).stem.lower() == card.lower() and '/large/' not in a['path']),
                        next(a for a in units if Path(a['path']).stem.lower() == card.lower()))
            item['cardImagePath'] = unit['path']
            item['cardImageSourcePath'] = unit.get('sourcePath', '')
            if virtual:
                item['card'] = card
        reasons = []
        folder = str(item.get('portrait') or '').strip('/').lower()
        prefix = f'ui/characters/{folder}/'
        selected = []
        for kind in KINDS:
            for large in ('', 'large/'):
                candidates = [prefix + f'stills/{kind}/{face}{large}{card.lower()}.png' for face in ('', 'faces/')]
                found = next((paths[p] for p in candidates if p in paths), None)
                if found: selected.append((found, False))
                else: reasons.append(f'{kind}/{large or "normal"}')
        for panel in ('large_panel', 'small_panel'):
            for mood in ('norm', 'angry', 'happy'):
                candidates = [prefix + f'composites/{face}{panel}/{mood}/{name}.png'
                              for face in ('', f'faces/{card.lower()}/') for name in (mood, 'noanim', 'normal', 'face')]
                found = next((paths[p] for p in candidates if p in paths), None)
                if not found:
                    panel_prefix = prefix + f'composites/{panel}/{mood}/'
                    alternatives = [a for p, a in paths.items() if p.startswith(panel_prefix)
                                    and '/' not in p[len(panel_prefix):] and p.endswith('.png')]
                    # The exporter provides norm/noanim aliases for a single
                    # authored panel filename, including legacy "norrm.png".
                    if len(alternatives) == 1: found = alternatives[0]
                if found: selected.append((found, True))
                else: reasons.append(f'{panel}/{mood}')
        fingerprints = []
        info = {}
        for p, asset in paths.items():
            source = Path(asset.get('sourcePath') or '')
            file = source / asset['path']
            # Unextracted pack-backed catalogs are not claimed content-verified.
            if not source.is_dir():
                fingerprints = None
                continue
            try:
                stat = file.stat()
                digest, alpha = _file_info(str(file), stat.st_size, stat.st_mtime_ns)
                info[p] = alpha
                relative = re.sub(r'^.*?ui/characters/[^/]+/', '', p)
                relative = relative.replace(f'/faces/{card.lower()}/', '/faces/{card}/') if card else relative
                if card and relative.endswith('/' + card.lower() + '.png'):
                    relative = relative[:-len(card)-4] + '{card}.png'
                if fingerprints is not None: fingerprints.append((relative, digest))
            except (OSError, ValueError):
                reasons.append('unreadable:' + p)
                fingerprints = None
        layered = any('/composites/' in p and 'ancillary_armour_' in p for p in paths)
        for asset, panel in selected:
            if info.get(asset['path'].replace('\\', '/').lower()) == 0 and not (panel and layered):
                reasons.append('empty:' + asset['path'])
        if 'placeholder' in folder or (len(folder.split('/')) > 1 and len(set(folder.split('/'))) < len(folder.split('/'))):
            reasons.append('not_standalone_portrait')
        item['imageCatalogEligible'] = bool(card and assets and not reasons)
        item['imageCatalogIssues'] = reasons or ([] if card else ['unresolved_card'])
        item['imageContentSignature'] = hashlib.sha256(json.dumps(sorted(fingerprints)).encode()).hexdigest() if fingerprints else ''
    by_key = {x['key']: x for x in art_sets}
    for character in characters:
        item = by_key.get(character.get('artSet'))
        if not item: continue
        for field in ('imageCatalogEligible', 'imageCatalogIssues', 'imageContentSignature'):
            character[field] = item[field]
        if character.get('virtualImageOnly') or character.get('imageOnly'):
            character['card'] = item.get('card', '')
            character['cardPath'] = item.get('card', '')
            character['cardImagePath'] = item.get('cardImagePath', '')
            character['cardImageSourcePath'] = item.get('cardImageSourcePath', '')
