#pragma once
#if !defined(_MSC_VER) || !defined(_M_IX86)
#error Native glass allocator reconstruction requires MSVC Win32
#endif
#include <cstddef>
#include <cstdint>

struct TempPackedOutline;  // Type identity from exact-byte matched PDB.
template <class Item, int Count> struct StaticFixedSizeAllocator;

template <>
struct alignas(4) StaticFixedSizeAllocator<TempPackedOutline, 350> {
    // Only the raw size, free-list records, and known field offsets are
    // reconstructed. Do not invent TempPackedOutline's original layout.
    static constexpr std::size_t header_size = 28;
    static constexpr std::size_t entry_stride = 96;
    static constexpr std::size_t entry_count = 350;
    std::uint8_t bytes[header_size + entry_stride * entry_count];
    StaticFixedSizeAllocator();
};
static_assert(sizeof(StaticFixedSizeAllocator<TempPackedOutline,350>)==33628);
static_assert(alignof(StaticFixedSizeAllocator<TempPackedOutline,350>)==4);
