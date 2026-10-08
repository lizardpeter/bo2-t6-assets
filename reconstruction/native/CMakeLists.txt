cmake_minimum_required(VERSION 3.31)
project(t6_native_recomp LANGUAGES CXX)

# C++26 is the selected source target. It is not evidence of retail ABI parity.
# GCC/Clang have an explicit C++26 dialect selector. MSVC 19.51 supports
# /std:c++latest, but CMake 4.4 cannot enable the named CXX26 feature for MSVC.
# Use a CMake-known baseline and explicitly select MSVC's latest C++ dialect.
# Never silently downgrade compiler modes on either target.
if(MSVC)
    set(CMAKE_CXX_STANDARD 23)
    add_compile_options(/std:c++latest)
else()
    set(CMAKE_CXX_STANDARD 26)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Deliberately only admit reviewed, self-contained units. Generated Ghidra C
# is not link-ready source and must never be globbed into this target.
add_library(t6_native_recovered_leafs STATIC
    ../current_client/simd_candidates_v1.cpp
    current_client/stream_buffer_candidates_v1.cpp
    current_client/pdb_exact_game_candidates_v1.cpp
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

    # Links a second recovered T6 translation unit into a real executable.
    # Its unimplemented retail copy helper is supplied ONLY by the test target.
    add_executable(t6_native_stream_tests tests/stream_buffer_candidates_v1_test.cpp)
    target_link_libraries(t6_native_stream_tests PRIVATE t6_native_recovered_leafs)
    add_test(NAME t6_native_stream_state_machine COMMAND t6_native_stream_tests)

    add_executable(t6_native_pdb_game_tests tests/pdb_exact_game_candidates_v1_test.cpp)
    target_link_libraries(t6_native_pdb_game_tests PRIVATE t6_native_recovered_leafs)
    add_test(NAME t6_native_pdb_game_source_invariants COMMAND t6_native_pdb_game_tests)
endif()
