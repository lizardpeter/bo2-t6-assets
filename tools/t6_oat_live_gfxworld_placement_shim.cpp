#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <pthread.h>
#include <unistd.h>
#include <vector>

#include "Game/T6/T6_Assets.h"

namespace {
std::atomic<bool> g_dumped{false};
std::atomic<unsigned> g_scan_count{0};

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
        if (std::sscanf(line, "%lx-%lx %7s", &lo, &hi, perms) == 3)
            out.push_back({static_cast<uintptr_t>(lo), static_cast<uintptr_t>(hi), perms[0] == 'r', perms[1] == 'w'});
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
    if (!p || !n) return false;
    const auto* r = FindRegion(maps, p);
    return r && r->readable && n <= static_cast<size_t>(r->hi - p);
}

bool SafeCString(const std::vector<Region>& maps, uintptr_t p, const char** out = nullptr) {
    const auto* r = FindRegion(maps, p);
    if (!r || !r->readable || !p) return false;
    const size_t max_n = std::min<size_t>(256, static_cast<size_t>(r->hi - p));
    const auto* s = reinterpret_cast<const char*>(p);
    const auto* z = static_cast<const char*>(std::memchr(s, 0, max_n));
    if (!z || z == s) return false;
    for (const char* q = s; q < z; ++q) {
        const auto c = static_cast<unsigned char>(*q);
        if (c < 0x20 || c > 0x7e) return false;
    }
    if (out) *out = s;
    return true;
}

bool ValidateWorld(const std::vector<Region>& maps, T6::GfxWorld* w) {
    if (!ReadableRange(maps, reinterpret_cast<uintptr_t>(w), sizeof(T6::GfxWorld))) return false;
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
    for (unsigned i = 0; i < 64 && i < w->dpvs.smodelCount; ++i) {
        const auto* model = w->dpvs.smodelDrawInsts[i].model;
        if (!model || !ReadableRange(maps, reinterpret_cast<uintptr_t>(model), sizeof(uintptr_t))) continue;
        const char* n = nullptr;
        if (SafeCString(maps, reinterpret_cast<uintptr_t>(model->name), &n)) ++good;
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
    std::fputs("{\"format\":\"t6-gfxworld-static-placement-live-v2\",\"worldName\":", f);
    JsonString(f, w->name);
    std::fprintf(f,
        ",\"surfaceCount\":%d,\"smodelCount\":%u,\"structSizes\":{\"GfxWorld\":%zu,\"GfxWorldDpvsStatic\":%zu,\"GfxStaticModelInst\":%zu,\"GfxStaticModelDrawInst\":%zu},\"placements\":[",
        w->surfaceCount, w->dpvs.smodelCount, sizeof(T6::GfxWorld), sizeof(T6::GfxWorldDpvsStatic), sizeof(T6::GfxStaticModelInst), sizeof(T6::GfxStaticModelDrawInst));
    for (unsigned i = 0; i < w->dpvs.smodelCount; ++i) {
        const auto& d = w->dpvs.smodelDrawInsts[i];
        const auto& inst = w->dpvs.smodelInsts[i];
        const char* model_name = nullptr;
        if (d.model && ReadableRange(maps, reinterpret_cast<uintptr_t>(d.model), sizeof(uintptr_t)))
            SafeCString(maps, reinterpret_cast<uintptr_t>(d.model->name), &model_name);
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

bool ScanOnce() {
    const auto maps = ReadMaps();
    constexpr size_t count_off = offsetof(T6::GfxWorld, dpvs) + offsetof(T6::GfxWorldDpvsStatic, smodelCount);
    unsigned raw_hits = 0;
    unsigned named_hits = 0;
    char last_name[256]{};
    for (const auto& r : maps) {
        if (!r.readable || !r.writable || r.hi <= r.lo + sizeof(uint32_t)) continue;
        uintptr_t q = (r.lo + 3u) & ~uintptr_t(3u);
        for (; q + sizeof(uint32_t) <= r.hi; q += 4) {
            if (*reinterpret_cast<const uint32_t*>(q) != 2992u || q < count_off) continue;
            ++raw_hits;
            const uintptr_t wp = q - count_off;
            if (!ReadableRange(maps, wp, sizeof(T6::GfxWorld))) continue;
            auto* w = reinterpret_cast<T6::GfxWorld*>(wp);
            const char* n = nullptr;
            if (SafeCString(maps, reinterpret_cast<uintptr_t>(w->name), &n)) {
                ++named_hits;
                std::snprintf(last_name, sizeof(last_name), "%s", n);
            }
            if (!ValidateWorld(maps, w)) continue;
            if (DumpWorld(w, maps)) return true;
        }
    }
    FILE* d = std::fopen("gfxworld-shim-debug.txt", "w");
    if (d) {
        std::fprintf(d, "scan=%u countOffset=%zu raw2992Hits=%u candidateNamedHits=%u lastCandidateName=%s\n",
                     g_scan_count.load(), count_off, raw_hits, named_hits, last_name);
        std::fclose(d);
    }
    return false;
}

void* Scanner(void*) {
    // Let the loader establish its zone structures, then sample repeatedly while
    // --list walks the fully loaded asset pool.
    usleep(150000);
    for (unsigned i = 0; i < 40 && !g_dumped.load(std::memory_order_acquire); ++i) {
        g_scan_count.fetch_add(1, std::memory_order_relaxed);
        if (ScanOnce()) {
            g_dumped.store(true, std::memory_order_release);
            break;
        }
        usleep(25000);
    }
    return nullptr;
}

__attribute__((constructor)) void StartScanner() {
    FILE* f = std::fopen("gfxworld-shim-loaded.txt", "w");
    if (f) { std::fputs("loaded\n", f); std::fclose(f); }
    pthread_t t{};
    if (pthread_create(&t, nullptr, Scanner, nullptr) == 0) pthread_detach(t);
}
} // namespace
