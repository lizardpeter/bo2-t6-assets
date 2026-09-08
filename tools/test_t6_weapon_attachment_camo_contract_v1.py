#!/usr/bin/env python3
from __future__ import annotations

from t6_weapon_attachment_camo_contract_v1 import (
    CAMO_REQUIRED_MARKERS,
    REQUIRED_ATTACHMENT,
    REQUIRED_UNIQUE,
    build,
)


def field_table(owner: str, required: dict[str, tuple[str, str]]) -> bytes:
    lines = ["#pragma once", "namespace T6 {", "inline cspField_t fields[]{"]
    for name, (member, typ) in required.items():
        lines.append(f'{{"{name}", offsetof({owner}, {member}), {typ}}},')
    lines.extend(["};", "}"])
    return ("\n".join(lines) + "\n").encode()


def camo_schema() -> bytes:
    return ("\n".join(CAMO_REQUIRED_MARKERS.values()) + "\n").encode()


def expect_fail(fn, contains: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert contains in str(e), (contains, str(e))
    else:
        raise AssertionError("expected ValueError")


def main() -> int:
    a = field_table("WeaponAttachment", REQUIRED_ATTACHMENT)
    u = field_table("WeaponAttachmentUniqueFull", REQUIRED_UNIQUE)
    c = camo_schema()

    doc = build(a, u, c, require_pinned=False)
    assert doc["format"] == "t6-weapon-attachment-camo-contract-v1"
    assert doc["summary"]["allRequiredCanariesExact"] is True
    assert doc["summary"]["runtimeCompositionSemanticsClosed"] is False
    assert doc["summary"]["camoEquipSchemaClosed"] is True
    assert doc["equipStateContract"]["canonicalBaseWeaponImmutable"] is True
    assert doc["equipStateContract"]["rawAuthoredModifiersAlwaysPreserved"] is True

    # Wrong member/type must fail rather than silently accepting a friendly name.
    broken = a.replace(b"fFireTimeScale", b"notFireTimeScale", 1)
    expect_fail(lambda: build(broken, u, c, require_pinned=False), "fireTimeScale")

    # Missing camo semantics must fail; there is no filename-based fallback.
    broken_camo = c.replace(b"std::string baseMaterial;", b"", 1)
    expect_fail(lambda: build(a, u, broken_camo, require_pinned=False), "baseMaterial")

    # Duplicate required source row must fail because a unique field identity is required.
    extra = b'{"clipSize", offsetof(WeaponAttachment, iClipSize), CSPFT_INT},\n'
    duplicated = a.replace(b"};\n}", extra + b"};\n}")
    expect_fail(lambda: build(duplicated, u, c, require_pinned=False), "clipSize")

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
