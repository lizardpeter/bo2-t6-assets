#include <array>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <iostream>
extern "C" void t6_sub_00622f10(void*);

int main() {
    std::array<unsigned char, 36> state{};
    state.fill(0x9b);
    t6_sub_00622f10(state.data()+4);
    constexpr std::array<std::uint32_t, 7> expected{
        0x67452301U,0xefcdab89U,0x98badcfeU,0x10325476U,0xc3d2e1f0U,0U,0U};
    for (std::size_t i=0;i<expected.size();++i) {
        std::uint32_t got{};
        std::memcpy(&got, state.data()+4+4*i,4);
        if (got != expected[i]) { std::cerr << "FAIL: SHA-1 initialization word "<<i<<'\n'; return 1; }
    }
    constexpr std::array<std::size_t,8> guards{0,1,2,3,32,33,34,35};
    for (std::size_t i: guards) {
        if (state[i]!=0x9b) {std::cerr<<"FAIL: SHA-1 guard "<<i<<'\n'; return 1;}
    }
    std::cout<<"PASS: SHA-1 context IV and counters with surrounding guard bytes\n";
}
