// Native reference harness for the golden tests (see tests/test_wasm_runtime.py).
//
//   prg32-core-harness cartridge.prg32 FRAMES EVERY [frame.ppm]
//
// Runs FRAMES frames with the same scripted input as tools/wasm_harness.mjs and prints
// prg32_state_json() after every EVERY frames, one JSON object per line. With a fourth
// argument it also writes the last frame as a PPM image, in the same format as
// `prg32qt-headless --dump-ppm`, so the two can be compared byte for byte.
//
//   prg32-core-harness --debug cartridge.prg32 COMMAND...
//
// Runs a debugger script instead (the same as `node tools/wasm_harness.mjs ... --debug`) and
// prints one JSON line per command. Commands (N defaults to 1; TARGET is init, update, draw,
// update+OFFSET or a 0x address):
//   step:N  stepi:N  over:N  out:N  continue:N  frame:N  break:TARGET  unbreak:TARGET
//   slice:BUDGET (one browser playback slice: run at most BUDGET instructions, no resume)
//   disasm:TARGET:COUNT  state (prints prg32_state_json, as the frame-by-frame mode does)

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

extern "C" {
int prg32_load(const uint8_t* data, uint32_t size);
const char* prg32_last_error();
int prg32_frame(uint32_t input);
const char* prg32_state_json();
const uint16_t* prg32_framebuffer();
int prg32_width();
int prg32_height();
int prg32_debug_step(uint32_t input);
int prg32_debug_step_instruction(uint32_t input);
int prg32_debug_run(uint32_t input, uint32_t budget, int mode, int stopAtFrameEnd);
void prg32_debug_resume();
int prg32_breakpoint(uint32_t address, int enabled);
uint32_t prg32_entry(int which);
const char* prg32_disassemble(uint32_t address, uint32_t count);
const char* prg32_debug_state_json();
}

// Same conversion as PRG32-QT's src/core/headless.cpp.
static void writePpm(const char* path) {
    std::ofstream output(path, std::ios::binary);
    output << "P6\n" << prg32_width() << " " << prg32_height() << "\n255\n";
    const uint16_t* pixels = prg32_framebuffer();
    for (int index = 0; index < prg32_width() * prg32_height(); ++index) {
        const uint16_t pixel = pixels[index];
        const char rgb[3] = {char(((pixel >> 11) & 31) * 255 / 31), char(((pixel >> 5) & 63) * 255 / 63),
                             char((pixel & 31) * 255 / 31)};
        output.write(rgb, 3);
    }
}

// Press each PRG32 button for 30 frames in turn, like prg32qt-headless --verify-media.
static uint32_t scriptedInput(int frame) {
    static const uint32_t sequence[] = {0, 1, 2, 4, 8, 16, 32, 64, 17, 34};
    return sequence[(frame / 30) % 10];
}

// TARGET of a debugger command: init, update, draw, update+OFFSET or a number (0x... allowed).
static uint32_t target(const std::string& text) {
    const auto plus = text.find('+');
    const std::string name = text.substr(0, plus);
    const uint32_t offset = plus == std::string::npos ? 0 : uint32_t(std::stoul(text.substr(plus + 1), nullptr, 0));
    if (name == "init" || name == "update" || name == "draw")
        return prg32_entry(name == "init" ? 0 : name == "draw" ? 2 : 1) + offset;
    return uint32_t(std::stoul(name, nullptr, 0)) + offset;
}

static int runDebugScript(int count, char** commands) {
    for (int index = 0; index < count; ++index) {
        const std::string command = commands[index];
        const auto colon = command.find(':');
        const std::string verb = command.substr(0, colon), argument = colon == std::string::npos ? "" : command.substr(colon + 1);
        int result = 0;
        if (verb == "state") {
            std::printf("{\"command\":\"state\",\"state\":%s}\n", prg32_state_json());
            continue;
        }
        if (verb == "slice")
            result = prg32_debug_run(0, uint32_t(std::stoul(argument)), 0, 1);
        else if (verb == "break" || verb == "unbreak")
            result = prg32_breakpoint(target(argument), verb == "break");
        else if (verb == "disasm") {
            const auto second = argument.find(':');
            std::printf("{\"command\":\"%s\",\"disassembly\":%s}\n", command.c_str(),
                        prg32_disassemble(target(argument.substr(0, second)), uint32_t(std::stoul(argument.substr(second + 1)))));
            continue;
        } else {
            const int times = argument.empty() ? 1 : std::stoi(argument);
            for (int time = 0; time < times; ++time) {
                if (verb == "step")
                    result = prg32_debug_step(0);
                else if (verb == "stepi")
                    result = prg32_debug_step_instruction(0);
                else if (verb == "over" || verb == "out" || verb == "continue" || verb == "frame") {
                    if (verb == "continue" || verb == "frame")
                        prg32_debug_resume(); // the debugger's Resume / Step frame button
                    result = prg32_debug_run(0, 20000000, verb == "over" ? 1 : verb == "out" ? 2 : 0, verb == "frame");
                } else {
                    std::fprintf(stderr, "unknown command %s\n", command.c_str());
                    return 2;
                }
                if (result < 0 || (verb.rfind("step", 0) == 0 && result == 0))
                    break;
            }
        }
        std::printf("{\"command\":\"%s\",\"result\":%d,\"state\":%s}\n", command.c_str(), result, prg32_debug_state_json());
    }
    return 0;
}

int main(int argc, char** argv) {
    const bool debug = argc > 1 && std::string(argv[1]) == "--debug";
    if (debug) {
        ++argv;
        --argc;
    }
    if (argc < (debug ? 2 : 4)) {
        std::fprintf(stderr, "usage: prg32-core-harness cartridge.prg32 FRAMES EVERY | --debug cartridge.prg32 COMMAND...\n");
        return 2;
    }
    std::ifstream file(argv[1], std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)), {});
    if (!prg32_load(bytes.data(), uint32_t(bytes.size()))) {
        std::fprintf(stderr, "load: %s\n", prg32_last_error());
        return 3;
    }
    if (debug)
        return runDebugScript(argc - 2, argv + 2);
    const int frames = std::stoi(argv[2]);
    const int every = std::stoi(argv[3]);
    std::printf("%s\n", prg32_state_json());
    for (int frame = 0; frame < frames; ++frame) {
        if (!prg32_frame(scriptedInput(frame))) {
            std::fprintf(stderr, "frame %d: %s\n", frame, prg32_last_error());
            return 4;
        }
        if ((frame + 1) % every == 0)
            std::printf("%s\n", prg32_state_json());
    }
    if (argc > 4)
        writePpm(argv[4]);
    return 0;
}
