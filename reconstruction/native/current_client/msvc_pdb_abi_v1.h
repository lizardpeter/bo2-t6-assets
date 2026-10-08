#pragma once
// Verified-name ABI hypothesis for the exact T6 current-client / 2013 server
// byte-identical functions. Compiled only as native MSVC 32-bit code.
// Body implementations are the independently tested structural reconstructions.
//
// DO NOT conflate a decorated symbol matching the PDB with proof of exact
// executable behavior or full actor_t layout.
#if !defined(_MSC_VER) || !defined(_M_IX86)
#error T6 PDB ABI bridge requires MSVC x86
#endif
struct actor_t; // Opaque: original structure size/types not fully recovered.

void __fastcall Actor_ClearMoveHistory(actor_t*);
void __fastcall Actor_ClearScriptOrient(actor_t*);
void __fastcall Actor_ClearPileUp(actor_t*);
int __cdecl Session_GetQosPayloadBufferSize();
int __cdecl offsetOfBufInHunkUserDefault();
