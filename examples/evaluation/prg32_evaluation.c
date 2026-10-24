/*
 * PRG32 Evaluation: the workload of the PRG32 performance protocol, version 1
 * (contracts/prg32-evaluation-protocol-1.json, docs/evaluate.md).
 *
 * Every target runs exactly this cartridge, built by the kit from this file: the same bytes, so
 * the same SHA-256. Each start runs one suite of five cases, 60 frames each, and hands every
 * frame's times to the PRG32 performance broker (prg32_metrics.h). The broker keeps one compact
 * summary per case; the kit reads it after the suite ends (GET /api/performance.json, or through
 * QEMU's GDB stub) and starts the cartridge again for the next repetition.
 *
 * What one frame is: update (game logic), draw (the case's workload) and present (the picture
 * sent to the screen), each timed with prg32_perf_now_us(), the target's microsecond clock.
 * On an emulator that clock is the emulator's: its times are not a console's times.
 */
#include "prg32.h"
#include <stdint.h>

#define CASES 5u
#define FRAMES 60u

static uint32_t frame_in_case;      /* 0..FRAMES-1 */
static uint32_t current_case;       /* 0..CASES-1 */
static uint32_t frame_index;        /* frames since the suite began */
static uint64_t update_start;
static uint64_t update_end;
static int running;                 /* 1 while the suite runs */
static int finished;                /* 1 done, 2 aborted */
static int ball_x, ball_y, ball_dx, ball_dy, scroll;
static uint32_t seed;

/* The five cases: what each one draws, and what it is meant to measure. */
static const char *case_name(uint32_t index) {
    switch (index) {
    case 0: return "clear-fill";
    case 1: return "text-overlay";
    case 2: return "sprite-storm";
    case 3: return "scrolling";
    default: return "mixed-gameplay";
    }
}

static const char *case_goal(uint32_t index) {
    switch (index) {
    case 0: return "clearing the screen and filling large rectangles";
    case 1: return "drawing lines of 8x8 text";
    case 2: return "many moving sprite-sized rectangles";
    case 3: return "scrolling pixels and stripes";
    default: return "text, sprites and scrolling together";
    }
}

static void reset_scene(void) {
    ball_x = 24; ball_y = 32; ball_dx = 3; ball_dy = 2; scroll = 0;
    seed = 0x13579bdfu;                    /* the same "random" numbers every run */
}

static int begin_case(void) {
    prg32_perf_case_desc_t description;
    description.abi_version = PRG32_PERF_ABI_VERSION;
    description.struct_size = sizeof(description);
    description.case_index = current_case;
    description.color_mode = PRG32_PERF_COLOR_RGB565;
    description.name = case_name(current_case);
    description.metric_goal = case_goal(current_case);
    reset_scene();
    frame_in_case = 0;
    return prg32_perf_case_begin(&description, FRAMES);
}

static void start_suite(void) {
    prg32_perf_suite_desc_t suite;
    suite.abi_version = PRG32_PERF_ABI_VERSION;
    suite.struct_size = sizeof(suite);
    suite.suite_version = 1;
    suite.name = "prg32-evaluation-1";
    current_case = 0;
    frame_index = 0;
    finished = 0;
    running = prg32_perf_begin(&suite) == 0 && begin_case() == 0;
    if (!running) {
        finished = 2;
    }
}

static void stop(int how) {
    if (how == 2) {
        prg32_perf_abort();                /* frees the broker's memory; no result is kept */
    }
    running = 0;
    finished = how;
}

/* The workload of the current case (the "draw" part of a frame). */
static void workload(void) {
    seed = seed * 1664525u + 1013904223u;
    scroll = (scroll + 3) % 320;
    ball_x += ball_dx;
    ball_y += ball_dy;
    if (ball_x <= 0 || ball_x >= 308) ball_dx = -ball_dx;
    if (ball_y <= 24 || ball_y >= 188) ball_dy = -ball_dy;
    prg32_gfx_clear(current_case == 1 ? PRG32_COLOR_BLACK : 0x0008);
    prg32_gfx_text8(8, 8, case_name(current_case), PRG32_COLOR_WHITE, 0);
    prg32_gfx_rect(248, 8, (int)((frame_in_case + 1u) * 60u / FRAMES), 5, PRG32_COLOR_CYAN);
    if (current_case == 0) {
        for (int i = 0; i < 8; i++) {
            prg32_gfx_rect(10 + i * 7, 38 + i * 18, 300 - i * 22, 10, (i & 1) ? PRG32_COLOR_BLUE : PRG32_COLOR_MAGENTA);
        }
    } else if (current_case == 1) {
        for (int y = 32; y < 190; y += 8) {
            prg32_gfx_text8(8, y, "REGISTER TRACE  FRAME BUDGET  ABI PRG2", (y & 8) ? PRG32_COLOR_GREEN : PRG32_COLOR_CYAN, 0);
        }
    } else if (current_case == 2) {
        for (int i = 0; i < 36; i++) {
            int x = (int)((uint32_t)(i * 23) + frame_in_case * (uint32_t)(2 + (i & 3))) % 306;
            int y = 30 + (int)(((uint32_t)(i * 19) + (seed >> (i & 7))) % 150u);
            prg32_gfx_rect(x, y, 12, 12, (i & 1) ? PRG32_COLOR_RED : PRG32_COLOR_BLUE);
        }
    } else {
        int count = current_case == 3 ? 72 : 42;
        for (int i = 0; i < count; i++) {
            int x = (i * 37 + scroll * (1 + (i & 3))) % 320;
            int y = 28 + (int)(((uint32_t)(i * 17) + frame_in_case * (uint32_t)(i & 1)) % 125u);
            prg32_gfx_pixel(x, y, (i & 1) ? PRG32_COLOR_WHITE : PRG32_COLOR_CYAN);
        }
        for (int y = 152; y < 200; y += 9) {
            for (int x = -(scroll % 44); x < 320; x += 44) {
                prg32_gfx_rect(x, y, 20, 2, PRG32_COLOR_YELLOW);
            }
        }
        if (current_case == 4) {
            prg32_gfx_rect(ball_x, ball_y, 12, 12, PRG32_COLOR_RED);
            prg32_gfx_text8(8, 136, "MIXED GAMEPLAY", PRG32_COLOR_WHITE, 0);
        }
    }
}

void prg32_evaluation_init(void) {
    prg32_gfx_set_fullscreen(1);
    start_suite();
}

void prg32_evaluation_update(void) {
    update_start = prg32_perf_now_us();
    if (running) {
        scroll = (scroll + 1) % 320;          /* the "game logic" of the workload */
    }
    update_end = prg32_perf_now_us();
}

void prg32_evaluation_draw(void) {
    if (!running) {
        prg32_gfx_clear(PRG32_COLOR_BLACK);
        prg32_gfx_text8(24, 100, finished == 1 ? "EVALUATION COMPLETE" : "EVALUATION ABORTED",
                        finished == 1 ? PRG32_COLOR_GREEN : PRG32_COLOR_YELLOW, 0);
        return;
    }
    uint64_t draw_start = prg32_perf_now_us();
    workload();
    uint64_t draw_end = prg32_perf_now_us();
    uint64_t present_start = prg32_perf_now_us();
    prg32_gfx_present();
    uint64_t present_end = prg32_perf_now_us();

    prg32_perf_sample_t sample;
    sample.abi_version = PRG32_PERF_ABI_VERSION;
    sample.struct_size = sizeof(sample);
    sample.frame_index = frame_index;
    sample.update_us = (uint32_t)(update_end - update_start);
    sample.draw_us = (uint32_t)(draw_end - draw_start);
    sample.present_us = (uint32_t)(present_end - present_start);
    sample.frame_total_us = (uint32_t)(present_end - update_start);
    sample.input_mask = 0;
    if (prg32_perf_record(&sample) != 0) {
        stop(2);
        return;
    }
    ++frame_in_case;
    ++frame_index;
    if (frame_in_case == FRAMES) {
        if (prg32_perf_case_end() != 0) {
            stop(2);
            return;
        }
        ++current_case;
        if (current_case == CASES) {
            stop(prg32_perf_end() == 0 ? 1 : 2);   /* the broker now holds the suite's summary */
        } else if (begin_case() != 0) {
            stop(2);
        }
    }
}
