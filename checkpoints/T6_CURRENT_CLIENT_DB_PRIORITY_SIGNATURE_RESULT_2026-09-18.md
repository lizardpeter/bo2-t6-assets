# T6 current-client DB priority signature result — 2026-09-18

## Authority boundary

Comparative current Plutonium client evidence only. This does **not** establish historical retail `t6mp.exe` behavior and does not select any winner among the 58 unresolved retail Technique conflicts.

## Completed exact-byte experiment

GitHub Actions run `35316817943`, job `105510164177`, completed successfully against commit `103433ebf87864c507de9b5efd606c9f4bccf00c`.

Artifact `10535742275`, `T6_CURRENT_CLIENT_DB_PRIORITY_SIGNATURE_PROBE_V1`, digest `sha256:216efc72c278b04002f4ac05b47820a9cbfd6f019b2d290e1d8ba7a0ed3e28a7`.

SHA-pinned current client: revision 5346, 13,263,640 bytes, SHA-256 `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`.

Exact address-free server-fragment results:

- explicit `0x80` priority compare ladder: **0 hits**
- server `mov eax,54; pop ebp; ret` return fragment: **0 hits**
- explicit `0x8000` priority compare ladder: **0 hits**
- server `mov eax,57; pop ebp; ret` return fragment: **0 hits**
- `and eax,0x3fffffff`: **40 hits**
- `and ecx,0x3fffffff`: **32 hits**

The 72 mask hits are too broad to identify `DB_OverrideAsset`; no function identity is promoted from them. The zero exact priority-fragment hits mean the current client does not conserve those particular dedicated-server byte sequences. This does not disprove semantic conservation because compiler/register/branch-layout differences can change bytes while retaining control flow.

## Follow-on experiment

Added `tools/t6_current_client_db_priority_semantic_probe_v1.py` and `.github/workflows/t6_current_client_db_priority_semantic_probe_v1.yml` in commits `639461b6018c436635c75fe3b2668f27060ad4a8` and `1952cd6345d1c3ed159aa5d67d0b31d111c79227`.

The semantic probe searches decoded executable instructions for the independently server-proved ordered compare ladders `0x80 -> 0x100 -> 0x200` and `0x8000 -> 0x10000 -> 0x20000`, requiring a conditional branch after each comparison while allowing small instruction-layout variation. It separately inventories `mov eax,54; ret` and `mov eax,57; ret` candidates. Any matches remain comparative-only anchors for function-boundary recovery.

## Durable next blocker

Recover the semantic-probe CI result. If it produces a small candidate set, recover complete current-client function boundaries and callers around those candidates and test whether the masked-zone-flag comparison/call structure converges independently on the server lineage. If it produces no useful candidates, stop relying on priority-byte conservation and pivot to call/data-flow recovery around zone-name flag storage and duplicate XAsset linking. Historical-retail Technique winners remain fail-closed until genuine retail-client/runtime evidence exists.
