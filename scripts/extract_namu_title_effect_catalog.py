from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract read-only title/effect snippets from cached namuwiki HTML.")
    parser.add_argument("--html", type=Path, default=ROOT / "work" / "tmp_namu" / "types.html")
    parser.add_argument("--output", type=Path, default=ROOT / "tk_pack_builder" / "data" / "title_effects.ko.json")
    args = parser.parse_args()

    text = html_to_text(args.html)
    entries = extract_title_effects(text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"entries": len(entries), "output": str(args.output)}, ensure_ascii=False))
    return 0


def html_to_text(path: Path) -> str:
    parser = TextParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parser.parts)


def extract_title_effects(text: str) -> list[dict[str, object]]:
    sections = _target_sections(text)
    by_title: dict[str, dict[str, object]] = {}
    for section in sections:
        for entry in _parse_numbered_titles(section):
            title = str(entry["title"])
            existing = by_title.get(title)
            if existing is None:
                by_title[title] = entry
                continue
            merged = list(existing["effects"])
            for effect in entry["effects"]:
                if effect not in merged:
                    merged.append(effect)
            existing["effects"] = merged
    return sorted(by_title.values(), key=lambda item: str(item["title"]))


def _target_sections(text: str) -> list[str]:
    lines = text.splitlines()
    sections: list[str] = []
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in {"일반 칭호", "도적 전용 일반 칭호", "황건 전용 일반 칭호와 기술", "칭호"}:
            start = max(0, index - 1)
            continue
        if start is not None and re.fullmatch(r"\d+(?:\.\d+)+\.?", stripped):
            if index > start + 2:
                sections.append("\n".join(lines[start:index]))
            start = None
    if start is not None:
        sections.append("\n".join(lines[start:]))
    return sections


def _parse_numbered_titles(section: str) -> list[dict[str, object]]:
    lines = [line.strip() for line in section.splitlines() if line.strip() and line.strip() != "[편집]"]
    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines:
        match = re.match(r"^(\d+)\.\s*(.+)$", line)
        if match and not re.match(r"^\d+\.\d+", line):
            if current:
                entries.append(_clean_entry(current))
            current = {"title": match.group(2).strip(), "raw": []}
            continue
        if current is not None:
            current["raw"].append(line)
    if current:
        entries.append(_clean_entry(current))
    return [entry for entry in entries if entry["title"] and entry["effects"]]


def _clean_entry(entry: dict[str, object]) -> dict[str, object]:
    effects: list[str] = []
    skip_rest = False
    for raw in entry.get("raw", []):
        line = str(raw).strip()
        if line.startswith("스킬트리 구성:"):
            skip_rest = True
            continue
        if skip_rest:
            continue
        if not line or re.fullmatch(r"\[\d+\]|,.*|해당 인물:.*|1렙 습득 기술:.*", line):
            continue
        if line.startswith(("+", "-")):
            continue
        if line in {"능력", "군사", "내정", "스킬"}:
            continue
        effects.append(line)
    return {"title": str(entry.get("title") or "").strip(), "effects": effects}


if __name__ == "__main__":
    raise SystemExit(main())
