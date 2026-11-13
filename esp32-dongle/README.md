# Zero 2 → 自定义 USB 键盘：外挂 dongle（实现 + 步骤）

本目录给出外挂 dongle 路线的**可编译实现**与选购/接线/烧录/配对说明。

```
8BitDo Zero 2  ──蓝牙经典(BR/EDR, gamepad 模式)──▶  ESP32(原版)  ──UART──▶  CH9329  ──USB HID 键盘──▶  PC / iPad / Android / …
```

> 顶层调研结论、各路线对比、主机端软件改键矩阵见
> [`../research/alternatives/README.md`](../research/alternatives/README.md)。
> 零代码快速验证路线（Pico W + HID Remapper 预发布固件）见 [`picow/README.md`](picow/README.md)。

---

## 1. 为什么是「ESP32 原版 + CH9329」

三个硬约束决定了这个组合：

| 约束 | 事实 | 结论 |
|---|---|---|
| Zero 2 手柄模式是**蓝牙经典**（BR/EDR） | Bluepad32 官方支持列表把 8BitDo 全系标为 BR/EDR，并在 FAQ 写明：ESP32-S3/C3/C5/C6/H2 **不支持 BR/EDR**，连 DualSense/Switch 都连不上，要 BR/EDR 手柄请用 ESP32 原版或 Pico W | ESP32-S3/C3 SuperMini **不能**做本路线的主机；Zero 2 手柄模式只能由 ESP32 原版 / Pico W 这类支持经典蓝牙的芯片接 |
| 需要输出 **USB HID 键盘** | ESP32 原版没有 USB-OTG（不能当 USB 设备）；ESP32-S3 有 USB-OTG 但没有 BR/EDR | ESP32 原版 + 外部 USB HID 芯片（CH9329），或 Pico W 单板（RP2040 原生 USB） |
| 便宜、国内好买 | CH9329 是沁恒的「串口转 USB 键盘鼠标」芯片，模块 ¥10–20，免驱、免配置，主机看到的就是标准 USB 键盘 | 总成本 ≈ ¥30–45 |

更细的板卡对比见 [`../research/alternatives/README.md`](../research/alternatives/README.md#板卡对比)。

---

## 2. 物料清单（BOM）

| 物料 | 说明 | 参考价（RMB） |
|---|---|---|
| ESP32 原版 DevKit | 必须**原版 ESP32**（ESP32-WROOM-32 / ESP32-DevKitC），**不要** S3/C3/C6 | ¥18–30 |
| CH9329 模块 | 串口转 USB HID 键盘/鼠标，带 USB-A 公头或 Type-C 版本均可，需要引出 VCC/GND/TXD/RXD 四针 | ¥10–20 |
| USB 线 ×2 | 一根给 ESP32 供电+串口调试（Micro-USB/Type-C 看板子），一根给 CH9329 接目标主机 | 手边一般有 |
| 杜邦线 4 根 | 3.3V TTL 串口，母对母即可（视模块排针） | ¥2 |

> CH9329 模块**不需要**改固件/配置，出厂默认工作模式即可用。它的 USB 端是「键盘+鼠标」复合 HID 设备，VID:PID 默认 `1a86:e129`；在 iPad/Android 上即使鼠标部分不被识别，键盘部分仍可用。

---

## 3. 接线

```
ESP32 DevKit                      CH9329 模块（UART 侧）
  3V3  ──── 可选，一般不用 ────     VCC   ← 建议接 ESP32 的 5V(VIN) 或 3V3（按模块丝印，常见 3.3–5V）
  GND  ────────────────────────    GND
  GPIO17 (TX2) ────────────────    RXD
  GPIO16 (RX2)  ◀──────────────    TXD   （本固件不解析回包，可不接）
```

- CH9329 的 **USB 口插到目标主机**（PC / iPad 的 USB-C 转接 / Android OTG）。
- ESP32 的 USB 口接**调参电脑**（供电 + 看串口日志；也可以接同一个 PC，主机看到的键盘来自 CH9329，不冲突）。
- 两个板子必须**共 GND**。
- CH9329 的 TXD 是 3.3V TTL，可直连 ESP32；若模块标 5V TTL，请串 1kΩ 或确认模块电平后再接。

---

## 4. 软件：编译与烧录

### 4.1 安装 Arduino 环境

1. 安装 **Arduino IDE 2.x**（<https://www.arduino.cc/en/software>）。
2. 文件 → 首选项 → 附加开发板管理器网址，加入**两个**索引：
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   https://raw.githubusercontent.com/ricardoquesada/esp32-arduino-lib-builder/master/bluepad32_files/package_esp32_bluepad32_index.json
   ```
3. 开发板管理器里安装：
   - `esp32`（Espressif 官方，3.x）
   - `esp32_bluepad32`（Bluepad32 作者提供的板包）
4. 开发板选择：`ESP32 + Bluepad32 Arduino` → 你的板子，常用 `ESP32 Dev Module`。
   - Flash Size: `4MB`；Partition Scheme 默认即可
   - Upload Speed: 921600（不稳定就降到 115200）

### 4.2 打开工程

`zero2_kb_dongle/` 就是 Arduino sketch 工程：

```
zero2_kb_dongle/
├── zero2_kb_dongle.ino   # 主固件
└── mapping.h             # 由 mapping.example.json 生成的映射表
```

用 Arduino IDE 打开 `zero2_kb_dongle.ino`，选择正确串口后点「上传」。

### 4.3 改映射（两种方式）

**方式 A：改 JSON（推荐，可读性好）**

```bash
cd zero2-keyboard/esp32-dongle/arduino
python tools/gen_mapping.py mapping.example.json --out zero2_kb_dongle/mapping.h
```

- 复制 `mapping.example.json` 为 `my_mapping.json`，改每个按钮的 `mods` / `key`；
- `key` 为 `null` 表示「只按住修饰键」（如 Shift/Ctrl/Alt），可和其它按钮叠加；
- 重新生成 `mapping.h` 后重新编译上传。
- 需要 Python 3.8+，只用标准库，不用装包。

**方式 B：直接改 `mapping.h`**

`kZero2Mapping[]` 里每行 `{ "id", "label", mod, key, "desc" }`，`key` 是 USB HID usage id（字母 A=0x04…Z=0x1D，`[`=0x2F，`]`=0x30，space=0x2C，tab=0x2B，esc=0x29……）。改完直接编译。

> 默认映射就是一套绘图快捷键（撤销/重做/笔刷大小/图层上下移/抓手/吸管/面板/取消），见 `arduino/mapping.example.json`。

### 4.4 默认映射一览（实体丝印）

按钮 id 按 **Zero 2 实体丝印** 命名（A 在右、B 在下、X 在上、Y 在左）；固件内部会把 Bluepad32 的位置语义换算成丝印语义。

| 按钮 | 输出 | 用途 |
|---|---|---|
| 十字↑ | `[` | 笔刷变小 |
| 十字↓ | `]` | 笔刷变大 |
| 十字← | Ctrl+`[` | 图层下移（PS/CSP） |
| 十字→ | Ctrl+`]` | 图层上移 |
| A | Ctrl+Z | 撤销 |
| B | Ctrl+Shift+Z | 重做 |
| X | 按住 Shift | 约束比例 / 加选 / Shift+`[` 柔化笔刷 |
| Y | 按住 Space | 临时抓手平移 |
| L | 按住 Ctrl | 组合修饰键 |
| R | 按住 Alt | 吸管（配合触笔点击）/ 临时切换 |
| Select | Tab | 显示/隐藏面板 |
| Start | Esc | 取消选择 / 退出变换 |

叠加生效的例子：按住 X（Shift）+ 十字↑（`[`）= `Shift+[`；按住 R（Alt）+ 触笔点击 = Photoshop 吸管。

---

## 5. 使用：配对流程

1. 把 CH9329 的 USB 插入目标主机（PC/iPad/Android），确认主机识别到「USB 键盘」（PC：设备管理器 → 键盘）。
2. ESP32 上电，串口 115200 能看到 `等待 Zero 2`，板载 LED 慢闪 = 未连接。
3. **Zero 2 进入 Windows(X-input) 模式**：按住 **Start + X** 开机（LED 闪 2 下/循环）。
4. **进入配对**：按住 **Select 3 秒**，LED 快闪。
5. 等几秒，dongle 自动连上（Bluepad32 自动扫描并连接）：串口打印 `已连接`，LED 常亮。
6. 在主机记事本/文本编辑器里按各个按钮，确认输出与映射一致。
7. 以后：Zero 2 按一下 **Start** 开机即自动回连 dongle。

> 换回 iPad/PC 直连时，需要重新走一次宿主机的配对；想让 Zero 2「忘掉」dongle，可在手柄连上 dongle 后长按 **L + R + Select 3 秒**（固件里实现的清除配对组合），再按 Select 3 秒重新配对。
>
> 其他 gamepad 模式（Switch = Start+Y，Android = Start+B，macOS = Start+A）也能连，只是按钮位置语义相同，映射照旧。

---

## 6. 延迟预估

| 环节 | 典型值 | 说明 |
|---|---|---|
| Zero 2 → 主机（直连） | 15–30 ms | 蓝牙经典 HID 常见量级 |
| Zero 2 → ESP32（BR/EDR） | 15–30 ms | 同上，Bluepad32 事件驱动 |
| ESP32 处理 + CH9329（9600 默认） | 5–20 ms | 一个 14 字节帧在 9600 下约 15 ms |
| CH9329 → 主机 USB HID | < 2 ms | USB 全速 1 ms 轮询 |
| **合计（9600）** | **约 25–50 ms** | 快捷键场景完全够用 |
| **合计（CH9329 改 115200）** | **约 20–35 ms** | 需用 WCH 工具改模块波特率并同步改固件宏 |

> 以上为数量级估算，未在真机上实测。对「画图快捷键」这类操作，20–50 ms 无感；对格斗/音游级别操作不适用。

---

## 7. 故障排查

| 现象 | 排查 |
|---|---|
| 串口一直 `等待 Zero 2` | Zero 2 是不是 gamepad 模式？（R+Start 是键盘模式，不收）；确认按住 Select 3 秒进入了快闪配对；断电重来；实在不行长按 L+R+Select 3 秒清配对后重试 |
| 连上但主机没反应 | CH9329 的 USB 是否插好、是否被识别为键盘；先拔插 CH9329；确认 TX→RXD、GND 共地；串口日志里是否有 `mask=... mod=... keys=...` 变化 |
| 按钮对应关系反了（A/B、X/Y） | 这是任天堂/微软布局差异；本固件已按 Zero 2 丝印换算，若你换了别的手柄需改 `readButtons()` 里的换算 |
| 出现「粘键」 | 断开手柄时固件会发全 0 报告松键；若仍异常，拔插 CH9329 或重启 dongle |
| 主机把 dongle 认成鼠标 | CH9329 是键盘+鼠标复合设备，正常；不影响键盘功能 |
| 想换 CH9329 波特率 | 用 WCH 的 `CH9329 配置工具` 把「串口通信波特率」改成 115200，再把 `zero2_kb_dongle.ino` 里 `CH9329_BAUD` 改成 115200 |

---

## 8. 已知边界

- **只输出 USB 键盘**：iPad 需要 USB-C 转接/直连，优点是任何 app 都能用（走系统键盘快捷键），缺点是有线。
- 这套 dongle 不修改 Zero 2 本身的固件，Zero 2 在 dongle 眼里就是一只普通蓝牙手柄；不刷机、无风险。
- CH9329 是固定 HID 描述符的成品芯片，不能自定义键盘厂商/设备名；能输出标准键盘按键 + 组合键，够用。
- 6 键无冲（标准 HID boot keyboard 限制），对本用途足够。
- ESP32 原版 + Bluepad32 的配对信息存在 NVS，换 dongle 固件/清 flash 会丢配对，重新按 Select 3 秒配对即可。
