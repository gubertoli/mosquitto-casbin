cmake_minimum_required(VERSION 3.19)
project(mosquitto-casbin)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")
endif()

find_package(OpenSSL REQUIRED)

find_path(MOSQUITTO_INCLUDE_DIR
          NAMES mosquitto_broker.h
          HINTS "C:/mosquitto/devel" "C:/mosquitto" "/usr/include" "/usr/local/include")

find_library(MOSQUITTO_LIB NAMES mosquitto_broker mosquitto 
          HINTS "C:/mosquitto" "C:/mosquitto/devel" "/usr/lib" "/usr/local/lib" "/usr/lib/x86_64-linux-gnu")


if(NOT MOSQUITTO_INCLUDE_DIR OR NOT MOSQUITTO_LIB)
    message(FATAL_ERROR "Mosquitto headers or library not found! Check your installation paths.")
endif()

include(FetchContent)
FetchContent_Declare(
    casbin
    GIT_REPOSITORY https://github.com/casbin/casbin-cpp.git
    GIT_TAG v1.67.0
)

set(CASBIN_BUILD_TEST OFF CACHE BOOL "" FORCE)
set(CASBIN_BUILD_BENCHMARK OFF CACHE BOOL "" FORCE)
set(CASBIN_BUILD_BINDINGS OFF CACHE BOOL "" FORCE)
set(CASBIN_BUILD_PYTHON_BINDINGS OFF CACHE BOOL "" FORCE)

FetchContent_MakeAvailable(casbin)

add_library(mosquitto-casbin SHARED src/mosquitto-casbin.cpp)

set_target_properties(mosquitto-casbin PROPERTIES PREFIX "")

target_include_directories(mosquitto-casbin PRIVATE 
    "${casbin_SOURCE_DIR}/include"
    "${MOSQUITTO_INCLUDE_DIR}"
)

target_link_libraries(mosquitto-casbin PRIVATE
    casbin
    OpenSSL::SSL
    OpenSSL::Crypto
    "${MOSQUITTO_LIB}"
)

target_compile_options(mosquitto-casbin PRIVATE
    $<$<CXX_COMPILER_ID:MSVC>:/W4 /permissive->
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
)

install(TARGETS mosquitto-casbin DESTINATION lib)

enable_testing()
find_package(Python3 REQUIRED COMPONENTS Interpreter)

find_program(MOSQUITTO_EXE mosquitto HINTS "C:/mosquitto" "/usr/bin" "/usr/local/bin")
if(MOSQUITTO_EXE)
    set(PLUGIN_PATH "$<TARGET_FILE:mosquitto-casbin>")
    set(MODEL_PATH "${CMAKE_SOURCE_DIR}/tests/casbin/model.conf")
    set(POLICY_PATH "${CMAKE_SOURCE_DIR}/tests/casbin/policy.csv")

    configure_file(tests/mosquitto.conf.in ${CMAKE_BINARY_DIR}/tests/mosquitto.conf @ONLY)
    
    file(GENERATE 
        OUTPUT ${CMAKE_BINARY_DIR}/tests/mosquitto_functional_$<CONFIG>.conf
        INPUT ${CMAKE_BINARY_DIR}/tests/mosquitto.conf
    )

    add_test(
        NAME FunctionalTest
        COMMAND ${Python3_EXECUTABLE} -u
                "${CMAKE_SOURCE_DIR}/tests/functional_test.py"
                "${MOSQUITTO_EXE}"
                "${CMAKE_BINARY_DIR}/tests/mosquitto_functional_$<CONFIG>.conf"
    )

    add_test(
        NAME PerformanceBenchmark
        COMMAND ${Python3_EXECUTABLE} -u
                "${CMAKE_SOURCE_DIR}/tests/performance_test.py"
                "${MOSQUITTO_EXE}"
                "${CMAKE_BINARY_DIR}/tests/mosquitto_functional_$<CONFIG>.conf"
    )
else()
    message(WARNING "Mosquitto broker executable not found. Functional tests skipped.")
endif()