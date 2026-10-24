# Builds the PRG32 core for the browser (Emscripten) and the native golden-test harness.
#
#   Native:  cmake -S wasm -B build/wasm-native -DPRG32QT_DIR=../PRG32-QT -DPRG32_DIR=../PRG32 && cmake --build build/wasm-native
#   Browser: emcmake cmake -S wasm -B build/wasm -DPRG32QT_DIR=../PRG32-QT -DPRG32_DIR=../PRG32 && cmake --build build/wasm
#            (tools/build_wasm.py does this and copies the result to static/wasm/)
#
# The sources are compiled from checkouts; nothing is copied into this repository:
# - PRG32-QT's Qt-free core (the RV32IMAC interpreter and the PRG32 ABI);
# - the PRG32 firmware's audio engine (components/prg32_audio), so the browser sounds
#   exactly like the console (ADR-0021). wasm/audio holds only the kit's port: build
#   settings, the FreeRTOS/timer stand-ins and the output queue.
cmake_minimum_required(VERSION 3.20)
project(prg32_core_api C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)
set(PRG32QT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../PRG32-QT" CACHE PATH "PRG32-QT checkout")
set(PRG32_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../PRG32" CACHE PATH "PRG32 SDK checkout")
get_filename_component(PRG32QT_DIR "${PRG32QT_DIR}" ABSOLUTE)
get_filename_component(PRG32_DIR "${PRG32_DIR}" ABSOLUTE)
if(NOT EXISTS "${PRG32QT_DIR}/src/core/Runtime.cpp")
  message(FATAL_ERROR "PRG32QT_DIR does not contain src/core/Runtime.cpp: ${PRG32QT_DIR}")
endif()
set(PRG32_AUDIO_DIR "${PRG32_DIR}/components/prg32_audio")
if(NOT EXISTS "${PRG32_AUDIO_DIR}/audio_synth.c")
  message(FATAL_ERROR "PRG32_DIR does not contain components/prg32_audio: ${PRG32_DIR}")
endif()

# The core is used as PRG32-QT has it, with one addition for the kit: a pair of hooks
# around every host call, so the kit's audio engine sees the audio calls (and their
# arguments) while PRG32-QT's own handling, timing and state stay exactly as they are.
# The core is copied into the build folder and the hook is added to that copy; if
# PRG32-QT changes the lines it is anchored to, the build stops here and says so.
set(KIT_CORE "${CMAKE_BINARY_DIR}/kit-core")
file(GLOB PRG32QT_CORE_FILES "${PRG32QT_DIR}/src/core/*.h" "${PRG32QT_DIR}/src/core/*.cpp")
file(MAKE_DIRECTORY "${KIT_CORE}")
foreach(source ${PRG32QT_CORE_FILES})
  get_filename_component(name "${source}" NAME)
  configure_file("${source}" "${KIT_CORE}/${name}" COPYONLY)
endforeach()

function(kit_patch file anchor replacement)
  file(READ "${KIT_CORE}/${file}" text)
  string(FIND "${text}" "${anchor}" found)
  if(found EQUAL -1)
    message(FATAL_ERROR "PRG32-QT changed ${file}: the kit's host-call hook cannot find\n${anchor}\n"
                        "Update wasm/CMakeLists.txt (ADR-0021).")
  endif()
  string(REPLACE "${anchor}" "${replacement}" text "${text}")
  file(WRITE "${KIT_CORE}/${file}" "${text}")
endfunction()

kit_patch(Runtime.h "    void hostCall(uint32_t);\n"
  "    void hostCall(uint32_t);\n    void hostCallCore(uint32_t);\n")
kit_patch(Runtime.h "    void setLEDCallback(std::function<void(RGBState)> cb) {"
  "    /** Construction Kit: called before and after every host call (ADR-0021). */\n    void setHostHooks(std::function<void(uint32_t)> before, std::function<void(uint32_t)> after) {\n        hostBefore_ = std::move(before);\n        hostAfter_ = std::move(after);\n    }\n    /** Construction Kit: the value a host call returns in a0. */\n    void setHostResult(uint32_t value) {\n        cpu_.setReg(10, value);\n    }\n    void setLEDCallback(std::function<void(RGBState)> cb) {")
kit_patch(Runtime.h "    std::function<void(RGBState)> ledCallback_;\n"
  "    std::function<void(RGBState)> ledCallback_;\n    std::function<void(uint32_t)> hostBefore_, hostAfter_;\n")
kit_patch(Runtime.cpp "void Runtime::hostCall(uint32_t i) {\n"
  "void Runtime::hostCall(uint32_t i) {\n    if (hostBefore_)\n        hostBefore_(i);\n    hostCallCore(i);\n    if (hostAfter_)\n        hostAfter_(i);\n}\nvoid Runtime::hostCallCore(uint32_t i) {\n")

# The Qt-free core, exactly the files of PRG32-QT's prg32qt_core library (from the copy).
set(PRG32_CORE_SOURCES
  ${KIT_CORE}/Audio.cpp
  ${KIT_CORE}/Cartridge.cpp
  ${KIT_CORE}/Framebuffer.cpp
  ${KIT_CORE}/PerformanceTiming.cpp
  ${KIT_CORE}/RiscVDisassembler.cpp
  ${KIT_CORE}/Rv32Cpu.cpp
  ${KIT_CORE}/Runtime.cpp)

# The PRG32 firmware's audio engine, unchanged, and the kit's port of it.
set(PRG32_AUDIO_SOURCES
  ${PRG32_AUDIO_DIR}/audio.c
  ${PRG32_AUDIO_DIR}/audio_assets.c
  ${PRG32_AUDIO_DIR}/audio_mixer.c
  ${PRG32_AUDIO_DIR}/audio_synth.c
  ${PRG32_AUDIO_DIR}/audio_tracker.c
  ${CMAKE_CURRENT_SOURCE_DIR}/audio/audio_port.c)
add_library(prg32_audio_engine STATIC ${PRG32_AUDIO_SOURCES})
target_include_directories(prg32_audio_engine
  PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/audio/shim ${PRG32_AUDIO_DIR}
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/audio ${PRG32_AUDIO_DIR}/include)
target_compile_options(prg32_audio_engine PRIVATE -O2)

# No host-specific floating-point contraction, so native and WebAssembly round the same way.
set(PRG32_DETERMINISM_FLAGS -ffp-contract=off)

if(EMSCRIPTEN)
  add_executable(prg32-core prg32_core_api.cpp ${PRG32_CORE_SOURCES})
  target_include_directories(prg32-core PRIVATE ${KIT_CORE})
  target_link_libraries(prg32-core PRIVATE prg32_audio_engine)
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
    -sEXPORTED_RUNTIME_METHODS=ccall,cwrap,UTF8ToString,HEAPU8,HEAPU16,HEAP16,HEAP32,HEAPF32
    -sEXPORTED_FUNCTIONS=_malloc,_free)
else()
  add_executable(prg32-core-harness harness_main.cpp prg32_core_api.cpp ${PRG32_CORE_SOURCES})
  target_include_directories(prg32-core-harness PRIVATE ${KIT_CORE})
  target_link_libraries(prg32-core-harness PRIVATE prg32_audio_engine)
  target_compile_definitions(prg32-core-harness PRIVATE PRG32QT_VERSION="native")
  target_compile_options(prg32-core-harness PRIVATE -O2 ${PRG32_DETERMINISM_FLAGS})
endif()
