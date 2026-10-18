// Native reference harness for the golden tests (see tests/test_wasm_runtime.py).
//
//   prg32-core-harness cartridge.prg32 FRAMES EVERY [frame.ppm]
//
// Runs FRAMES frames with the same scripted input as tools/wasm_harness.mjs and prints
// prg32_state_json() after every EVERY frames, one JSON object per line. With a fourth
// argument it also writes the last frame as a PPM image, in the same format as
// `prg32qt-headless --dump-ppm`, so the two can be compared byte for byte.

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

int main(int argc, char** argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: prg32-core-harness cartridge.prg32 FRAMES EVERY\n");
        return 2;
    }
    std::ifstream file(argv[1], std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)), {});
    if (!prg32_load(bytes.data(), uint32_t(bytes.size()))) {
        std::fprintf(stderr, "load: %s\n", prg32_last_error());
        return 3;
    }
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
