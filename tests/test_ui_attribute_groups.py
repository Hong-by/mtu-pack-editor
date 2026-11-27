import unittest

from tk_pack_builder import web


class AttributeGroupingTest(unittest.TestCase):
    def test_mode_equivalence_preserves_bounds_and_keys(self):
        rows = [
            {"set_name": "test_records", "attribute_type": "resolve_records", "base_value": 40, "min_range": 5, "max_range": 200},
            {"set_name": "test_romance", "attribute_type": "resolve", "base_value": 40, "min_range": 5, "max_range": 200},
            {"set_name": "other_romance", "attribute_type": "resolve", "base_value": 40, "min_range": 5, "max_range": 100},
        ]
        stats = {r["set_name"]: {"resolve": 40} for r in rows}
        result = {r["key"]: r for r in web._build_attribute_set_catalog([], {"character_attributes": rows}, stats)}
        self.assertEqual(result["test_records"]["equivalenceKey"], result["test_romance"]["equivalenceKey"])
        self.assertNotEqual(result["test_records"]["equivalenceKey"], result["other_romance"]["equivalenceKey"])
        self.assertEqual(result["test_records"]["gameMode"], "historical")
        self.assertEqual(result["test_romance"]["gameMode"], "romance")
        self.assertEqual(rows[0]["attribute_type"], "resolve_records")


if __name__ == "__main__":
    unittest.main()
