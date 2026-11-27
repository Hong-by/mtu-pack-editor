import tempfile
import unittest
from pathlib import Path
from tk_pack_builder import __version__
from tk_pack_builder.portable_cache import inventory, load_portable_summary

class PortableCacheTests(unittest.TestCase):
    def test_relocated_paths_preserve_selection_keys_and_reject_changed_resources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            resource = root / 'materials.json'
            resource.write_text('{}')
            payload = {'portable': {'version': __version__, 'profile': '190', 'assets': inventory(root, '190'), 'resources': {'materials.json': 2}}, 'summary': {'characters': [{'key': 'saved_original_key', 'image': '@APP@/work/assets/test.png'}]}}
            result = load_portable_summary(payload, root, '190')
            self.assertEqual(result['characters'][0]['key'], 'saved_original_key')
            self.assertEqual(result['characters'][0]['image'], str(root / 'work/assets/test.png'))
            self.assertIsNone(load_portable_summary(payload, root, '190-korea'))
            resource.write_text('{"changed":true}')
            self.assertIsNone(load_portable_summary(payload, root, '190'))

    def test_missing_assets_and_old_versions_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = {'portable': {'version': __version__, 'profile': '190', 'assets': [1, 10]}, 'summary': {}}
            self.assertIsNone(load_portable_summary(payload, root, '190'))
            payload['portable'].update(assets=[0, 0], version='old')
            self.assertIsNone(load_portable_summary(payload, root, '190'))
