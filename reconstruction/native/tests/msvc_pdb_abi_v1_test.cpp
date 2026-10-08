#include "../current_client/msvc_pdb_abi_v1.h"
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>

namespace {
std::uint32_t read32(const unsigned char* bytes, std::size_t offset) {
    std::uint32_t result{};
    std::memcpy(&result, bytes + offset, sizeof(result));
    return result;
}
bool expect(bool condition, const char* label) {
    if (!condition) std::cerr << "FAIL: " << label << '\n';
    return condition;
}
}

int main() {
    std::array<unsigned char, 0xc20> actor{};
    actor.fill(0xaf);
    // actor_t is intentionally opaque. This executable is a raw-memory
    // ABI smoke test, not construction of a genuine actor_t game object.
    auto* simulated_actor = reinterpret_cast<actor_t*>(actor.data());

    Actor_ClearMoveHistory(simulated_actor);
    for (std::size_t i = 0xba4; i <= 0xbf0; i += 4)
        if (!expect(read32(actor.data(), i) == 0, "move history")) return 1;
    if (!expect(read32(actor.data(), 0xb9c) == 0, "move metadata")) return 1;
    if (!expect(actor[0xba0] == 0xaf, "move guard")) return 1;

    actor.fill(0xaf);
    Actor_ClearPileUp(simulated_actor);
    if (!expect(read32(actor.data(), 0x97c) == 0 && read32(actor.data(), 0x980) == 0,
                "pileup zero")) return 1;

    actor.fill(0xaf);
    std::uint32_t zero = 0;
    std::memcpy(actor.data() + 0x1c4, &zero, sizeof(zero));
    for (int i = 0; i < 16; i++) actor[0x1b4 + i] = static_cast<unsigned char>(i + 1);
    Actor_ClearScriptOrient(simulated_actor);
    if (!expect(read32(actor.data(), 0x1c4) == 0, "orient mode latch")) return 1;
    for (int i = 4; i < 16; i++)
        if (!expect(actor[0x1c4 + i] == i + 1, "orient copy")) return 1;

    if (!expect(Session_GetQosPayloadBufferSize() == 0x10, "QoS payload length")) return 1;
    if (!expect(offsetOfBufInHunkUserDefault() == 0x28, "hunk buffer offset")) return 1;
    std::cout << "PASS: five named MSVC x86 PDB function ABI bridges\n";
}
