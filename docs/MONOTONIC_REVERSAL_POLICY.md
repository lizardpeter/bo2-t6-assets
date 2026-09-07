# Monotonic reversal policy

This repository treats reverse-engineering conclusions as cumulative machine-enforced knowledge, not disposable chat context.

## Core rule

Once a property is promoted as source/native-proven, every later extractor, converter, Blender handoff, or portable export that claims the same fidelity level MUST preserve it. A later artifact may add fidelity, but it may not silently weaken a promoted invariant.

Knowledge progresses only in this direction:

`unknown -> observed -> structurally/source/native-proven -> promoted invariant -> mandatory regression gate`

A promoted invariant can be changed only by an explicit superseding proof that identifies the old assertion, the new assertion, and the independent evidence for the change. Exporter convenience, visual plausibility, stale artifacts, adjacency, names, or compatibility shortcuts are never sufficient reasons to weaken a promoted invariant.

## Promotion rules

1. **Promote facts, not artifacts.** Artifacts are evidence carriers. The durable knowledge is the exact invariant plus its provenance.
2. **Fail closed.** Missing authority, missing evidence, missing expected fields, or an unrecognized representation fails promotion.
3. **Compare to authority mechanically.** Where exact canonical bytes or structures exist, compare against them rather than re-deriving a heuristic expectation.
4. **No stale carrier authority.** A file retained only to carry materials, animation, or metadata cannot become geometry authority merely because it is convenient.
5. **No silent fidelity downgrade.** A portable approximation must declare which proven retail inputs it omits. It cannot be labeled exact/full-retail while discarding them.
6. **Monotonic minimums.** Proven coverage counters such as recovered textures, bound material inputs, animations, or closed identities may increase but must never decrease without an explicit superseding proof.
7. **Forbidden regressions stay forbidden.** Once a representation defect is closed, encode it as a negative invariant (for example, `COLOR_0` must not reappear on the promoted SEAL6 LOD0 geometry).
8. **Lineage is mandatory.** Every promoted output must identify the authority/evidence versions it consumed. An output with unknown or stale lineage is not promotable.
9. **Visual canaries complement structural gates.** Render tests are required for shading/material work, but screenshots never replace structural/source proof.
10. **One-way deprecation.** Superseded exporters and artifacts remain clearly marked as non-authoritative and must not be accepted by current promotion workflows.

## Required pipeline shape

Every fidelity-sensitive build should have four stages:

1. **Extract** source/native evidence.
2. **Construct** the candidate artifact.
3. **Verify** candidate structure directly against promoted invariants and exact authorities.
4. **Promote** only after all gates pass and emit a machine-readable proof receipt containing invariant IDs, authority identifiers, observed values, and hashes.

A candidate that skips stage 3 is an inspection artifact, never a promoted artifact.

## Regression classes

### Structural

Examples: vertex/index changes, bone count, primitive count, winding, UV/joint/weight mutations, reappearance of a forbidden attribute.

These should be checked by exact candidate-vs-authority comparison whenever possible.

### Semantic/source binding

Examples: Material identity, GfxImage identity, TechniqueSet ownership, animation identity, pointer/backreference semantics.

These require the existing source/native proof path. Names, adjacency, visual similarity, or ordering do not substitute.

### Fidelity/coverage

Examples: 42 proven retail texture payloads collapsing to 23 visualization images, or a five-input retail material collapsing to one base color plus one normal.

The export must publish explicit coverage counts and omissions. A higher-fidelity promoted build establishes a new minimum that later builds cannot fall below.

### Visual

A promoted material/shader change should include deterministic Blender render canaries from fixed camera/light/world settings. Visual comparison catches classes of errors that structural counts cannot, while structural/source gates prevent a visually plausible approximation from being mistaken for retail truth.

## SEAL6 lesson encoded

The SEAL6 handoff regression occurred because a stale full-retail GLB was used as a carrier after geometry-v3 had already closed two defects. The stale carrier reintroduced `COLOR_0` and the old triangle winding even though both were previously solved.

The permanent rule is therefore:

- geometry authority is explicit and versioned;
- carrier files are never implicit authority;
- every future SEAL6 LOD0 candidate is compared mechanically against the promoted geometry authority before Blender or downstream promotion;
- `COLOR_0` is a forbidden regression for that promoted geometry;
- material fidelity is tracked separately and monotonically, so fixing geometry cannot conceal a material downgrade and improving materials cannot replace geometry proof.
