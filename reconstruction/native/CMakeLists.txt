cmake_minimum_required(VERSION 3.31)
project(t6_native_recomp LANGUAGES CXX)

# C++26 is the selected source target. It is not evidence of retail ABI parity.
set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Deliberately only admit reviewed, self-contained units. Generated Ghidra C
# is not link-ready source and must never be globbed into this target.
add_library(t6_native_recovered_leafs STATIC
    ../current_client/simd_candidates_v1.cpp
)

if(MSVC)
    target_compile_options(t6_native_recovered_leafs PRIVATE /W4)
else()
    target_compile_options(t6_native_recovered_leafs PRIVATE -Wall -Wextra -Wpedantic)
endif()

include(CTest)
if(BUILD_TESTING)
    add_executable(t6_native_leaf_tests tests/simd_candidates_v1_test.cpp)
    target_link_libraries(t6_native_leaf_tests PRIVATE t6_native_recovered_leafs)
    add_test(NAME t6_native_leaf_invariants COMMAND t6_native_leaf_tests)
endif()
