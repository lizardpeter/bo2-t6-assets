#!/usr/bin/env python3
from __future__ import annotations

import t6_vertex_output_symbolic_v1 as symbolic
import t6_retail_special_shdr_symbolic_v1 as shared


def main() -> int:
    dag = shared.Dag()
    n = tuple(dag.add("symbol", name=f"N.{c}") for c in "xyz")
    t = tuple(dag.add("symbol", name=f"T.{c}") for c in "xyz")
    h = dag.add("symbol", name="T.w")

    expected = symbolic.cross_times_handedness(dag, n, t, h)
    result = symbolic.classify_cross_handedness(
        dag,
        normal=n,
        tangent=t,
        handedness=h,
        candidate=expected,
    )
    assert result["uniqueMatch"] == "cross(normal,tangent)*handedness"
    assert result["matches"] == ["cross(normal,tangent)*handedness"]

    # Build the same X component with multiplication operands reversed and the
    # negative product listed first. Canonicalization must still recognize the
    # exact algebra rather than depending on compiler operand order.
    ny_tz = dag.add("op", op="mul", args=[t[2], n[1]])
    nz_ty = dag.add("op", op="mul", args=[t[1], n[2]])
    x_alt = dag.add("op", op="add", args=[
        dag.add("op", op="neg", args=[nz_ty]),
        ny_tz,
    ])
    x_alt = dag.add("op", op="mul", args=[h, x_alt])
    alt = (x_alt, expected[1], expected[2])
    result = symbolic.classify_cross_handedness(
        dag,
        normal=n,
        tangent=t,
        handedness=h,
        candidate=alt,
    )
    assert result["uniqueMatch"] == "cross(normal,tangent)*handedness"

    reversed_cross = symbolic.cross_times_handedness(dag, t, n, h)
    result = symbolic.classify_cross_handedness(
        dag,
        normal=n,
        tangent=t,
        handedness=h,
        candidate=reversed_cross,
    )
    assert result["uniqueMatch"] == "cross(tangent,normal)*handedness"

    # An ancestry-compatible but arithmetically wrong sum must not be promoted.
    wrong = tuple(
        dag.add("op", op="add", args=[n[i], t[i]])
        for i in range(3)
    )
    result = symbolic.classify_cross_handedness(
        dag,
        normal=n,
        tangent=t,
        handedness=h,
        candidate=wrong,
    )
    assert result["matches"] == []
    assert result["uniqueMatch"] is None

    print("PASS: T6 vertex output symbolic cross/handedness algebra classifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
