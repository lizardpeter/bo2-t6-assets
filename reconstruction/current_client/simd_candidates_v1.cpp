// Exact-build structural reconstruction, current-client SHA-256 770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf.
// Names remain unassigned. These routines preserve the observed five-argument cdecl interface.
// Original aligned SIMD accesses require valid 16-byte aligned top/output rows.
// Destination must provide sixteen 16-byte rows; left must provide sixteen readable stride-spaced bytes.
extern "C" void t6_sub_009f6c0f(unsigned char *dst, int dst_stride,
                              const unsigned char *top, const unsigned char *left,
                              int left_stride)
{
    unsigned int sum = 0;
    for (int i = 0; i < 16; ++i) {
        sum += top[i];
        sum += left[i * left_stride];
    }
    const unsigned char value = static_cast<unsigned char>((sum + 16u) >> 5);
    for (int y = 0; y < 16; ++y)
        for (int x = 0; x < 16; ++x)
            dst[y * dst_stride + x] = value;
}

extern "C" void t6_sub_009f6d72(unsigned char *dst, int dst_stride,
                              const unsigned char * /* unused argument retained */,
                              const unsigned char *left, int left_stride)
{
    unsigned int sum = 0;
    for (int i = 0; i < 16; ++i)
        sum += left[i * left_stride];
    const unsigned char value = static_cast<unsigned char>((sum + 8u) >> 4);
    for (int y = 0; y < 16; ++y)
        for (int x = 0; x < 16; ++x)
            dst[y * dst_stride + x] = value;
}
