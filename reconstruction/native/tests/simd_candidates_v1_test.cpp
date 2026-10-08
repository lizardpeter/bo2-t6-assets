#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>

extern "C" void t6_sub_009f6c0f(unsigned char *, int, const unsigned char *,
                                  const unsigned char *, int);
extern "C" void t6_sub_009f6d72(unsigned char *, int, const unsigned char *,
                                  const unsigned char *, int);

namespace {
constexpr int width = 16;
constexpr int height = 16;
constexpr int stride = 32;
constexpr int left_stride = 3;

bool verify_rectangle(const std::array<unsigned char, stride * height + 16>& dst,
                      unsigned char expected) {
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < stride; ++x) {
            const auto actual = dst[static_cast<std::size_t>(y * stride + x)];
            if (actual != (x < width ? expected : 0xA5)) return false;
        }
    }
    for (int i = stride * height; i < stride * height + 16; ++i)
        if (dst[static_cast<std::size_t>(i)] != 0xA5) return false;
    return true;
}

bool check_pair(unsigned char top_fill, unsigned char left_fill,
                unsigned char expected, bool left_only) {
    alignas(16) std::array<unsigned char, 16> top{};
    std::array<unsigned char, left_stride * 16> left{};
    std::array<unsigned char, stride * height + 16> dst{};
    top.fill(top_fill);
    left.fill(left_fill);
    dst.fill(0xA5);
    if (left_only) {
        t6_sub_009f6d72(dst.data(), stride, top.data(), left.data(), left_stride);
    } else {
        t6_sub_009f6c0f(dst.data(), stride, top.data(), left.data(), left_stride);
    }
    return verify_rectangle(dst, expected);
}
}

int main() {
    struct Case { unsigned char top; unsigned char left; unsigned char expected; bool left_only; };
    constexpr std::array cases{
        Case{0, 0, 0, false},
        Case{255, 255, 255, false},
        Case{255, 0, 128, false},
        Case{0, 255, 128, false},
        Case{0, 0, 0, true},
        Case{255, 255, 255, true},
        Case{0, 255, 255, true},
        Case{255, 0, 0, true},
    };
    for (std::size_t i = 0; i < cases.size(); ++i) {
        const auto& c = cases[i];
        if (!check_pair(c.top, c.left, c.expected, c.left_only)) {
            std::cerr << "simd_candidates_v1 test failed: case " << i << '\n';
            return 1;
        }
    }
    std::cout << "PASS: eight 16x16 candidate invariants and stride guards\n";
}
