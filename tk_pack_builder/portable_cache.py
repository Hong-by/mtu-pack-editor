"""Relocate release catalog caches without changing saved character keys."""
from pathlib import Path
from . import __version__


def map_paths(value, transform):
    if isinstance(value, str):
        return transform(value)
    if isinstance(value, list):
        return [map_paths(item, transform) for item in value]
    if isinstance(value, dict):
        return {key: map_paths(item, transform) for key, item in value.items()}
    return value


def inventory(root, profile):
    names = ['17309a40b912', 'hby_generated_character_sets']
    if profile != 'vanilla-mtu-v1':
        names.append('profile_190')
    if profile == '190-korea':
        names.append('profile_korea')
    sizes = [p.stat().st_size for name in names for p in (Path(root) / 'work/assets' / name).rglob('*') if p.is_file()]
    return [len(sizes), sum(sizes)]


def load_portable_summary(payload, root, profile):
    meta = payload.get('portable') or {}
    if meta.get('version') != __version__ or meta.get('profile') != profile:
        return None
    if meta.get('assets') != inventory(root, profile):
        return None
    for relative, size in meta.get('resources', {}).items():
        path = Path(root) / relative
        if not path.is_file() or path.stat().st_size != size:
            return None
    return map_paths(payload.get('summary'), lambda text: str(Path(root) / text[6:]) if text.startswith('@APP@/') else text)
