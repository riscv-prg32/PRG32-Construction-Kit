// A small C interface over the Qt-free PRG32-QT core (prg32::Cartridge + prg32::Runtime).
//
// The same file is compiled twice:
//   - with Emscripten into static/wasm/prg32-core.{js,wasm}, so a browser runs real
//     PRG32 cartridges: the RISC-V guest is interpreted inside WebAssembly;
//   - natively into prg32-core-harness, the reference used by the golden tests.
// Both builds expose exactly the same functions, so the tests can compare them frame by frame.
//
// The core is not copied into this repository: wasm/CMakeLists.txt compiles PRG32-QT's
// src/core files from a checkout (see docs/wasm_runtime.md and docs/adr/0003).

#include "Cartridge.h"
#include "Runtime.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#define PRG32_EXPORT extern "C" EMSCRIPTEN_KEEPALIVE
#else
#define PRG32_EXPORT extern "C"
#endif

namespace {

// One audio call made by the cartridge, for the browser to play.
// kind: 1 configure, 2 tone, 3 noteOn, 4 synthNoteOn, 5 noteOff, 6 playPCM, 7 stop, 8 stopAll,
//       9 masterVolume, 10 channelVolume, 11 channelPan.
struct AudioRecord {
    int32_t kind;
    int32_t channel;
    int32_t a;      // tone: duration ms; note calls: MIDI note; pcm: sample start offset in the PCM pool
    int32_t b;      // pcm: number of samples; volume calls: volume
    float f0;       // tone: frequency Hz; pcm: playback rate (Hz)
    float f1;       // pcm: base frequency
    int32_t volume; // 0..255
    int32_t pan;    // -128..127
    int32_t loopStart;
    int32_t loopEnd;
    int32_t waveform;
    int32_t reserved;
};
static_assert(sizeof(AudioRecord) == 48, "the browser reads AudioRecord as 12 x 32-bit values");

constexpr size_t MaxAudioRecords = 512;
constexpr size_t MaxPcmSamples = 1 << 20;

// Collects audio calls between two drains instead of playing them (the browser plays them).
class QueueAudioSink final : public prg32::AudioSink {
  public:
    void configure(int rate) override {
        push({1, 0, rate});
    }
    void shutdown() override {
    }
    void tone(double frequency, int durationMs, uint8_t volume) override {
        AudioRecord record{2, 0, durationMs};
        record.f0 = float(frequency);
        record.volume = volume;
        push(record);
    }
    void noteOn(int channel, int note, uint8_t volume, int8_t pan) override {
        AudioRecord record{3, channel, note};
        record.volume = volume;
        record.pan = pan;
        push(record);
    }
    void synthNoteOn(int channel, int note, uint8_t volume, int8_t pan, prg32::SynthParameters synth) override {
        AudioRecord record{4, channel, note};
        record.volume = volume;
        record.pan = pan;
        record.waveform = synth.waveform;
        push(record);
    }
    void noteOff(int channel) override {
        push({5, channel});
    }
    void playPCM(int channel, const std::vector<float>& samples, double rate, double baseFrequency, uint8_t volume,
                 int8_t pan, int loopStart, int loopEnd) override {
        if (pcm.size() + samples.size() > MaxPcmSamples)
            return; // a burst larger than the pool is dropped rather than growing memory without bound
        AudioRecord record{6, channel, int32_t(pcm.size()), int32_t(samples.size())};
        record.f0 = float(rate);
        record.f1 = float(baseFrequency);
        record.volume = volume;
        record.pan = pan;
        record.loopStart = loopStart;
        record.loopEnd = loopEnd;
        pcm.insert(pcm.end(), samples.begin(), samples.end());
        push(record);
    }
    void stop(int channel) override {
        push({7, channel});
    }
    void stopAll() override {
        push({8});
    }
    void setMasterVolume(uint8_t volume) override {
        push({9, 0, 0, volume});
    }
    void setChannelVolume(int channel, uint8_t volume) override {
        push({10, channel, 0, volume});
    }
    void setChannelPan(int channel, int8_t pan) override {
        AudioRecord record{11, channel};
        record.pan = pan;
        push(record);
    }

    std::vector<AudioRecord> records;
    std::vector<float> pcm;
    uint64_t total = 0;
    uint64_t dropped = 0;

  private:
    void push(const AudioRecord& record) {
        ++total;
        if (records.size() >= MaxAudioRecords) {
            ++dropped;
            return;
        }
        records.push_back(record);
    }
};

struct Session {
    prg32::Runtime runtime;
    QueueAudioSink audio;
    std::vector<uint16_t> pixels;
    std::string name;
    std::string metadata;
    uint64_t frames = 0;
};

std::unique_ptr<Session> session;
std::string lastError;
std::string stateText;

uint64_t fnv1a(const std::vector<uint16_t>& pixels) {
    // The same 64-bit FNV-1a hash as prg32qt-headless --verify-media.
    uint64_t hash = 1469598103934665603ull;
    for (uint16_t pixel : pixels) {
        hash ^= pixel;
        hash *= 1099511628211ull;
    }
    return hash;
}

bool fail(const std::string& message) {
    lastError = message;
    return false;
}

} // namespace

/** Load a .prg32 cartridge and run its init function. Returns 1 on success, 0 on error (see prg32_last_error). */
PRG32_EXPORT int prg32_load(const uint8_t* data, uint32_t size) {
    lastError.clear();
    session.reset();
    std::string error;
    auto cartridge = prg32::Cartridge::parse(std::span<const uint8_t>(data, size), error);
    if (!cartridge)
        return fail(error.empty() ? "not a PRG32 cartridge" : error);
    auto next = std::make_unique<Session>();
    next->runtime.setAudioSink(&next->audio);
    if (!next->runtime.load(*cartridge, error) || !next->runtime.init(error))
        return fail(error);
    next->name = cartridge->name();
    next->metadata = cartridge->metadataJson();
    next->pixels = next->runtime.framebuffer().rgb565Pixels();
    session = std::move(next);
    return 1;
}

PRG32_EXPORT const char* prg32_last_error() {
    return lastError.c_str();
}

PRG32_EXPORT int prg32_loaded() {
    return session ? 1 : 0;
}

/** Stop the cartridge and free its memory. */
PRG32_EXPORT void prg32_unload() {
    if (session)
        session->runtime.stop();
    session.reset();
}

/** Run one update + draw with the PRG32 input bit mask. Returns 1 on success, 0 on a guest trap. */
PRG32_EXPORT int prg32_frame(uint32_t input) {
    if (!session)
        return fail("no cartridge is loaded");
    std::string error;
    if (!session->runtime.frame(input, error))
        return fail(error);
    session->pixels = session->runtime.framebuffer().rgb565Pixels();
    ++session->frames;
    return 1;
}

/** Execute exactly one guest RV32IMAC instruction of the current update/draw call (debugger). */
PRG32_EXPORT int prg32_debug_step(uint32_t input) {
    if (!session)
        return fail("no cartridge is loaded");
    std::string error;
    if (!session->runtime.debugStep(input, error))
        return fail(error);
    session->pixels = session->runtime.framebuffer().rgb565Pixels();
    return 1;
}

PRG32_EXPORT int prg32_debug_call_active() {
    return session && session->runtime.debugCallActive() ? 1 : 0;
}

/** 320 x 200 RGB565 pixels, row by row, valid until the next frame. */
PRG32_EXPORT const uint16_t* prg32_framebuffer() {
    return session ? session->pixels.data() : nullptr;
}

PRG32_EXPORT int prg32_width() {
    return prg32::Framebuffer::Width;
}

PRG32_EXPORT int prg32_height() {
    return prg32::Framebuffer::Height;
}

PRG32_EXPORT uint32_t prg32_pc() {
    return session ? session->runtime.programCounter() : 0;
}

PRG32_EXPORT uint32_t prg32_register(uint32_t index) {
    return session ? session->runtime.registerValue(index) : 0;
}

PRG32_EXPORT uint32_t prg32_guest_base() {
    return session ? session->runtime.guestBase() : 0;
}

PRG32_EXPORT uint32_t prg32_guest_size() {
    return session ? uint32_t(session->runtime.guestMemorySize()) : 0;
}

/** Copy up to `length` (at most 4096) guest bytes into `out`; returns how many were copied. */
PRG32_EXPORT uint32_t prg32_read_memory(uint32_t address, uint8_t* out, uint32_t length) {
    if (!session || !out)
        return 0;
    auto bytes = session->runtime.debugMemory(address, length > 4096 ? 4096 : length);
    std::memcpy(out, bytes.data(), bytes.size());
    return uint32_t(bytes.size());
}

/** 0 = accurate ESP32-C6 virtual timing (default, deterministic), 1 = optimal, 2 = unlimited. */
PRG32_EXPORT void prg32_set_performance_mode(int mode) {
    if (session)
        session->runtime.setPerformanceMode(mode == 2   ? prg32::PerformanceMode::Unlimited
                                            : mode == 1 ? prg32::PerformanceMode::Optimal
                                                        : prg32::PerformanceMode::Esp32C6Accurate);
}

PRG32_EXPORT const char* prg32_cartridge_name() {
    return session ? session->name.c_str() : "";
}

PRG32_EXPORT const char* prg32_cartridge_metadata() {
    return session ? session->metadata.c_str() : "";
}

/** Audio calls since the last prg32_audio_clear: count, then a pointer to that many 48-byte records. */
PRG32_EXPORT uint32_t prg32_audio_count() {
    return session ? uint32_t(session->audio.records.size()) : 0;
}

PRG32_EXPORT const void* prg32_audio_records() {
    return session ? session->audio.records.data() : nullptr;
}

PRG32_EXPORT const float* prg32_audio_pcm() {
    return session ? session->audio.pcm.data() : nullptr;
}

PRG32_EXPORT void prg32_audio_clear() {
    if (session) {
        session->audio.records.clear();
        session->audio.pcm.clear();
    }
}

/**
 * The machine state as JSON: frames run, pc, x0..x31, retired instructions, virtual cycles,
 * framebuffer hash and non-black pixel count, audio call count. The golden tests compare this
 * text between the native harness and the WebAssembly build.
 */
PRG32_EXPORT const char* prg32_state_json() {
    if (!session) {
        stateText = "{}";
        return stateText.c_str();
    }
    auto& runtime = session->runtime;
    size_t nonBlack = 0;
    for (uint16_t pixel : session->pixels)
        nonBlack += pixel != 0;
    char buffer[64];
    stateText = "{\"frames\":" + std::to_string(session->frames);
    std::snprintf(buffer, sizeof buffer, "\"0x%08x\"", runtime.programCounter());
    stateText += ",\"pc\":" + std::string(buffer) + ",\"x\":[";
    for (unsigned index = 0; index < 32; ++index) {
        std::snprintf(buffer, sizeof buffer, "%s\"0x%08x\"", index ? "," : "", runtime.registerValue(index));
        stateText += buffer;
    }
    std::snprintf(buffer, sizeof buffer, "\"%016llx\"", static_cast<unsigned long long>(fnv1a(session->pixels)));
    stateText += "],\"retired\":" + std::to_string(runtime.retiredInstructions()) +
                 ",\"cycles\":" + std::to_string(runtime.virtualCycles()) + ",\"framebuffer_fnv1a\":" + buffer +
                 ",\"non_black\":" + std::to_string(nonBlack) +
                 ",\"audio_calls\":" + std::to_string(session->audio.total) + "}";
    return stateText.c_str();
}
