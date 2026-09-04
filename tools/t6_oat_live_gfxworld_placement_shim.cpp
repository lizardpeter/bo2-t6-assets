#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <fcntl.h>
#include <string>
#include <unistd.h>
#include <vector>

#include "Game/T6/T6_Assets.h"

namespace {
using RealWrite = ssize_t (*)(int, const void*, size_t);
std::atomic<bool> g_dumped{false};
thread_local bool g_scanning = false;
RealWrite g_real_write = nullptr;

struct Region {
    uintptr_t lo{};
    uintptr_t hi{};
    bool readable{};
    bool writable{};
};

std::vector<Region> ReadMaps() {
    std::vector<Region> out;
    FILE* f = std::fopen("/proc/self/maps", "r");
    if (!f) return out;
    char line[1024];
    while (std::fgets(line, sizeof(line), f)) {
        unsigned long lo = 0, hi = 0;
        char perms[8]{};
        if (std::sscanf(line, "%lx-%lx %7s", &lo, &hi, perms) == 3) {
            out.push_back({static_cast<uintptr_t>(lo), static_cast<uintptr_t>(hi), perms[0] == 'r', perms[1] == 'w'});
        }
    }
    std::fclose(f);
    return out;
}

const Region* FindRegion(const std::vector<Region>& maps, uintptr_t p) {
    for (const auto& r : maps) {
        if (p >= r.lo && p < r.hi) return &r;
        if (p < r.lo) break;
    }
    return nullptr;
}

bool ReadableRange(const std::vector<Region>& maps, uintptr_t p, size_t n) {
    if (!p || n == 0) return false;
    const auto* r = FindRegion(maps, p);
    if (!r || !r->readable) return false;
    return n <= static_cast<size_t>(r->hi - p);
}

bool SafeCString(const std::vector<Region>& maps, uintptr_t p, const char** out = nullptr) {
    const auto* r = FindRegion(maps, p);
    if (!r || !r->readable || !p) return false;
    const size_t max_n = std::min<size_t>(256, static_cast<size_t>(r->hi - p));
    const auto* s = reinterpret_cast<const char*>(p);
    const void* z = std::memchr(s, 0, max_n);
    if (!z) return false;
    const size_t n = static_cast<const char*>(z) - s;
    if (n == 0) return false;
    for (size_t i = 0; i < n; ++i) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x20 || c > 0x7e) return false;
    }
    if (out) *out = s;
    return true;
}

std::vector<uintptr_t> FindNuketownStrings(const std::vector<Region>& maps) {
    static constexpr char needle[] = "mp_nuketown_2020";
    std::vector<uintptr_t> starts;
    for (const auto& r : maps) {
        if (!r.readable || r.hi <= r.lo || r.hi - r.lo > (uintptr_t(1) << 30)) continue;
        const auto* begin = reinterpret_cast<const char*>(r.lo);
        const size_t n = static_cast<size_t>(r.hi - r.lo);
        for (size_t i = 0; i + sizeof(needle) - 1 <= n; ++i) {
            if (begin[i] != 'm') continue;
            if (std::memcmp(begin + i, needle, sizeof(needle) - 1) != 0) continue;
            const uintptr_t hit = r.lo + i;
            for (size_t back = 0; back <= 64 && back <= i; ++back) {
                const uintptr_t p = hit - back;
                if (p > r.lo && *reinterpret_cast<const unsigned char*>(p - 1) != 0) continue;
                const char* s = nullptr;
                if (!SafeCString(maps, p, &s)) continue;
                if (std::strstr(s, needle) == nullptr) continue;
                bool seen = false;
                for (const auto x : starts) if (x == p) { seen = true; break; }
                if (!seen) starts.push_back(p);
            }
        }
    }
    return starts;
}

bool ValidateWorld(const std::vector<Region>& maps, T6::GfxWorld* w) {
    const uintptr_t wp = reinterpret_cast<uintptr_t>(w);
    if (!ReadableRange(maps, wp, sizeof(T6::GfxWorld))) return false;
    const char* world_name = nullptr;
    if (!SafeCString(maps, reinterpret_cast<uintptr_t>(w->name), &world_name)) return false;
    if (!std::strstr(world_name, "mp_nuketown_2020")) return false;
    if (w->dpvs.smodelCount != 2992u) return false;
    if (w->surfaceCount < 1000 || w->surfaceCount > 10000) return false;
    if (!ReadableRange(maps, reinterpret_cast<uintptr_t>(w->dpvs.smodelDrawInsts),
                       size_t(w->dpvs.smodelCount) * sizeof(T6::GfxStaticModelDrawInst))) return false;
    if (!ReadableRange(maps, reinterpret_cast<uintptr_t>(w->dpvs.smodelInsts),
                       size_t(w->dpvs.smodelCount) * sizeof(T6::GfxStaticModelInst))) return false;

    unsigned good = 0;
    for (unsigned i = 0; i < w->dpvs.smodelCount && i < 64; ++i) {
        const auto* model = w->dpvs.smodelDrawInsts[i].model;
        if (!model) continue;
        if (!ReadableRange(maps, reinterpret_cast<uintptr_t>(model), sizeof(uintptr_t))) continue;
        const char* name = nullptr;
        if (SafeCString(maps, reinterpret_cast<uintptr_t>(model->name), &name) && name && *name) ++good;
    }
    return good >= 16;
}

void JsonString(FILE* f, const char* s) {
    if (!s) { std::fputs("null", f); return; }
    std::fputc('"', f);
    for (; *s; ++s) {
        const unsigned char c = static_cast<unsigned char>(*s);
        if (c == '"' || c == '\\') { std::fputc('\\', f); std::fputc(c, f); }
        else if (c == '\n') std::fputs("\\n", f);
        else if (c == '\r') std::fputs("\\r", f);
        else if (c == '\t') std::fputs("\\t", f);
        else if (c >= 0x20) std::fputc(c, f);
    }
    std::fputc('"', f);
}

void Vec3(FILE* f, const T6::vec3_t& v) {
    std::fprintf(f, "[%.9g,%.9g,%.9g]", double(v.v[0]), double(v.v[1]), double(v.v[2]));
}

bool DumpWorld(T6::GfxWorld* w, const std::vector<Region>& maps) {
    FILE* f = std::fopen("gfxworld-static-placements-live.json", "w");
    if (!f) return false;
    std::fputs("{\"format\":\"t6-gfxworld-static-placement-live-v1\",\"worldName\":", f);
    JsonString(f, w->name);
    std::fprintf(f,
        ",\"surfaceCount\":%d,\"smodelCount\":%u,\"structSizes\":{\"GfxWorld\":%zu,\"GfxStaticModelInst\":%zu,\"GfxStaticModelDrawInst\":%zu},\"placements\":[",
        w->surfaceCount, w->dpvs.smodelCount, sizeof(T6::GfxWorld), sizeof(T6::GfxStaticModelInst), sizeof(T6::GfxStaticModelDrawInst));

    for (unsigned i = 0; i < w->dpvs.smodelCount; ++i) {
        const auto& d = w->dpvs.smodelDrawInsts[i];
        const auto& inst = w->dpvs.smodelInsts[i];
        const char* model_name = nullptr;
        if (d.model && ReadableRange(maps, reinterpret_cast<uintptr_t>(d.model), sizeof(uintptr_t))) {
            SafeCString(maps, reinterpret_cast<uintptr_t>(d.model->name), &model_name);
        }
        if (i) std::fputc(',', f);
        std::fprintf(f, "{\"index\":%u,\"model\":", i);
        JsonString(f, model_name);
        std::fprintf(f, ",\"cullDist\":%.9g,\"origin\":", double(d.cullDist));
        Vec3(f, d.placement.origin);
        std::fputs(",\"axis\":[", f);
        Vec3(f, d.placement.axis[0]); std::fputc(',', f);
        Vec3(f, d.placement.axis[1]); std::fputc(',', f);
        Vec3(f, d.placement.axis[2]);
        std::fprintf(f, "],\"scale\":%.9g,\"flags\":%d,\"mins\":", double(d.placement.scale), d.flags);
        Vec3(f, inst.mins);
        std::fputs(",\"maxs\":", f); Vec3(f, inst.maxs);
        std::fputs(",\"lightingOrigin\":", f); Vec3(f, inst.lightingOrigin);
        std::fprintf(f,
            ",\"lightingHandle\":%u,\"colorsIndex\":%u,\"primaryLightIndex\":%d,\"visibility\":%d,\"reflectionProbeIndex\":%d,\"smid\":%u}",
            unsigned(d.lightingHandle), unsigned(d.colorsIndex), int(d.primaryLightIndex), int(d.visibility), int(d.reflectionProbeIndex), d.smid);
    }
    std::fputs("]}\n", f);
    const bool ok = std::fflush(f) == 0 && std::ferror(f) == 0;
    std::fclose(f);
    return ok;
}

void TryDump() {
    if (g_dumped.load(std::memory_order_acquire)) return;
    const auto maps = ReadMaps();
    const auto strings = FindNuketownStrings(maps);
    if (strings.empty()) return;

    for (const auto& r : maps) {
        if (!r.readable || !r.writable) continue;
        const uintptr_t stop = r.hi >= sizeof(T6::GfxWorld) ? r.hi - sizeof(T6::GfxWorld) : r.lo;
        for (uintptr_t p = (r.lo + 3u) & ~uintptr_t(3u); p <= stop; p += 4) {
            const uintptr_t first = *reinterpret_cast<const uintptr_t*>(p);
            bool name_match = false;
            for (const auto s : strings) if (first == s) { name_match = true; break; }
            if (!name_match) continue;
            auto* w = reinterpret_cast<T6::GfxWorld*>(p);
            if (!ValidateWorld(maps, w)) continue;
            if (DumpWorld(w, maps)) {
                g_dumped.store(true, std::memory_order_release);
                return;
            }
        }
    }
}
} // namespace

extern "C" ssize_t write(int fd, const void* buf, size_t count) {
    if (!g_real_write) g_real_write = reinterpret_cast<RealWrite>(dlsym(RTLD_NEXT, "write"));
    if (!g_scanning && !g_dumped.load(std::memory_order_acquire)) {
        g_scanning = true;
        TryDump();
        g_scanning = false;
    }
    if (g_real_write) return g_real_write(fd, buf, count);
    return -1;
}
