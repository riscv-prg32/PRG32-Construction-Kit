/* The kit's side of the PRG32 audio engine: see audio_port.h and ADR-0021.
 *
 * Everything that makes a sound (voices, ADSR, synth, filter, samples, tracker, mixing,
 * clipping) is the firmware's own code. This file replaces only what is tied to the
 * console's hardware: the I2S output (the queue below) and the audio task's timing
 * (prg32_kit_audio_advance_ms, in exact 20 ms steps as the console under QEMU uses). */
#include "audio_port.h"

#include <string.h>

#include "audio_internal.h"

#if CONFIG_PRG32_AUDIO_MAX_VOICES != 8
#error "The Construction Kit's audio engine must have exactly 8 voices (contracts/prg32-audio-contract-1.json)"
#endif
#if CONFIG_PRG32_AUDIO_SAMPLE_RATE != 22050
#error "The Construction Kit's audio engine runs at 22050 Hz"
#endif

static int16_t queue_[PRG32_KIT_AUDIO_QUEUE_FRAMES * 2u];
static size_t queued_;          /* frames in queue_ */
static uint32_t dropped_;
static uint32_t pending_ms_;    /* engine time not yet mixed (under 20 ms) */
static uint64_t hash_ = 0xcbf29ce484222325ull;
static uint32_t delay_depth_;

/* --- what the I2S driver would do (audio.c calls these) ----------------------------- */

int prg32_audio_i2s_start(const prg32_audio_config_t *config) {
    (void)config;
    return 0;   /* an output is there: the kit's queue */
}

void prg32_audio_i2s_stop(void) {}

int prg32_audio_i2s_write(const int16_t *samples, size_t frames, prg32_audio_mode_t mode) {
    (void)samples;
    (void)frames;
    (void)mode;
    return 0;   /* not used: the kit mixes in prg32_kit_audio_advance_ms */
}

/* --- time ---------------------------------------------------------------------------- */

static void push(const int16_t *frames, size_t count) {
    if (count > PRG32_KIT_AUDIO_QUEUE_FRAMES) {
        frames += (count - PRG32_KIT_AUDIO_QUEUE_FRAMES) * 2u;
        dropped_ += (uint32_t)(count - PRG32_KIT_AUDIO_QUEUE_FRAMES);
        count = PRG32_KIT_AUDIO_QUEUE_FRAMES;
    }
    if (queued_ + count > PRG32_KIT_AUDIO_QUEUE_FRAMES) {   /* drop the oldest */
        size_t drop = queued_ + count - PRG32_KIT_AUDIO_QUEUE_FRAMES;
        memmove(queue_, queue_ + drop * 2u, (queued_ - drop) * 2u * sizeof(int16_t));
        queued_ -= drop;
        dropped_ += (uint32_t)drop;
    }
    memcpy(queue_ + queued_ * 2u, frames, count * 2u * sizeof(int16_t));
    queued_ += count;
}

static void step(void) {
    int16_t mixed[PRG32_KIT_AUDIO_STEP_FRAMES * 2u];
    prg32_audio_tracker_step(PRG32_KIT_AUDIO_STEP_MS);
    prg32_audio_voices_step(PRG32_KIT_AUDIO_STEP_MS);
    if (prg32_audio_get_mode() == PRG32_AUDIO_MODE_STEREO) {
        prg32_audio_mix_stereo(mixed, PRG32_KIT_AUDIO_STEP_FRAMES);
    } else {
        /* A mono console drives one speaker: the same mix on both sides. */
        int16_t mono[PRG32_KIT_AUDIO_STEP_FRAMES];
        prg32_audio_mix_mono(mono, PRG32_KIT_AUDIO_STEP_FRAMES);
        for (size_t i = 0; i < PRG32_KIT_AUDIO_STEP_FRAMES; ++i) {
            mixed[i * 2u] = mono[i];
            mixed[i * 2u + 1u] = mono[i];
        }
    }
    for (size_t i = 0; i < PRG32_KIT_AUDIO_STEP_FRAMES * 2u; ++i) {
        hash_ ^= (uint16_t)mixed[i];
        hash_ *= 1099511628211ull;
    }
    push(mixed, PRG32_KIT_AUDIO_STEP_FRAMES);
}

void prg32_kit_audio_advance_ms(uint32_t ms) {
    if (!g_prg32_audio.initialized) {
        return;
    }
    if (ms > 60000u) {
        ms = 60000u;   /* one call never renders more than a minute */
    }
    pending_ms_ += ms;
    while (pending_ms_ >= PRG32_KIT_AUDIO_STEP_MS) {
        pending_ms_ -= PRG32_KIT_AUDIO_STEP_MS;
        step();
    }
}

/* prg32_audio_notes waits between notes (vTaskDelay); here that time is rendered. */
void prg32_kit_audio_delay_ms(uint32_t ms) {
    if (delay_depth_ > 0) {
        return;
    }
    delay_depth_++;
    prg32_kit_audio_advance_ms(ms);
    delay_depth_--;
}

/* --- start, cartridges, output --------------------------------------------------------- */

int prg32_kit_audio_start(void) {
    queued_ = 0;
    dropped_ = 0;
    pending_ms_ = 0;
    hash_ = 0xcbf29ce484222325ull;
    return prg32_audio_init(NULL) ? 0 : -1;
}

int prg32_kit_audio_load(const uint8_t *block, size_t size) {
    if (block && size) {
        return prg32_audio_load_block(block, size);
    }
    prg32_audio_clear_assets();
    return 0;
}

size_t prg32_kit_audio_frames(void) { return queued_; }

const int16_t *prg32_kit_audio_pcm(void) { return queue_; }

void prg32_kit_audio_clear(void) { queued_ = 0; }

uint32_t prg32_kit_audio_dropped(void) { return dropped_; }

uint64_t prg32_kit_audio_hash(void) { return hash_; }

int prg32_kit_audio_tracker_active(void) { return g_prg32_audio.tracker.active ? 1 : 0; }

void prg32_kit_audio_voice(int voice, int32_t out[6]) {
    memset(out, 0, 6 * sizeof(int32_t));
    if (voice < 0 || voice >= CONFIG_PRG32_AUDIO_MAX_VOICES) {
        return;
    }
    const prg32_audio_voice_t *v = &g_prg32_audio.voices[voice];
    out[0] = v->active;
    out[1] = v->synth;
    out[2] = v->synth_state.envelope_state;
    out[3] = (int32_t)v->synth_state.envelope_level;
    out[4] = v->volume;
    out[5] = v->pan;
}
