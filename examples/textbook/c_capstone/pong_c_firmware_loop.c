#include "prg32.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void pong_c_init(void);
void pong_c_update(void);
void pong_c_draw(void);

void app_main(void) {
    prg32_init();
    pong_c_init();
    while (1) {
        pong_c_update();
        pong_c_draw();
        prg32_gfx_present();             /* show the finished frame */
        vTaskDelay(pdMS_TO_TICKS(33));   /* ~30 frames per second */
    }
}
