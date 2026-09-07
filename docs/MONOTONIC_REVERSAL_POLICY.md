# Monotonic reversal policy

This repository treats reverse-engineering conclusions as cumulative knowledge, not disposable chat context.

The objective is **not** to make experimentation rigid. It is to make sure later work starts from what is already known, understands which artifacts are authoritative or stale, and does not accidentally present an old limitation as a new result.

## Core rule

Knowledge should accumulate monotonically even when experiments remain flexible.

A useful progression is:

`unknown -> observed -> structurally/source/native-proven -> promoted knowledge -> reused context`

Hard regression gates are reserved for artifacts that are being **promoted as authoritative or retail-closed**. Exploratory scripts, temporary conversions, diagnostics, and experiments may intentionally violate promoted assumptions when that helps answer a question; they simply must not silently replace the current authority or be mistaken for a promoted result.

## Two operating modes

### Exploration mode

Exploration should stay fast and permissive.

- Try alternate decoders, carriers, shaders, coordinate transforms, and representations freely.
- Old artifacts may be inspected or reused deliberately when useful.
- Temporary outputs do not need every production invariant.
- A failed experiment is useful evidence and should not require ceremony.
- The important requirement is awareness: the experiment should know when it is using something superseded and should not accidentally inherit that component as authority.

### Promotion mode

Promotion is where fail-closed checks belong.

An artifact labeled exact, authoritative, full-retail, source-closed, native-closed, or otherwise promoted should preserve the knowledge already established for the layer it claims.

If a promoted artifact changes a previously established fact, that should be an explicit new discovery with evidence rather than an unnoticed side effect of a conversion step.

## Knowledge retention rules

1. **Retain conclusions with provenance.** Record what was learned, why it is believed, and which evidence or run established it.
2. **Track authority by layer.** Geometry, materials, textures, animations, shader semantics, and identity may have different current authorities. A convenient carrier for one layer is not automatically authority for another.
3. **Record supersession.** When v3 fixes v2, preserve the fact that v2 is stale for that layer. Later work should therefore naturally avoid using v2 as authority without needing a blanket prohibition on opening it.
4. **Separate known truth from portable approximation.** For example, 42 recovered retail texture payloads can be proven source truth even while the current Blender material representation exposes only 23 visualization images.
5. **Carry unresolved limitations forward.** A later step should inherit known open problems instead of rediscovering or forgetting them.
6. **Prefer comparative checks at promotion.** Where an exact authority exists, a promoted candidate should be compared against it rather than relying on memory or a heuristic.
7. **Use negative regression tests selectively.** Defects that are especially easy to reintroduce, such as the SEAL6 `COLOR_0` misuse, deserve a small targeted promotion gate. Not every discovery needs a hard assertion.
8. **Keep lineage visible.** Promoted outputs should identify which geometry/material/animation authorities they consumed so stale combinations are obvious.
9. **Use visual canaries for visual work.** Structural correctness and visual correctness are different. Material/shader promotion should include deterministic render inspection, while render appearance never replaces source/native proof.
10. **Do not let process replace reasoning.** Gates are a safety net, not a substitute for understanding why a choice makes sense in the current state of the reversal.

## Practical pipeline

For substantial work, think in four stages without forcing every experiment through bureaucracy:

1. **Understand current knowledge** — read the latest authority/supersession context for the layers being touched.
2. **Experiment/build** — work freely.
3. **Validate claimed layers** — before calling the result authoritative, compare only the layers it claims against their current promoted knowledge.
4. **Update knowledge** — record new conclusions, superseded assumptions, remaining blockers, and artifact lineage so the next piece of work starts ahead of this one.

## Regression classes

### Structural

Examples: vertex/index changes, bone count, primitive count, winding, UV/joint/weight mutations, or reappearance of an unsafe standard semantic.

Exact comparison is useful for promotion when a canonical geometry authority exists, but exploratory geometry experiments remain allowed.

### Semantic/source binding

Examples: Material identity, GfxImage identity, TechniqueSet ownership, animation identity, and pointer/backreference semantics.

These continue to require the appropriate source/native evidence before they are promoted. Names, adjacency, or visual similarity may guide exploration but do not become proof by themselves.

### Fidelity/coverage

Examples: 42 proven retail texture payloads collapsing to 23 visualization images, or a five-input retail material collapsing to one base color plus one normal.

The key is to preserve that distinction in context. An approximation can still be useful; it simply should not cause us to forget that a higher-fidelity source representation is already known.

### Visual

For material/shader work, fixed Blender render canaries are valuable because they catch errors that counts and hashes cannot. They complement rather than replace structural/source evidence.

## SEAL6 lesson

The SEAL6 handoff regression happened because a stale full-retail GLB was reused after geometry-v3 had already fixed two geometry-carrier defects. The stale carrier reintroduced `COLOR_0` and the old triangle winding.

The durable lesson is not “never use old files.” It is:

- remember that geometry-v3 is the current geometry authority;
- remember that the older full-retail GLB is useful only as a carrier for layers it still contains correctly;
- when combining layers from different artifacts, explicitly keep authority per layer in mind;
- before promoting the combined result, compare the geometry portion to geometry-v3 and confirm the known `COLOR_0` defect did not return;
- separately preserve the known material limitation that the portable 23-image representation is not equivalent to the 42 recovered retail texture payloads.

That keeps the project cumulative without making experimentation cumbersome.
