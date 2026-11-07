/* The engine's log lines (PRG32 1fa8474 logs only in its QEMU audio path). The browser has no
 * console to write them to, so they are left out. */
#ifndef PRG32_KIT_ESP_LOG_H
#define PRG32_KIT_ESP_LOG_H

#define ESP_LOGE(tag, ...) ((void)(tag))
#define ESP_LOGW(tag, ...) ((void)(tag))
#define ESP_LOGI(tag, ...) ((void)(tag))
#define ESP_LOGD(tag, ...) ((void)(tag))

#endif
