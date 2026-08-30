typedef struct {
    int x;          /* position */
    int y;
    int vx;         /* velocity */
    int vy;
    uint16_t w;     /* size */
    uint16_t h;
    uint16_t state; /* collision/status flags */
    uint8_t layer;
    uint8_t reserved;
} prg32_platform_actor_t;
