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
//
// Sound (ADR-0021): the audio calls a cartridge makes are played by the PRG32 firmware's
// own audio engine (components/prg32_audio, compiled from a PRG32 checkout), so the
// browser renders the same 8 voices, ADSR envelopes and stereo samples as the console.
// PRG32-QT's runtime still sees every call (its timing and state stay as they are); a
// hook after each audio call gives the call, with its arguments, to that engine.

#include "Cartridge.h"
#include "RiscVDisassembler.h"
#include "Runtime.h"
#include "audio_port.h"
#include "prg32_audio.h"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <set>
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
    // The firmware audio engine (see the top of this file).
    std::vector<uint8_t> audioBlock;   // the cartridge's AUD0 block; the engine reads it in place
    uint32_t audioArgs[8] = {};        // a0..a7 of the audio call being made
    uint64_t audioNanoseconds = 0;     // virtual time the engine has reached
    uint64_t buzzerCalls = 0;          // obsolete prg32_buzzer_* calls: silent, as on a console without one
    std::vector<uint16_t> pixels;
    std::string name;
    std::string metadata;
    uint64_t frames = 0;
    // Debugger state (see "Debugger" below). Breakpoints are guest instruction addresses.
    std::set<uint32_t> breakpoints;
    bool ignoreBreakpointOnce = false; // PRG32-QT: resume ignores the current breakpoint once
    uint64_t breakpointHits = 0;
    uint32_t lastBreakpoint = 0;
    bool stoppedAtBreakpoint = false; // stopped and not moved since: stopping again is not a new hit
    uint64_t lastRunSteps = 0;
    int performanceMode = 0; // what prg32_set_performance_mode chose (0 = accurate), for the CSR view
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

// --- Sound: the PRG32 firmware's audio engine (ADR-0021) ----------------------------------

constexpr uint32_t FirstAudioCall = 5, LastAudioCall = 25;   // the portable ABI's audio entries

/** The cartridge's AUD0 block, found where the console looks: after the header and the code. */
std::vector<uint8_t> audioBlockOf(const uint8_t* data, uint32_t size) {
    if (size < 20)
        return {};
    const uint32_t headerSize = uint32_t(data[8]) | uint32_t(data[9]) << 8;
    const uint32_t codeSize = uint32_t(data[16]) | uint32_t(data[17]) << 8 | uint32_t(data[18]) << 16 |
                              uint32_t(data[19]) << 24;
    const uint64_t offset = uint64_t(headerSize) + codeSize;
    if (offset + 40 > size || std::memcmp(data + offset, "AUD0", 4) != 0)
        return {};
    const uint8_t* block = data + offset;
    const uint32_t blockSize = uint32_t(block[36]) | uint32_t(block[37]) << 8 | uint32_t(block[38]) << 16 |
                               uint32_t(block[39]) << 24;
    if (blockSize < 40 || offset + blockSize > size)
        return {};
    return {block, block + blockSize};
}

/** Let the engine catch up with the cartridge's virtual time (whole milliseconds). */
void syncAudio() {
    const uint64_t now = session->runtime.virtualNanoseconds();
    if (now <= session->audioNanoseconds)
        return;
    const uint64_t ms = (now - session->audioNanoseconds) / 1000000ull;
    if (ms == 0)
        return;
    session->audioNanoseconds += ms * 1000000ull;
    prg32_kit_audio_advance_ms(uint32_t(std::min<uint64_t>(ms, 60000)));
}

void beforeHostCall(uint32_t index) {
    if (index < FirstAudioCall || index > LastAudioCall)
        return;
    syncAudio();   // the call happens at this point of virtual time
    for (int n = 0; n < 8; ++n)
        session->audioArgs[n] = session->runtime.registerValue(10 + n);
}

void afterHostCall(uint32_t index) {
    if (index < FirstAudioCall || index > LastAudioCall)
        return;
    const uint32_t* a = session->audioArgs;
    auto& runtime = session->runtime;
    auto u8 = [](uint32_t v) { return uint8_t(v); };
    auto i8 = [](uint32_t v) { return int8_t(uint8_t(v)); };
    switch (index) {
    case 5:   // prg32_buzzer_tone: obsolete (contracts/prg32-audio-contract-1.json "legacy_buzzer")
    case 7:   // prg32_buzzer_play_notes: obsolete
    case 8:   // prg32_buzzer_sample_u8: obsolete
        ++session->buzzerCalls;
        break;
    case 6:
        prg32_audio_note(u8(a[0]), u8(a[1]), u8(a[2]), u8(a[3]), a[4]);
        break;
    case 9: {
        // prg32_audio_init(config): the console starts the engine again (forgetting the
        // cartridge's assets, as the firmware does). The kit keeps 22050 Hz and 8 voices.
        prg32_audio_config_t config{};
        config.sample_rate = 22050;
        config.mode = PRG32_AUDIO_MODE_STEREO;
        config.max_voices = 8;
        if (a[0]) {
            const auto bytes = runtime.debugMemory(a[0], 9);
            if (bytes.size() == 9) {
                const uint32_t mode = uint32_t(bytes[4]) | uint32_t(bytes[5]) << 8;
                config.mode = mode == PRG32_AUDIO_MODE_MONO ? PRG32_AUDIO_MODE_MONO : PRG32_AUDIO_MODE_STEREO;
                config.max_voices = bytes[8] && bytes[8] < 8 ? bytes[8] : 8;
            }
        }
        config.gpio_bclk = config.gpio_lrclk = config.gpio_data = config.gpio_sd = -1;
        runtime.setHostResult(prg32_audio_init(&config) ? 1 : 0);
        break;
    }
    case 10:
        prg32_audio_shutdown();
        break;
    case 11:
        runtime.setHostResult(uint32_t(prg32_audio_get_mode()));
        break;
    case 12:
        runtime.setHostResult(uint32_t(prg32_audio_play_sample(uint16_t(a[0]), u8(a[1]), uint16_t(a[2]))));
        break;
    case 13:
        runtime.setHostResult(uint32_t(prg32_audio_play_sample_pan(uint16_t(a[0]), u8(a[1]), uint16_t(a[2]), i8(a[3]))));
        break;
    case 14:
        prg32_audio_stop_channel(int32_t(a[0]));
        break;
    case 15:
        prg32_audio_stop_all();
        break;
    case 16:
        prg32_audio_note_on(u8(a[0]), u8(a[1]), u8(a[2]), u8(a[3]));
        break;
    case 17:
        prg32_audio_note_on_pan(u8(a[0]), u8(a[1]), u8(a[2]), u8(a[3]), i8(a[4]));
        break;
    case 18:
        prg32_audio_note_off(u8(a[0]));
        break;
    case 19: {
        // prg32_audio_notes(channel, instrument, volume, notes, count): the firmware plays the
        // notes one after the other, waiting in between; here that waiting renders the audio.
        const uint32_t count = std::min<uint32_t>(a[4], 256);
        const auto bytes = runtime.debugMemory(a[3], size_t(count) * 4);
        std::vector<prg32_midi_note_t> notes;
        for (size_t n = 0; n + 4 <= bytes.size(); n += 4)
            notes.push_back({bytes[n], uint16_t(bytes[n + 2] | bytes[n + 3] << 8)});
        prg32_audio_notes(u8(a[0]), u8(a[1]), u8(a[2]), notes.data(), notes.size());
        break;
    }
    case 20:
        prg32_audio_play_track(uint16_t(a[0]));
        break;
    case 21:
        prg32_audio_stop_track();
        break;
    case 22:
        prg32_audio_set_tempo(uint16_t(a[0]));
        break;
    case 23:
        prg32_audio_set_master_volume(u8(a[0]));
        break;
    case 24:
        prg32_audio_set_channel_volume(u8(a[0]), u8(a[1]));
        break;
    case 25:
        prg32_audio_set_channel_pan(u8(a[0]), i8(a[1]));
        break;
    default:
        break;
    }
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
    next->runtime.setHostHooks(beforeHostCall, afterHostCall);
    // As the console: the engine is running before the cartridge starts, and the cartridge's
    // audio block (if any) replaces the assets; a block the engine refuses stops the load.
    if (prg32_kit_audio_start() != 0)
        return fail("the audio engine did not start");
    next->audioBlock = audioBlockOf(data, size);
    if (prg32_kit_audio_load(next->audioBlock.data(), next->audioBlock.size()) != 0)
        return fail("failed to load cartridge AUDIO block");
    session = std::move(next);   // the hooks use the session while init runs
    if (!session->runtime.load(*cartridge, error) || !session->runtime.init(error)) {
        session.reset();
        return fail(error);
    }
    session->name = cartridge->name();
    session->metadata = cartridge->metadataJson();
    session->pixels = session->runtime.framebuffer().rgb565Pixels();
    syncAudio();
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
    syncAudio();
    return 1;
}

// --- Debugger -------------------------------------------------------------------------
//
// The same rules as PRG32-QT's desktop debugger (src/qt/AppController.cpp):
//   - the "execution address" is the PC while an update/draw call is active, otherwise the
//     update entry point (the next instruction a new frame will run);
//   - breakpoints are checked before an instruction runs; resume ignores the breakpoint at the
//     current address once, so execution can move on, and the next visit stops again;
//   - Runtime::debugStep runs exactly one instruction of the current update/draw call.
// Step over and step out are added here (PRG32-QT has only step); they read the instruction at
// the PC to recognise calls (jal/jalr that write ra or t0) and returns (jalr x0 through ra/t0).

constexpr int RunError = -1, RunBudget = 0, RunFrameEnd = 1, RunBreakpoint = 2, RunDone = 3;

namespace {

bool inGuestMemory(uint32_t address) {
    return address >= session->runtime.guestBase() &&
           uint64_t(address) < uint64_t(session->runtime.guestBase()) + session->runtime.guestMemorySize();
}

uint32_t entryAddress(int which) {
    const auto& header = session->runtime.cartridge().header();
    const uint32_t offset = which == 0 ? header.initOffset : which == 2 ? header.drawOffset : header.updateOffset;
    return session->runtime.guestBase() + offset;
}

uint32_t executionAddress() {
    return session->runtime.debugCallActive() ? session->runtime.programCounter() : entryAddress(1);
}

// The instruction at `address`: its width in bytes (2 or 4, 0 if unreadable) and its bits.
unsigned fetch(uint32_t address, uint32_t& instruction) {
    const auto low = session->runtime.debugMemory(address, 2);
    if (low.size() != 2)
        return 0;
    instruction = uint32_t(low[0]) | uint32_t(low[1]) << 8;
    if ((instruction & 3u) != 3u)
        return 2;
    const auto all = session->runtime.debugMemory(address, 4);
    if (all.size() != 4)
        return 0;
    instruction |= uint32_t(all[2]) << 16 | uint32_t(all[3]) << 24;
    return 4;
}

bool isLink(uint32_t reg) {
    return reg == 1 || reg == 5; // ra or t0, the RISC-V calling convention's link registers
}

// 1 = a call (jal/jalr/c.jal/c.jalr that saves a return address), -1 = a return, 0 = anything else.
int callKind(uint32_t instruction, unsigned width) {
    if (width == 4) {
        const uint32_t opcode = instruction & 0x7f, rd = (instruction >> 7) & 31, rs1 = (instruction >> 15) & 31;
        if ((opcode == 0x6f || opcode == 0x67) && isLink(rd))
            return 1;
        if (opcode == 0x67 && rd == 0 && isLink(rs1))
            return -1;
        return 0;
    }
    if (width == 2) {
        const uint32_t quadrant = instruction & 3, function3 = instruction >> 13;
        const uint32_t rs1 = (instruction >> 7) & 31, rs2 = (instruction >> 2) & 31, bit12 = (instruction >> 12) & 1;
        if (quadrant == 1 && function3 == 1)
            return 1; // c.jal (RV32 only)
        if (quadrant == 2 && function3 == 4 && rs2 == 0 && rs1 != 0)
            return bit12 ? 1 : (isLink(rs1) ? -1 : 0); // c.jalr / c.jr ra
    }
    return 0;
}

// One debugStep with frame bookkeeping. Returns false on a guest trap (lastError is set).
bool stepOnce(uint32_t input, bool& frameEnded) {
    std::string error;
    const bool wasActive = session->runtime.debugPhase() != "idle";
    if (!session->runtime.debugStep(input, error))
        return fail(error);
    ++session->lastRunSteps;
    session->stoppedAtBreakpoint = false;
    frameEnded = wasActive && session->runtime.debugPhase() == "idle";
    if (frameEnded)
        ++session->frames;
    return true;
}

// Breakpoint check before an instruction, with PRG32-QT's "ignore once after resume" rule.
bool atBreakpoint() {
    const uint32_t address = executionAddress();
    if (!session->breakpoints.count(address))
        return false;
    if (session->ignoreBreakpointOnce) {
        session->ignoreBreakpointOnce = false;
        return false;
    }
    if (!session->stoppedAtBreakpoint)
        ++session->breakpointHits;
    session->stoppedAtBreakpoint = true;
    session->lastBreakpoint = address;
    return true;
}

// Finish a host ABI call the guest has jumped into, so the PC is back in guest code.
bool leaveHostCall(uint32_t input) {
    bool frameEnded = false;
    while (session->runtime.debugCallActive() && !inGuestMemory(session->runtime.programCounter()))
        if (!stepOnce(input, frameEnded))
            return false;
    return true;
}

enum class Goal { Continue, Over, Out };

// One guest instruction; a jump into a PRG32 ABI call also runs that call, so the PC is in guest code.
bool stepInstruction(uint32_t input) {
    bool frameEnded = false;
    return stepOnce(input, frameEnded) && leaveHostCall(input);
}

int run(uint32_t input, uint64_t budget, bool stopAtFrameEnd, Goal goal) {
    if (!session) {
        fail("no cartridge is loaded");
        return RunError;
    }
    session->lastRunSteps = 0;
    const std::string startPhase = session->runtime.debugPhase();
    uint32_t instruction = 0;
    const uint32_t start = executionAddress();
    const unsigned width = fetch(start, instruction);
    // Step over an instruction that is not a call, or step out between frames: just one step.
    if ((goal == Goal::Over && callKind(instruction, width) != 1) || (goal == Goal::Out && startPhase == "idle"))
        return stepInstruction(input) ? RunDone : RunError;
    const uint32_t returnAddress = start + width, stackPointer = session->runtime.registerValue(2);
    int depth = 0;
    if (goal != Goal::Continue)
        session->ignoreBreakpointOnce = session->breakpoints.count(start) > 0; // leave the current breakpoint
    while (budget--) {
        if (atBreakpoint())
            return RunBreakpoint;
        int kind = 0;
        if (goal == Goal::Out) {
            const uint32_t pc = session->runtime.programCounter();
            if (!inGuestMemory(pc))
                kind = -1; // a PRG32 ABI call returns straight to ra
            else {
                const unsigned size = fetch(pc, instruction);
                kind = callKind(instruction, size);
            }
        }
        bool frameEnded = false;
        if (!stepOnce(input, frameEnded))
            return RunError;
        if (goal == Goal::Continue) {
            if (frameEnded && stopAtFrameEnd)
                return RunFrameEnd;
            continue;
        }
        if (startPhase != "idle" && session->runtime.debugPhase() != startPhase)
            return RunDone; // the update (or draw) function itself returned
        if (goal == Goal::Over && session->runtime.programCounter() == returnAddress &&
            session->runtime.registerValue(2) >= stackPointer)
            return RunDone;
        if (goal == Goal::Out && kind == 1)
            ++depth;
        else if (goal == Goal::Out && kind == -1 && depth-- == 0)
            return leaveHostCall(input) ? RunDone : RunError;
    }
    return RunBudget;
}

void refreshPixels() {
    session->pixels = session->runtime.framebuffer().rgb565Pixels();
    syncAudio();   // whatever ran, the engine follows its virtual time (as prg32_frame does)
}

void appendNumber(std::string& out, uint32_t value) {
    char buffer[16];
    std::snprintf(buffer, sizeof buffer, "%u", value);
    out += buffer;
}

} // namespace

/** Execute exactly one guest RV32IMAC instruction of the current update/draw call (PRG32-QT's step). */
PRG32_EXPORT int prg32_debug_step(uint32_t input) {
    if (!session)
        return fail("no cartridge is loaded");
    session->lastRunSteps = 0;
    bool frameEnded = false;
    const bool ok = stepOnce(input, frameEnded);
    refreshPixels();
    return ok ? 1 : 0;
}

PRG32_EXPORT int prg32_debug_call_active() {
    return session && session->runtime.debugCallActive() ? 1 : 0;
}

/** The kit's "step instruction": one guest instruction; a jump into a PRG32 ABI call also runs that call. */
PRG32_EXPORT int prg32_debug_step_instruction(uint32_t input) {
    if (!session)
        return fail("no cartridge is loaded");
    session->lastRunSteps = 0;
    const bool ok = stepInstruction(input);
    refreshPixels();
    return ok ? 1 : 0;
}

/**
 * Run instrumented, checking breakpoints before every instruction, for at most `budget` instructions.
 * mode 0 = continue (stop_at_frame_end chooses whether the end of a frame stops it),
 *      1 = step over the call at the PC, 2 = step out of the current function.
 * Returns -1 guest trap, 0 budget used up, 1 frame finished, 2 breakpoint hit, 3 step over/out done.
 * Step over/out leave a breakpoint at the starting address; a continue stops on it unless
 * prg32_debug_resume() was called first. The browser runs in slices: one resume, many runs.
 */
PRG32_EXPORT int prg32_debug_run(uint32_t input, uint32_t budget, int mode, int stopAtFrameEnd) {
    const int result = run(input, budget, stopAtFrameEnd != 0, mode == 1 ? Goal::Over : mode == 2 ? Goal::Out : Goal::Continue);
    if (session)
        refreshPixels();
    return result;
}

/** PRG32-QT's resume: the next continue ignores the breakpoint at the current address once. */
PRG32_EXPORT void prg32_debug_resume() {
    if (session)
        session->ignoreBreakpointOnce = session->breakpoints.count(executionAddress()) > 0;
}

/** How many instructions the last step/run executed. */
PRG32_EXPORT uint32_t prg32_debug_last_steps() {
    return session ? uint32_t(session->lastRunSteps) : 0;
}

/** 0 idle (between frames), 1 inside update, 2 inside draw. */
PRG32_EXPORT int prg32_debug_phase() {
    if (!session)
        return 0;
    const std::string phase = session->runtime.debugPhase();
    return phase == "update" ? 1 : phase == "draw" ? 2 : 0;
}

/** The next instruction to run: the PC inside a call, otherwise the update entry point (as PRG32-QT). */
PRG32_EXPORT uint32_t prg32_debug_pc() {
    return session ? executionAddress() : 0;
}

/** Guest address of the cartridge's init (0), update (1) or draw (2) function, from the PRG32 header. */
PRG32_EXPORT uint32_t prg32_entry(int which) {
    return session ? entryAddress(which) : 0;
}

/** Set (enabled = 1) or clear a breakpoint. Returns 0 when the address is not guest memory. */
PRG32_EXPORT int prg32_breakpoint(uint32_t address, int enabled) {
    if (!session)
        return fail("no cartridge is loaded");
    if (session->runtime.debugMemory(address, 2).size() != 2)
        return fail("invalid breakpoint address");
    if (enabled)
        session->breakpoints.insert(address);
    else
        session->breakpoints.erase(address);
    return 1;
}

PRG32_EXPORT void prg32_breakpoints_clear() {
    if (session)
        session->breakpoints.clear();
}

/**
 * Disassemble `count` (at most 256) instructions from `address` with PRG32-QT's RiscVDisassembler, as JSON:
 * [{"address":N,"width":2|4,"word":N,"text":"addi sp, sp, -16"}, ...]. Stops at the end of guest memory.
 */
PRG32_EXPORT const char* prg32_disassemble(uint32_t address, uint32_t count) {
    stateText = "[";
    if (session) {
        for (uint32_t line = 0; line < count && line < 256; ++line) {
            uint32_t instruction = 0;
            const unsigned width = fetch(address, instruction);
            if (!width)
                break;
            std::string text = prg32::disassembleRv32(address, instruction, width), escaped;
            for (char c : text)
                if (c == '"' || c == '\\')
                    escaped += '\\', escaped += c;
                else if (uint8_t(c) >= 32)
                    escaped += c;
            stateText += line ? ",{\"address\":" : "{\"address\":";
            appendNumber(stateText, address);
            stateText += ",\"width\":" + std::to_string(width) + ",\"word\":";
            appendNumber(stateText, instruction);
            stateText += ",\"text\":\"" + escaped + "\"}";
            address += width;
        }
    }
    stateText += "]";
    return stateText.c_str();
}

/**
 * The debugger state as JSON, with PRG32-QT's /api/debug names where they exist (phase, pc,
 * breakpoints, registers) plus what the kit adds (entries, hits, guest time).
 */
PRG32_EXPORT const char* prg32_debug_state_json() {
    if (!session) {
        stateText = "{}";
        return stateText.c_str();
    }
    auto& runtime = session->runtime;
    std::string& out = stateText;
    out = "{\"phase\":\"" + runtime.debugPhase() + "\",\"pc\":";
    appendNumber(out, executionAddress());
    out += ",\"raw_pc\":";
    appendNumber(out, runtime.programCounter());
    out += ",\"call_active\":" + std::string(runtime.debugCallActive() ? "true" : "false") + ",\"registers\":[";
    for (unsigned index = 0; index < 32; ++index) {
        if (index)
            out += ",";
        appendNumber(out, runtime.registerValue(index));
    }
    out += "],\"breakpoints\":[";
    bool first = true;
    for (uint32_t address : session->breakpoints) {
        if (!first)
            out += ",";
        first = false;
        appendNumber(out, address);
    }
    out += "],\"breakpoint_hits\":" + std::to_string(session->breakpointHits) + ",\"last_breakpoint\":";
    appendNumber(out, session->lastBreakpoint);
    out += ",\"entries\":{\"init\":";
    appendNumber(out, entryAddress(0));
    out += ",\"update\":";
    appendNumber(out, entryAddress(1));
    out += ",\"draw\":";
    appendNumber(out, entryAddress(2));
    out += "},\"frames\":" + std::to_string(session->frames) + ",\"retired\":" +
           std::to_string(runtime.retiredInstructions()) + ",\"cycles\":" + std::to_string(runtime.virtualCycles()) +
           ",\"guest_ns\":" + std::to_string(runtime.virtualNanoseconds()) +
           ",\"last_steps\":" + std::to_string(session->lastRunSteps);
    // The counter CSRs a cartridge can read with csrr, by the same rule as the core's
    // Rv32Cpu (CSR 0xC00 cycle, 0xC01 time, 0xC02 instret; 0xC8x are the high halves):
    // in accurate ESP32-C6 timing cycle and time follow the virtual clock, otherwise
    // every counter is the number of retired instructions.
    const uint64_t retired = runtime.retiredInstructions();
    const bool accurate = session->performanceMode == 0;
    const uint64_t cycle = accurate ? runtime.virtualCycles() : retired;
    const uint64_t time = accurate ? runtime.virtualNanoseconds() : retired;
    out += ",\"csr\":{\"cycle\":" + std::to_string(uint32_t(cycle)) + ",\"cycleh\":" +
           std::to_string(uint32_t(cycle >> 32)) + ",\"time\":" + std::to_string(uint32_t(time)) +
           ",\"timeh\":" + std::to_string(uint32_t(time >> 32)) + ",\"instret\":" +
           std::to_string(uint32_t(retired)) + ",\"instreth\":" + std::to_string(uint32_t(retired >> 32)) + "}}";
    return out.c_str();
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
        session->performanceMode = mode;
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
                 ",\"audio_calls\":" + std::to_string(session->audio.total) +
                 ",\"audio_pcm_fnv1a\":\"" + [] {
                     char hash[32];
                     std::snprintf(hash, sizeof hash, "%016llx", static_cast<unsigned long long>(prg32_kit_audio_hash()));
                     return std::string(hash);
                 }() + "\"}";
    return stateText.c_str();
}

// --- Sound output (ADR-0021) ------------------------------------------------------------
// The browser takes the rendered stereo frames after each frame and plays them; tests read
// them directly. Frames are signed 16-bit, interleaved left, right, at 22050 Hz.

/** Stereo frames waiting to be played. */
PRG32_EXPORT uint32_t prg32_audio_frames() {
    return uint32_t(prg32_kit_audio_frames());
}

/** The waiting frames: 2 x prg32_audio_frames() signed 16-bit values (left, right, ...). */
PRG32_EXPORT const int16_t* prg32_audio_samples() {
    return prg32_kit_audio_pcm();
}

/** Forget the waiting frames (the browser has queued them for playing). */
PRG32_EXPORT void prg32_audio_take() {
    prg32_kit_audio_clear();
}

/** Frames dropped because nobody took them in time. */
PRG32_EXPORT uint32_t prg32_audio_dropped() {
    return prg32_kit_audio_dropped();
}

/** How many obsolete buzzer calls the cartridge made (they make no sound). */
PRG32_EXPORT uint32_t prg32_audio_buzzer_calls() {
    return session ? uint32_t(session->buzzerCalls) : 0;
}

/** One voice for envelope traces: out[6] = active, synth, envelope state, level, volume, pan. */
PRG32_EXPORT void prg32_audio_voice(int voice, int32_t* out) {
    prg32_kit_audio_voice(voice, out);
}
