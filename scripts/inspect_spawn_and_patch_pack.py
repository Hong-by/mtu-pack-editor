from __future__ import annotations

from pathlib import Path

from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web import _ensure_rpfm_server


def has_any(row: dict, needles: list[str]) -> bool:
    text = " ".join(str(value) for value in row.values()).lower()
    return any(needle.lower() in text for needle in needles)


def main() -> None:
    pack = Path("output/my_hero_patch.pack").resolve()
    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(pack)
    try:
        print("PACK", pack)
        print("FILES")
        for path in session.list_files():
            if path.startswith(("script/", "db/", "text/")):
                if any(token in path for token in ("hby", "incident", "character_generation", "campaign_character")):
                    print(" ", path)

        for alias in [
            "character_generation_templates",
            "character_generation_template_game_mode_details",
            "campaign_character_art_sets",
            "campaign_character_arts",
            "incidents",
            "cdir_events_incident_payloads",
            "cdir_events_incident_option_junctions",
        ]:
            try:
                rows = session.read_table(alias)
            except Exception as exc:
                print("\nTABLE", alias, "ERR", exc)
                continue
            hits = [row for row in rows if has_any(row, ["hby_", "cao_cao", "gongsun", "SPAWN_AGENT_OFF_MAP"])]
            print("\nTABLE", alias, "rows", len(rows), "hits", len(hits))
            for row in hits[:40]:
                print(" ", row)
    finally:
        session.close()


if __name__ == "__main__":
    main()
