/* The kit's side of the PRG32 audio engine (ADR-0021, docs/audio_engine.md).
 *
 * The engine itself is the PRG32 firmware's (components/prg32_audio). This file gives it
 * what the console's audio task and I2S driver would: time, in steps of 20 ms, and a place
 * to put what it mixed, a bounded queue of signed 16-bit stereo frames (left, right). */
#ifndef PRG32_KIT_AUDIO_PORT_H
#define PRG32_KIT_AUDIO_PORT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PRG32_KIT_AUDIO_STEP_MS 20u
#define PRG32_KIT_AUDIO_STEP_FRAMES 441u            /* 20 ms at 22050 Hz */
#define PRG32_KIT_AUDIO_QUEUE_FRAMES (22050u * 4u)  /* at most 4 s waiting to be played */

/* Start the engine as the console does at power-on (prg32_audio_init(NULL)): 8 voices,
 * 22050 Hz, stereo, the default instruments. */
int prg32_kit_audio_start(void);
/* Load a cartridge's AUD0 block (or clear the assets when there is none), as the
 * console does when it starts a cartridge. The block must stay alive while used. */
int prg32_kit_audio_load(const uint8_t *block, size_t size);

/* Let `ms` of engine time pass: every full 20 ms runs the tracker and the voices and
 * mixes 441 frames into the queue. */
void prg32_kit_audio_advance_ms(uint32_t ms);
/* Frames waiting, a pointer to them (interleaved left, right) and removing them. */
size_t prg32_kit_audio_frames(void);
const int16_t *prg32_kit_audio_pcm(void);
void prg32_kit_audio_clear(void);
/* Frames dropped because nobody took them in time (the queue is bounded). */
uint32_t prg32_kit_audio_dropped(void);
/* FNV-1a (64-bit) over every sample mixed since the start, as unsigned 16-bit values in
 * order (left, right, ...): equal on every build that renders the same sound. */
uint64_t prg32_kit_audio_hash(void);

/* One voice, for envelope traces: active, synth, envelope state (0 off, 1 attack,
 * 2 decay, 3 sustain, 4 release), envelope level 0..65535, volume, pan. */
void prg32_kit_audio_voice(int voice, int32_t out[6]);
/* 1 while a soundtrack is playing (it can wait between notes with every voice quiet). */
int prg32_kit_audio_tracker_active(void);

#ifdef __cplusplus
}
#endif

#endif
