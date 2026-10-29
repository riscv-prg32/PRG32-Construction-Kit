# 第 10 课：在积木、Python、C 和汇编中使用你的素材

时间：约 40 分钟。只需要这个工具包（访客也可以）。规则见
[在游戏中使用项目素材](../project_art.md)。

## 1. 添加 Star Catcher

1. 在 **项目** 页的示例中找到 **Star Catcher (Blocks)**（标记为 *精灵和声音*），然后按 **添加**。
2. 打开它，按 **运行**（Shift+F10）。用方向键移动火箭，接住落下的星星。
3. 在项目文件中打开 **精灵 → rocket**。Sprite Lab 会在一个标签页中打开。

## 2. 改素材，不改代码

1. 在 Sprite Lab 中把火箭的头部涂成另一种颜色，然后按 **保存**。
2. 再按 **运行**：游戏画出了新的火箭。你没有改动任何积木。
3. 看看 Sprite Lab 中 **在游戏中使用** 下面。依次选择 **积木**、**PRG32 Python**、**C** 和
   **汇编**：同一个精灵，用四种语言来使用。

## 3. 读积木

**精灵和图块** 类别里有三个用于素材的积木：

```text
当游戏开始时：  加载背景 sky
每帧绘制：      绘制背景 sky
                绘制精灵 rocket x rocket_x y 160
                绘制精灵 star x star_x y star_y
```

背景只需加载一次，每帧先绘制背景，再在上面绘制精灵。按 **生成** 并打开 `game.c`：第 3 部分包含
由素材生成的 `rocket_draw`、`star_draw`、`sky_load` 和 `sky_draw`。

## 4. 同一个游戏的 PRG32 Python 版本

添加 **Star Catcher (Python)** 并打开 `game.py`。素材的名字写在引号里：

```python
def draw() -> None:
    prg32.background_draw("sky")
    prg32.sprite("rocket", rocket_x, ROCKET_Y)
    prg32.sprite("star", star_x, star_y)
```

把 `"star"` 改成 `"stars"` 并保存。问题面板会在那一行指出项目里没有这个名字的精灵。再改回来。

## 5. 同一个游戏的 C 版本

添加 **Star Catcher (C)**。`game.c` 的开头只有一行代表全部素材：

```c
#include "prg32_assets.h"
```

在项目文件中打开 **项目素材 → prg32_assets.h**：它是只读的，显示编译游戏时工具包写在这一行位置上
的代码。找到 `rocket_draw`、`ROCKET_WIDTH`、`sky_load`、`sfx_coin` 和 `TRACK_THEME`，再找出
`game.c` 在哪里使用它们。

## 6. 同一个游戏的汇编版本

添加 **Star Catcher (Assembly)**。它的那一行是 `#include "prg32_assets.S"`，素材像固件函数一样
被调用：

```text
la t0, rocket_x
lw a0, 0(t0)
li a1, ROCKET_Y
call rocket_draw
```

运行这四个游戏：它们画出的画面完全相同。

## 7. 自己试试

- 在 Sprite Lab 中画一个叫 `comet` 的新精灵并保存。在每个游戏里画出它：一个积木、一行
  `prg32.sprite("comet", ...)`、C 中的 `comet_draw(x, y);`、汇编中的 `call comet_draw`。
- 在 **背景** 中给 `sky` 加上有云的第二层。`绘制背景 sky` 会把它画在前面，图块 0 是透明的。
- 在 AudioStudio 中修改 **Coin** 声音。每个游戏都会播放新的声音。
