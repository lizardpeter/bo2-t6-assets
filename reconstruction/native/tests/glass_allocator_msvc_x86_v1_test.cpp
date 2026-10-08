#include "../current_client/glass_allocator_msvc_x86_v1.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <new>

namespace {
std::uint32_t read32(const unsigned char* p, std::size_t offset) {
    std::uint32_t value=0;
    std::memcpy(&value,p+offset,sizeof(value));
    return value;
}
std::uint32_t pointer32(const void* p) {
    return static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(p));
}
bool check(bool ok, const char* message) {
    if(!ok) std::cerr << "FAIL: " << message << '\n';
    return ok;
}
}

int main() {
    using Pool=StaticFixedSizeAllocator<TempPackedOutline,350>;
    alignas(Pool) std::array<unsigned char, sizeof(Pool)> backing{};
    backing.fill(0xa5);
    auto* pool = new (backing.data()) Pool;
    auto* bytes=reinterpret_cast<unsigned char*>(pool);
    const auto cookie = static_cast<std::uint32_t>(0xdead0000U | (pointer32(pool) & 0xffffU));
    if(!check(read32(bytes,0)==pointer32(bytes+28),"head pointer")) return 1;
    if(!check(read32(bytes,4)==pointer32(bytes+28+349*96),"tail pointer")) return 1;
    if(!check(read32(bytes,8)==0,"allocator field2")) return 1;
    if(!check(read32(bytes,12)==350,"capacity")) return 1;
    if(!check(read32(bytes,16)==0 && read32(bytes,20)==0,"counters")) return 1;
    if(!check(read32(bytes,24)==cookie,"header cookie")) return 1;

    for(std::size_t i=0;i<350;++i) {
        const auto o=28+i*96;
        const auto next = i==349 ? 0U : pointer32(bytes+o+96);
        const auto prev = i==0 ? 0U : pointer32(bytes+o-96);
        if(!check(read32(bytes,o)==next,"forward link")) return 1;
        if(!check(read32(bytes,o+4)==prev,"reverse link")) return 1;
        if(!check(read32(bytes,o+8)==cookie,"entry cookie")) return 1;
        if(!check(bytes[o+12]==0xa5 && bytes[o+95]==0xa5,"entry payload guards")) return 1;
    }
    std::cout << "PASS: complete 350-entry native glass allocator free list\n";
}
