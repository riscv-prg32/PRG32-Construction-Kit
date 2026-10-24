# 第 5 课：老师的实验课流程

目标：组织一次 45 分钟的课堂活动。

## 准备

1. 启动 PRG32-Construction-Kit。使用 Docker（`docker compose up -d --build`）时，
   卡带构建开箱即用。上课前用下面的命令检查一下：
   `docker compose exec prg32-construction-kit python tools/check_build.py --students 10 --windows 2`
   （参见 `../install_cartridge_build.md`）。
2. 可选：启动 Cartridge Store。
3. 可选：连接一台 PRG32 设备，或者准备好 QEMU。
4. 检查学生能打开这个网页应用。

## 0-5 分钟：演示

展示起始项目。在模拟器中移动玩家方块。

## 5-20 分钟：学生动手

学生修改：

- 玩家的颜色；
- 玩家的速度；
- 起始位置；
- 标题文字。

## 20-30 分钟：讨论生成的 C

学生点击 **生成**，打开 **生成的文件（只读）** 中的 `game.c`，找到某个积木生成的 C 语句。年级较高的
学生打开旁边的 `game.S`，在汇编中找到同一个积木：它的注释显示对应的 C 语句，每条指令都说明了它做什么
（参见 `../generated_code.md`）。`game.py` 用 PRG32 Python 显示同样的积木。

## 30-40 分钟：精灵和制品

学生画一个精灵，把它转换为 C，然后下载制品。
如果有 PRG32 电路板或 QEMU，学生点击 **编译**，从 **构建** 标签页下载，并加载自己的 PRG32 卡带。

## 40-45 分钟：反思

问一问：

- 哪个积木改变了一个变量？
- 它变成了哪条 C 语句？
- 哪些 RISC-V 指令做了同样的工作？
- 在使用硬件之前，模拟器为什么有帮助？
- 和生成的 C 相比，`.prg32` 卡带里面有什么？

## 接下来：关于经典游戏的单元

`examples/games/` 中的五个完整游戏各有一节 90-120 分钟的课和一套幻灯片（`docs/tutorials/games/`，
幻灯片在 `/docs/presentations/<game>.html`）。Pong 介绍游戏循环和碰撞；Breakout 介绍列表；
Space Invaders 介绍图片和对象池；Asteroids 介绍定点数物理；Snake 介绍图块和环形缓冲区。每套
幻灯片最后都有练习和一个检查理解的问题。
