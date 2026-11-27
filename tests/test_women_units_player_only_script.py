from __future__ import annotations

from scripts.patch_women_units_korea_permissions import (
    ALL_DAMAGE_RESISTANCE_TARGET,
    BALANCE_TARGETS,
    UNIT_KEY_MAP,
    _apply_balance_targets,
    _balance_targets_valid,
    _contains_unmigrated_unit_key,
    _player_only_lua,
    _replace_unit_key_tokens,
    _unique_main_unit_index,
    _valid_player_only_script,
)


def test_player_only_listener_is_registered_from_first_tick_callback() -> None:
    units = [
        "ep_unit_water_qi_crossbowmen",
        "ep_unit_wood_qi_guardsmen",
        "ep_unit_water_archers_of_jing",
    ]

    script = _player_only_lua(units)
    first_tick = script.index("cm:add_first_tick_callback")
    registration = script.index("hby_mj_register_turn_listener()", first_tick)

    assert registration > first_tick
    assert _valid_player_only_script(script, set(units))


def test_player_only_script_rejects_pre_first_tick_only_registration() -> None:
    units = ["ep_unit_water_qi_crossbowmen"]
    old_style_script = '''
core:add_listener("hby_mj_women_units_player_only_v1", "FactionTurnStart", true, function() end, true)
cm:add_first_tick_callback(function() end)
-- faction:is_human()
-- add_event_restricted_unit_record(unit_key)
-- remove_event_restricted_unit_record(unit_key)
-- "ep_unit_water_qi_crossbowmen"
'''

    assert not _valid_player_only_script(old_style_script, set(units))


def test_balance_targets_are_applied_idempotently() -> None:
    main_units = [
        {
            "unit": key,
            "recruitment_cost": 9999,
            "upkeep_cost": 9999,
        }
        for key in BALANCE_TARGETS
    ]
    land_units = [
        {
            "key": key,
            "melee_defence": -1,
            "reload_time_reduction_percentage": -1,
            "damage_mod_all": -1,
        }
        for key in BALANCE_TARGETS
    ]

    first_changes = _apply_balance_targets(main_units, land_units)
    second_changes = _apply_balance_targets(main_units, land_units)

    assert first_changes == len(BALANCE_TARGETS) * 5
    assert second_changes == 0
    assert _balance_targets_valid(main_units, land_units)
    assert all(
        row["damage_mod_all"] == ALL_DAMAGE_RESISTANCE_TARGET
        for row in land_units
    )


def test_balance_targets_match_requested_cost_and_reload_examples() -> None:
    crossbow = BALANCE_TARGETS[UNIT_KEY_MAP["ep_unit_water_qi_crossbowmen"]]
    northern_archers = BALANCE_TARGETS[
        UNIT_KEY_MAP["3k_dlc07_unit_water_northern_mounted_archers"]
    ]
    jing_archers = BALANCE_TARGETS[UNIT_KEY_MAP["ep_unit_water_archers_of_jing"]]

    assert (crossbow["recruitment_cost"], crossbow["upkeep_cost"]) == (360, 95)
    assert crossbow["reload_time_reduction_percentage"] == 40
    assert northern_archers["reload_time_reduction_percentage"] == 80
    assert jing_archers["reload_time_reduction_percentage"] == 20


def test_every_women_unit_has_an_independent_key() -> None:
    assert len(UNIT_KEY_MAP) == 14
    assert len(set(UNIT_KEY_MAP.values())) == 14
    assert all(key.startswith("hby_mj_") for key in UNIT_KEY_MAP.values())
    assert not set(UNIT_KEY_MAP) & set(UNIT_KEY_MAP.values())


def test_nested_effect_and_loc_keys_are_retargeted() -> None:
    old = "ep_unit_water_qi_crossbowmen"
    new = UNIT_KEY_MAP[old]

    assert _replace_unit_key_tokens(f"hby_mj_effect_unit_cap_{old}") == (
        f"hby_mj_effect_unit_cap_{new}"
    )
    assert _replace_unit_key_tokens(f"main_units_onscreen_name_{old}") == (
        f"main_units_onscreen_name_{new}"
    )
    assert _contains_unmigrated_unit_key(old)
    assert not _contains_unmigrated_unit_key(new)
    assert not _contains_unmigrated_unit_key(f"hby_mj_effect_unit_cap_{new}")


def test_generated_main_unit_index_is_stable_and_avoids_reserved_values() -> None:
    unit_key = UNIT_KEY_MAP["ep_unit_water_qi_crossbowmen"]
    first = _unique_main_unit_index(unit_key, set())
    second = _unique_main_unit_index(unit_key, set())
    replacement = _unique_main_unit_index(unit_key, {first})

    assert first == second
    assert 1_500_000_000 <= first < 2_000_000_000
    assert replacement != first
