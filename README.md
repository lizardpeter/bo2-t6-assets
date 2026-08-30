# Black Ops II (T6) Asset Archive

Private archival/research repository for the ongoing Call of Duty: Black Ops II (T6) asset extraction and reconstruction project.

## Goals

- Preserve exact source provenance (`common_mp` -> `common_patch_mp` -> `patch_mp`).
- Keep extracted/decoded assets separate from reconstruction tooling and manifests.
- Store human-readable manifests, classifications, hashes, and scripts in normal Git.
- Store large binary assets through Git LFS when added from a local clone.
- Never treat patch-layer counts as additive when they override base XAssets.
- Preserve proof boundaries: inferred identities are labeled as such until exact serialized definitions are recovered.

## Current verified checkpoint

Stage 18C classifies all 172 top-level `common_mp` weapon definitions:

- 39 standard player weapon families
- 15 selectable equipment definitions
- 47 alternate/attachment variants
- 71 scorestreak/internal/helper definitions

`common_patch_mp` contains 81 weapon definitions, all of which are names already present in `common_mp`; it is therefore an override/update layer for those names rather than 81 additional guns.

The clean final multiplayer loadout catalog currently contains 40 weapon families (including the patch-era Peacekeeper) plus 15 equipment items = 55 player-facing rows.

## Repository layout

```text
assets/                  # decoded/exported assets; large binaries via Git LFS
manifests/               # inventories, hashes, dependency graphs, classifications
tools/                   # collectors, decoders, verification scripts
source-containers/       # optional original FF/IPAK/etc. sources via Git LFS
research/                # notes and proof-boundary documentation
```

## Large-file policy

Do not commit large `.ff`, `.ipak`, `.bin`, model, texture, audio, archive, or other binary payloads to ordinary Git history. `.gitattributes` defines the intended Git LFS classes. A local clone with Git LFS installed is required to upload the binary archive itself.

This repository is intentionally separate from `bo2-pc-server-decompile`.
