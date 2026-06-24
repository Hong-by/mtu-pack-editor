from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters import adapter_for
from .analyzer import analyze_pack
from .builder import build_pack
from .probe import probe_pack
from .pfh import extract_entry, read_db_header_from_entry, read_pfh_index
from .recipe import load_recipe
from .validation import has_errors, messages_to_dicts, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tk-pack-builder")
    parser.add_argument("--adapter", choices=["mock", "rpfm"], default="mock")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--input", required=True, type=Path)

    list_tables_parser = subparsers.add_parser("list-tables")
    list_tables_parser.add_argument("--input", required=True, type=Path)
    list_tables_parser.add_argument("--source", choices=["pack", "vanilla"], default="pack")
    list_tables_parser.add_argument("--limit", default=200, type=int)
    list_tables_parser.add_argument("--contains")

    read_table_parser = subparsers.add_parser("read-table")
    read_table_parser.add_argument("--input", required=True, type=Path)
    read_table_parser.add_argument("--table", required=True)
    read_table_parser.add_argument("--source", choices=["pack", "vanilla"], default="pack")
    read_table_parser.add_argument("--limit", default=20, type=int)

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--input", required=True, type=Path)
    probe_parser.add_argument("--limit", default=200, type=int)

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--input", required=True, type=Path)
    index_parser.add_argument("--limit", default=50, type=int)
    index_parser.add_argument("--contains")

    extract_parser = subparsers.add_parser("extract-raw")
    extract_parser.add_argument("--input", required=True, type=Path)
    extract_parser.add_argument("--path", required=True)
    extract_parser.add_argument("--output", required=True, type=Path)

    db_header_parser = subparsers.add_parser("db-header")
    db_header_parser.add_argument("--input", required=True, type=Path)
    db_header_parser.add_argument("--path", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--recipe", required=True, type=Path)
    validate_parser.add_argument("--input", required=True, type=Path)
    validate_parser.add_argument("--output", type=Path)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--recipe", required=True, type=Path)
    build_parser.add_argument("--input", required=True, type=Path)
    build_parser.add_argument("--output", type=Path)
    build_parser.add_argument("--in-place", action="store_true")
    build_parser.add_argument("--delta", action="store_true", help="Write only changed rows to a small patch pack.")

    args = parser.parse_args(argv)
    adapter = adapter_for(args.adapter)

    try:
        if args.command == "analyze":
            session = adapter.open_pack(args.input)
            _print_json(analyze_pack(session).to_dict())
            return 0

        if args.command == "list-tables":
            session = adapter.open_pack(args.input)
            tables = session.list_tables(args.source)
            if args.contains:
                needle = args.contains.lower()
                tables = [table for table in tables if needle in table.lower()]
            _print_json(
                {
                    "source": args.source,
                    "tableCount": len(tables),
                    "tables": tables[: args.limit],
                }
            )
            return 0

        if args.command == "read-table":
            session = adapter.open_pack(args.input)
            rows = session.read_table(args.table, args.source)
            _print_json(
                {
                    "table": args.table,
                    "source": args.source,
                    "rowCount": len(rows),
                    "rows": rows[: args.limit],
                }
            )
            return 0

        if args.command == "probe":
            _print_json(probe_pack(args.input, args.limit).to_dict())
            return 0

        if args.command == "index":
            index = read_pfh_index(args.input)
            if args.contains:
                needle = args.contains.lower()
                entries = [
                    entry for entry in index.entries
                    if needle in entry.path.lower()
                ]
                _print_json(
                    {
                        **index.to_dict(limit=0),
                        "entries": [entry.to_dict() for entry in entries[:args.limit]],
                        "matchedCount": len(entries),
                    }
                )
            else:
                _print_json(index.to_dict(limit=args.limit))
            return 0

        if args.command == "extract-raw":
            entry = extract_entry(args.input, args.path, args.output)
            _print_json(
                {
                    "entry": entry.to_dict(),
                    "output": str(args.output),
                }
            )
            return 0

        if args.command == "db-header":
            entry, header = read_db_header_from_entry(args.input, args.path)
            _print_json(
                {
                    "entry": entry.to_dict(),
                    "dbHeader": header.to_dict(),
                }
            )
            return 0

        if args.command == "validate":
            session = adapter.open_pack(args.input)
            recipe = load_recipe(args.recipe)
            messages = validate(session, recipe, str(args.output) if args.output else None)
            _print_json({"messages": messages_to_dicts(messages)})
            return 1 if has_errors(messages) else 0

        if args.command == "build":
            if args.in_place and args.output:
                raise ValueError("Use either --output for Save As or --in-place for original save, not both.")
            if args.in_place and args.delta:
                raise ValueError("Use either --delta for a patch pack or --in-place for original save, not both.")
            if args.delta and args.adapter != "rpfm":
                raise ValueError("--delta is currently supported only with --adapter rpfm.")
            if not args.in_place and not args.output:
                raise ValueError("Either --output for Save As or --in-place for original save is required.")
            session = adapter.open_pack(args.input)
            recipe = load_recipe(args.recipe)
            messages = build_pack(session, recipe, args.output, in_place=args.in_place, delta=args.delta)
            _print_json({"messages": messages})
            return 1 if any(message["level"] == "error" for message in messages) else 0
    except ValueError as error:
        _print_json(
            {
                "messages": [
                    {
                        "level": "error",
                        "code": "cli_error",
                        "message": str(error),
                    }
                ]
            }
        )
        return 1

    return 2


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))
