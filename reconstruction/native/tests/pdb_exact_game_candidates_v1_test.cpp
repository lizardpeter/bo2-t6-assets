#include "../current_client/pdb_exact_game_candidates_v1.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <iostream>
#include <initializer_list>

namespace {
void require(bool ok, const char* what) {
    if (!ok) { std::cerr << "FAIL: " << what << '\n'; std::exit(1); }
}
template <class T, std::size_t N>
void write(std::array<std::uint8_t,N>& state, std::size_t off, T value) {
    std::memcpy(state.data() + off, &value, sizeof(value));
}
template <class T, std::size_t N>
T read(const std::array<std::uint8_t,N>& state, std::size_t off) {
    T value{};
    std::memcpy(&value, state.data() + off, sizeof(value));
    return value;
}
}

int main() {
    std::array<std::uint8_t, 0xc20> actor{};
    actor.fill(0xa5);
    t6_sub_00421740(actor.data());
    require(read<std::uint32_t>(actor, 0xb9c) == 0, "move-history extra slot");
    for (std::size_t at = 0xba4; at <= 0xbf0; at += 4)
        require(read<std::uint32_t>(actor, at) == 0, "move-history contiguous state");
    require(actor[0xb98] == 0xa5 && actor[0xba0] == 0xa5 &&
            actor[0xbf4] == 0xa5, "move-history guard bytes");

    actor.fill(0xa5);
    t6_sub_0056f580(actor.data());
    require(read<std::uint32_t>(actor, 0x97c) == 0 &&
            read<std::uint32_t>(actor, 0x980) == 0, "pile-up state clears");
    require(actor[0x97b] == 0xa5 && actor[0x984] == 0xa5, "pile-up bounds");

    std::array<std::uint8_t, 0x200> orient{};
    orient.fill(0xa5);
    for (int i=0; i<16; ++i)
        orient[0x1b4+i] = static_cast<std::uint8_t>(0x40+i);
    write<std::uint32_t>(orient, 0x1c4, 0U);
    t6_sub_005731d0(orient.data());
    require(read<std::uint32_t>(orient, 0x1c4) == 0, "orientation latch clears on copy");
    for (int i=4; i<16; ++i)
        require(orient[0x1c4+i] == static_cast<std::uint8_t>(0x40+i), "orientation source to target");
    for (int i=0; i<16; ++i)
        orient[0x1c4+i] = static_cast<std::uint8_t>(0x80+i);
    t6_sub_005731d0(orient.data());
    for (int i=0; i<16; ++i)
        require(orient[0x1b4+i] == static_cast<std::uint8_t>(0x80+i), "orientation target to source");
    require(read<std::uint32_t>(orient, 0x1c4) == 0, "orientation latch clears on return");
    for (int i=4; i<16; ++i)
        require(orient[0x1c4+i] == static_cast<std::uint8_t>(0x80+i), "orientation untouched tail");

    std::array<std::uint8_t,0x2a80> curve{};
    curve.fill(0xa5);
    t6_sub_0050b1f0(curve.data());
    require(read<std::uint8_t>(curve,0x2a44)==1, "curve enabled");
    require(read<std::uint8_t>(curve,0x2a50)==0, "curve mode");
    require(read<std::uint16_t>(curve,0x2a64)==0x100, "curve 0x100");
    require(read<std::uint32_t>(curve,0x2a30)==0x3ff &&
            read<std::uint32_t>(curve,0x2a34)==0x3ff, "curve 1023 limits");
    require(read<std::uint32_t>(curve,0x2a70)==0xffffffffU, "curve index sentinel");
    for (auto at : {0x2a40,0x2a48,0x2a4c,0x2a68,0x2a6c})
        require(read<std::uint32_t>(curve,at)==0, "curve cleared fields");
    require(read<std::uint8_t>(curve,0x2a38)==0, "curve initial byte");
    require(curve[0x2a2f]==0xa5 && curve[0x2a74]==0xa5, "curve guard bytes");

    std::array<std::uint8_t,0x504> notify{};
    notify.fill(0xa5);
    t6_sub_0041ccb0(notify.data());
    require(read<std::uint32_t>(notify,0x500)==0, "notify constructor field");
    require(notify[0x4ff]==0xa5, "notify guard");

    std::array<std::uint8_t,0x400> mover{};
    mover.fill(0);
    write<std::int32_t>(mover,0x380,0);
    require(t6_sub_004c9190(mover.data()) == mover.data()+0x364, "mover empty");
    write<std::int32_t>(mover,0x380,1);
    require(t6_sub_004c9190(mover.data()) == mover.data(), "mover one");
    write<std::int32_t>(mover,0x380,4);
    require(t6_sub_004c9190(mover.data()) == mover.data()+3*0x1c, "mover four");

    require(t6_sub_0059ee50()==6, "GJK OBB enum");
    require(t6_sub_006f9e20()==0x10, "QoS buffer size");
    require(t6_sub_00a48780()==0x28, "hunk default offset");
    std::cout << "PASS: nine PDB-matched T6 source candidates and byte-layout invariants\n";
}
