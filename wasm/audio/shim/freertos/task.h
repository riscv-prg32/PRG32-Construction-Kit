/* No audio task in the browser: the kit renders audio when engine time advances
 * (audio_port.c). A delay renders that much audio (see FreeRTOS.h). */
#ifndef PRG32_KIT_TASK_H
#define PRG32_KIT_TASK_H

#include "FreeRTOS.h"

#define vTaskDelay(ticks) prg32_kit_audio_delay_ms((uint32_t)(ticks))
#define vTaskDelete(handle) ((void)(handle))
#define xTaskCreate(function, name, stack, argument, priority, handle) \
    ((void)(function), (void)(name), (void)(stack), (void)(argument), (void)(priority), *(handle) = 0, pdPASS)

#endif
