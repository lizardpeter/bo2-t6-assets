// Differential tests against SHA-verified original x86 instructions.
#include "t6_simd_reference.inc"
using Fn = void (*)(unsigned char*, int, const unsigned char*, const unsigned char*, int);
extern "C" void t6_sub_009f6c0f(unsigned char*,int,const unsigned char*,const unsigned char*,int);
extern "C" void t6_sub_009f6d72(unsigned char*,int,const unsigned char*,const unsigned char*,int);
alignas(16) static unsigned char expected[4096], actual[4096], top[16], left[4096];
static unsigned rng = 0x6c0f6d72u;
static unsigned random_byte() { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng & 255; }
static int run_tests() {
 const int ds[8]={16,32,48,64,-16,-32,-48,-64};
 const int ls[8]={1,2,3,16,-1,-2,-3,-16};
 Fn originals[2]={reinterpret_cast<Fn>(const_cast<unsigned char*>(ref_009f6c0f)),reinterpret_cast<Fn>(const_cast<unsigned char*>(ref_009f6d72))};
 Fn candidates[2]={t6_sub_009f6c0f,t6_sub_009f6d72};
 for(int f=0;f<2;++f) for(int d=0;d<8;++d) for(int l=0;l<8;++l) for(int p=0;p<16;++p) {
  for(int i=0;i<4096;++i) {
   expected[i]=actual[i]=static_cast<unsigned char>(0xa5u ^ i);
   left[i]=static_cast<unsigned char>(p==0?0:p==1?255:p==2?((i&1)?255:0):random_byte());
  }
  for(int i=0;i<16;++i) top[i]=static_cast<unsigned char>(p==0?0:p==1?255:p==2?((i&1)?0:255):random_byte());
  originals[f](expected+2048,ds[d],top,left+2048,ls[l]);
  candidates[f](actual+2048,ds[d],top,left+2048,ls[l]);
  for(int i=0;i<4096;++i) if(expected[i]!=actual[i]) return f+1;
 }
 return 0;
}
extern "C" [[noreturn]] void _start() {
 int status=run_tests();
 asm volatile("int $0x80" : : "a"(1), "b"(status) : "memory");
 __builtin_unreachable();
}
