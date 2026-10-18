# Builds the PRG32 core for the browser (Emscripten) and the native golden-test harness.
#
#   Native:  cmake -S wasm -B build/wasm-native -DPRG32QT_DIR=../PRG32-QT && cmake --build build/wasm-native
#   Browser: emcmake cmake -S wasm -B build/wasm -DPRG32QT_DIR=../PRG32-QT && cmake --build build/wasm
#            (tools/build_wasm.py does this and copies the result to static/wasm/)
#
# The core sources are compiled from a PRG32-QT checkout; nothing is copied into this repository.
cmake_minimum_required(VERSION 3.20)
project(prg32_core_api CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(PRG32QT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../PRG32-QT" CACHE PATH "PRG32-QT checkout")
get_filename_component(PRG32QT_DIR "${PRG32QT_DIR}" ABSOLUTE)
if(NOT EXISTS "${PRG32QT_DIR}/src/core/Runtime.cpp")
  message(FATAL_ERROR "PRG32QT_DIR does not contain src/core/Runtime.cpp: ${PRG32QT_DIR}")
endif()

# The Qt-free core, exactly the files of PRG32-QT's prg32qt_core library.
set(PRG32_CORE_SOURCES
  ${PRG32QT_DIR}/src/core/Audio.cpp
  ${PRG32QT_DIR}/src/core/Cartridge.cpp
  ${PRG32QT_DIR}/src/core/Framebuffer.cpp
  ${PRG32QT_DIR}/src/core/PerformanceTiming.cpp
  ${PRG32QT_DIR}/src/core/RiscVDisassembler.cpp
  ${PRG32QT_DIR}/src/core/Rv32Cpu.cpp
  ${PRG32QT_DIR}/src/core/Runtime.cpp)

# No host-specific floating-point contraction, so native and WebAssembly round the same way.
set(PRG32_DETERMINISM_FLAGS -ffp-contract=off)

if(EMSCRIPTEN)
  add_executable(prg32-core prg32_core_api.cpp ${PRG32_CORE_SOURCES})
  target_include_directories(prg32-core PRIVATE ${PRG32QT_DIR}/src/core)
  target_compile_definitions(prg32-core PRIVATE PRG32QT_VERSION="wasm")
  target_compile_options(prg32-core PRIVATE -O2 ${PRG32_DETERMINISM_FLAGS})
  set_target_properties(prg32-core PROPERTIES SUFFIX ".js")
  target_link_options(prg32-core PRIVATE
    -O2
    -sMODULARIZE=1
    -sEXPORT_NAME=createPrg32Core
    -sENVIRONMENT=web,worker,node
    -sALLOW_MEMORY_GROWTH=1
    -sINITIAL_MEMORY=33554432
    -sMAXIMUM_MEMORY=268435456
    -sFILESYSTEM=0
    -sEXPORTED_RUNTIME_METHODS=ccall,cwrap,UTF8ToString,HEAPU8,HEAPU16,HEAP32,HEAPF32
    -sEXPORTED_FUNCTIONS=_malloc,_free)
else()
  add_executable(prg32-core-harness harness_main.cpp prg32_core_api.cpp ${PRG32_CORE_SOURCES})
  target_include_directories(prg32-core-harness PRIVATE ${PRG32QT_DIR}/src/core)
  target_compile_definitions(prg32-core-harness PRIVATE PRG32QT_VERSION="native")
  target_compile_options(prg32-core-harness PRIVATE -O2 ${PRG32_DETERMINISM_FLAGS})
endif()
