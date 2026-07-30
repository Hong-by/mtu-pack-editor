from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tk_pack_builder.dedicated_armour_pool import (
    CcdFingerprint,
    DedicatedArmourPool,
    DedicatedArmourPoolError,
    DedicatedArmourSlot,
    allocate_dedicated_armour_slot,
    load_dedicated_armour_pools,
    ordered_active_ccd_pack_paths,
    resolve_pool_status,
    validate_pool_assignments,
    verify_pool_asset,
)
from tk_pack_builder.delta_builder import (
    _materialize_dedicated_armour_ccd,
    _materialize_dedicated_armour_db_rows,
)
from tk_pack_builder.recipe import recipe_from_dict


class DedicatedArmourPoolTest(unittest.TestCase):
    def test_load_allocate_and_verify_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ccd = root / "pool.ccd"
            ccd.write_bytes(b"compiled CEO pool")
            compiled_hash = hashlib.sha256(ccd.read_bytes()).hexdigest()
            base_hash = hashlib.sha256(b"base CEO").hexdigest()
            (root / "vanilla.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "poolId": "vanilla-poc",
                        "label": "Vanilla POC",
                        "baseCcdSha256": base_hash,
                        "compiledCcdSha256": compiled_hash,
                        "ccdFile": "pool.ccd",
                        "slots": [
                            {
                                "slotId": "slot-001",
                                "sourceCeoKey": "source_armour",
                                "sourceInitialCeoKey": "source_initial",
                                "sourceArmourTypeKey": "source_armour_type",
                                "armourCeoKey": "hby_armour_001",
                                "initialCeoKey": "hby_initial_001",
                                "armourTypeKey": "hby_armour_type_001",
                            },
                            {
                                "slotId": "slot-002",
                                "sourceCeoKey": "source_armour",
                                "sourceInitialCeoKey": "source_initial",
                                "sourceArmourTypeKey": "source_armour_type",
                                "armourCeoKey": "hby_armour_002",
                                "initialCeoKey": "hby_initial_002",
                                "armourTypeKey": "hby_armour_type_002",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            pool = load_dedicated_armour_pools([root])[0]
            verify_pool_asset(pool)
            self.assertEqual(
                pool.slots[0].source_initial_ceo_key,
                "source_initial",
            )
            self.assertEqual(
                allocate_dedicated_armour_slot(pool, ["slot-001"]).slot_id,
                "slot-002",
            )
            with self.assertRaises(DedicatedArmourPoolError):
                allocate_dedicated_armour_slot(pool, ["slot-001", "slot-002"])
            valid = SimpleNamespace(
                pool_id="vanilla-poc",
                slot_id="slot-001",
                source_ceo_key="source_armour",
                source_initial_ceo_key="source_initial",
                source_armour_type_key="source_armour_type",
                armour_ceo_key="hby_armour_001",
                initial_ceo_key="hby_initial_001",
                armour_type_key="hby_armour_type_001",
            )
            validate_pool_assignments(pool, [valid])
            invalid = SimpleNamespace(
                **{
                    **vars(valid),
                    "source_armour_type_key": "wrong_armour_type",
                }
            )
            with self.assertRaises(DedicatedArmourPoolError):
                validate_pool_assignments(pool, [invalid])

    def test_reference_mods_are_layered_after_source_ccd(self) -> None:
        source = Path("my_hero.pack")
        expanded = Path("190-expanded.pack")
        korea = Path("korea-addon.pack")
        self.assertEqual(
            ordered_active_ccd_pack_paths(
                source,
                [expanded, source, korea],
            ),
            [source, expanded, korea],
        )
    def test_status_rejects_mismatched_ccd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ccd = root / "pool.ccd"
            ccd.write_bytes(b"compiled")
            compiled_hash = hashlib.sha256(ccd.read_bytes()).hexdigest()
            base_hash = hashlib.sha256(b"base").hexdigest()
            (root / "pool.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "poolId": "pool",
                        "baseCcdSha256": base_hash,
                        "compiledCcdSha256": compiled_hash,
                        "ccdFile": "pool.ccd",
                        "slots": [
                            {
                                "slotId": "slot",
                                "sourceCeoKey": "source_armour",
                                "sourceInitialCeoKey": "source_initial",
                                "sourceArmourTypeKey": "source_armour_type",
                                "armourCeoKey": "armour",
                                "initialCeoKey": "initial",
                                "armourTypeKey": "armour_type",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            pool = load_dedicated_armour_pools([root])[0]
            mismatch = CcdFingerprint(
                pack_path=Path("korea.pack"),
                packed_path="campaigns/ceo_data.ccd",
                sha256=hashlib.sha256(b"korea").hexdigest(),
                size=5,
            )
            with patch(
                "tk_pack_builder.dedicated_armour_pool.resolve_effective_ccd",
                return_value=mismatch,
            ):
                status = resolve_pool_status([pool], [Path("korea.pack")])
            self.assertFalse(status.available)
            self.assertIn("안전을 위해 기능을 차단", status.reason)

    def test_recipe_parses_dedicated_armour_assignment(self) -> None:
        recipe = recipe_from_dict(
            {
                "modName": "test",
                "characterCloneRecipes": [
                    {
                        "newTemplateKey": "new",
                        "sourceTemplateKey": "source",
                        "detailSourceTemplateKey": "source",
                        "newArtSetId": None,
                        "artSetSourceId": None,
                        "newAgeRangeKey": None,
                        "ageRangeSourceKey": None,
                        "newInitialCeoKey": "hby_initial_001",
                        "initialCeoSourceKey": "source_initial",
                        "templateOverrides": {},
                        "detailOverrides": {},
                        "artSetOverrides": {},
                        "artOverrides": {},
                        "ageRangeOverrides": {},
                        "dedicatedArmour": {
                            "poolId": "pool",
                            "slotId": "slot-001",
                            "sourceCeoKey": "source_armour",
                            "sourceInitialCeoKey": "source_initial",
                            "sourceArmourTypeKey": "source_armour_type",
                            "armourCeoKey": "hby_armour_001",
                            "initialCeoKey": "hby_initial_001",
                            "armourTypeKey": "hby_armour_type_001",
                            "armourValue": 77,
                        },
                    }
                ],
            }
        )
        assignment = recipe.character_clones[0].dedicated_armour
        self.assertIsNotNone(assignment)
        assert assignment is not None
        self.assertEqual(assignment.armour_value, 77)
        self.assertEqual(assignment.slot_id, "slot-001")
        self.assertEqual(assignment.source_initial_ceo_key, "source_initial")

    def test_materializes_dedicated_armour_db_rows(self) -> None:
        clone = recipe_from_dict(
            {
                "characterCloneRecipes": [
                    {
                        "newTemplateKey": "new",
                        "sourceTemplateKey": "source",
                        "detailSourceTemplateKey": "source",
                        "templateOverrides": {},
                        "detailOverrides": {},
                        "dedicatedArmour": {
                            "poolId": "pool",
                            "slotId": "slot-001",
                            "sourceCeoKey": "source_armour_ceo",
                            "sourceInitialCeoKey": "source_initial",
                            "sourceArmourTypeKey": "source_armour_type",
                            "armourCeoKey": "new_armour_ceo",
                            "initialCeoKey": "new_initial",
                            "armourTypeKey": "new_armour_type",
                            "armourValue": 123,
                        },
                    }
                ]
            }
        ).character_clones[0]
        tables = {
            "ceo_initial_datas": [
                {
                    "key": "source_initial",
                    "template_manager": "character_ceo_manager",
                    "_sourceTablePath": "db/ceo_initial_datas_tables/data__",
                }
            ],
            "equipment_variants_armours": [
                {
                    "ceos_key": "source_armour_ceo",
                    "game_mode": "",
                    "armour": "source_armour_type",
                    "male_vmd": "source.vmd",
                    "_sourceTablePath": "db/ceos_to_equipment_variants_tables/data__",
                }
            ],
            "unit_armour_types": [
                {
                    "key": "source_armour_type",
                    "armour_value": 45,
                    "audio_type": "Leather",
                    "_sourceTablePath": "db/unit_armour_types_tables/data__",
                }
            ],
        }
        rows_by_table: dict[str, list[dict[str, object]]] = {}
        loc_rows: dict[str, str] = {}
        _materialize_dedicated_armour_db_rows(
            tables,
            {},
            {},
            rows_by_table,
            loc_rows,
            clone,
        )
        self.assertEqual(
            rows_by_table["db/ceo_initial_datas_tables/data__"][0]["key"],
            "new_initial",
        )
        variant = rows_by_table["db/ceos_to_equipment_variants_tables/data__"][0]
        self.assertEqual(variant["ceos_key"], "new_armour_ceo")
        self.assertEqual(variant["armour"], "new_armour_type")
        armour = rows_by_table["db/unit_armour_types_tables/data__"][0]
        self.assertEqual(armour["key"], "new_armour_type")
        self.assertEqual(armour["armour_value"], 123)
        self.assertEqual(
            loc_rows["ceo_nodes_title_new_armour_ceo"],
            "전용 갑옷",
        )
        self.assertEqual(
            loc_rows["ceo_nodes_description_new_armour_ceo"],
            "신규 장수를 위해 제작된 전용 갑옷입니다.",
        )


    def test_packaged_precompiled_pool_supports_arbitrary_db_sources(self) -> None:
        root = (
            Path(__file__).resolve().parents[1]
            / "tk_pack_builder"
            / "data"
            / "dedicated_armour_pools"
        )
        pool = next(
            item
            for item in load_dedicated_armour_pools([root])
            if item.pool_id == "mtu-core-dedicated-armour-032"
        )
        self.assertEqual(pool.mode, "precompiled")
        self.assertEqual(len(pool.slots), 32)
        self.assertEqual(len({slot.slot_id for slot in pool.slots}), 32)
        self.assertEqual(len({slot.armour_ceo_key for slot in pool.slots}), 32)
        verify_pool_asset(pool)

        slot = allocate_dedicated_armour_slot(
            pool,
            ["slot-001"],
            source_ceo_key="arbitrary_mod_armour_ceo",
        )
        self.assertEqual(slot.slot_id, "slot-002")
        assignment = SimpleNamespace(
            pool_id=pool.pool_id,
            slot_id=slot.slot_id,
            source_ceo_key="arbitrary_mod_armour_ceo",
            source_initial_ceo_key="arbitrary_mod_initial_ceo",
            source_armour_type_key="arbitrary_mod_armour_type",
            armour_ceo_key=slot.armour_ceo_key,
            initial_ceo_key=slot.initial_ceo_key,
            armour_type_key=slot.armour_type_key,
        )
        validate_pool_assignments(pool, [assignment])

    def test_dynamic_pool_is_rejected_before_materialization(self) -> None:
        slot = DedicatedArmourSlot(
            slot_id="slot-001",
            source_ceo_key="*",
            source_initial_ceo_key="*",
            source_armour_type_key="*",
            armour_ceo_key="hby_armour_001",
            initial_ceo_key="hby_initial_001",
            armour_type_key="hby_armour_type_001",
        )
        pool = DedicatedArmourPool(
            pool_id="legacy-dynamic",
            label="Legacy dynamic",
            mode="dynamic",
            base_ccd_sha256="0" * 64,
            compiled_ccd_sha256="0" * 64,
            ccd_path=None,
            slots=(slot,),
            manifest_path=Path("legacy-dynamic.json"),
        )
        with self.assertRaisesRegex(
            DedicatedArmourPoolError,
            "런타임 동적 CCD 복제",
        ):
            _materialize_dedicated_armour_ccd(pool, [], [])

    def test_precompiled_materialization_returns_packaged_ccd(self) -> None:
        root = (
            Path(__file__).resolve().parents[1]
            / "tk_pack_builder"
            / "data"
            / "dedicated_armour_pools"
        )
        pool = next(
            item
            for item in load_dedicated_armour_pools([root])
            if item.pool_id == "vanilla-dedicated-armour-032"
        )
        output = _materialize_dedicated_armour_ccd(pool, [], [])
        self.assertEqual(output, pool.ccd_path)
        self.assertIsNotNone(output)
        assert output is not None
        self.assertTrue(output.is_file())
if __name__ == "__main__":
    unittest.main()
