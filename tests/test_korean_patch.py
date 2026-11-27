import json
import unittest
from pathlib import Path

from tk_pack_builder.korean_patch import overlay, translations
from tk_pack_builder import web
from tk_pack_builder.source_profiles import using


class KoreanPatchTest(unittest.TestCase):
    def test_overlay_preserves_untranslated_entries_and_uses_patch(self):
        key = 'ceo_nodes_title_3k_main_ceo_node_career_historical_he_man_01'
        source = {key: '최강자', 'custom_name': '화령'}
        result = overlay(source)
        self.assertEqual(result[key], '절천야차')
        self.assertEqual(result['custom_name'], '화령')
        self.assertEqual(source[key], '최강자')

    def test_all_profile_catalog_titles_match_patch_without_old_alias(self):
        loc = translations()
        for profile in ['vanilla-mtu-v1', '190', '190-korea']:
            with using(profile):
                for path in web._title_effect_catalog_paths():
                    for item in json.loads(path.read_text(encoding='utf-8')):
                        key = 'ceo_nodes_title_' + item['key']
                        if key in loc:
                            self.assertEqual(item['title'], loc[key])
                        if item['key'] == '3k_main_ceo_node_career_historical_he_man_01':
                            self.assertNotIn('최강자', json.dumps(item, ensure_ascii=False))

    def test_patch_has_no_gameplay_tables(self):
        from tk_pack_builder.korean_patch import PATCH_PATH
        payload = json.loads(PATCH_PATH.read_text(encoding='utf-8'))
        self.assertEqual(set(payload), {'source', 'sha256', 'rows'})
        self.assertTrue(all(isinstance(v, str) for v in payload['rows'].values()))
