// Structural reconstruction of exact current-client 0x005F2550.
// Cross-build unique instruction hash:
// 1b54ce3f688e910b31ed9bd7beceba1f965b2868c748defecc89f24a8326bcc9
// Decompiler output SHA-256:
// 726155dae153755459827397c816d72afe8012bbfcb38f75541ffaf4894045a8
// PDB: glass_client.obj
// ??0?$StaticFixedSizeAllocator@UTempPackedOutline@@$0BFO@@@QAE@XZ
//
// This models the x86 free-list construction and compiler calling convention
// only; destructor, allocation/free API, and full object layout remain open.
#include "glass_allocator_msvc_x86_v1.h"
#include <cstdint>
#include <cstring>

namespace {
void write32(std::uint8_t* base, std::size_t offset, std::uint32_t value) {
    std::memcpy(base + offset, &value, sizeof(value));
}
std::uint32_t ptr32(const void* value) {
    return static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(value));
}
}

StaticFixedSizeAllocator<TempPackedOutline,350>::StaticFixedSizeAllocator() {
    auto* base = bytes;
    const auto cookie = static_cast<std::uint32_t>(
        (ptr32(this) & 0xffffU) | 0xdead0000U);

    write32(base, 4, 0);      // last/free-tail pointer
    write32(base, 8, 0);
    write32(base, 24, cookie);
    write32(base, 0, ptr32(base + header_size)); // first/free-head pointer
    write32(base, 12, 350);
    write32(base, 16, 0);
    write32(base, 20, 0);

    std::uint32_t previous = 0;
    for (std::size_t i = 0; i < entry_count; ++i) {
        const auto offset = header_size + entry_stride * i;
        const auto current = ptr32(base + offset);
        write32(base, offset + 8, cookie);
        if (i != 0) {
            const auto previous_offset = offset - entry_stride;
            write32(base, previous_offset, current); // prior->next
        }
        write32(base, offset + 4, previous); // current->prev
        write32(base, offset, 0);            // current->next
        write32(base, 4, current);           // tail
        previous = current;
    }
}
