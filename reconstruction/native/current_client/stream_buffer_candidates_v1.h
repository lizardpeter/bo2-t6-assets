#pragma once
#include <cstdint>

// Exact-build current-client addresses, not source-level semantic names.
// Signatures are structural candidates, not established retail ABI declarations.
extern "C" void* t6_sub_009a7d00(void* self, std::uint32_t start_plus_four,
                                   std::uint32_t end, std::uint32_t tag);
extern "C" bool t6_sub_009a7d60(void* self);

// 0x00A72BF0 is a REQUIRED unresolved imported retail dependency.
// The test harness supplies a fake implementation solely for deterministic tests.
// No production implementation, functional equivalence, or import ABI is claimed.
extern "C" void t6_sub_00a72bf0(void* dest, const void* virtual_source,
                                  std::uint32_t size);
