import concurrent.futures
import json
import unittest
from pathlib import Path
from tk_pack_builder.source_profiles import using, current, directory, profiled, BASE
from tk_pack_builder.source_policy import require_clean_references
from tk_pack_builder.title_registry import registry, require_known_title
from tk_pack_builder.ceo_ccd import _Reader, _read_sized_utf8, _write_sized_utf8

class SourceProfilesTest(unittest.TestCase):
    def test_legacy_bytes_are_preserved_without_guessing_keys(self):
        raw=b'\x06\x00l\xfcyou!'
        value=_read_sized_utf8(_Reader(raw),2)
        out=bytearray();_write_sized_utf8(out,value,2)
        self.assertEqual(bytes(out),raw)

    def test_request_context_is_thread_local_and_resets_on_failure(self):
        def check(profile):
            with using(profile):
                self.assertEqual(current(),profile)
                return directory().name
        with concurrent.futures.ThreadPoolExecutor() as pool:
            self.assertEqual(list(pool.map(check,['190','190-korea',BASE])),['190','190-korea','vanilla_mtu'])
        with self.assertRaises(ValueError):
            with using('190'):raise ValueError('test')
        self.assertEqual(current(),BASE)

    def test_effective_registries_and_quarantine(self):
        for profile in ('190','190-korea'):
            with using(profile):
                data=registry()
                self.assertGreater(len(data['ceoKeys']),3000)
                require_known_title('3k_dlc05_ceo_career_historical_ji_ling')
                with self.assertRaises(ValueError):require_known_title('3k_main_ceo_career_historical_ji_ling')
                with self.assertRaises(ValueError):require_clean_references({'key':'3k_main_template_historical_yan_xiang_hero_water'})
                if profile=='190-korea':
                    with self.assertRaises(ValueError):require_clean_references({'key':'3k_mod_patriotic_solidarity'})
        with self.assertRaises(ValueError):require_clean_references({'key':'ironic_example'})

    def test_cross_profile_queue_fails_before_build(self):
        called=[]
        @profiled
        def build_payload(payload):called.append(payload);return {}
        with self.assertRaisesRegex(ValueError,'보류'):
            build_payload({'sourceProfile':BASE,'recipe':{'workItems':[{'sourceProfile':'190','title':'보관 작업'}]}})
        self.assertEqual(called,[])

    def test_optional_materials_have_unique_primary_keys_and_no_quarantined_rows(self):
        for profile in ('190','190-korea'):
            with using(profile):
                blocked=set(registry()['blockedKeys'])
                material=json.loads((directory()/'materials.v015.json').read_text(encoding='utf-8'))
                for path,entry in material['tables'].items():
                    fields=entry['db']['table']['definition']['fields']
                    keys=[f['name'] for f in fields if f.get('is_key')]
                    if keys:
                        identities=[tuple(str(r.get(k,'')) for k in keys) for r in entry['rows']]
                        self.assertEqual(len(identities),len(set(identities)),path)
                    for row in entry['rows']:
                        self.assertFalse(any(isinstance(v,str) and v in blocked for v in row.values()),path)

if __name__=='__main__':unittest.main()
