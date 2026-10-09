#include <cstdint>
using uint=std::uint32_t; using ulong=std::uint32_t;
using uchar=std::uint8_t; using byte=std::uint8_t;
using ushort=std::uint16_t;

static std::int32_t candidate_0040de00(std::int32_t param_1, std::int32_t param_2) {
  if (param_1 < param_2) {
    param_1 = param_2;
  }
  return param_1;
}
extern "C" std::uint32_t x86check_0040de00(std::int32_t param_1, std::int32_t param_2) {return static_cast<std::uint32_t>(candidate_0040de00(param_1, param_2));}

static std::int32_t candidate_0040de20(std::int32_t param_1, std::int32_t param_2) {
  if (param_1 <= param_2) {
    param_2 = param_1;
  }
  return param_2;
}
extern "C" std::uint32_t x86check_0040de20(std::int32_t param_1, std::int32_t param_2) {return static_cast<std::uint32_t>(candidate_0040de20(param_1, param_2));}

static bool candidate_0045bf40(std::int32_t param_1) {
  if ((param_1 != 0) && (param_1 != 3)) {
    return false;
  }
  return true;
}
extern "C" std::uint32_t x86check_0045bf40(std::int32_t param_1) {return static_cast<std::uint32_t>(candidate_0045bf40(param_1));}

static std::uint32_t candidate_00552f80() {
  return 0x13e0;
}
extern "C" std::uint32_t x86check_00552f80() {return static_cast<std::uint32_t>(candidate_00552f80());}

static bool candidate_005623d0(std::uint32_t param_1) {
  return true;
}
extern "C" std::uint32_t x86check_005623d0(std::uint32_t param_1) {return static_cast<std::uint32_t>(candidate_005623d0(param_1));}

static std::int32_t candidate_005e7ae0() {
  return 0x5808;
}
extern "C" std::uint32_t x86check_005e7ae0() {return static_cast<std::uint32_t>(candidate_005e7ae0());}

static std::int32_t candidate_005e7af0() {
  return 0x2720;
}
extern "C" std::uint32_t x86check_005e7af0() {return static_cast<std::uint32_t>(candidate_005e7af0());}

static bool candidate_006440c0(std::int32_t param_1) {
  return param_1 == 1;
}
extern "C" std::uint32_t x86check_006440c0(std::int32_t param_1) {return static_cast<std::uint32_t>(candidate_006440c0(param_1));}

static bool candidate_006440d0(std::int32_t param_1) {
  if (((param_1 != 0) && (param_1 != 3)) && (param_1 != 1)) {
    return false;
  }
  return true;
}
extern "C" std::uint32_t x86check_006440d0(std::int32_t param_1) {return static_cast<std::uint32_t>(candidate_006440d0(param_1));}

static bool candidate_006440f0(std::int32_t param_1) {
  return param_1 != 1;
}
extern "C" std::uint32_t x86check_006440f0(std::int32_t param_1) {return static_cast<std::uint32_t>(candidate_006440f0(param_1));}

static std::int32_t candidate_006c1930() {
  return 0x12;
}
extern "C" std::uint32_t x86check_006c1930() {return static_cast<std::uint32_t>(candidate_006c1930());}

static std::int32_t candidate_006c1a40() {
  return 10;
}
extern "C" std::uint32_t x86check_006c1a40() {return static_cast<std::uint32_t>(candidate_006c1a40());}

static std::uint8_t candidate_0078db60(std::uint8_t param_1) {
  byte bVar1;
  
  bVar1 = param_1 - 0x30;
  if (9 < bVar1) {
    bVar1 = 7;
  }
  return bVar1;
}
extern "C" std::uint32_t x86check_0078db60(std::uint8_t param_1) {return static_cast<std::uint32_t>(candidate_0078db60(param_1));}

static std::int16_t candidate_0078dce0(std::int16_t param_1) {
  return param_1;
}
extern "C" std::uint32_t x86check_0078dce0(std::int16_t param_1) {return static_cast<std::uint32_t>(candidate_0078dce0(param_1));}

static bool candidate_0078df60(std::int32_t param_1) {
  if ((((param_1 < 0x61) || (0x7a < param_1)) && (0x19 < param_1 - 0x41U)) && (9 < param_1 - 0x30U))
  {
    return false;
  }
  return true;
}
extern "C" std::uint32_t x86check_0078df60(std::int32_t param_1) {return static_cast<std::uint32_t>(candidate_0078df60(param_1));}

static bool candidate_0078df90(std::int32_t param_1) {
  if ((((param_1 < 0x61) || (0x7a < param_1)) && (0x19 < param_1 - 0x41U)) &&
     (((9 < param_1 - 0x30U && (param_1 != 0x5f)) && (param_1 != 0x2d)))) {
    return false;
  }
  return true;
}
extern "C" std::uint32_t x86check_0078df90(std::int32_t param_1) {return static_cast<std::uint32_t>(candidate_0078df90(param_1));}

static char candidate_0078e720(char param_1) {
  if (param_1 == -0x6e) {
    param_1 = '\'';
  }
  return param_1;
}
extern "C" std::uint32_t x86check_0078e720(char param_1) {return static_cast<std::uint32_t>(candidate_0078e720(param_1));}

static bool candidate_007910b0(std::int32_t param_1) {
  if ((param_1 != 0x15) && ((param_1 < 0x18 || (0x1b < param_1)))) {
    return false;
  }
  return true;
}
extern "C" std::uint32_t x86check_007910b0(std::int32_t param_1) {return static_cast<std::uint32_t>(candidate_007910b0(param_1));}

static bool candidate_0080bbd0() {
  return false;
}
extern "C" std::uint32_t x86check_0080bbd0() {return static_cast<std::uint32_t>(candidate_0080bbd0());}

static std::int32_t candidate_008d2960() {
  return 0x19;
}
extern "C" std::uint32_t x86check_008d2960() {return static_cast<std::uint32_t>(candidate_008d2960());}

static std::int32_t candidate_008e6790() {
  return 0x20000;
}
extern "C" std::uint32_t x86check_008e6790() {return static_cast<std::uint32_t>(candidate_008e6790());}

static std::int32_t candidate_0090c720() {
  return 0x80000;
}
extern "C" std::uint32_t x86check_0090c720() {return static_cast<std::uint32_t>(candidate_0090c720());}

static std::uint32_t candidate_0097fbf0() {
  return 0x30a5f3;
}
extern "C" std::uint32_t x86check_0097fbf0() {return static_cast<std::uint32_t>(candidate_0097fbf0());}

static std::int32_t candidate_00982f90() {
  return 1;
}
extern "C" std::uint32_t x86check_00982f90() {return static_cast<std::uint32_t>(candidate_00982f90());}

static std::int32_t candidate_00983a90() {
  return 0x10400;
}
extern "C" std::uint32_t x86check_00983a90() {return static_cast<std::uint32_t>(candidate_00983a90());}

static std::int32_t candidate_00984f00() {
  return 0;
}
extern "C" std::uint32_t x86check_00984f00() {return static_cast<std::uint32_t>(candidate_00984f00());}

static std::uint32_t candidate_009ac150(std::uint32_t param_1) {
  return param_1;
}
extern "C" std::uint32_t x86check_009ac150(std::uint32_t param_1) {return static_cast<std::uint32_t>(candidate_009ac150(param_1));}

static std::int32_t candidate_009d5f90() {
  return 0x28;
}
extern "C" std::uint32_t x86check_009d5f90() {return static_cast<std::uint32_t>(candidate_009d5f90());}

static std::uint16_t candidate_00a29ab0() {
  return 0xa9;
}
extern "C" std::uint32_t x86check_00a29ab0() {return static_cast<std::uint32_t>(candidate_00a29ab0());}

static std::uint16_t candidate_00a29ac0() {
  return 0xaa;
}
extern "C" std::uint32_t x86check_00a29ac0() {return static_cast<std::uint32_t>(candidate_00a29ac0());}

static std::uint16_t candidate_00a29ad0() {
  return 0xab;
}
extern "C" std::uint32_t x86check_00a29ad0() {return static_cast<std::uint32_t>(candidate_00a29ad0());}

static std::uint16_t candidate_00a29ae0() {
  return 0xac;
}
extern "C" std::uint32_t x86check_00a29ae0() {return static_cast<std::uint32_t>(candidate_00a29ae0());}

static std::uint16_t candidate_00a29af0() {
  return 0xa5;
}
extern "C" std::uint32_t x86check_00a29af0() {return static_cast<std::uint32_t>(candidate_00a29af0());}

static std::uint16_t candidate_00a29b00() {
  return 0xa6;
}
extern "C" std::uint32_t x86check_00a29b00() {return static_cast<std::uint32_t>(candidate_00a29b00());}
