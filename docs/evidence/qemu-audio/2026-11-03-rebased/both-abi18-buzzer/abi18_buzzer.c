/* Built with the unpatched SDK (ABI 1.8): every buzzer call, then a note, so the sound shows it kept running. */
#include "prg32.h"
static uint32_t frame;
static const prg32_note_t notes[] = {{440, 20}, {0, 20}};
static const uint8_t pcm[] = {128, 200, 128, 56};
void abi18_init(void) { frame = 0; prg32_audio_set_master_volume(200); }
void abi18_update(void) {
  if (frame == 10) {
    prg32_buzzer_tone(440, 20, 512);
    prg32_buzzer_play_notes(notes, 2);
    prg32_buzzer_sample_u8(pcm, sizeof pcm, 8000);
    prg32_audio_note(0, 0, 69, 200, 500);
  }
  frame++;
}
void abi18_draw(void) {}
