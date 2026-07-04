from __future__ import annotations

from pathlib import Path

from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web import _ensure_rpfm_server


ROOT = Path(__file__).resolve().parents[1]
PACKS = [
    ROOT / "work" / "reference_zip_v17" / "[모드.합류]순욱1턴.pack",
    ROOT / "work" / "reference_zip_v17" / "8King_4P_1.7_up.pack",
]


ALIASES = [
    "character_generation_templates",
    "character_generation_template_game_mode_details",
    "campaign_character_art_sets",
    "campaign_character_arts",
    "names",
    "incidents",
    "cdir_events_incident_payloads",
    "cdir_events_incident_option_junctions",
]


def interesting(row: dict) -> bool:
    text = " ".join(str(value) for value in row.values()).lower()
    needles = [
        "new_hero",
        "xun_yu",
        "3k_dlc04_xun_yu",
        "spawn_agent",
        "character_template",
        "names_name_",
        "names_alt_name_",
    ]
    return any(needle in text for needle in needles)


def main() -> None:
    _ensure_rpfm_server()
    for pack in PACKS:
        print("\n====", pack, "====")
        session = adapter_for("rpfm").open_pack(pack.resolve())
        try:
            files = session.list_files()
            print("FILES", len(files))
            for path in files:
                if path.startswith(("db/", "text/", "script/", "ui/characters/")):
                    if any(token in path.lower() for token in ["new_hero", "xun", "event", "character", "names", "script"]):
                        print(" ", path)
            for alias in ALIASES:
                try:
                    rows = session.read_table(alias)
                except Exception as exc:
                    print("TABLE", alias, "ERR", exc)
                    continue
                hits = [row for row in rows if interesting(row)]
                print("TABLE", alias, "rows", len(rows), "hits", len(hits))
                for row in hits[:50]:
                    print(" ", row)
            for loc_path in session.list_loc_files():
                loc = session.read_loc(loc_path)
                hits = {
                    key: value
                    for key, value in loc.items()
                    if any(token in key.lower() for token in ["new_hero", "xun", "names_name", "names_alt_name", "incident"])
                }
                if hits:
                    print("LOC", loc_path, len(hits))
                    for key, value in list(hits.items())[:30]:
                        print(" ", key, "=>", value)
        finally:
            session.close()


if __name__ == "__main__":
    main()
