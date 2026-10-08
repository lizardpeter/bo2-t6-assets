// Source recovery from exact SHA-pinned current-client Ghidra C, with unique
// exact-instruction-hash cross-build PDB symbol witnesses, 2026-10-07.
// Current-client executable SHA256:
// 770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf
// Input generated C: 10 verified retained Ghidra archives, extracted to
// workflow artifact t6-pdb-ghidra-unreviewed (manifest has per-file SHA256).
//
// Every function is still a *structural source candidate*, not retail-parity
// or MSVC x86 ABI validated. Nonstandard original __fastcall ABI intentionally
// is NOT assumed here. Host functions take explicit object pointers.
#include "pdb_exact_game_candidates_v1.h"
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace {
std::uint8_t* raw(void* p) {
    return static_cast<std::uint8_t*>(p);
}
const std::uint8_t* raw(const void* p) {
    return static_cast<const std::uint8_t*>(p);
}
template <class T>
void store(std::uint8_t* p, std::size_t off, T value) {
    std::memcpy(p + off, &value, sizeof(value));
}
template <class T>
T load(const std::uint8_t* p, std::size_t off) {
    T value{};
    std::memcpy(&value, p + off, sizeof(value));
    return value;
}
}

extern "C" void t6_sub_00421740(void* actor) {
    auto* p = raw(actor);
    // Exact Ghidra writes: 0xBA4..0xBF0 inclusive (20 u32), then 0xB9C.
    for (std::size_t offset = 0xba4; offset <= 0xbf0; offset += 4)
        store<std::uint32_t>(p, offset, 0U);
    store<std::uint32_t>(p, 0xb9c, 0U);
}

extern "C" void t6_sub_0050b1f0(void* curve) {
    auto* p = raw(curve);
    store<std::uint8_t>(p, 0x2a44, 1);
    store<std::uint8_t>(p, 0x2a50, 0);
    store<std::uint16_t>(p, 0x2a64, 0x100);
    store<std::uint32_t>(p, 0x2a30, 0x3ff);
    store<std::uint8_t>(p, 0x2a38, 0);
    store<std::uint32_t>(p, 0x2a34, 0x3ff);
    store<std::uint32_t>(p, 0x2a70, 0xffffffffU);
    store<std::uint32_t>(p, 0x2a40, 0U);
    store<std::uint32_t>(p, 0x2a48, 0U);
    store<std::uint32_t>(p, 0x2a4c, 0U);
    store<std::uint32_t>(p, 0x2a68, 0U);
    store<std::uint32_t>(p, 0x2a6c, 0U);
}

extern "C" void t6_sub_005731d0(void* actor) {
    auto* p = raw(actor);
    if (load<std::int32_t>(p, 0x1c4) == 0) {
        std::memcpy(p + 0x1c4, p + 0x1b4, 16);
    } else {
        std::memcpy(p + 0x1b4, p + 0x1c4, 16);
    }
    store<std::uint32_t>(p, 0x1c4, 0U);
}

extern "C" void t6_sub_0056f580(void* actor) {
    auto* p = raw(actor);
    store<std::uint32_t>(p, 0x97c, 0U);
    store<std::uint32_t>(p, 0x980, 0U);
}

extern "C" void t6_sub_0041ccb0(void* notify_list) {
    store<std::uint32_t>(raw(notify_list), 0x500, 0U);
}

extern "C" const std::uint8_t* t6_sub_004c9190(const void* mover) {
    const auto* p = raw(mover);
    const auto count = load<std::int32_t>(p, 0x380);
    return count > 0 ? p + static_cast<std::size_t>(count - 1) * 0x1cU : p + 0x364;
}

extern "C" std::uint32_t t6_sub_0059ee50() { return 6; }
extern "C" std::uint32_t t6_sub_006f9e20() { return 0x10; }
extern "C" std::uint32_t t6_sub_00a48780() { return 0x28; }
