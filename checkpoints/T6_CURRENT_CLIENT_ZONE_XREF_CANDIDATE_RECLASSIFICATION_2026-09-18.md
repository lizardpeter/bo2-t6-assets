# T6 current-client zone-xref candidate reclassification — 2026-09-18

## Authority boundary

This checkpoint records **comparative current-client discovery only** from the SHA-classified Plutonium revision 5346 client. It does not establish historical retail `t6mp.exe` behavior, DB function identity, zone precedence, or any of the 58 unresolved Technique winners.

Exact current-client identity:

- bytes: `13,263,640`
- SHA-1: `f101e28c3a18ce1ffe37a40d23cd04f7f57925d3`
- SHA-256: `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`
- source artifact: workflow `361254456`, run `35332134272`, job `105558636245`
- artifact `10542240096`, ZIP SHA-256 `87f9f681cf4b67f34e6021bac1f91ad09d21d14b4cf88aaa85b056fa81b736b4`
- proof JSON SHA-256 `d3b5d7ac74b8963aad325431337bc20d70b9115dea71367704e605fa45f15307`

## Correction: 0x005225f0 was a fixed-window false positive

The v1 zone-xref probe classified call target `0x005225f0` as mask-bearing because it scanned the first 512 bytes beginning at that target.

Exact disassembly shows that `0x005225f0` is a small, separate function:

```text
005225f0  mov eax,[esp+4]
005225f4  and eax,0xff
005225f9  mov ecx,[eax*4+0x324cd88]
00522600  mov eax,[ecx+8]
00522603  ret
00522604..0052260f  int3 padding
```

The first `and eax,0x3fffffff` reported by the old 512-byte window is at `0x0052269b`, inside a later function beginning around `0x00522670`. It is therefore **not reachable evidence from the called function at 0x005225f0**.

This is exactly the contamination class the new CFG probe is designed to eliminate. `0x005225f0` is now retained only as a negative control.

## Reclassification of the two recurring shared anchors

The old probe found `0x00424f00` and `0x004c0830` near several `common`, `patch`, and `_mp` string references. Exact instruction behavior shows both are generic string-manipulation helpers rather than useful zone-precedence leads.

### 0x00424f00

The routine:

- receives destination/source/bound-like arguments from the stack;
- copies bytes in a loop;
- stops on NUL or the supplied bound;
- explicitly NUL-terminates the destination;
- returns at `0x00424f3d`.

No zone mask or duplicate-XAsset mutation is present in this function.

### 0x004c0830

The routine:

- scans the destination until its terminating NUL;
- compares the resulting length with a supplied bound;
- then copies/appends bytes from another source;
- explicitly NUL-terminates the result;
- returns at `0x004c089b`.

Its recurrence around zone-name construction is therefore not evidence of DB precedence.

Both addresses are removed from the active precedence frontier.

## Surviving current-client mask-bearing call targets

Three exact call targets remain genuinely mask-bearing within their own reachable control-flow paths:

### 0x006ad580

Exact path:

```text
006ad580  mov ecx,[esp+8]
006ad584  mov eax,[ecx]
006ad586  and eax,0xf
...
006ad59a  cmp eax,4
006ad59d  jne 0x6ad5c0
006ad59f  mov ecx,[ecx+4]
006ad5a2  mov eax,[ecx+4]
006ad5aa  and eax,0x3fffffff
...
006ad5b4  call 0x005f1d60
...
006ad5ce  ret
```

### 0x005fb2f0

Exact path:

```text
005fb2f5  mov eax,[ecx]
005fb2fa  and eax,0xf
...
005fb316  cmp eax,4
005fb319  jne 0x5fb347
005fb31b  mov ecx,[ecx+4]
005fb31e  mov eax,[ecx+4]
005fb326  and eax,0x3fffffff
...
005fb330  call 0x005f1d60
...
005fb34b  ret
```

### 0x00682340

Exact path:

```text
0068234e  mov eax,[ebx]
00682350  and eax,0xf
...
00682376  mov ecx,[esp+0x118]
0068237d  mov eax,[ebx+4]
00682388  mov edx,[eax+4]
0068238b  and edx,0x3fffffff
00682391  mov [ecx],edx
...
0068239d  ret
```

These three functions all first inspect a low-nibble discriminator and then, on one path, consume a nested field whose upper bits are masked with `0x3fffffff`. This is an exact structural commonality for this current client. It is **not** sufficient to identify the data type or to call any of them DB/zone functions.

## Newly promoted comparative target: 0x005f1d60

`0x005f1d60` is an exact direct callee shared by two independently surviving mask-bearing paths:

- call at `0x006ad5b4`
- call at `0x005fb330`

That makes it a stronger byte-supported next target than the removed generic string helpers. It still has no historical-retail authority.

## Probe change

`tools/t6_current_client_candidate_cfg_dataflow_probe_v1.py` was refined so the next CI run analyzes:

- `0x005225f0` as an explicit negative control;
- `0x006ad580`;
- `0x005fb2f0`;
- `0x00682340`;
- shared direct callee `0x005f1d60`.

It no longer spends CFG work on `0x00424f00` or `0x004c0830`.

## Next exact experiment

For each surviving target, recover only decoded reachable CFG blocks and exact global inbound direct calls. Around each in-CFG `0x3fffffff` instruction, record:

1. the nearest prior writer of the masked register in the same basic block;
2. the concrete memory operand supplying that writer, when present;
3. uses of the masked value before overwrite;
4. outbound direct-call targets reached from the same CFG.

For `0x005f1d60`, recover its inbound callers and its own memory/call graph without assigning a function name.

If this family proves to be generic tagged-value handling rather than zone/XAsset data flow, remove it from the precedence search rather than forcing a DB interpretation.

## Existing closure boundary preserved

- exact production texture denominator: **450 identity-deduplicated GfxImages**
- exact DDS bridge coverage: **75/450**
- unresolved shader-side ownership: **58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials**
