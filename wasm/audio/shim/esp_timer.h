/* The audio task's clock; the kit has no audio task (see freertos/task.h). */
#ifndef PRG32_KIT_ESP_TIMER_H
#define PRG32_KIT_ESP_TIMER_H

#include <stdint.h>

static inline int64_t esp_timer_get_time(void) { return 0; }

#endif
