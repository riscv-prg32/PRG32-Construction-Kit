/* The PRG32 audio engine's build settings for the Construction Kit (ADR-0021).
 *
 * The firmware's own audio sources (the .c files of components/prg32_audio in the PRG32 SDK) are
 * compiled unchanged; ESP-IDF normally generates this file from Kconfig. These are the
 * values of the PRG32 profiles (profiles/sdkconfig.defaults) with stereo output, which
 * is what contracts/prg32-audio-contract-1.json describes. */
#ifndef PRG32_KIT_SDKCONFIG_H
#define PRG32_KIT_SDKCONFIG_H

#define CONFIG_PRG32_AUDIO_ENABLED 1
#define CONFIG_PRG32_AUDIO_SAMPLE_RATE 22050
#define CONFIG_PRG32_AUDIO_MAX_VOICES 8
#define CONFIG_PRG32_AUDIO_MODE_STEREO 1
#define CONFIG_PRG32_DISPLAY_QEMU_RGB 0
#define CONFIG_PRG32_AUDIO_I2S_BCLK_GPIO -1
#define CONFIG_PRG32_AUDIO_I2S_LRCLK_GPIO -1
#define CONFIG_PRG32_AUDIO_I2S_DATA_GPIO -1
#define CONFIG_PRG32_AUDIO_I2S_SD_GPIO -1

#endif
