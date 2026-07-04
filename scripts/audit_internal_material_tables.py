from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from scripts.build_internal_materials_v015 import REQUIRED_TABLE_FOLDERS, table_folder


def main() -> None:
    materials = json.loads(Path("work/internal_materials/materials.v015.json").read_text(encoding="utf-8"))
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for table_path, entry in materials.get("tables", {}).items():
        folder = table_folder(table_path)
        counts[folder][0] += 1
        counts[folder][1] += len(entry.get("rows", []))
    for folder in sorted(REQUIRED_TABLE_FOLDERS):
        table_count, row_count = counts[folder]
        status = "OK" if table_count and row_count else "MISSING"
        print(f"{status}\t{folder}\ttables={table_count}\trows={row_count}")


if __name__ == "__main__":
    main()
