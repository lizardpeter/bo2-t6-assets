# T6 current-client xref-method correction — 2026-09-18

## Authority boundary

This checkpoint records comparative analysis of the SHA-classified current Plutonium revision 5346 client only. It does not establish historical retail `t6mp.exe` behavior or select any retail Technique winner.

Exact current-client identity remains:

- bytes: `13,263,640`
- SHA-1: `f101e28c3a18ce1ffe37a40d23cd04f7f57925d3`
- SHA-256: `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`

Source discovery artifact remains workflow `361254456`, run `35332134272`, job `105558636245`, artifact `10542240096`.

## Raw-byte xrefs are no longer admissible

The v1 zone-xref probe found candidate xrefs by searching executable bytes for the little-endian 32-bit VA of a target string. That is not sufficient proof that an instruction references the string.

Concrete false-positive example for `mp_nuketown_2020`:

- string VA: `0x00be0ae8`
- reported raw-byte “xref”: `0x00af1251`
- actual decoded instruction at `0x00af1251`:
  ```text
  e8 0a be 00 00    call 0x00afd060
  ```
- the four bytes beginning at the CALL opcode happen to be `e8 0a be 00`, which decode as little-endian `0x00be0ae8`, but the instruction has no operand referencing that string.

Therefore future xref work must match the target VA in **decoded instruction operands** only.

## The genuine mp_nuketown_2020 operand xref is not a load-list path

The same artifact contains a real decoded operand reference at `0x00456048`:

```text
00456043  mov eax,[0x036223fc]
00456048  mov ecx,0x00be0ae8   ; exact mp_nuketown_2020 string VA
00456050  mov dl,[eax]
...
00456075  cmp eax,ebx
```

The following code manually compares a global string with `mp_nuketown_2020`; on equality it clears bytes across an object array and continues into `0x0060c9c0`. This is exact map-specific current-client behavior, but it is not evidence of XZoneInfo construction or DB load flags.

## The previous mask frontier was proximity contamination

At the real `_mp` operand xref in the function beginning at `0x009735b0`, the actual direct string-flow chain is:

```text
009735d6  push 0x00bf1a10      ; "_mp"
009735db  push eax
009735dc  push 0x00bfd490
009735e1  call 0x00593820
009735e6  push eax
009735e7  call 0x004c0080
009735ec  push eax
009735ed  call 0x005225f0
```

The old mask candidates were nearby rather than string-fed:

- `0x006ad580` and two calls to `0x005fb2f0` are in the preceding function, which returns at `0x009735ab`.
- the xref-bearing function starts at `0x009735b0` and returns at `0x00973622`.
- `0x00682340` is called from the following function beginning at `0x00973630`.

Thus those three mask-bearing functions are not established consumers of the `_mp` literal by this evidence.

The earlier `0x005225f0` mask classification was independently invalidated because the called function itself returns at `0x00522603`; the mask at `0x0052269b` belongs to a later function.

## Exact behavior of the real _mp chain

`0x00593820` uses a four-slot 0x400-byte temporary-buffer scheme:

- calls `0x005efba0`;
- reads/increments a slot index at `+0x1000` modulo four;
- selects a 0x400-byte slot;
- calls `0x00a739ff` with that buffer and a format/vararg-style argument arrangement;
- forces a trailing NUL and returns the selected buffer.

This is exact current-client structure; no source-level function name is promoted.

`0x004c0080` is a tiny wrapper around `0x00699500`:

```text
004c0080  mov eax,[esp+4]
004c0084  push 0
004c0086  push eax
004c0087  call 0x00699500
004c008f  ret
```

`0x005225f0` masks its argument to eight bits, indexes a pointer table at `0x0324cd88`, and returns the dword at entry offset `+8`:

```text
005225f0  mov eax,[esp+4]
005225f4  and eax,0xff
005225f9  mov ecx,[eax*4+0x0324cd88]
00522600  mov eax,[ecx+8]
00522603  ret
```

None of this establishes a DB zone-priority path.

## Historical retail recovery update

An independent public Hybrid Analysis report matches the exact historical retail client identity already tracked by this project:

- size `12,850,328`
- SHA-256 `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`
- SHA-1 `44eba16d0d9c66f40637611137affbe6b0364f20`
- MD5 `a24478561e1a03b90307f40c26a41c3e`
- original filename `t6mp.exe`
- product `Call of Duty(R): Black Ops II - Multiplayer`

The service reports the sample as unavailable, so this metadata is corroboration only, not executable evidence.

## Method change

Future current-client string-xref probes must:

1. locate exact target strings in mapped PE data;
2. disassemble executable sections;
3. accept an xref only when a decoded immediate or absolute-memory operand equals the target string VA;
4. keep direct call/data-flow analysis inside decoded control-flow boundaries;
5. never promote proximity-only calls.

A new instruction-operand xref probe is the next implementation step.

## Existing closure boundary preserved

- exact production GfxImage denominator: **450**
- exact DDS bridge coverage: **75/450**
- unresolved shader-side ownership: **58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials**
