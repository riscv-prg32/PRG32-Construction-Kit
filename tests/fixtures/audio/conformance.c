/* Audio conformance fixture (ADR-0021, docs/audio_engine.md): one PRG32 cartridge that
 * exercises the whole eight-voice engine at fixed frames (30 per second), so the same
 * cartridge can be compared on every runtime. Built by tools/build_audio_fixtures.py with
 * the audio block described there (instruments 0..8, one sample, one soundtrack).
 *
 *   frame   1  all 8 voices gated at once: different waveform, note, ADSR, volume, pan
 *   frame  12  voice 2 moved hard right, voice 5 turned down
 *   frame  18  master volume down
 *   frame  24  voices 0..3 released (their ADSR release runs), 4..7 keep sustaining
 *   frame  40  stop all: silence
 *   frame  44  the sample, hard left only
 *   frame  60  one voice, hard right only
 *   frame  70  the soundtrack (track 0) from the audio block
 *   frame 130  track and voices stopped: silence
 *   frame 134  all 8 voices loud and in phase: the mix clips
 *   frame 144  stop all: silence
 *   frame 148  a note on voice 0, replaced by another note on voice 0
 *   frame 156  stop all: silence until the end */
#include "prg32.h"

static uint32_t frame;
static const int8_t pans[8] = {-64, -45, -27, -9, 9, 27, 45, 63};
static const uint8_t notes[8] = {48, 52, 55, 60, 64, 67, 72, 76};
static const uint8_t volumes[8] = {255, 230, 205, 180, 155, 130, 105, 80};

void aconf_init(void) {
    frame = 0;
    prg32_audio_set_master_volume(160);
}

void aconf_update(void) {
    switch (frame) {
    case 1:
        for (uint8_t voice = 0; voice < 8; voice++) {
            prg32_audio_note_on_pan(voice, voice, notes[voice], volumes[voice], pans[voice]);
        }
        break;
    case 12:
        prg32_audio_set_channel_pan(2, 63);
        prg32_audio_set_channel_volume(5, 64);
        break;
    case 18:
        prg32_audio_set_master_volume(96);
        break;
    case 24:
        for (uint8_t voice = 0; voice < 4; voice++) {
            prg32_audio_note_off(voice);
        }
        break;
    case 40:
        prg32_audio_stop_all();
        break;
    case 44:
        prg32_audio_set_master_volume(160);
        prg32_audio_play_sample_pan(0, 255, 1024, -64);
        break;
    case 60:
        prg32_audio_stop_all();
        prg32_audio_note_on_pan(0, 7, 60, 255, 63);
        break;
    case 70:
        prg32_audio_stop_all();
        prg32_audio_play_track(0);
        break;
    case 130:
        prg32_audio_stop_track();
        prg32_audio_stop_all();
        break;
    case 134:
        prg32_audio_set_master_volume(255);
        for (uint8_t voice = 0; voice < 8; voice++) {
            prg32_audio_set_channel_volume(voice, 255);
            prg32_audio_note_on_pan(voice, 8, 36, 255, 1);
        }
        break;
    case 144:
        prg32_audio_stop_all();
        break;
    case 148:
        prg32_audio_set_master_volume(160);
        prg32_audio_note_on_pan(0, 1, 60, 200, 1);
        prg32_audio_note_on_pan(0, 2, 72, 200, 1);
        break;
    case 156:
        prg32_audio_stop_all();
        break;
    default:
        break;
    }
    frame++;
}

void aconf_draw(void) {
    prg32_gfx_clear(0);
}
