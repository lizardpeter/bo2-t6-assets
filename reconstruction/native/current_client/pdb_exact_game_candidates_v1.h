#pragma once
#include <cstdint>

// Structural host-callable reconstructions, NOT demonstrated original MSVC
// calling conventions or binary equivalence. Symbols retain exact client VAs.
extern "C" void t6_sub_00421740(void* actor); // PDB Actor_ClearMoveHistory
extern "C" void t6_sub_0050b1f0(void* curve); // PDB cCurve::Reinit
extern "C" void t6_sub_005731d0(void* actor); // PDB Actor_ClearScriptOrient
extern "C" void t6_sub_0056f580(void* actor); // PDB Actor_ClearPileUp
extern "C" void t6_sub_0041ccb0(void* notify_list); // PDB XAnimClientNotifyList ctor
extern "C" const std::uint8_t* t6_sub_004c9190(const void* mover); // PDB get_prev_origin
extern "C" std::uint32_t t6_sub_0059ee50(); // PDB gjk_obb_t::get_type
extern "C" std::uint32_t t6_sub_006f9e20(); // PDB Session_GetQosPayloadBufferSize
extern "C" std::uint32_t t6_sub_00a48780(); // PDB offsetOfBufInHunkUserDefault
