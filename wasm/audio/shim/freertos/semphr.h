/* One thread, no lock (see FreeRTOS.h). */
#ifndef PRG32_KIT_SEMPHR_H
#define PRG32_KIT_SEMPHR_H

#include "FreeRTOS.h"

#define xSemaphoreCreateMutex() ((SemaphoreHandle_t)1)
#define xSemaphoreTake(handle, ticks) ((void)(handle), (void)(ticks), 1)
#define xSemaphoreGive(handle) ((void)(handle), 1)
#define vSemaphoreDelete(handle) ((void)(handle))

#endif
