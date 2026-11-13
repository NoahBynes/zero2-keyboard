# 路线 1A（零代码）：Pico W + HID Remapper（Bluetooth Classic 预发布固件）

如果只想**最快把 Zero 2 变成自定义键盘**、不打算自己写固件，这是目前成本最低、步骤最少的外挂 dongle 路线：
用树莓派 **Pico W / Pico 2 W** 当「蓝牙经典 HID 主机 + USB HID 键盘」，映射在 Chrome 网页里配置，不用写代码、不用装工具链。

> 状态：HID Remapper 的 Pico W 蓝牙经典版本是 **2026-08 开始的实验性版本**（作者在论坛明说「不能保证会进正式版」），
> 2026-11-06 发布了 pre-release。作者实测设备列表里**明确包含 8BitDo Zero 2**。
> 若追求稳定/可维护，用同目录的 ESP32+CH9329 自写固件（[`../README.md`](../README.md)）。

参考：
- HID Remapper 主仓库：<https://github.com/jfedor2/hid-remapper>
- 项目手册：<https://www.remapper.org/manual/>
- 蓝牙经典 Pico W 版发布帖（作者亲测 Zero 2）：<https://forum.remapper.org/t/bluetooth-classic-on-pico-w-2026-edition/359>
- 预发布固件：<https://github.com/jfedor2/hid-remapper/releases/tag/r2026-11-06-test1>

---

## 1. 为什么是 Pico W

| 能力 | 为什么必须 |
|---|---|
| 蓝牙**经典** BR/EDR 主机 | Zero 2 手柄模式是 BR/EDR（Switch/Windows/Android/macOS 模式都是）；ESP32-S3/C3 这类 BLE-only 芯片连不上 |
| USB 设备（HID 键盘） | RP2040 有原生 USB device，Pico W 可以直接插到 PC/iPad，被识别为标准键盘 |
| 便宜、好买 | Pico W 官方约 ¥60–75，国产克隆约 ¥25–35；Pico 2 W 稍贵 |

> 备选：自写固件也可以走 Pico W（Bluepad32 Pico SDK 示例已经是 `pico_btstack_classic`，再加 TinyUSB HID 键盘即可），
> 但工作量和风险都比「刷现成固件」大，本仓库不提供该版本源码，只给路线（见文末）。

---

## 2. 物料

- Raspberry Pi **Pico W**（或 Pico 2 W）一块，焊好排针或直接用（不需要额外外设）
- Micro-USB / USB-C 数据线（按板子型号）
- 目标主机：PC（Windows/macOS/Linux）或 iPad（USB-C 直连/转接）、Android（OTG）

不需要 CH9329、不需要焊接。

---

## 3. 烧录（约 5 分钟）

1. 下载预发布固件：
   - Pico W → `remapper_bt.uf2`
   - Pico 2 W → `remapper_bt_pico2_w.uf2`
   - 地址：<https://github.com/jfedor2/hid-remapper/releases/tag/r2026-11-06-test1>
2. 按住 Pico W 上的 **BOOTSEL** 键，再插 USB 到电脑，松开。
   电脑会出现一个名为 `RPI-RP2` 的 U 盘。
3. 把对应的 `.uf2` 文件拖进这个 U 盘。板子自动重启。
4. 板载 LED 状态含义（作者定义）：
   - **常亮**：正在配对（pairing mode）
   - **慢闪**：当前没有设备连接
   - **快闪 N 下**：已连接 N 台设备

> 这个版本**没有物理按键**，配对/遗忘设备都通过网页配置工具完成。

---

## 4. 配置映射（Chrome / Edge，WebHID）

1. 用 **桌面版 Chrome**（或基于 Chromium 的 Edge）打开 <https://www.remapper.org/config/>
2. 点 **Open device**，选择出现的 HID Remapper 设备。
3. Zero 2 进入 **Windows(X-input) 模式**（Start+X 开机）→ 长按 **Select 3 秒**进入快闪配对。
4. 在网页里点 **Pair new device**（或者「Actions」里同名按钮），等 Zero 2 和 Pico W 连上（LED 变成快闪 N 下）。
5. 设置：
   - **Emulated device type** = `Mouse and keyboard`（这样输出才是键盘；需要重启设备生效时网页会提示，拔插一次 Pico W）
   - **Input labels** = `gamepad`（Zero 2 会被当作手柄输入）
   - **Unmapped inputs passthrough**：建议关闭（否则手柄摇杆/方向可能被当鼠标移动，鼠标会乱飞）
6. 在 **Monitor** 标签里逐个按 Zero 2 的按钮，确认能看到对应的 gamepad 输入；用输入旁的 `+` 直接生成映射。
7. 按下面「默认绘图映射」建映射，写回设备：**Save to device**。
8. 把配置导出 JSON 备份（网页可导入导出），以后换设备/回滚方便。

### 默认绘图映射（建议先照抄，再按习惯改）

Zero 2 走 gamepad 模式时按钮按**位置**上报，而 Zero 2 实体是任天堂布局（A 在右、B 在下、X 在上、Y 在左），
所以在 HID Remapper 的 Monitor 里看到的「位置」和丝印的对应关系是：实体 A=Right，B=Bottom，X=Top，Y=Left。

| 实体按钮 | 映射到 | 用途 |
|---|---|---|
| 十字↑ | `[` | 笔刷变小 |
| 十字↓ | `]` | 笔刷变大 |
| 十字← | Ctrl + `[` | 图层下移（PS/CSP） |
| 十字→ | Ctrl + `]` | 图层上移 |
| 实体 A（右） | Ctrl+Z | 撤销 |
| 实体 B（下） | Ctrl+Shift+Z | 重做 |
| 实体 X（上） | 按住 Shift（两个映射：Shift 作为输出） | 约束/加选 |
| 实体 Y（左） | Space | 临时抓手 |
| L | 按住 Ctrl | 组合修饰 |
| R | 按住 Alt | 吸管/临时切换 |
| Select | Tab | 面板 |
| Start | Esc | 取消 |

> HID Remapper 的 map 规则是「输入 → 输出」一对多：一个按钮可以同时映射多个输出（组合键就靠这个，
> 例如 A 映射两条：`Left Control` + `Z` 就是 Ctrl+Z）。「按住」类动作直接映射到修饰键即可，按住手柄时修饰键保持按下。

---

## 5. 限制与风险

- **实验性 pre-release**：可能有断连、重连慢、某些设备识别不了的问题；不要用于关键工作流。
- 这一版只支持**蓝牙经典**输入（正是 Zero 2 需要的），不支持 BLE 设备。
- 不能作为 boot protocol keyboard（老 BIOS/引导层可能用不了），PC 系统内使用不受影响。
- 输出是 USB：**iPad 需要 USB-C 直连或转接**，不能无线连 iPad。
- 若系统不允许 WebHID/Chrome 无法打开设备：换 Edge，或用仓库里的命令行配置工具。
- 若 Zero 2 连不上：确认是 **Start+X**（gamepad 模式）而不是 R+Start（键盘模式）；先点「Forget all devices」再配对。
- 作者只说了测过 Zero 2，**没写是哪种模式**；如果 Windows 模式连不上，换 Switch（Start+Y）/ Android（Start+B）/
  macOS（Start+A）模式再试——它们都是经典 HID 手柄，HID Remapper 只关心 HID 报告。

---

## 6. 备选：自己写 Pico W 固件（不推荐作为第一选择）

Pico W 官方 SDK 的 Bluepad32 示例已经链接 `pico_btstack_classic`，能收 Zero 2 的手柄报告；
再按 Pico SDK 的 TinyUSB HID 键盘示例加一个 HID 描述符、把按键写成键盘报告即可。

- Bluepad32 Pico W 文档：<https://bluepad32.readthedocs.io/en/latest/plat_picow/>
- Bluepad32 Pico 示例源码：<https://github.com/ricardoquesada/bluepad32/tree/main/examples/pico_w>
- 关键改动：`pico_enable_stdio_usb(0)`（USB 让给 HID）+ `pico_enable_stdio_uart(1)`（用 UART 看日志）+ 链接 `tinyusb_device`/`tinyusb_board`；
  在 `my_platform_on_controller_data()` 里把 `uni_gamepad_t` 的按钮换成键盘报告发送。
- 工作量：熟悉 CMake/Pico SDK 的人约 1–2 天（含调试 HID 描述符）。

如果只是想「有固件可控、可改」，本目录的 ESP32+CH9329 方案（`../README.md`）代码量更小、环境更简单（Arduino IDE）。
