from __future__ import annotations

from pathlib import Path

from .adapters import PackSession
from .character_clone import apply_character_clones, apply_character_patches
from .delta_builder import build_delta_pack
from .recipe import Recipe
from .stat_tables import resolve_stat_target
from .validation import has_errors, validate


def build_pack(
    session: PackSession,
    recipe: Recipe,
    output_path: Path | None,
    in_place: bool = False,
    delta: bool = False,
) -> list[dict[str, object]]:
    if delta:
        if output_path is None:
            raise ValueError("Delta patch pack output path is required.")
        return build_delta_pack(session, recipe, output_path)  # type: ignore[arg-type]

    messages = validate(session, recipe, str(output_path) if output_path else None)
    if has_errors(messages):
        return [
            {"level": message.level, "code": message.code, "message": message.message}
            for message in messages
        ]

    changed = 0
    rows_by_table: dict[str, list[dict[str, object]]] = {}
    for patch in recipe.equipment_stat_patches:
        target = resolve_stat_target(
            session,
            patch.equipment_key,
            patch.stat_table,
            patch.column,
            patch.value,
            patch.game_mode,
        )
        rows = rows_by_table.setdefault(target.table_name, session.read_table(target.table_name))
        for row in rows:
            if row.get("key") == target.row_key:
                row[target.column] = target.value
                changed += 1
                break

    for table_name, rows in rows_by_table.items():
        session.replace_table(table_name, rows)

    changed_characters = apply_character_patches(session, recipe.character_patches)
    created_characters = apply_character_clones(session, recipe.character_clones)

    session.set_metadata("lastRecipeModName", recipe.mod_name)
    session.set_metadata("changedStatCount", changed)
    session.set_metadata("changedCharacterFieldCount", changed_characters)
    session.set_metadata("createdCharacterCount", created_characters)
    if in_place:
        session.save_pack()
        target = session.pack_path
        code = "pack_saved"
    else:
        if output_path is None:
            raise ValueError("Either --output or --in-place is required.")
        session.save_as_pack(output_path)
        target = output_path
        code = "pack_written"

    return [
        {"level": message.level, "code": message.code, "message": message.message}
        for message in messages
    ] + [
        {
            "level": "success",
            "code": code,
            "message": (
                f"Wrote {target} with {changed} edited equipment stat value(s), "
                f"{changed_characters} edited character field(s), "
                f"and {created_characters} cloned character(s)."
            ),
        }
    ]
