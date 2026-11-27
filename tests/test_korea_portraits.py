import unittest
from tk_pack_builder.web import _build_asset_index, _find_art_portrait
class KoreaPortraitTests(unittest.TestCase):
    def test_shared_folder_resolves_exact_character_not_armour_or_other_face(self):
        blank='ui/characters/KRC_artsets/stills/halfbody_large/armour.png'
        a='ui/characters/KRC_artsets/stills/halfbody_large/faces/silvercat_an_ryu_wood.png'
        b='ui/characters/KRC_artsets/stills/halfbody_large/faces/silvercat_go_uru_earth.png'
        idx=_build_asset_index([blank,a,b])
        self.assertEqual(_find_art_portrait(idx,'KRC_artsets/','silvercat_go_uru_earth'),b)
        self.assertEqual(_find_art_portrait(idx,'KRC_artsets/','silvercat_an_ryu_wood'),a)
        self.assertIsNone(_find_art_portrait(idx,'KRC_artsets/','unknown'))
    def test_other_portraits_keep_existing_selection(self):
        p='ui/characters/hero/composites/large_panel/norm/norm.png'
        self.assertEqual(_find_art_portrait(_build_asset_index([p]),'hero','hero'),p)
