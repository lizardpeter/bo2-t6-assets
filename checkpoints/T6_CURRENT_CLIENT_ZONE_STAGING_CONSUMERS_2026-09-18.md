# T6 current-client zone staging consumers — 2026-09-18

## Exact CI identity

- client: Plutonium revision 5346, SHA-256 `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`
- workflow: `T6 current client zone staging consumers probe v1` (`361414117`)
- run: `35353294327`
- job: `105626397815`
- artifact: `10550043310` (`T6_CURRENT_CLIENT_ZONE_STAGING_CONSUMERS_PROBE_V1`)
- artifact ZIP SHA-256: `55f55b37720a85332fa80b09f5d2fff75bb70f2c1a53ace849d318f45cec642f`
- persisted proof JSON SHA-256: `51c83eac69b1ecd1844dc2e1702ff7b2c9166ed2c6e3186f0841eca7153d5b0f`
- persisted proof commit: `a5c24b51f2bdcd3d60a8274cd81473071ed17dcb`

The job completed successfully, deleted the executable before artifact upload, and `git diff --check` passed.

## Exact result

The bounded decode covered 489 instructions and recovered six direct stack-arena access instructions, two constant-displacement staging slots, and 23 direct calls.

The strongest downstream staging path is byte-exact:

1. local staging begins at `[esp+0x6c]` (`0x00417f40`: `lea ebp,[esp+0x6c]`);
2. the staging arena has a second exact boundary pointer at `[esp+0x15c]` (`0x00417f44`: `lea edi,[esp+0x15c]`), exactly `0xf0 = 20 * 12` bytes after the staging base;
3. after the counted input-row loop, `0x004181c4` loads a staged-row count/index value from `[esp+0x1c]`;
4. `0x004181d6` computes `3*edi`, then `0x004181d9` computes `esi = esp + 0x6c + 12*edi` exactly;
5. `0x004181dd` independently reconstructs the staging base in `edx`;
6. `0x004181e1..0x004181f8` computes the exact 12-byte-record index from `(esi-base)/12` using the signed magic multiply `0x2aaaaaab`;
7. `0x004181ff..0x00418201` passes staging-derived pointers/index state to direct callee `0x005e91b0` on the guarded path;
8. the common tail at `0x0041820f` reconstructs the staging base, then `0x00418213..0x00418215` pushes the recovered count (`edi`) and staging-base pointer (`edx`) and directly calls `0x007fddd0`.

Thus `0x007fddd0` is now an exact current-client post-staging consumer of `(stagingBase,count)` by decoded call-site data flow. This label describes only its proved role. It is **not** promoted to a source symbol.

## Proof boundary

This is current-client evidence only. The 20-record local arena capacity, exact 12-byte indexing, and `(base,count)` call are byte-supported for this client. They do not establish historical-retail identity, source-level `XZoneInfo` field names, duplicate precedence, or a Technique winner. The server `DB_LoadXAssets` lineage remains comparative evidence only.

## Next transaction already started

`tools/t6_current_client_zone_staging_callee_cfg_probe_v1.py` and its workflow now trace complete bounded CFG/caller evidence for `0x007fddd0` plus guarded helper `0x005e91b0`. Recover that CI result next and follow the post-staging consumer into persistent queue/zone state. If it is a thunk or dispatcher, follow its exact direct target rather than naming it from similarity.

## Existing closure preserved

Production textures remain 450 identity-deduplicated GfxImages with 75/450 exact DDS coverage. Historical-retail shader ownership remains fail-closed: 58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials.
