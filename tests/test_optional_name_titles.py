import json
import unittest

from tk_pack_builder.delta_builder import _bind_private_name_group, _db_with_rows, _decoded_rows_from_db
from tk_pack_builder.internal_materials import MaterialPackSession
from tk_pack_builder.source_profiles import using, directory


class OptionalNameTitlesTest(unittest.TestCase):
    def test_colour_columns_do_not_shift_faction_references(self):
        fields = [{'name': 'key'}, *[{'name': 'colour_' + c, 'is_part_of_colour': 1} for c in 'rgb'], {'name': 'culture'}]
        db = {'table': {'definition': {'fields': fields}, 'table_data': [
            [{'StringU8': 'goguryeo'}, {'StringU8': 'korea'}, {'ColourRGB': '76191A'}]]}}
        decoded = _decoded_rows_from_db(db)
        self.assertEqual(decoded[0]['culture'], 'korea')
        self.assertEqual(decoded[0]['__colour_1_hex'], '76191A')
        self.assertEqual(_db_with_rows(db, decoded), db)

    def test_gogukcheon_title_has_original_effects_in_both_profiles(self):
        for profile in ('190', '190-korea'):
            catalog = json.loads((directory(profile) / 'assembly_kit_title_effects.ko.json').read_text(encoding='utf-8'))
            title = next(t for t in catalog if t['ceoKey'] == '3k_main_ceo_career_historical_gogukcheon')
            self.assertEqual(title['title'], '관대한 왕')
            effects = {r['effectKey']: r for r in title['effectRows']}
            self.assertEqual(effects['3k_main_effect_character_attribute_instinct_mod']['value'], 20)
            self.assertEqual(effects['3k_main_effect_force_all_campaign_recruitment_cost_all']['value'], -10)

    def test_private_name_pool_covers_goguryeo_without_overwriting_cultural_pools(self):
        with using('190-korea'):
            session = MaterialPackSession.open(directory() / 'materials.v015.json')
            source, output = {}, {}
            name = {'id': '2071331077', 'names_group': 221, 'frequency': 1}
            _bind_private_name_group(session, source, output, name, 'forename')
            self.assertNotEqual(name['names_group'], 221)
            self.assertEqual(name['frequency'], 0)
            mappings = next(rows for path, rows in output.items() if '/faction_to_name_groups_tables/' in path)
            self.assertTrue(any(r['faction'] == 'ironic_faction_goguryeo' for r in mappings))
            self.assertTrue(all(r['name_group'] == name['names_group'] and r['probability'] == 0 for r in mappings))
            self.assertTrue(all(path in source for path in output))


if __name__ == '__main__':
    unittest.main()
