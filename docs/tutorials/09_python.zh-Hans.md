# 第 9 课：你的第一个 PRG32 Python 游戏

时间：大约 40 分钟。你只需要本工具（以访客身份也可以）。这门语言的说明在
[PRG32 Python](../python_language.md) 中。

## 1. 创建一个 Python 项目

1. 在 **项目** 页面上，按 **新建项目**。
2. 选择 **Python（PRG32 Python）**，命名为 `Catcher`，然后按 **创建**。
3. IDE 会打开 `game.py`：一个已经能运行的小游戏。按 **运行**（Shift+F10）。点击屏幕，用方向键移动
   黄色方块。

## 2. 读一读这三个函数

- `init()` 在游戏开始时运行一次。
- `update()` 每一帧都运行：它读取按钮，让东西移动。
- `draw()` 每一帧在 `update()` 之后运行：它负责画屏幕。

把鼠标停在 `prg32.rect` 上，可以读到它的作用。在新的一行输入 `prg32.`，然后按 **Ctrl+Space**，就能
看到 PRG32 提供的所有内容。

## 3. 加一颗下落的星星

在开头 `score` 的下面加两个变量：

```python
star_x: int = 100
star_y: int = 0
```

在 `update()` 中，`global` 那一行列出了 `update()` 会修改的每一个外部变量。让它也列出星星，然后让
星星往下落：

```python
    global player_x, star_x, star_y, score
    star_y += 2
    if star_y > prg32.SCREEN_H:
        star_y = 0
        star_x = prg32.random(0, 304)
```

在 `draw()` 中把它画出来：`prg32.rect(star_x, star_y, 8, 8, prg32.WHITE)`。按 **运行**。

## 4. 接住它

还是在 `update()` 中：

```python
    if prg32.touching(star_x, star_y, 8, 8, player_x, player_y, 16, 16):
        score += 1
        star_y = 0
        prg32.note(72, voice=1, ms=80)
```

在 `draw()` 中显示分数：`prg32.number(score, 8, 24, prg32.YELLOW)`。

## 5. 故意犯个错

写 `star_y = star_y / 2`，然后稍等一下：编辑器会在 `/` 下面画线，并告诉你 PRG32 的数都是整数。把它
改成 `//`。现在在新的一行写 `while True:`：编辑器会解释为什么循环必须用 `for i in range(...)`。再把
它删掉。

## 6. 看看 C 和汇编

按 **生成**（Ctrl+Shift+G）。在 **生成的文件（只读）** 中打开 `game.c` 和 `game.S`。找到你的
`star_y += 2`：上面的注释写着 `Step "change star_y by 2"`，C 语句是 `star_y += 2;`。在汇编中，
同一步是一次加载、一条 `addi` 和一次保存，每一条都有解释。

## 7. 调试一行代码

打开 **调试** 标签页，按 **运行**。在 **game.py** 中点击 `score += 1` 的行号。接住一颗星星：游戏会
在那一行停下。看看 **变量**，然后按 **下一行 Python**。按 **继续** 接着玩。

## 给老师

- 本工具从不运行学生的 Python：它会被读取，按 PRG32 Python 的规则检查，翻译成和积木相同的 IR，
  然后再变成带解释的 C 和汇编。
- 同一个 game.py 总是得到逐字节完全相同的 C、汇编和卡带，无论界面使用哪种语言。
- Python 项目始终是 Python 项目：保存操作不能把它变成积木、C 或汇编。想比较不同语言，可以根据同样
  的想法新建一个 C 项目，或者打开生成的 C。
