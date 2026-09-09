#!/usr/bin/env python3
from __future__ import annotations

from t6_oat_layered_component_texture_recovery_v3 import (
    RecoveryError,
    _canonical,
    _candidate_for_position,
    _name_hash,
    _project,
    _subtract_exact,
    _suffix_row,
)


def row(name: str, image: str) -> dict:
    return {
        "name": name,
        "semantic": "colorMap",
        "isMatureContent": False,
        "samplerState": {
            "filter": "linear",
            "mipMap": "nearest",
            "clampU": False,
            "clampV": False,
            "clampW": False,
        },
        "image": image,
    }


def main() -> int:
    base = [row("normalMap", "base_n"), row("colorMap", "base_c")]
    decal = [row("colorMap", "decal_c"), row("specularMap", "decal_s")]
    tables = {"base": base, "decal": decal}

    generated = _project(["base", "decal"], tables)
    assert [x["name"] for x in generated] == [
        x["name"] for x in sorted(generated, key=lambda x: _name_hash(x["name"]))
    ]
    assert any(x["name"] == "colorMap1" for x in generated)
    assert any(x["name"] == "specularMap1" for x in generated)
    # Sampler state is preserved exactly; v3 must not reintroduce BO1 mip promotion.
    assert all(x["samplerState"]["mipMap"] == "nearest" for x in generated)

    known = [_suffix_row(x, 0) for x in base]
    residual = _subtract_exact(generated, known)
    recovered = _candidate_for_position(residual, [1], 1)
    assert _canonical(recovered) == _canonical(sorted(decal, key=lambda x: _name_hash(x["name"])))

    repeated = _project(["base", "decal", "decal"], tables)
    repeated_known = [_suffix_row(x, 0) for x in base]
    repeated_residual = _subtract_exact(repeated, repeated_known)
    c1 = _candidate_for_position(repeated_residual, [1, 2], 1)
    c2 = _candidate_for_position(repeated_residual, [1, 2], 2)
    assert _canonical(c1) == _canonical(c2) == _canonical(sorted(decal, key=lambda x: _name_hash(x["name"])))
    assert len(c1) + len(c2) == len(repeated_residual)

    try:
        _candidate_for_position([row("colorMap2", "bad")], [1], 1)
    except RecoveryError:
        pass
    else:
        raise AssertionError("wrong layer suffix did not fail closed")

    try:
        _subtract_exact(generated, [row("notPresent", "none")])
    except RecoveryError:
        pass
    else:
        raise AssertionError("missing known row did not fail closed")

    print("GREEN T6 LAYERED COMPONENT TEXTURE RECOVERY V3 REGRESSION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
