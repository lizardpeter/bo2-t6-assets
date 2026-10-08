// Candidate reconstructions for exact current-client SHA-256:
// 770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf
// Derived from separately retained uregraph source:C representations:
//   0x009A7D00 / 0x009A7D60
// Evidence witness: fa0cf584261bb99137ebb734c3371119404800d3
// These are NOT proof of retail behavioral equivalence or valid production ABI.
#include "stream_buffer_candidates_v1.h"
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace {
// The retail target is little-endian MSVC x86. memcpy avoids host aliasing /
// unaligned-access undefined behavior during stand-alone tests; it does not
// establish alignment-sensitive binary identity.
std::uint32_t get32(const std::uint8_t* p, std::size_t offset) {
    std::uint32_t result = 0;
    std::memcpy(&result, p + offset, sizeof(result));
    return result;
}
void put32(std::uint8_t* p, std::size_t offset, std::uint32_t value) {
    std::memcpy(p + offset, &value, sizeof(value));
}
}

extern "C" void* t6_sub_009a7d00(void* self, std::uint32_t start_plus_four,
                                   std::uint32_t end, std::uint32_t tag) {
    auto* bytes = static_cast<std::uint8_t*>(self);
    put32(bytes, 0x1600, tag);
    const auto start = static_cast<std::uint32_t>(start_plus_four - 4U);
    put32(bytes, 0x1608, end);
    put32(bytes, 0x1604, start);
    put32(bytes, 0x160c, 4U);
    std::uint32_t copy_size = end - start;
    if (copy_size > 0x15ffU) copy_size = 0x15ffU;
    put32(bytes, 0x1610, copy_size);
    t6_sub_00a72bf0(self,
                      reinterpret_cast<const void*>(static_cast<std::uintptr_t>(start)),
                      copy_size);
    return self;
}

extern "C" bool t6_sub_009a7d60(void* self) {
    auto* bytes = static_cast<std::uint8_t*>(self);
    const auto cursor = get32(bytes, 0x1604);
    const auto end = get32(bytes, 0x1608);
    put32(bytes, 0x160c, 0U);
    if (cursor >= end) return false;

    std::uint32_t span = get32(bytes, 0x1610);
    put32(bytes, 0, get32(bytes, static_cast<std::size_t>(span - 4U)));
    const auto advanced = static_cast<std::uint32_t>(span + 4U);
    if (advanced < 0x15ffU) {
        put32(bytes, 0x1604, span + cursor);
        return false;
    }

    const auto next = static_cast<std::uint32_t>(span + cursor - 4U);
    const auto remaining = static_cast<std::uint32_t>(end - next - 4U);
    put32(bytes, 0x1604, next);
    std::uint32_t copy_size = remaining;
    if (copy_size >= 0x15fbU) copy_size = 0x15fbU;
    t6_sub_00a72bf0(bytes + 4,
                      reinterpret_cast<const void*>(static_cast<std::uintptr_t>(next + 4U)),
                      copy_size);
    span = copy_size + 4U;
    put32(bytes, 0x1610, span);
    return true;
}
