import copy
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from tk_pack_builder.image_catalog import annotate_image_catalog, KINDS

class ImageCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make(self, folder='hero', card='actual', virtual=True):
        paths = [f'stills/{kind}/{size}{card}.png' for kind in KINDS for size in ('', 'large/')]
        paths += [f'composites/{panel}/{mood}/noanim.png' for panel in ('large_panel','small_panel') for mood in ('norm','angry','happy')]
        assets = []
        for suffix in paths:
            path = f'ui/characters/{folder}/{suffix}'
            p = self.root/path
            p.parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGBA',(4,4),(255,0,0,255)).save(p)
            assets.append({'path':path,'sourcePath':str(self.root)})
        return {'key':folder,'portrait':folder,'card':folder if virtual else card,'imageOnly':virtual,
                'cardImagePath':f'ui/characters/{folder}/composites/large_panel/norm/noanim.png','imageAssets':assets}

    def test_noanim_is_replaced_by_actual_card_and_legacy_key_survives(self):
        a=self.make();characters=[{'artSet':'hero','key':'saved','virtualImageOnly':True}]
        annotate_image_catalog([a],characters)
        self.assertTrue(a['imageCatalogEligible'])
        self.assertEqual(a['card'],'actual')
        self.assertIn('/stills/unitcards/',a['cardImagePath'])
        self.assertEqual(characters[0]['key'],'saved')
        self.assertEqual(characters[0]['card'],'actual')

    def test_missing_large_is_excluded_not_deleted(self):
        a=self.make();a['imageAssets']=[x for x in a['imageAssets'] if '/bobbleheads/large/' not in x['path']]
        sets=[a];annotate_image_catalog(sets,[])
        self.assertEqual(len(sets),1)
        self.assertFalse(a['imageCatalogEligible'])
        self.assertIn('bobbleheads/large/',a['imageCatalogIssues'])

    def test_real_character_with_wrong_card_is_not_silently_reassigned(self):
        a=self.make(virtual=False);a['card']='other_person'
        annotate_image_catalog([a],[])
        self.assertFalse(a['imageCatalogEligible'])
        self.assertEqual(a['card'],'other_person')

    def test_same_content_different_keys_group_but_changed_large_does_not(self):
        a,b=self.make(),self.make('alias','another')
        annotate_image_catalog([a,b],[])
        self.assertEqual(a['imageContentSignature'],b['imageContentSignature'])
        p=self.root/'ui/characters/alias/stills/bobbleheads/large/another.png'
        Image.new('RGBA',(4,4),(0,255,0,255)).save(p)
        annotate_image_catalog([b],[])
        self.assertNotEqual(a['imageContentSignature'],b['imageContentSignature'])

    def test_empty_face_is_not_accepted_as_complete(self):
        a=self.make();p=self.root/'ui/characters/hero/stills/bobbleheads/actual.png'
        Image.new('RGBA',(4,4),(0,0,0,0)).save(p)
        annotate_image_catalog([a],[])
        self.assertFalse(a['imageCatalogEligible'])

    def test_explicit_unique_armour_card_is_a_valid_portrait(self):
        a=self.make(card='3k_dlc06_ancillary_armour_nanman_ahuinan_unique',virtual=False)
        annotate_image_catalog([a],[])
        self.assertTrue(a['imageCatalogEligible'])

if __name__=='__main__': unittest.main()
