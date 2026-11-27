from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import copy
import struct
from typing import Iterable, Iterator


SIGNATURE_CAAB = b"\xCA\xAB\x00\x00"
SIGNATURE_CBAB = b"\xCB\xAB\x00\x00"

RECORD_FLAG = 0x80
NESTED_BLOCKS_FLAG = 0x40
NON_OPTIMIZED_INFO_FLAG = 0x20

UTF16_MARKER = 0x0E
ASCII_MARKER = 0x0F
UTF16_ARRAY_MARKER = 0x4E
ASCII_ARRAY_MARKER = 0x4F
UNKNOWN_26_MARKER = 0x26

_FIXED_PAYLOAD_SIZES = {
    0x01: 1,
    0x02: 1,
    0x03: 2,
    0x04: 4,
    0x05: 8,
    0x06: 1,
    0x07: 2,
    0x08: 4,
    0x09: 8,
    0x0A: 4,
    0x0B: 8,
    0x0C: 8,
    0x0D: 12,
    0x10: 2,
    0x12: 0,
    0x13: 0,
    0x14: 0,
    0x15: 0,
    0x16: 1,
    0x17: 2,
    0x18: 3,
    0x19: 0,
    0x1A: 1,
    0x1B: 2,
    0x1C: 3,
    0x1D: 0,
    0x21: 4,
    0x23: 1,
    0x24: 2,
    0x25: 4,
}
_ARRAY_MARKERS = set(range(0x41, 0x51)) | {0x56, 0x57, 0x58, 0x5A, 0x5B, 0x5C}
_ARRAY_ELEMENT_SIZES = {
    0x41: 1,
    0x42: 1,
    0x43: 2,
    0x44: 4,
    0x45: 8,
    0x46: 1,
    0x47: 2,
    0x48: 4,
    0x49: 8,
    0x4A: 4,
    0x4B: 8,
    0x4C: 8,
    0x4D: 12,
    0x50: 2,
    0x56: 1,
    0x57: 2,
    0x58: 3,
    0x5A: 1,
    0x5B: 2,
    0x5C: 3,
}

class CeoCcdError(ValueError):
    pass


@dataclass
class CeoCcdMergeStats:
    groups_added: int = 0
    string_values_added: int = 0
    array_items_added: int = 0


@dataclass
class DedicatedArmourCcdCloneStats:
    definition_rows_cloned: int = 0
    membership_rows_cloned: int = 0
    string_arrays_extended: int = 0
    numeric_arrays_extended: int = 0

@dataclass
class EsfNode:
    marker: int
    payload: bytes = b""
    string_value: str | None = None
    string_values: list[str] | None = None
    record_name: str | None = None
    record_flags: int = 0
    version: int = 0
    groups: list[list["EsfNode"]] = field(default_factory=list)

    @property
    def is_record(self) -> bool:
        return bool(self.marker & RECORD_FLAG)

    def walk(self) -> Iterator["EsfNode"]:
        yield self
        for group in self.groups:
            for child in group:
                yield from child.walk()

    def strings(self) -> Iterator[str]:
        if self.string_value is not None:
            yield self.string_value
        if self.string_values:
            yield from self.string_values

    def replace_strings(self, replacements: dict[str, str]) -> int:
        changed = 0
        if self.string_value in replacements:
            self.string_value = replacements[self.string_value]
            changed += 1
        if self.string_values:
            updated = [replacements.get(value, value) for value in self.string_values]
            changed += sum(left != right for left, right in zip(self.string_values, updated, strict=True))
            self.string_values = updated
        for group in self.groups:
            for child in group:
                changed += child.replace_strings(replacements)
        return changed


@dataclass
class _IndexedStringTable:
    entries: list[tuple[int, str]]
    _value_indexes: dict[str, int] | None = field(default=None, init=False, repr=False)

    def by_index(self) -> dict[int, str]:
        return dict(self.entries)

    def index_for(self, value: str) -> int:
        if self._value_indexes is None:
            self._value_indexes = {}
            for index, existing in self.entries:
                self._value_indexes.setdefault(existing, index)
        if value in self._value_indexes:
            return self._value_indexes[value]
        next_index = max((index for index, _ in self.entries), default=-1) + 1
        self.entries.append((next_index, value))
        self._value_indexes[value] = next_index
        return next_index


@dataclass
class CeoCcd:
    signature: bytes
    unknown_1: int
    creation_date: int
    root: EsfNode
    record_names: list[str]
    strings_utf16: _IndexedStringTable
    strings_utf8: _IndexedStringTable

    @classmethod
    def from_bytes(cls, data: bytes) -> "CeoCcd":
        reader = _Reader(data)
        signature = reader.read(4)
        if signature not in {SIGNATURE_CAAB, SIGNATURE_CBAB}:
            raise CeoCcdError(f"Unsupported CCD signature: {signature.hex()}")
        unknown_1 = reader.u32()
        creation_date = reader.u32()
        string_table_offset = reader.u32()
        if string_table_offset < 16 or string_table_offset > len(data):
            raise CeoCcdError(
                f"Invalid CCD string table offset {string_table_offset} for {len(data)} bytes."
            )

        table_reader = _Reader(data, string_table_offset)
        record_names = [
            _read_sized_utf8(table_reader, 2)
            for _ in range(table_reader.u16())
        ]
        utf16_entries = []
        for _ in range(table_reader.u32()):
            value = _read_sized_utf16(
                table_reader,
                2 if signature == SIGNATURE_CAAB else 4,
            )
            utf16_entries.append((table_reader.u32(), value))
        utf8_entries = []
        for _ in range(table_reader.u32()):
            value = _read_sized_utf8(
                table_reader,
                2 if signature == SIGNATURE_CAAB else 4,
            )
            utf8_entries.append((table_reader.u32(), value))
        if table_reader.offset != len(data):
            raise CeoCcdError(
                f"CCD string tables ended at {table_reader.offset}, expected {len(data)}."
            )

        node_reader = _Reader(data, 16)
        root = _read_node(
            node_reader,
            is_root=True,
            record_names=record_names,
            strings_utf8=dict(utf8_entries),
            strings_utf16=dict(utf16_entries),
        )
        if node_reader.offset != string_table_offset:
            raise CeoCcdError(
                f"CCD node tree ended at {node_reader.offset}, expected {string_table_offset}."
            )
        return cls(
            signature=signature,
            unknown_1=unknown_1,
            creation_date=creation_date,
            root=root,
            record_names=record_names,
            strings_utf16=_IndexedStringTable(utf16_entries),
            strings_utf8=_IndexedStringTable(utf8_entries),
        )

    @classmethod
    def from_path(cls, path: Path) -> "CeoCcd":
        return cls.from_bytes(path.read_bytes())

    def to_bytes(self) -> bytes:
        self._ensure_string_tables()
        record_name_indexes = {
            value: index
            for index, value in enumerate(self.record_names)
        }
        node_data = _write_node(
            self.root,
            is_root=True,
            record_name_indexes=record_name_indexes,
            strings_utf8=self.strings_utf8,
            strings_utf16=self.strings_utf16,
        )
        string_data = bytearray()
        string_data.extend(_pack_u16(len(self.record_names)))
        for value in self.record_names:
            _write_sized_utf8(string_data, value, 2)
        string_data.extend(_pack_u32(len(self.strings_utf16.entries)))
        for index, value in self.strings_utf16.entries:
            _write_sized_utf16(
                string_data,
                value,
                2 if self.signature == SIGNATURE_CAAB else 4,
            )
            string_data.extend(_pack_u32(index))
        string_data.extend(_pack_u32(len(self.strings_utf8.entries)))
        for index, value in self.strings_utf8.entries:
            _write_sized_utf8(
                string_data,
                value,
                2 if self.signature == SIGNATURE_CAAB else 4,
            )
            string_data.extend(_pack_u32(index))
        string_table_offset = 16 + len(node_data)
        return b"".join(
            (
                self.signature,
                _pack_u32(self.unknown_1),
                _pack_u32(self.creation_date),
                _pack_u32(string_table_offset),
                node_data,
                bytes(string_data),
            )
        )

    def clone(self) -> "CeoCcd":
        return copy.deepcopy(self)

    def all_strings(self) -> Iterator[str]:
        for node in self.root.walk():
            yield from node.strings()

    def find_records_containing(self, value: str) -> list[EsfNode]:
        records: list[EsfNode] = []
        for node in self.root.walk():
            if not node.is_record:
                continue
            if any(value == string for child in node.walk() for string in child.strings()):
                records.append(node)
        return records

    def _ensure_string_tables(self) -> None:
        for node in self.root.walk():
            if node.is_record:
                if node.record_name is None:
                    raise CeoCcdError("Record node is missing its name.")
                if node.record_name not in self.record_names:
                    self.record_names.append(node.record_name)
            if node.marker == UTF16_MARKER and node.string_value is not None:
                self.strings_utf16.index_for(node.string_value)
            elif node.marker == ASCII_MARKER and node.string_value is not None:
                self.strings_utf8.index_for(node.string_value)
            elif node.marker == UTF16_ARRAY_MARKER and node.string_values is not None:
                for value in node.string_values:
                    self.strings_utf16.index_for(value)
            elif node.marker == ASCII_ARRAY_MARKER and node.string_values is not None:
                for value in node.string_values:
                    self.strings_utf8.index_for(value)

    def apply_additive_delta(
        self,
        *,
        base: "CeoCcd",
        augmented: "CeoCcd",
        ignored_top_level_records: Iterable[str] = ("CEO_DATA_TIMESTAMP",),
    ) -> CeoCcdMergeStats:
        return apply_additive_delta(
            target=self,
            base=base,
            augmented=augmented,
            ignored_top_level_records=ignored_top_level_records,
        )


def apply_additive_delta(
    *,
    target: CeoCcd,
    base: CeoCcd,
    augmented: CeoCcd,
    ignored_top_level_records: Iterable[str] = ("CEO_DATA_TIMESTAMP",),
) -> CeoCcdMergeStats:
    """Apply only additions found between two CCD snapshots to another CCD.

    The Assembly Kit/BOB output is treated as ``base + additions``. Existing rows
    and mod-specific rows in ``target`` are never replaced. Scalar mutations or
    removals are rejected so generated data cannot erase another mod's CEO data.
    """

    ignored = set(ignored_top_level_records)
    base_records = _top_level_record_map(base.root)
    augmented_records = _top_level_record_map(augmented.root)
    target_records = _top_level_record_map(target.root)
    stats = CeoCcdMergeStats()

    for name, augmented_record_list in augmented_records.items():
        if name in ignored:
            continue
        base_record_list = base_records.get(name)
        if base_record_list is None:
            raise CeoCcdError(
                f"Additive CCD delta introduced unsupported top-level record: {name}"
            )
        if len(base_record_list) != len(augmented_record_list):
            raise CeoCcdError(
                f"Additive CCD delta changed top-level record count: {name}"
            )
        target_record_list = target_records.get(name)
        if target_record_list is None or len(target_record_list) < len(base_record_list):
            raise CeoCcdError(
                f"Target CCD is missing required top-level record: {name}"
            )
        for index, (base_record, augmented_record) in enumerate(
            zip(base_record_list, augmented_record_list, strict=True)
        ):
            if base_record == augmented_record:
                continue
            _merge_node_additions(
                base_record,
                augmented_record,
                target_record_list[index],
                stats,
            )

    removed = set(base_records) - set(augmented_records) - ignored
    if removed:
        raise CeoCcdError(
            "Additive CCD delta removed top-level records: " + ", ".join(sorted(removed))
        )
    return stats


def _top_level_record_map(root: EsfNode) -> dict[str, list[EsfNode]]:
    records: dict[str, list[EsfNode]] = {}
    for group in root.groups:
        for child in group:
            if not child.is_record or child.record_name is None:
                continue
            records.setdefault(child.record_name, []).append(child)
    return records


def _merge_node_additions(
    base: EsfNode,
    augmented: EsfNode,
    target: EsfNode,
    stats: CeoCcdMergeStats,
) -> None:
    if (base.marker, base.record_name) != (augmented.marker, augmented.record_name):
        raise CeoCcdError("CCD delta changed a node marker or record name.")
    if (base.marker, base.record_name) != (target.marker, target.record_name):
        raise CeoCcdError("Target CCD structure does not match the additive delta base.")

    if base.is_record:
        if base.record_flags != augmented.record_flags or base.version != augmented.version:
            raise CeoCcdError(f"CCD delta mutated record metadata: {base.record_name}")
        _merge_group_additions(
            base.groups,
            augmented.groups,
            target.groups,
            stats,
            record_name=base.record_name or "<unnamed>",
        )
        return

    if base.marker in {UTF16_ARRAY_MARKER, ASCII_ARRAY_MARKER}:
        base_values = base.string_values or []
        augmented_values = augmented.string_values or []
        target_values = target.string_values
        if target_values is None:
            target_values = []
            target.string_values = target_values
        additions = _sequence_additions(base_values, augmented_values)
        for augmented_index, value in additions:
            if value not in target_values:
                insertion_index = _target_group_insertion_index(
                    augmented_values,
                    augmented_index,
                    target_values,
                )
                target_values.insert(insertion_index, value)
                stats.string_values_added += 1
        return

    if base.marker in _ARRAY_MARKERS:
        item_size = _ARRAY_ELEMENT_SIZES[base.marker]
        base_items = _payload_items(base.payload, item_size)
        augmented_items = _payload_items(augmented.payload, item_size)
        target_items = _payload_items(target.payload, item_size)
        for augmented_index, item in _sequence_additions(base_items, augmented_items):
            if item not in target_items:
                insertion_index = _target_group_insertion_index(
                    augmented_items,
                    augmented_index,
                    target_items,
                )
                target_items.insert(insertion_index, item)
                stats.array_items_added += 1
        target.payload = b"".join(target_items)
        return

    if base != augmented:
        raise CeoCcdError(
            f"CCD delta contains a non-additive scalar mutation at marker 0x{base.marker:02X}."
        )


def _merge_group_additions(
    base_groups: list[list[EsfNode]],
    augmented_groups: list[list[EsfNode]],
    target_groups: list[list[EsfNode]],
    stats: CeoCcdMergeStats,
    *,
    record_name: str,
) -> None:
    if base_groups == augmented_groups:
        return

    base_keys = [_group_key(group) for group in base_groups]
    augmented_keys = [_group_key(group) for group in augmented_groups]
    target_keys = [_group_key(group) for group in target_groups]
    can_key = (
        (len(base_groups) > 1 or len(augmented_groups) != len(base_groups))
        and all(key is not None for key in base_keys + augmented_keys + target_keys)
        and len(set(base_keys)) == len(base_keys)
        and len(set(augmented_keys)) == len(augmented_keys)
        and len(set(target_keys)) == len(target_keys)
    )

    if can_key:
        base_map = dict(zip(base_keys, base_groups, strict=True))
        augmented_map = dict(zip(augmented_keys, augmented_groups, strict=True))
        target_map = dict(zip(target_keys, target_groups, strict=True))
        removed = set(base_map) - set(augmented_map)
        if removed:
            raise CeoCcdError(
                f"CCD delta removed groups from {record_name}: "
                + ", ".join(sorted(str(key) for key in removed))
            )

        for index, key in enumerate(augmented_keys):
            if key in base_map:
                if augmented_map[key] == base_map[key]:
                    continue
                target_group = target_map.get(key)
                if target_group is None:
                    raise CeoCcdError(
                        f"Target CCD is missing changed group {key!r} in {record_name}."
                    )
                _merge_node_list_additions(
                    base_map[key], augmented_map[key], target_group, stats, record_name
                )
                continue
            if key in target_map:
                continue
            insertion_index = _target_group_insertion_index(
                augmented_keys, index, target_keys
            )
            cloned = copy.deepcopy(augmented_map[key])
            target_groups.insert(insertion_index, cloned)
            target_keys.insert(insertion_index, key)
            target_map[key] = cloned
            stats.groups_added += 1
        return

    if len(base_groups) != len(augmented_groups):
        raise CeoCcdError(
            f"Cannot safely align unkeyed CCD groups in {record_name}: "
            f"{len(base_groups)} -> {len(augmented_groups)}."
        )
    if len(target_groups) != len(base_groups):
        raise CeoCcdError(
            f"Target CCD has incompatible unkeyed group count in {record_name}."
        )
    for base_group, augmented_group, target_group in zip(
        base_groups, augmented_groups, target_groups, strict=True
    ):
        _merge_node_list_additions(
            base_group, augmented_group, target_group, stats, record_name
        )


def _merge_node_list_additions(
    base_nodes: list[EsfNode],
    augmented_nodes: list[EsfNode],
    target_nodes: list[EsfNode],
    stats: CeoCcdMergeStats,
    record_name: str,
) -> None:
    if len(base_nodes) != len(augmented_nodes):
        raise CeoCcdError(
            f"CCD delta added unkeyed nodes inside {record_name}; this is not safe to merge."
        )
    if len(target_nodes) != len(base_nodes):
        raise CeoCcdError(
            f"Target CCD has incompatible node count inside {record_name}."
        )
    for base, augmented, target in zip(
        base_nodes, augmented_nodes, target_nodes, strict=True
    ):
        _merge_node_additions(base, augmented, target, stats)


def _group_key(group: list[EsfNode]) -> str | None:
    for node in group:
        for nested in node.walk():
            for value in nested.strings():
                return value
    return None


def initial_ceo_active_ceos(ccd: CeoCcd, initial_ceo_key: str) -> list[str]:
    """Return CEO keys explicitly activated by one initial-CEO definition.

    The campaign CCD stores these inside ``CEO_STARTING_POINTS_PAIRS_BLOCK``
    records.  Reading that block avoids confusing permissions, spawners,
    triggers, or initial equipment with the character's actual title/traits.
    """
    key = str(initial_ceo_key or "").strip()
    if not key:
        return []
    records = _top_level_record_map(ccd.root)
    initial_record = _single_top_level_record(
        records,
        "INITAL_CEO_TABLE_POPULATE",
    )
    initial_group = next(
        (group for group in initial_record.groups if _group_key(group) == key),
        None,
    )
    if initial_group is None:
        return []

    result: list[str] = []
    seen: set[str] = set()
    for node in initial_group:
        for nested in node.walk():
            if nested.record_name != "CEO_STARTING_POINTS_PAIRS_BLOCK":
                continue
            for group in nested.groups:
                active_key = str(_group_key(group) or "").strip()
                if active_key and active_key not in seen:
                    seen.add(active_key)
                    result.append(active_key)
    return result


def rebase_dedicated_armour_initial_ceo(
    ccd: CeoCcd,
    *,
    source_initial_ceo_key: str,
    destination_initial_ceo_key: str,
    source_armour_ceo_key: str,
    destination_armour_ceo_key: str,
) -> list[str]:
    """Copy the source character's complete initial CEO set into a fixed slot."""
    values = {
        "source_initial_ceo_key": source_initial_ceo_key,
        "destination_initial_ceo_key": destination_initial_ceo_key,
        "source_armour_ceo_key": source_armour_ceo_key,
        "destination_armour_ceo_key": destination_armour_ceo_key,
    }
    missing = [name for name, value in values.items() if not str(value).strip()]
    if missing:
        raise CeoCcdError(
            "Blank dedicated-armour initial CEO key(s): " + ", ".join(missing)
        )
    if source_initial_ceo_key == destination_initial_ceo_key:
        raise CeoCcdError(
            "Dedicated-armour source and destination initial CEO keys must differ."
        )

    records = _top_level_record_map(ccd.root)
    populate = _single_top_level_record(records, "INITAL_CEO_TABLE_POPULATE")
    keys = [_group_key(group) for group in populate.groups]
    try:
        source_index = keys.index(source_initial_ceo_key)
    except ValueError as error:
        raise CeoCcdError(
            "CCD initial-CEO populate table does not contain source key: "
            + source_initial_ceo_key
        ) from error
    try:
        destination_index = keys.index(destination_initial_ceo_key)
    except ValueError as error:
        raise CeoCcdError(
            "CCD initial-CEO populate table does not contain dedicated destination key: "
            + destination_initial_ceo_key
        ) from error

    replacement = copy.deepcopy(populate.groups[source_index])
    replacements = {
        source_initial_ceo_key: destination_initial_ceo_key,
        source_armour_ceo_key: destination_armour_ceo_key,
    }
    changed = 0
    for node in replacement:
        changed += _replace_node_substrings(node, replacements)
    if changed < 2:
        raise CeoCcdError(
            "Dedicated-armour initial CEO rebase did not replace both the initial "
            "CEO and armour CEO keys."
        )
    populate.groups[destination_index] = replacement

    expected = [
        destination_armour_ceo_key
        if key == source_armour_ceo_key
        else key
        for key in initial_ceo_active_ceos(ccd, source_initial_ceo_key)
    ]
    actual = initial_ceo_active_ceos(ccd, destination_initial_ceo_key)
    if actual != expected:
        raise CeoCcdError(
            "Dedicated-armour initial CEO rebase did not preserve the source CEO set."
        )
    if destination_armour_ceo_key not in actual or source_armour_ceo_key in actual:
        raise CeoCcdError(
            "Dedicated-armour initial CEO rebase did not replace the source armour."
        )
    return actual


def rebase_dedicated_armour_ceo_as_regular(
    ccd: CeoCcd,
    *,
    source_ceo_key: str,
    destination_ceo_key: str,
) -> DedicatedArmourCcdCloneStats:
    """Turn an existing custom armour CEO into a normal, grantable armour.

    The precompiled slots originally inherit a unique/bound armour definition.
    Replacing only DB equipment variants cannot make those CEOs grantable.
    This copies the normal armour's CEO record, effects, and manager/group
    memberships while preserving the destination threshold/node rows so the
    custom localisation and icon remain independent.
    """
    source_ceo_key = str(source_ceo_key or "").strip()
    destination_ceo_key = str(destination_ceo_key or "").strip()
    if not source_ceo_key or not destination_ceo_key:
        raise CeoCcdError("Regular-armour CEO source and destination keys are required.")
    if source_ceo_key == destination_ceo_key:
        raise CeoCcdError("Regular-armour CEO source and destination keys must differ.")

    records = _top_level_record_map(ccd.root)
    ceo_populate = _single_top_level_record(records, "CEO_TABLE_POPULATE")
    threshold_populate = _single_top_level_record(
        records, "CEO_THRESHOLD_TABLE_POPULATE"
    )
    effect_populate = _single_top_level_record(
        records, "EFFECTS_LIST_TABLE_POPULATE"
    )

    source_ceo_group = _keyed_group(
        ceo_populate, source_ceo_key, "normal armour CEO"
    )
    destination_ceo_index, destination_ceo_group = _keyed_group_with_index(
        ceo_populate, destination_ceo_key, "custom armour CEO"
    )
    threshold_keys = {
        key
        for group in threshold_populate.groups
        if (key := _group_key(group))
    }
    source_threshold = _single_referenced_key(
        source_ceo_group,
        threshold_keys,
        "normal armour threshold",
    )
    destination_threshold = _single_referenced_key(
        destination_ceo_group,
        threshold_keys,
        "custom armour threshold",
    )

    replacements = {
        source_ceo_key: destination_ceo_key,
        source_threshold: destination_threshold,
    }
    replacement = copy.deepcopy(source_ceo_group)
    for node in replacement:
        _replace_node_substrings(node, replacements)
    ceo_populate.groups[destination_ceo_index] = replacement

    source_effect_group = _keyed_group(
        effect_populate, source_ceo_key, "normal armour effect list"
    )
    destination_effect_index, _ = _keyed_group_with_index(
        effect_populate, destination_ceo_key, "custom armour effect list"
    )
    effect_replacement = copy.deepcopy(source_effect_group)
    for node in effect_replacement:
        _replace_node_substrings(
            node, {source_ceo_key: destination_ceo_key}
        )
    effect_populate.groups[destination_effect_index] = effect_replacement

    stats = DedicatedArmourCcdCloneStats(definition_rows_cloned=2)
    _clone_regular_armour_spawner(
        records,
        source_ceo_key=source_ceo_key,
        destination_ceo_key=destination_ceo_key,
        stats=stats,
    )
    for name in _CEO_MEMBERSHIP_RECORDS:
        record = _single_top_level_record(records, name)
        _clone_membership_references(
            record,
            source_ceo_key,
            destination_ceo_key,
            stats,
        )

    destination_ceo_strings = [
        value
        for node in ceo_populate.groups[destination_ceo_index]
        for nested in node.walk()
        for value in nested.strings()
    ]
    destination_effect_strings = [
        value
        for node in effect_populate.groups[destination_effect_index]
        for nested in node.walk()
        for value in nested.strings()
    ]
    if "unique" in destination_ceo_strings:
        raise CeoCcdError("Custom armour CEO still has unique rarity after rebase.")
    if "3k_dummy_effect_ceo_subcategory_armour_unique" in destination_effect_strings:
        raise CeoCcdError("Custom armour CEO still has the unique armour subcategory.")
    return stats


def _clone_regular_armour_spawner(
    records: dict[str, list[EsfNode]],
    *,
    source_ceo_key: str,
    destination_ceo_key: str,
    stats: DedicatedArmourCcdCloneStats,
) -> None:
    create = _single_top_level_record(records, "SPAWNER_TABLE_CREATE")
    populate = _single_top_level_record(records, "SPAWNER_TABLE_POPULATE")
    source_matches = [
        (index, group)
        for index, group in enumerate(populate.groups)
        if _group_contains_string(group, source_ceo_key)
    ]
    if len(source_matches) != 1:
        raise CeoCcdError(
            "CCD requires exactly one normal armour spawner; "
            f"found {len(source_matches)} for {source_ceo_key}."
        )
    source_index, source_group = source_matches[0]
    source_spawner_key = str(_group_key(source_group) or "")
    destination_spawner_key = destination_ceo_key.replace(
        "_ancillary_", "_ceo_spawner_", 1
    )
    if destination_spawner_key == destination_ceo_key:
        destination_spawner_key = destination_ceo_key + "_spawner"
    replacements = {
        source_spawner_key: destination_spawner_key,
        source_ceo_key: destination_ceo_key,
    }

    create_keys = [_group_key(group) for group in create.groups]
    if destination_spawner_key not in create_keys:
        source_create_index = create_keys.index(source_spawner_key)
        cloned_create = copy.deepcopy(create.groups[source_create_index])
        for node in cloned_create:
            _replace_node_substrings(node, replacements)
        next_id = max(_create_group_id(group) for group in create.groups) + 1
        _set_create_group_id(cloned_create, next_id)
        create.groups.insert(source_create_index + 1, cloned_create)
        stats.definition_rows_cloned += 1

    populate_keys = [_group_key(group) for group in populate.groups]
    cloned_populate = copy.deepcopy(source_group)
    for node in cloned_populate:
        _replace_node_substrings(node, replacements)
    if destination_spawner_key in populate_keys:
        populate.groups[populate_keys.index(destination_spawner_key)] = cloned_populate
    else:
        populate.groups.insert(source_index + 1, cloned_populate)
    stats.definition_rows_cloned += 1


def _group_contains_string(group: list[EsfNode], value: str) -> bool:
    return any(
        candidate == value
        for node in group
        for nested in node.walk()
        for candidate in nested.strings()
    )


def _keyed_group(
    record: EsfNode,
    key: str,
    label: str,
) -> list[EsfNode]:
    return _keyed_group_with_index(record, key, label)[1]


def _keyed_group_with_index(
    record: EsfNode,
    key: str,
    label: str,
) -> tuple[int, list[EsfNode]]:
    matches = [
        (index, group)
        for index, group in enumerate(record.groups)
        if _group_key(group) == key
    ]
    if len(matches) != 1:
        raise CeoCcdError(
            f"CCD requires exactly one {label} row in {record.record_name}; "
            f"found {len(matches)} for {key}."
        )
    return matches[0]


def _single_referenced_key(
    group: list[EsfNode],
    candidates: set[str],
    label: str,
) -> str:
    matches = {
        value
        for node in group
        for nested in node.walk()
        for value in nested.strings()
        if value in candidates
    }
    if len(matches) != 1:
        raise CeoCcdError(
            f"CCD requires exactly one referenced {label}; found {sorted(matches)}."
        )
    return next(iter(matches))


def _target_group_insertion_index(
    augmented_keys: list[str | None],
    augmented_index: int,
    target_keys: list[str | None],
) -> int:
    for next_key in augmented_keys[augmented_index + 1 :]:
        if next_key in target_keys:
            return target_keys.index(next_key)
    for previous_key in reversed(augmented_keys[:augmented_index]):
        if previous_key in target_keys:
            return target_keys.index(previous_key) + 1
    return len(target_keys)

def _payload_items(payload: bytes, item_size: int) -> list[bytes]:
    if len(payload) % item_size:
        raise CeoCcdError(
            f"CCD array payload size {len(payload)} is not divisible by {item_size}."
        )
    return [
        payload[offset : offset + item_size]
        for offset in range(0, len(payload), item_size)
    ]


def _sequence_additions(
    base_values: list,
    augmented_values: list,
) -> list[tuple[int, object]]:
    additions: list[tuple[int, object]] = []
    remaining: dict[object, int] = {}
    for value in base_values:
        remaining[value] = remaining.get(value, 0) + 1
    for augmented_index, value in enumerate(augmented_values):
        if remaining.get(value, 0):
            remaining[value] -= 1
        else:
            additions.append((augmented_index, value))
    if sum(remaining.values()):
        raise CeoCcdError("CCD delta removed values from an array.")
    return additions

_CEO_DEFINITION_CREATE_RECORDS = (
    "CEO_TABLE_CREATE",
    "CEO_THRESHOLD_TABLE_CREATE",
    "CEO_NODE_TABLE_CREATE",
    "EFFECTS_LIST_TABLE_CREATE",
)
_CEO_DEFINITION_POPULATE_RECORDS = (
    "CEO_TABLE_POPULATE",
    "CEO_THRESHOLD_TABLE_POPULATE",
    "CEO_NODE_TABLE_POPULATE",
    "EFFECTS_LIST_TABLE_POPULATE",
)
_INITIAL_DEFINITION_RECORDS = (
    "INITAL_CEO_TABLE_CREATE",
    "INITAL_CEO_TABLE_POPULATE",
)
_CEO_MEMBERSHIP_RECORDS = (
    "CEO_TEMPLATE_MANAGER_TABLE_POPULATE",
    "CEO_EQUIPMENT_MANAGER_TABLE_POPULATE",
    "CEO_GROUP_TABLE_POPULATE",
)


def clone_dedicated_armour_ceo(
    ccd: CeoCcd,
    *,
    source_ceo_key: str,
    source_initial_ceo_key: str,
    new_ceo_key: str,
    new_initial_ceo_key: str,
) -> DedicatedArmourCcdCloneStats:
    """Clone one armour CEO and its initial-equipment chain inside an active CCD."""

    values = {
        "source_ceo_key": source_ceo_key,
        "source_initial_ceo_key": source_initial_ceo_key,
        "new_ceo_key": new_ceo_key,
        "new_initial_ceo_key": new_initial_ceo_key,
    }
    missing = [name for name, value in values.items() if not str(value).strip()]
    if missing:
        raise CeoCcdError("Blank dedicated-armour CCD key(s): " + ", ".join(missing))
    if new_ceo_key == source_ceo_key or new_initial_ceo_key == source_initial_ceo_key:
        raise CeoCcdError("Dedicated-armour CCD destination keys must differ from sources.")

    existing = set(ccd.all_strings())
    for key in (new_ceo_key, new_initial_ceo_key):
        if key in existing:
            raise CeoCcdError(f"Dedicated-armour CCD key already exists: {key}")

    stats = DedicatedArmourCcdCloneStats()
    records = _top_level_record_map(ccd.root)
    replacements = {
        source_ceo_key: new_ceo_key,
        source_initial_ceo_key: new_initial_ceo_key,
    }

    for name in _CEO_DEFINITION_CREATE_RECORDS:
        record = _single_top_level_record(records, name)
        if name != "CEO_TABLE_CREATE" and not _record_has_group_key(
            record, source_ceo_key
        ):
            continue
        _clone_keyed_definition_group(
            record,
            source_key=source_ceo_key,
            replacements=replacements,
            allocate_create_id=True,
        )
        stats.definition_rows_cloned += 1

    for name in _CEO_DEFINITION_POPULATE_RECORDS:
        record = _single_top_level_record(records, name)
        if name != "CEO_TABLE_POPULATE" and not _record_has_group_key(
            record, source_ceo_key
        ):
            continue
        _clone_keyed_definition_group(
            record,
            source_key=source_ceo_key,
            replacements=replacements,
            allocate_create_id=False,
        )
        stats.definition_rows_cloned += 1

    for name in _INITIAL_DEFINITION_RECORDS:
        record = _single_top_level_record(records, name)
        _clone_keyed_definition_group(
            record,
            source_key=source_initial_ceo_key,
            replacements=replacements,
            allocate_create_id=name.endswith("_CREATE"),
        )
        stats.definition_rows_cloned += 1

    for name in _CEO_MEMBERSHIP_RECORDS:
        record = _single_top_level_record(records, name)
        _clone_membership_references(
            record,
            source_ceo_key,
            new_ceo_key,
            stats,
        )

    if sum(1 for value in ccd.all_strings() if value == new_ceo_key) < 2:
        raise CeoCcdError(
            f"Dedicated-armour CCD clone did not materialize enough CEO references: {new_ceo_key}"
        )
    if sum(1 for value in ccd.all_strings() if value == new_initial_ceo_key) < 2:
        raise CeoCcdError(
            "Dedicated-armour CCD clone did not materialize the initial CEO chain: "
            + new_initial_ceo_key
        )
    return stats


def _single_top_level_record(
    records: dict[str, list[EsfNode]],
    name: str,
) -> EsfNode:
    matches = records.get(name) or []
    if len(matches) != 1:
        raise CeoCcdError(
            f"CCD requires exactly one {name} record; found {len(matches)}."
        )
    return matches[0]


def _clone_keyed_definition_group(
    record: EsfNode,
    *,
    source_key: str,
    replacements: dict[str, str],
    allocate_create_id: bool,
) -> None:
    keys = [_group_key(group) for group in record.groups]
    try:
        source_index = keys.index(source_key)
    except ValueError as error:
        raise CeoCcdError(
            f"CCD record {record.record_name} does not contain source key: {source_key}"
        ) from error
    destination_key = replacements[source_key]
    if destination_key in keys:
        raise CeoCcdError(
            f"CCD record {record.record_name} already contains destination key: {destination_key}"
        )

    cloned = copy.deepcopy(record.groups[source_index])
    for node in cloned:
        _replace_node_substrings(node, replacements)
    if allocate_create_id:
        next_id = max(_create_group_id(group) for group in record.groups) + 1
        _set_create_group_id(cloned, next_id)
    record.groups.insert(source_index + 1, cloned)


def _record_has_group_key(record: EsfNode, key: str) -> bool:
    return any(_group_key(group) == key for group in record.groups)

def _replace_node_substrings(node: EsfNode, replacements: dict[str, str]) -> int:
    changed = 0
    if node.string_value is not None:
        updated = node.string_value
        for source, destination in replacements.items():
            updated = updated.replace(source, destination)
        if updated != node.string_value:
            node.string_value = updated
            changed += 1
    if node.string_values is not None:
        updated_values = []
        for value in node.string_values:
            updated = value
            for source, destination in replacements.items():
                updated = updated.replace(source, destination)
            updated_values.append(updated)
        changed += sum(
            left != right
            for left, right in zip(node.string_values, updated_values, strict=True)
        )
        node.string_values = updated_values
    for group in node.groups:
        for child in group:
            changed += _replace_node_substrings(child, replacements)
    return changed


def _create_group_id(group: list[EsfNode]) -> int:
    if len(group) < 2:
        raise CeoCcdError("CCD create-table group is missing its numeric row id.")
    node = group[1]
    if node.marker == 0x14:
        return 0
    if node.marker == 0x15:
        return 1
    if node.marker in {0x16, 0x17, 0x18, 0x08}:
        return int.from_bytes(node.payload, "little", signed=False)
    raise CeoCcdError(
        f"Unsupported CCD create-table id marker: 0x{node.marker:02X}"
    )


def _set_create_group_id(group: list[EsfNode], value: int) -> None:
    if value < 0 or value > 0xFFFFFFFF:
        raise CeoCcdError(f"CCD create-table id is outside u32 range: {value}")
    if value == 0:
        group[1] = EsfNode(marker=0x14)
    elif value == 1:
        group[1] = EsfNode(marker=0x15)
    elif value <= 0xFF:
        group[1] = EsfNode(marker=0x16, payload=value.to_bytes(1, "little"))
    elif value <= 0xFFFF:
        group[1] = EsfNode(marker=0x17, payload=value.to_bytes(2, "little"))
    elif value <= 0xFFFFFF:
        group[1] = EsfNode(marker=0x18, payload=value.to_bytes(3, "little"))
    else:
        group[1] = EsfNode(marker=0x08, payload=value.to_bytes(4, "little"))


def _clone_membership_references(
    record: EsfNode,
    source_key: str,
    destination_key: str,
    stats: DedicatedArmourCcdCloneStats,
) -> None:
    for group in record.groups:
        _clone_membership_references_in_group(
            group,
            source_key,
            destination_key,
            stats,
        )


def _clone_membership_references_in_group(
    group: list[EsfNode],
    source_key: str,
    destination_key: str,
    stats: DedicatedArmourCcdCloneStats,
) -> None:
    string_arrays = [
        node
        for node in group
        if node.marker in {UTF16_ARRAY_MARKER, ASCII_ARRAY_MARKER}
        and node.string_values is not None
        and source_key in node.string_values
    ]
    numeric_arrays = [node for node in group if node.marker in _ARRAY_ELEMENT_SIZES]
    modified_numeric_ids: set[int] = set()
    for string_node in string_arrays:
        values = string_node.string_values or []
        if destination_key in values:
            continue
        source_index = values.index(source_key)
        original_count = len(values)
        values.insert(source_index + 1, destination_key)
        stats.string_arrays_extended += 1
        for numeric_node in numeric_arrays:
            if id(numeric_node) in modified_numeric_ids:
                continue
            item_size = _ARRAY_ELEMENT_SIZES[numeric_node.marker]
            items = _payload_items(numeric_node.payload, item_size)
            if len(items) != original_count:
                continue
            items.insert(source_index + 1, items[source_index])
            numeric_node.payload = b"".join(items)
            modified_numeric_ids.add(id(numeric_node))
            stats.numeric_arrays_extended += 1

    original_groups = list(group)
    for node in original_groups:
        if node.is_record:
            child_groups = list(node.groups)
            child_keys = [_direct_group_key(child_group) for child_group in child_groups]
            if source_key in child_keys and destination_key not in child_keys:
                source_index = child_keys.index(source_key)
                cloned = copy.deepcopy(child_groups[source_index])
                for child in cloned:
                    _replace_node_substrings(child, {source_key: destination_key})
                node.groups.insert(source_index + 1, cloned)
                stats.membership_rows_cloned += 1
            for child_group in child_groups:
                _clone_membership_references_in_group(
                    child_group,
                    source_key,
                    destination_key,
                    stats,
                )

def _direct_group_key(group: list[EsfNode]) -> str | None:
    for node in group:
        for value in node.strings():
            return value
    return None

class _Reader:
    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.offset = offset

    def read(self, size: int) -> bytes:
        end = self.offset + size
        if size < 0 or end > len(self.data):
            raise CeoCcdError(
                f"Unexpected end of CCD at {self.offset}; requested {size} bytes."
            )
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.read(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def cauleb128(self) -> int:
        value = 0
        while True:
            byte = self.u8()
            value = (value << 7) | (byte & 0x7F)
            if not byte & 0x80:
                return value


def _read_node(
    reader: _Reader,
    *,
    is_root: bool,
    record_names: list[str],
    strings_utf8: dict[int, str],
    strings_utf16: dict[int, str],
) -> EsfNode:
    marker = reader.u8()
    if marker & RECORD_FLAG:
        flags = marker & 0xE0
        if is_root or flags & NON_OPTIMIZED_INFO_FLAG:
            name_index = reader.u16()
            version = reader.u8()
        else:
            version = (marker & 0x1E) >> 1
            name_index = ((marker & 1) << 8) | reader.u8()
        try:
            record_name = record_names[name_index]
        except IndexError as error:
            raise CeoCcdError(f"Unknown CCD record name index: {name_index}") from error
        block_size = reader.cauleb128()
        nested = bool(flags & NESTED_BLOCKS_FLAG)
        group_count = reader.cauleb128() if nested else 1
        final_block_offset = reader.offset + block_size
        groups: list[list[EsfNode]] = []
        for _ in range(group_count):
            if nested:
                group_size = reader.cauleb128()
                final_group_offset = reader.offset + group_size
            else:
                final_group_offset = final_block_offset
            group = []
            while reader.offset < final_group_offset:
                group.append(
                    _read_node(
                        reader,
                        is_root=False,
                        record_names=record_names,
                        strings_utf8=strings_utf8,
                        strings_utf16=strings_utf16,
                    )
                )
            if reader.offset != final_group_offset:
                raise CeoCcdError(
                    f"CCD record group overrun at {reader.offset}; expected {final_group_offset}."
                )
            groups.append(group)
        if reader.offset != final_block_offset:
            raise CeoCcdError(
                f"CCD record block overrun at {reader.offset}; expected {final_block_offset}."
            )
        return EsfNode(
            marker=marker,
            record_name=record_name,
            record_flags=flags,
            version=version,
            groups=groups,
        )

    if marker == UTF16_MARKER:
        index = reader.u32()
        return EsfNode(
            marker=marker,
            string_value=_lookup_string(strings_utf16, index, "UTF-16"),
        )
    if marker == ASCII_MARKER:
        index = reader.u32()
        return EsfNode(
            marker=marker,
            string_value=_lookup_string(strings_utf8, index, "UTF-8"),
        )
    if marker in {UTF16_ARRAY_MARKER, ASCII_ARRAY_MARKER}:
        payload_size = reader.cauleb128()
        if payload_size % 4:
            raise CeoCcdError(
                f"CCD string array payload has invalid size {payload_size}."
            )
        table = strings_utf16 if marker == UTF16_ARRAY_MARKER else strings_utf8
        label = "UTF-16" if marker == UTF16_ARRAY_MARKER else "UTF-8"
        values = [
            _lookup_string(table, reader.u32(), label)
            for _ in range(payload_size // 4)
        ]
        return EsfNode(marker=marker, string_values=values)
    if marker == UNKNOWN_26_MARKER:
        first = reader.u8()
        trailing_size = first if first and first % 8 == 0 else 7
        payload = bytearray((first,))
        payload.extend(reader.read(trailing_size))
        if reader.offset < len(reader.data) and reader.data[reader.offset] == 0x9C:
            payload.extend(reader.read(1))
        return EsfNode(marker=marker, payload=bytes(payload))
    if marker in _ARRAY_MARKERS:
        payload_size = reader.cauleb128()
        return EsfNode(marker=marker, payload=reader.read(payload_size))
    if marker in _FIXED_PAYLOAD_SIZES:
        return EsfNode(marker=marker, payload=reader.read(_FIXED_PAYLOAD_SIZES[marker]))
    raise CeoCcdError(f"Unsupported CCD node marker 0x{marker:02X} at {reader.offset - 1}.")


def _write_node(
    node: EsfNode,
    *,
    is_root: bool,
    record_name_indexes: dict[str, int],
    strings_utf8: _IndexedStringTable,
    strings_utf16: _IndexedStringTable,
) -> bytes:
    output = bytearray()
    if node.is_record:
        if node.record_name is None:
            raise CeoCcdError("Record node is missing its name.")
        try:
            name_index = record_name_indexes[node.record_name]
        except KeyError as error:
            raise CeoCcdError(f"Missing CCD record name: {node.record_name}") from error
        flags = node.record_flags & 0xE0
        if is_root or flags & NON_OPTIMIZED_INFO_FLAG:
            output.append(flags)
            output.extend(_pack_u16(name_index))
            output.append(node.version)
        else:
            if name_index > 0x1FF:
                raise CeoCcdError(
                    f"Optimized CCD record name index exceeds 511: {name_index}"
                )
            if node.version > 0x0F:
                raise CeoCcdError(
                    f"Optimized CCD record version exceeds 15: {node.version}"
                )
            output.append(flags | (node.version << 1) | ((name_index >> 8) & 1))
            output.append(name_index & 0xFF)

        nested = bool(flags & NESTED_BLOCKS_FLAG)
        children_data = bytearray()
        if nested:
            for group in node.groups:
                group_data = b"".join(
                    _write_node(
                        child,
                        is_root=False,
                        record_name_indexes=record_name_indexes,
                        strings_utf8=strings_utf8,
                        strings_utf16=strings_utf16,
                    )
                    for child in group
                )
                children_data.extend(_write_cauleb128(len(group_data)))
                children_data.extend(group_data)
            output.extend(_write_cauleb128(len(children_data)))
            output.extend(_write_cauleb128(len(node.groups)))
        else:
            group = node.groups[0] if node.groups else []
            children_data.extend(
                b"".join(
                    _write_node(
                        child,
                        is_root=False,
                        record_name_indexes=record_name_indexes,
                        strings_utf8=strings_utf8,
                        strings_utf16=strings_utf16,
                    )
                    for child in group
                )
            )
            output.extend(_write_cauleb128(len(children_data)))
        output.extend(children_data)
        return bytes(output)

    output.append(node.marker)
    if node.marker == UTF16_MARKER:
        if node.string_value is None:
            raise CeoCcdError("UTF-16 CCD node is missing its value.")
        output.extend(_pack_u32(strings_utf16.index_for(node.string_value)))
    elif node.marker == ASCII_MARKER:
        if node.string_value is None:
            raise CeoCcdError("UTF-8 CCD node is missing its value.")
        output.extend(_pack_u32(strings_utf8.index_for(node.string_value)))
    elif node.marker in {UTF16_ARRAY_MARKER, ASCII_ARRAY_MARKER}:
        values = node.string_values or []
        table = strings_utf16 if node.marker == UTF16_ARRAY_MARKER else strings_utf8
        payload = b"".join(_pack_u32(table.index_for(value)) for value in values)
        output.extend(_write_cauleb128(len(payload)))
        output.extend(payload)
    elif node.marker == UNKNOWN_26_MARKER:
        output.extend(node.payload)
    elif node.marker in _ARRAY_MARKERS:
        output.extend(_write_cauleb128(len(node.payload)))
        output.extend(node.payload)
    elif node.marker in _FIXED_PAYLOAD_SIZES:
        expected = _FIXED_PAYLOAD_SIZES[node.marker]
        if len(node.payload) != expected:
            raise CeoCcdError(
                f"CCD marker 0x{node.marker:02X} expects {expected} payload bytes, "
                f"got {len(node.payload)}."
            )
        output.extend(node.payload)
    else:
        raise CeoCcdError(f"Unsupported CCD node marker 0x{node.marker:02X}.")
    return bytes(output)


def clone_records_with_string(
    ccd: CeoCcd,
    *,
    source_value: str,
    replacements: dict[str, str],
) -> list[EsfNode]:
    matches = ccd.find_records_containing(source_value)
    if not matches:
        raise CeoCcdError(f"CCD does not contain source key: {source_value}")
    deepest: list[EsfNode] = []
    match_ids = {id(node) for node in matches}
    for node in matches:
        has_matching_descendant = any(
            id(child) in match_ids
            for group in node.groups
            for direct in group
            for child in direct.walk()
        )
        if not has_matching_descendant:
            deepest.append(node)
    clones = [copy.deepcopy(node) for node in deepest]
    for node in clones:
        if not node.replace_strings(replacements):
            raise CeoCcdError(
                f"CCD clone for {source_value} did not apply any string replacements."
            )
    return clones


def iter_record_paths(root: EsfNode) -> Iterator[tuple[tuple[int, ...], EsfNode]]:
    def walk(node: EsfNode, path: tuple[int, ...]) -> Iterator[tuple[tuple[int, ...], EsfNode]]:
        if node.is_record:
            yield path, node
        for group_index, group in enumerate(node.groups):
            for child_index, child in enumerate(group):
                yield from walk(child, path + (group_index, child_index))

    yield from walk(root, ())


def append_sibling_records(
    root: EsfNode,
    *,
    source_value: str,
    replacements: dict[str, str],
) -> int:
    parents: list[tuple[list[EsfNode], int, EsfNode]] = []

    def visit(node: EsfNode) -> None:
        for group in node.groups:
            for index, child in enumerate(group):
                if child.is_record and any(
                    source_value == string
                    for nested in child.walk()
                    for string in nested.strings()
                ):
                    parents.append((group, index, child))
                visit(child)

    visit(root)
    deepest = []
    candidate_ids = {id(node) for _, _, node in parents}
    for group, index, node in parents:
        if not any(
            id(descendant) in candidate_ids
            for child_group in node.groups
            for child in child_group
            for descendant in child.walk()
        ):
            deepest.append((group, index, node))
    if not deepest:
        raise CeoCcdError(f"CCD does not contain source key: {source_value}")
    inserted = 0
    for group, index, source in reversed(deepest):
        clone = copy.deepcopy(source)
        if not clone.replace_strings(replacements):
            raise CeoCcdError(
                f"CCD clone for {source_value} did not apply any string replacements."
            )
        group.insert(index + 1, clone)
        inserted += 1
    return inserted


def _lookup_string(table: dict[int, str], index: int, label: str) -> str:
    try:
        return table[index]
    except KeyError as error:
        raise CeoCcdError(f"Unknown CCD {label} string index: {index}") from error


def _read_sized_utf8(reader: _Reader, size_width: int) -> str:
    size = reader.u16() if size_width == 2 else reader.u32()
    try:
        # Some workshop CCD keys contain legacy bytes. Preserve those bytes;
        # never guess an encoding or silently turn them into different keys.
        return reader.read(size).decode("utf-8", errors="surrogateescape")
    except UnicodeDecodeError as error:
        raise CeoCcdError("CCD contains invalid UTF-8 string data.") from error


def _read_sized_utf16(reader: _Reader, size_width: int) -> str:
    size = reader.u16() if size_width == 2 else reader.u32()
    try:
        return reader.read(size * 2).decode("utf-16-le")
    except UnicodeDecodeError as error:
        raise CeoCcdError("CCD contains invalid UTF-16 string data.") from error


def _write_sized_utf8(output: bytearray, value: str, size_width: int) -> None:
    encoded = value.encode("utf-8", errors="surrogateescape")
    output.extend(_pack_u16(len(encoded)) if size_width == 2 else _pack_u32(len(encoded)))
    output.extend(encoded)


def _write_sized_utf16(output: bytearray, value: str, size_width: int) -> None:
    encoded = value.encode("utf-16-le")
    units = len(encoded) // 2
    output.extend(_pack_u16(units) if size_width == 2 else _pack_u32(units))
    output.extend(encoded)


def _write_cauleb128(value: int) -> bytes:
    if value < 0 or value > 0xFFFFFFFF:
        raise CeoCcdError(f"CAULEB128 value is outside u32 range: {value}")
    encoded = [value & 0x7F]
    value >>= 7
    while value:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.reverse()
    encoded[-1] &= 0x7F
    return bytes(encoded)


def _pack_u16(value: int) -> bytes:
    return struct.pack("<H", value)


def _pack_u32(value: int) -> bytes:
    return struct.pack("<I", value)
