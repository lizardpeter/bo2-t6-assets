// 32-bit MSVC ABI bridge for five *uniquely exact-byte-matched* PDB symbols.
// Original decorated function names are independently checked from COFF .lib
// in CI. The linked bodies are host-recovered source candidates, not yet
// differential validated against BO2 retail execution.
#include "msvc_pdb_abi_v1.h"
#include "pdb_exact_game_candidates_v1.h"

void __fastcall Actor_ClearMoveHistory(actor_t* actor) {
    t6_sub_00421740(actor);
}
void __fastcall Actor_ClearScriptOrient(actor_t* actor) {
    t6_sub_005731d0(actor);
}
void __fastcall Actor_ClearPileUp(actor_t* actor) {
    t6_sub_0056f580(actor);
}
int __cdecl Session_GetQosPayloadBufferSize() {
    return static_cast<int>(t6_sub_006f9e20());
}
int __cdecl offsetOfBufInHunkUserDefault() {
    return static_cast<int>(t6_sub_00a48780());
}
