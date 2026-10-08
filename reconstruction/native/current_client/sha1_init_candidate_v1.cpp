// T6 current-client 0x00622F10, unique exact-byte match:
// server PDB symbol _SHA1_Init, object db_auth_sha1.obj.
// Ghidra C SHA-256 7e855a325b4c7ba17570fb3547beca1163f9f134dcc6da568b6a46e6d2f01e09
// Instruction SHA-256 5a4e9f2f29ef413b42f58cb26166a47a590683a517f2a42416ec93097b1112cf
// Candidate semantics: initial SHA-1 IV and zeroed bit counters, preserving
// original 7×u32 offsets; no unsupported context size claims.
#include <cstddef>
#include <cstdint>
#include <cstring>

extern "C" void t6_sub_00622f10(void* raw_context) {
    constexpr std::uint32_t words[7]{
        0x67452301U, 0xefcdab89U, 0x98badcfeU, 0x10325476U,
        0xc3d2e1f0U, 0U, 0U
    };
    std::memcpy(raw_context, words, sizeof(words));
}
