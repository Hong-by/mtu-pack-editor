from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .pfh import find_entry, read_entry_bytes, read_pfh_index


POOL_SCHEMA_VERSION = 2
CCD_PACK_PATH = "campaigns/ceo_data.ccd"


class DedicatedArmourPoolError(ValueError):
    """Raised when a precompiled dedicated-armour CEO pool is unsafe to use."""


@dataclass(frozen=True)
class DedicatedArmourSlot:
    slot_id: str
    source_ceo_key: str
    source_initial_ceo_key: str
    source_armour_type_key: str
    armour_ceo_key: str
    initial_ceo_key: str
    armour_type_key: str


@dataclass(frozen=True)
class DedicatedArmourPool:
    pool_id: str
    label: str
    mode: str
    base_ccd_sha256: str
    compiled_ccd_sha256: str
    ccd_path: Path | None
    slots: tuple[DedicatedArmourSlot, ...]
    manifest_path: Path


@dataclass(frozen=True)
class CcdFingerprint:
    pack_path: Path
    packed_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class DedicatedArmourPoolStatus:
    available: bool
    reason: str
    active_ccd: CcdFingerprint | None
    pool: DedicatedArmourPool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "activeCcd": (
                {
                    "packPath": str(self.active_ccd.pack_path),
                    "packedPath": self.active_ccd.packed_path,
                    "sha256": self.active_ccd.sha256,
                    "size": self.active_ccd.size,
                }
                if self.active_ccd
                else None
            ),
            "pool": (
                {
                    "poolId": self.pool.pool_id,
                    "label": self.pool.label,
                    "mode": self.pool.mode,
                    "slotCount": len(self.pool.slots),
                    "baseCcdSha256": self.pool.base_ccd_sha256,
                    "compiledCcdSha256": self.pool.compiled_ccd_sha256,
                    "slots": [
                        {
                            "slotId": slot.slot_id,
                            "sourceCeoKey": slot.source_ceo_key,
                            "sourceInitialCeoKey": slot.source_initial_ceo_key,
                            "sourceArmourTypeKey": slot.source_armour_type_key,
                            "armourCeoKey": slot.armour_ceo_key,
                            "initialCeoKey": slot.initial_ceo_key,
                            "armourTypeKey": slot.armour_type_key,
                        }
                        for slot in self.pool.slots
                    ],
                }
                if self.pool
                else None
            ),
        }


def load_dedicated_armour_pools(roots: Iterable[Path]) -> list[DedicatedArmourPool]:
    pools: list[DedicatedArmourPool] = []
    seen_ids: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for manifest_path in sorted(root.glob("*.json")):
            pool = _load_pool_manifest(manifest_path)
            if pool.pool_id in seen_ids:
                continue
            seen_ids.add(pool.pool_id)
            pools.append(pool)
    return pools


def inspect_pack_ccd(pack_path: Path) -> CcdFingerprint | None:
    if not pack_path.is_file():
        return None
    try:
        index = read_pfh_index(pack_path)
        entry = find_entry(index, CCD_PACK_PATH)
        data = read_entry_bytes(pack_path, entry)
        if data[:4] not in {b"\xCA\xAB\x00\x00", b"\xCB\xAB\x00\x00"}:
            return None
    except (OSError, ValueError):
        return None
    return CcdFingerprint(
        pack_path=pack_path.resolve(),
        packed_path=CCD_PACK_PATH,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
    )


def resolve_effective_ccd(pack_paths: Iterable[Path]) -> CcdFingerprint | None:
    active: CcdFingerprint | None = None
    for pack_path in pack_paths:
        fingerprint = inspect_pack_ccd(pack_path)
        if fingerprint is not None:
            active = fingerprint
    return active


def ordered_active_ccd_pack_paths(
    source_pack: Path | None,
    reference_packs: Iterable[Path],
) -> list[Path]:
    """Return CEO-data load order with explicit reference mods layered last."""
    ordered = [path for path in [source_pack, *reference_packs] if path is not None]
    result: list[Path] = []
    seen: set[str] = set()
    for path in ordered:
        try:
            identity = str(path.resolve()).lower()
        except OSError:
            identity = str(path).lower()
        if identity in seen:
            continue
        seen.add(identity)
        result.append(path)
    return result


def resolve_pool_status(
    pools: Iterable[DedicatedArmourPool],
    pack_paths: Iterable[Path],
) -> DedicatedArmourPoolStatus:
    active_ccd = resolve_effective_ccd(pack_paths)
    if active_ccd is None:
        return DedicatedArmourPoolStatus(
            available=False,
            reason="활성 campaigns/ceo_data.ccd를 찾지 못했습니다.",
            active_ccd=None,
            pool=None,
        )

    compatible = [
        pool
        for pool in pools
        if pool.mode == "precompiled"
        and active_ccd.sha256
        in {
            pool.base_ccd_sha256,
            pool.compiled_ccd_sha256,
        }
    ]
    if compatible:
        # A one-slot POC fixture may coexist with a production pool for the
        # same base CCD. Prefer the production pool with the most fixed slots.
        pool = max(compatible, key=lambda item: (len(item.slots), item.pool_id))
        return DedicatedArmourPoolStatus(
            available=True,
            reason="현재 CEO 데이터와 일치하는 사전 컴파일 전용 갑옷 슬롯입니다.",
            active_ccd=active_ccd,
            pool=pool,
        )

    return DedicatedArmourPoolStatus(
        available=False,
        reason=(
            "현재 CEO 데이터와 일치하는 사전 컴파일 전용 갑옷 슬롯이 없어 "
            "안전을 위해 기능을 차단합니다."
        ),
        active_ccd=active_ccd,
        pool=None,
    )


def allocate_dedicated_armour_slot(
    pool: DedicatedArmourPool,
    used_slot_ids: Iterable[str],
    source_ceo_key: str | None = None,
) -> DedicatedArmourSlot:
    used = {str(value) for value in used_slot_ids}
    for slot in pool.slots:
        if source_ceo_key and slot.source_ceo_key not in {"*", source_ceo_key}:
            continue
        if slot.slot_id not in used:
            return slot
    source_detail = f", source={source_ceo_key}" if source_ceo_key else ""
    raise DedicatedArmourPoolError(
        f"전용 갑옷 CEO 슬롯이 부족합니다: pool={pool.pool_id}, "
        f"slots={len(pool.slots)}{source_detail}"
    )


def verify_pool_asset(pool: DedicatedArmourPool) -> None:
    if pool.mode != "precompiled":
        raise DedicatedArmourPoolError(
            "런타임 동적 CCD 복제 풀은 안전하지 않아 지원하지 않습니다."
        )
    if pool.ccd_path is None or not pool.ccd_path.is_file():
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀 CCD가 없습니다: {pool.ccd_path}"
        )
    digest = _sha256_file(pool.ccd_path)
    if digest != pool.compiled_ccd_sha256:
        raise DedicatedArmourPoolError(
            "전용 갑옷 풀 CCD 해시가 manifest와 다릅니다: "
            f"pool={pool.pool_id}, expected={pool.compiled_ccd_sha256}, actual={digest}"
        )


def validate_pool_assignments(
    pool: DedicatedArmourPool,
    assignments: Iterable[Any],
) -> None:
    slots = {slot.slot_id: slot for slot in pool.slots}
    used: set[str] = set()
    for assignment in assignments:
        if str(getattr(assignment, "pool_id", "")) != pool.pool_id:
            raise DedicatedArmourPoolError(
                "서로 다른 전용 갑옷 CEO 풀을 한 팩에 넣을 수 없습니다."
            )
        slot_id = str(getattr(assignment, "slot_id", ""))
        if slot_id in used:
            raise DedicatedArmourPoolError(
                f"전용 갑옷 CEO 슬롯을 중복 사용했습니다: {slot_id}"
            )
        slot = slots.get(slot_id)
        if slot is None:
            raise DedicatedArmourPoolError(
                f"전용 갑옷 CEO 슬롯을 풀에서 찾지 못했습니다: {slot_id}"
            )
        expected = {
            "source_ceo_key": slot.source_ceo_key,
            "source_initial_ceo_key": slot.source_initial_ceo_key,
            "source_armour_type_key": slot.source_armour_type_key,
            "armour_ceo_key": slot.armour_ceo_key,
            "initial_ceo_key": slot.initial_ceo_key,
            "armour_type_key": slot.armour_type_key,
        }
        for field_name, expected_value in expected.items():
            actual = str(getattr(assignment, field_name, ""))
            if expected_value == "*" and field_name.startswith("source_"):
                if not actual:
                    raise DedicatedArmourPoolError(
                        "전용 갑옷 원본 정보가 비었습니다: "
                        f"slot={slot_id}, field={field_name}"
                    )
                continue
            if actual != expected_value:
                raise DedicatedArmourPoolError(
                    "전용 갑옷 CEO 슬롯 정보가 manifest와 다릅니다: "
                    f"slot={slot_id}, field={field_name}"
                )
        used.add(slot_id)


def _load_pool_manifest(manifest_path: Path) -> DedicatedArmourPool:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀 manifest를 읽지 못했습니다: {manifest_path}: {error}"
        ) from error

    schema_version = int(data.get("schemaVersion") or 0)
    if schema_version not in {1, POOL_SCHEMA_VERSION}:
        raise DedicatedArmourPoolError(
            f"지원하지 않는 전용 갑옷 풀 schemaVersion입니다: {manifest_path}"
        )
    pool_id = _required_text(data, "poolId", manifest_path)
    mode = str(data.get("mode") or "precompiled").strip().lower()
    if mode != "precompiled":
        raise DedicatedArmourPoolError(
            f"런타임 동적 전용 갑옷 풀은 지원하지 않습니다: {manifest_path}"
        )
    base_hash = _required_hash(data, "baseCcdSha256", manifest_path)
    compiled_hash = _required_hash(data, "compiledCcdSha256", manifest_path)
    ccd_file = _required_text(data, "ccdFile", manifest_path)

    raw_slots = data.get("slots")
    if not isinstance(raw_slots, list) or not raw_slots:
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀에 slots가 없습니다: {manifest_path}"
        )
    slots = tuple(
        DedicatedArmourSlot(
            slot_id=_required_text(item, "slotId", manifest_path),
            source_ceo_key=_required_text(item, "sourceCeoKey", manifest_path),
            source_initial_ceo_key=_required_text(
                item, "sourceInitialCeoKey", manifest_path
            ),
            source_armour_type_key=_required_text(
                item, "sourceArmourTypeKey", manifest_path
            ),
            armour_ceo_key=_required_text(item, "armourCeoKey", manifest_path),
            initial_ceo_key=_required_text(item, "initialCeoKey", manifest_path),
            armour_type_key=_required_text(item, "armourTypeKey", manifest_path),
        )
        for item in raw_slots
        if isinstance(item, dict)
    )
    if len(slots) != len(raw_slots):
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀 slots 형식이 잘못되었습니다: {manifest_path}"
        )
    slot_ids = [slot.slot_id for slot in slots]
    if len(set(slot_ids)) != len(slot_ids):
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀 slotId가 중복되었습니다: {manifest_path}"
        )

    return DedicatedArmourPool(
        pool_id=pool_id,
        label=str(data.get("label") or pool_id),
        mode=mode,
        base_ccd_sha256=base_hash,
        compiled_ccd_sha256=compiled_hash,
        ccd_path=(manifest_path.parent / ccd_file).resolve(),
        slots=slots,
        manifest_path=manifest_path.resolve(),
    )


def _required_text(data: dict[str, Any], key: str, path: Path) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀 manifest 필드가 비었습니다: {path}: {key}"
        )
    return value


def _required_hash(data: dict[str, Any], key: str, path: Path) -> str:
    value = _required_text(data, key, path).lower()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise DedicatedArmourPoolError(
            f"전용 갑옷 풀 SHA-256 형식이 잘못되었습니다: {path}: {key}"
        )
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
