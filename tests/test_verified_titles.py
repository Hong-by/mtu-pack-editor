import unittest
from tk_pack_builder.title_registry import registry, resolve_title, title_node, require_known_title, validate_recipe_titles
from tk_pack_builder.recipe import recipe_from_dict
from tk_pack_builder import web

class VerifiedTitleTests(unittest.TestCase):
    def test_real_relationships_not_name_replacement(self):
        cases = {
            '3k_dlc05_ceo_initial_data_character_historical_ji_ling': '3k_dlc05_ceo_career_historical_ji_ling',
            '3k_mtu_ceo_initial_data_character_historical_lady_guan_yinping': '3k_mtu_ceo_career_historical_lady_guan_yinping',
            '3k_mtu_ceo_initial_data_character_historical_lady_zhang_xingcai': '3k_mtu_ceo_career_historical_lady_zhang_xingcai',
        }
        for initial, title in cases.items():
            with self.subTest(initial=initial):
                self.assertEqual(resolve_title(initial=initial), title)
                require_known_title(title)
                self.assertTrue(title_node(title))

    def test_invalid_and_excluded_titles_are_rejected(self):
        for key in ['3k_main_ceo_career_historical_ji_ling', *registry()['excludedTitleKeys']]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                require_known_title(key)
        self.assertEqual(len(registry()['excludedNodes']), 6)
        self.assertFalse(set(registry()['excludedNodes']) & set(registry()['nodeToTitle']))

    def test_title_description_uses_actual_node_and_ceo(self):
        info = web._title_info_for_character(
            {'key': '3k_main_template_historical_ji_ling_hero_fire'},
            [{'gameMode': 'romance', 'initialCeos': '3k_dlc05_ceo_initial_data_character_historical_ji_ling'}], {})
        self.assertEqual(info['titleCeoKey'], '3k_dlc05_ceo_career_historical_ji_ling')
        self.assertEqual(info['ceoNodeKey'], '3k_dlc05_ceo_node_career_historical_ji_ling_01')

    def test_catalog_is_backed_by_registry(self):
        import json
        entries = json.loads(web.PACKAGED_ASSEMBLY_KIT_TITLE_EFFECT_CATALOG.read_text(encoding='utf-8'))
        self.assertEqual(len(entries), 429)
        for entry in entries:
            self.assertEqual(resolve_title(node=entry['key']), entry['ceoKey'])

if __name__ == '__main__':
    unittest.main()
