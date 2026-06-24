from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .game import THREE_KINGDOMS_GAME_KEY
from .rpfm_ws import RpfmWsClient


class PackAdapter(Protocol):
    def open_pack(self, file_path: Path) -> "PackSession":
        ...


class PackSession(Protocol):
    @property
    def pack_path(self) -> Path:
        ...

    def list_tables(self, source: str = "pack") -> list[str]:
        ...

    def read_table(self, table_name: str, source: str = "pack") -> list[dict[str, Any]]:
        ...

    def replace_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        ...

    def list_loc_files(self) -> list[str]:
        ...

    def read_loc(self, loc_path: str) -> dict[str, str]:
        ...

    def upsert_loc_rows(self, loc_path: str, rows: dict[str, str]) -> None:
        ...

    def list_files(self) -> list[str]:
        ...

    def metadata(self) -> dict[str, Any]:
        ...

    def set_metadata(self, key: str, value: Any) -> None:
        ...

    def save_as_pack(self, output_path: Path) -> None:
        ...

    def save_pack(self) -> None:
        ...


@dataclass
class MockPackSession:
    pack_path: Path
    envelope: dict[str, Any]

    def list_tables(self, source: str = "pack") -> list[str]:
        if source not in {"pack", "vanilla"}:
            raise ValueError(f"Unsupported table source: {source}")
        if source == "vanilla":
            return sorted(self.envelope.get("vanillaTables", {}).keys())
        return sorted(self.envelope.get("tables", {}).keys())

    def read_table(self, table_name: str, source: str = "pack") -> list[dict[str, Any]]:
        if source not in {"pack", "vanilla"}:
            raise ValueError(f"Unsupported table source: {source}")
        if source == "vanilla":
            return copy.deepcopy(self.envelope.get("vanillaTables", {}).get(table_name, []))
        return copy.deepcopy(self.envelope.get("tables", {}).get(table_name, []))

    def replace_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        self.envelope.setdefault("tables", {})[table_name] = copy.deepcopy(rows)

    def list_loc_files(self) -> list[str]:
        return sorted(self.envelope.get("loc", {}).keys())

    def read_loc(self, loc_path: str) -> dict[str, str]:
        return copy.deepcopy(self.envelope.get("loc", {}).get(loc_path, {}))

    def upsert_loc_rows(self, loc_path: str, rows: dict[str, str]) -> None:
        self.envelope.setdefault("loc", {}).setdefault(loc_path, {}).update(rows)

    def list_files(self) -> list[str]:
        return sorted(self.envelope.get("files", []))

    def metadata(self) -> dict[str, Any]:
        return copy.deepcopy(self.envelope.get("metadata", {}))

    def set_metadata(self, key: str, value: Any) -> None:
        self.envelope.setdefault("metadata", {})[key] = value

    def save_as_pack(self, output_path: Path) -> None:
        output_path = output_path.resolve()
        if output_path == self.pack_path:
            raise ValueError("Refusing to overwrite the input pack.")
        if output_path.suffix != ".pack":
            raise ValueError("Output path must end with .pack.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.envelope, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def save_pack(self) -> None:
        self.pack_path.write_text(
            json.dumps(self.envelope, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class MockPackAdapter:
    def open_pack(self, file_path: Path) -> MockPackSession:
        if file_path.suffix != ".pack":
            raise ValueError("Input path must end with .pack.")
        with file_path.open("rb") as handle:
            magic = handle.read(4)
        if magic.startswith(b"PFH"):
            raise ValueError(
                "This is a real Total War PFH pack. Use 'probe' for read-only inspection "
                "or '--adapter rpfm' after the RPFM adapter is implemented."
            )
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if data.get("format") != "tk-cce-mock-pack-v1":
            raise ValueError("Unsupported mock pack format.")
        return MockPackSession(file_path, data)


@dataclass
class RpfmPackSession:
    pack_path: Path
    client: RpfmWsClient
    pack_key: str
    pack_info: dict[str, Any]
    file_infos: list[dict[str, Any]]
    vanilla_pack_key: str | None = None
    vanilla_file_infos: list[dict[str, Any]] | None = None
    decoded_db_by_path: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata_updates: dict[str, Any] = field(default_factory=dict)

    def list_tables(self, source: str = "pack") -> list[str]:
        file_infos = self._file_infos_for_source(source)
        return sorted(
            info["path"]
            for info in file_infos
            if info.get("path", "").startswith(("db/", "ceo_db/"))
        )

    def read_table(self, table_name: str, source: str = "pack") -> list[dict[str, Any]]:
        path = self._resolve_table_path(table_name, source)
        pack_key = self._pack_key_for_source(source)
        response = self.client.send({"DecodePackedFile": [pack_key, path, "PackFile"]})
        data = response.get("data", {})
        if "Error" in data:
            raise ValueError(data["Error"])
        if "DBRFileInfo" not in data:
            raise ValueError(f"RPFM did not decode '{path}' as a DB table.")

        table = data["DBRFileInfo"][0]["table"]
        if source == "pack":
            self.decoded_db_by_path[path] = copy.deepcopy(data["DBRFileInfo"][0])
        fields = [field["name"] for field in table["definition"]["fields"]]
        rows = []
        for row in table["table_data"]:
            rows.append(
                {
                    field_name: _decode_rpfm_cell(value)
                    for field_name, value in zip(fields, row, strict=False)
                }
            )
        return rows

    def replace_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        path = self._resolve_table_path(table_name)
        if path not in self.decoded_db_by_path:
            self.read_table(path)
        db = self.decoded_db_by_path[path]
        table = db["table"]
        fields = [field["name"] for field in table["definition"]["fields"]]
        if len(rows) < len(table["table_data"]):
            raise ValueError("RPFM table replacement cannot remove rows.")
        if rows and not table["table_data"]:
            raise ValueError("RPFM table replacement cannot add rows to an empty table without a type template.")

        encoded_rows = []
        template_rows = table["table_data"]
        for row_index, source_row in enumerate(rows):
            template_row = template_rows[row_index] if row_index < len(template_rows) else template_rows[0]
            encoded_rows.append(
                [
                    _encode_rpfm_cell(template_cell, source_row[field_name])
                    for field_name, template_cell in zip(fields, template_row, strict=True)
                ]
            )
        table["table_data"] = encoded_rows

        response = self.client.send({"SavePackedFileFromView": [self.pack_key, path, {"DB": db}]})
        _raise_rpfm_error(response)

    def list_loc_files(self) -> list[str]:
        return sorted(
            info["path"]
            for info in self.file_infos
            if info.get("path", "").endswith(".loc")
        )

    def read_loc(self, loc_path: str) -> dict[str, str]:
        response = self.client.send({"DecodePackedFile": [self.pack_key, loc_path, "PackFile"]})
        data = response.get("data", {})
        if "Error" in data:
            raise ValueError(data["Error"])
        if "LocRFileInfo" not in data:
            raise ValueError(f"RPFM did not decode '{loc_path}' as a loc file.")

        table = data["LocRFileInfo"][0]["table"]
        fields = [field["name"] for field in table["definition"]["fields"]]
        rows: dict[str, str] = {}
        for row in table["table_data"]:
            decoded = {
                field_name: _decode_rpfm_cell(value)
                for field_name, value in zip(fields, row, strict=False)
            }
            if "key" in decoded and "text" in decoded:
                rows[str(decoded["key"])] = str(decoded["text"])
        return rows

    def upsert_loc_rows(self, loc_path: str, rows: dict[str, str]) -> None:
        raise NotImplementedError("RPFM loc writes are not needed for the current CLI prototype.")

    def list_files(self) -> list[str]:
        return sorted(
            info["path"]
            for info in self.file_infos
            if "path" in info
            and not info["path"].startswith(("db/", "ceo_db/"))
            and not info["path"].endswith(".loc")
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "gameKey": THREE_KINGDOMS_GAME_KEY,
            "adapter": "rpfm",
            "packKey": self.pack_key,
            "rpfmPackInfo": copy.deepcopy(self.pack_info),
            **copy.deepcopy(self.metadata_updates),
        }

    def set_metadata(self, key: str, value: Any) -> None:
        self.metadata_updates[key] = value

    def save_as_pack(self, output_path: Path) -> None:
        output_path = output_path.resolve()
        if output_path == self.pack_path:
            raise ValueError("Refusing to overwrite the input pack.")
        if output_path.suffix != ".pack":
            raise ValueError("Output path must end with .pack.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        response = self.client.send({"SavePackAs": [self.pack_key, str(output_path)]})
        _raise_rpfm_error(response)

    def save_pack(self) -> None:
        response = self.client.send({"SavePack": self.pack_key})
        _raise_rpfm_error(response)

    def close(self) -> None:
        self.client.close()

    def _resolve_table_path(self, table_name: str, source: str = "pack") -> str:
        if table_name.startswith(("db/", "ceo_db/")):
            return table_name

        matches = [
            path for path in self.list_tables(source)
            if f"/{table_name}_tables/" in path or path.split("/")[-1] == table_name
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"RPFM table not found in {source}: {table_name}")
        raise ValueError(f"RPFM table name is ambiguous: {table_name}: {matches[:5]}")

    def _file_infos_for_source(self, source: str) -> list[dict[str, Any]]:
        if source == "pack":
            return self.file_infos
        if source == "vanilla":
            self._ensure_vanilla_pack_loaded()
            return self.vanilla_file_infos or []
        raise ValueError(f"Unsupported table source: {source}")

    def _pack_key_for_source(self, source: str) -> str:
        if source == "pack":
            return self.pack_key
        if source == "vanilla":
            self._ensure_vanilla_pack_loaded()
            if self.vanilla_pack_key is None:
                raise ValueError("RPFM vanilla pack was not loaded.")
            return self.vanilla_pack_key
        raise ValueError(f"Unsupported table source: {source}")

    def _ensure_vanilla_pack_loaded(self) -> None:
        if self.vanilla_pack_key is not None and self.vanilla_file_infos is not None:
            return
        loaded = self.client.send("LoadAllCAPackFiles")
        try:
            _raise_rpfm_error(loaded)
        except ValueError as error:
            raise ValueError(
                "RPFM could not load vanilla CA pack files. "
                "Vanilla DB exposure requires RPFM's Total War: THREE KINGDOMS game path setting "
                f"to point at a valid install. Original RPFM error: {error}"
            ) from error
        self.vanilla_pack_key = loaded["data"]["StringContainerInfo"][0]

        tree = self.client.send({"GetPackFileDataForTreeView": self.vanilla_pack_key})
        _raise_rpfm_error(tree)
        self.vanilla_file_infos = tree["data"]["ContainerInfoVecRFileInfo"][1]


class RpfmAdapter:
    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.host = host or os.environ.get("TK_RPFM_HOST", "127.0.0.1")
        self.port = port or int(os.environ.get("TK_RPFM_PORT", "45127"))

    def open_pack(self, file_path: Path) -> RpfmPackSession:
        if file_path.suffix != ".pack":
            raise ValueError("Input path must end with .pack.")

        client = RpfmWsClient(host=self.host, port=self.port)
        try:
            client.connect()
            _raise_rpfm_error(client.send({"SetGameSelected": [THREE_KINGDOMS_GAME_KEY, False]}))
            opened = client.send({"OpenPackFiles": [str(file_path)]})
            _raise_rpfm_error(opened)
            pack_key, pack_info = opened["data"]["StringContainerInfo"]

            tree = client.send({"GetPackFileDataForTreeView": pack_key})
            _raise_rpfm_error(tree)
            file_infos = tree["data"]["ContainerInfoVecRFileInfo"][1]
            return RpfmPackSession(file_path, client, pack_key, pack_info, file_infos)
        except Exception:
            client.close()
            raise


def _raise_rpfm_error(response: dict[str, Any]) -> None:
    data = response.get("data")
    if isinstance(data, dict) and "Error" in data:
        raise ValueError(data["Error"])


def _decode_rpfm_cell(value: Any) -> Any:
    if not isinstance(value, dict) or len(value) != 1:
        return value
    kind, inner = next(iter(value.items()))
    if kind.startswith("Optional"):
        return inner
    return inner


def _encode_rpfm_cell(template: Any, value: Any) -> Any:
    if not isinstance(template, dict) or len(template) != 1:
        return value
    kind = next(iter(template.keys()))
    if kind in {"I16", "I32", "I64", "OptionalI16", "OptionalI32", "OptionalI64"}:
        value = int(value)
    elif kind in {"F32", "F64"}:
        value = float(value)
    elif kind == "Boolean":
        value = bool(value)
    elif value is None and kind.startswith("Optional"):
        value = ""
    return {kind: value}


def adapter_for(name: str) -> PackAdapter:
    if name == "mock":
        return MockPackAdapter()
    if name == "rpfm":
        return RpfmAdapter()
    raise ValueError(f"Unknown adapter: {name}")
