#include "../current_client/stream_buffer_candidates_v1.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <iostream>

namespace {
constexpr std::uint32_t virtual_base = 0x00100000U;
std::array<std::uint8_t, 0x3000> source{};
unsigned copy_calls = 0;
std::uint32_t last_copy_addr = 0;
std::uint32_t last_copy_size = 0;

std::uint32_t read32(const std::uint8_t* data, std::size_t off) {
    std::uint32_t value = 0;
    std::memcpy(&value, data + off, sizeof(value));
    return value;
}
void fail(const char* label) { std::cerr << "FAIL: " << label << '\n'; std::exit(1); }
void expect(bool ok, const char* label) { if (!ok) fail(label); }
void init_source() {
    for (std::size_t i = 0; i < source.size(); ++i)
        source[i] = static_cast<std::uint8_t>((13U * i + 17U) % 251U);
    copy_calls = 0;
    last_copy_addr = 0;
    last_copy_size = 0;
}
}

// Link-test ONLY: a virtual-source-memory adapter replacing unresolved
// address 0x00A72BF0. This is not a retail function reconstruction.
extern "C" void t6_sub_00a72bf0(void* dst, const void* src, std::uint32_t n) {
    const auto va = reinterpret_cast<std::uintptr_t>(src);
    if (va < virtual_base || va > virtual_base + source.size()) fail("virtual address");
    const auto offset = static_cast<std::size_t>(va - virtual_base);
    if (n > source.size() - offset) fail("virtual bounds");
    ++copy_calls;
    last_copy_addr = static_cast<std::uint32_t>(va);
    last_copy_size = n;
    std::memcpy(dst, source.data() + offset, n);
}

int main() {
    init_source();
    std::array<std::uint8_t, 0x1614> state{};
    state.fill(0xcd);

    // Short request: no refill, exactly one final 32-bit word and a terminal state.
    void* returned = t6_sub_009a7d00(state.data(), virtual_base + 4,
                                       virtual_base + 48, 0x87654321U);
    expect(returned == state.data(), "initializer returns self");
    expect(read32(state.data(), 0x1600) == 0x87654321U, "metadata tag");
    expect(read32(state.data(), 0x1604) == virtual_base, "initial cursor");
    expect(read32(state.data(), 0x1608) == virtual_base + 48, "end");
    expect(read32(state.data(), 0x160c) == 4, "initial latch");
    expect(read32(state.data(), 0x1610) == 48, "short span");
    expect(copy_calls == 1 && last_copy_addr == virtual_base &&
           last_copy_size == 48, "initial copy dependency contract");
    expect(std::memcmp(state.data(), source.data(), 48) == 0, "short initial bytes");
    const auto last_word = read32(state.data(), 44);
    expect(!t6_sub_009a7d60(state.data()), "short run terminates");
    expect(read32(state.data(), 0) == last_word, "short extracted word");
    expect(read32(state.data(), 0x1604) == virtual_base + 48, "short cursor");
    expect(read32(state.data(), 0x160c) == 0, "latch clears");
    expect(copy_calls == 1, "short run has no refill");
    expect(!t6_sub_009a7d60(state.data()) && copy_calls == 1, "exhausted repeat");

    // Large request: initial 0x15ff-byte copy and a second dependency call.
    init_source();
    state.fill(0xcd);
    const auto end = virtual_base + 0x2000U;
    returned = t6_sub_009a7d00(state.data(), virtual_base + 4, end, 0x33445566U);
    expect(returned == state.data(), "large initializer returns self");
    expect(read32(state.data(), 0x1610) == 0x15ffU, "initial clipped copy span");
    expect(copy_calls == 1 && last_copy_size == 0x15ffU, "large initial copy");
    const auto expected_word_1 = read32(source.data(), 0x15fbU);
    expect(t6_sub_009a7d60(state.data()), "refill requested");
    expect(read32(state.data(), 0) == expected_word_1, "first extracted word");
    expect(read32(state.data(), 0x1604) == virtual_base + 0x15fbU, "refill cursor");
    expect(copy_calls == 2, "one refill");
    expect(last_copy_addr == virtual_base + 0x15ffU, "refill address");
    expect(last_copy_size == 0x0a01U, "refill size");
    expect(read32(state.data(), 0x1610) == 0x0a05U, "refill span");
    expect(std::memcmp(state.data() + 4, source.data() + 0x15ffU, 0x0a01U) == 0,
           "refill bytes");
    const auto expected_word_2 = read32(state.data(), 0x0a01U);
    expect(!t6_sub_009a7d60(state.data()), "final buffer terminates");
    expect(read32(state.data(), 0) == expected_word_2, "final extracted word");
    expect(read32(state.data(), 0x1604) == end, "final cursor");
    expect(read32(state.data(), 0x160c) == 0, "final latch");
    expect(copy_calls == 2, "no spurious refill");
    expect(!t6_sub_009a7d60(state.data()), "terminal repeat");

    // Empty range: initialization copies zero bytes; advancing is a no-op.
    init_source();
    state.fill(0xcd);
    t6_sub_009a7d00(state.data(), virtual_base + 4, virtual_base, 1);
    expect(copy_calls == 1 && last_copy_size == 0, "empty initialization");
    expect(!t6_sub_009a7d60(state.data()) && copy_calls == 1, "empty advance");

    std::cout << "PASS: two recovered state-machine candidates, short/refill/empty paths\n";
}
