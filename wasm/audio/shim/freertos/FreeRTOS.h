/* Just enough FreeRTOS for the PRG32 audio engine off the console (ADR-0021).
 *
 * In the browser the engine runs on one thread: there is no audio task and no lock to
 * take. A delay inside the engine (prg32_audio_notes waits between notes) renders that
 * much audio instead, so the notes still follow each other in engine time. */
#ifndef PRG32_KIT_FREERTOS_H
#define PRG32_KIT_FREERTOS_H

#include <stdint.h>
#include <stdio.h>

/* The tracker logs every event on the console's serial port; the browser stays quiet. */
#define printf(...) ((void)0)

typedef void *SemaphoreHandle_t;
typedef void *TaskHandle_t;
typedef uint32_t TickType_t;
typedef int BaseType_t;

#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))
#define portMAX_DELAY ((TickType_t)0xffffffffu)
#define tskIDLE_PRIORITY 0
#define pdPASS 1

void prg32_kit_audio_delay_ms(uint32_t ms);

#endif
