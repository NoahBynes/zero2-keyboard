# 8BitDo Zero 2 → 自定义键盘：现实路线调研与选型

> 任务：Zero 2（无有线数据模式；键盘模式键位固定不可改）如何输出「自定义键盘」。
> 本文覆盖三条现实路线（**外挂 dongle**、**主机端软件改键**、**换 8BitDo Micro**），
> 给出硬件选型、接线、配对、延迟、成本/工期与可编译实现。
>
> 交付代码：
> - dongle 固件（ESP32 原版 + CH9329，Arduino）：[`../../esp32-dongle/`](../../esp32-dongle/README.md)
> - 零代码 dongle 路线（Pico W + HID Remapper）：[`../../esp32-dongle/picow/`](../../esp32-dongle/picow/README.md)
> - Windows 零成本改键（AutoHotkey v2）：[`../../windows/`](../../windows/README.md)
>
> 硬件拆解/键盘模式协议、固件逆向由队友负责（`research/hardware`、`research/firmware`），
> 本文凡是引用「推断/待实测」的地方都已标注证据等级。

---

## 0. 结论速览（TL;DR）

| # | 路线 | 一句话结论 | 成本 | 工期 | 推荐度 |
|---|---|---|---|---|---|
| 1A | **Pico W + HID Remapper**（Bluetooth Classic 预发布固件，零代码） | 唯一「不写代码、单板、支持经典蓝牙、USB HID 键盘输出」的现成方案；作者已实测 8BitDo Zero 2 | ¥25–75 | 0.5–2 h | ★★★★★（最快验证） |
| 1B | **ESP32 原版 + CH9329 + 自写固件**（本仓库交付） | 完全可控、可自己改映射、不依赖预发布固件；多一个 USB HID 芯片 | ¥30–45 | 3–6 h | ★★★★☆（长期/可控） |
| 1C | Pico W + 自写固件（Bluepad32 + TinyUSB HID） | 单板、可控，但 Pico SDK 环境与 HID 调试工作量最大 | ¥25–75 | 1–2 天 | ★★★（极客向） |
| 1D | 直接当 BLE/经典 HID host 收键盘模式 scancode 再重发 | 理论可行（esp_hidh / Bluepad32 keyboard），但零 2 键盘模式协议未最终确认 + 键盘 API 是 beta，不划算 | ¥20–75 | 1–2 天 | ★★（备选） |
| 2 | **主机端软件改键**（Windows AHK/PowerToys、macOS Karabiner、Linux input-remapper/keyd、Android Key Mapper） | 零成本、立即可用；但**只能作用于那一台主机**，换设备/换系统就失效；Windows 无法按设备区分，必须配开关 | ¥0 | 0.5–2 h | ★★★（先救急 Windows） |
| 3 | **买 8BitDo Micro 替代** | 官方支持「键盘模式 + 手机精英软件自定义单键/组合键 + 蓝牙/有线」，是**最省事**的答案；代价是 ¥99–149 | ¥99–149 | 10–30 min | ★★★★★（不折腾首选） |

**最终建议**：
1. 目标设备是 **iPad** 且预算 ~¥100：直接买 **Micro**（官方支持键盘模式自定义映射，蓝牙/有线都能当键盘）。
2. 必须复用 Zero 2、要「即插即用的 USB 键盘、任何主机都能用」：**Pico W + HID Remapper**（先验证），不稳定再换 **ESP32 + CH9329**（本仓库固件，长期可控）。
3. 只在 Windows 上用、且绘图软件支持改快捷键：先试 **AHK 脚本**（¥0），不够再上 dongle。
4. **不要**选 ESP32-S3 / ESP32-C3 SuperMini 做 dongle 主机：它们只有 BLE，没有蓝牙经典（BR/EDR），
   Zero 2 的手柄模式连不上（见 §1.1 的硬约束）。

> 补充：**设备侧改固件**这条路由队友在 `research/firmware` 独立评估（Zero 2 固件无签名校验、
> 理论上可劫持官方更新器刷入重加密的自定义固件，但需要刷写实验和失败恢复手段，且要改固件二进制）。
> 它不在本文的对比/实现范围内；如果后续刷固件路线验证成功，「发送端直接输出自定义键」会是成本最低的终局方案。

---

## 1. 外挂 dongle 路线（重点）

### 1.1 先明确硬约束（这决定了板卡选型）

**事实 1：Zero 2 的手柄模式是蓝牙经典（BR/EDR），不是 BLE。**
Bluepad32 官方支持列表把 8BitDo 全系列标为 `BR/EDR`（测试机型含 Zero 2），
官方 FAQ 更是直接写明：*"Only the original ESP32 chip supports Bluetooth Classic (BR/EDR).
ESP32-S3, ESP32-C3, ESP32-C5, ESP32-C6, and ESP32-H2 do not support BR/EDR...
Use an original ESP32 or a Pico W to connect BR/EDR controllers."*
（[Bluepad32 FAQ](https://bluepad32.readthedocs.io/en/latest/FAQ/)、
[Supported gamepads](https://bluepad32.readthedocs.io/en/latest/supported_gamepads/)）

**事实 2：Zero 2 没有有线数据模式，USB 口只能刷固件。**
官方 FAQ 原文：*"可以有线使用吗？不可以，有线连接只能用来升级固件。"*
（[Zero 2 常见问题](http://support.8bitdo.cn/faq/zero2.html)）
→ 所以「用线直接插电脑当键盘」不存在，必须靠蓝牙接收 + 转成 USB/其它协议。

**事实 3：键盘模式（R+Start）固定输出一套小写字母，不可改。**
官方说明书只说「键盘模式下所有按键输出皆为键盘英文字符」；社区实测/整理出的键位是
`上=C 下=D 左=E 右=F；A(右)=G B(下)=J X(上)=H Y(左)=I；L=K R=M Select=N Start=O`
（见附录 A 与 [`../../windows/README.md`](../../windows/README.md)）。
→ 想「自定义」只有两条路：**在接收端重映射**（本路线）或**在发送端改固件**（队友在评估）。

**事实 4：要输出 USB HID 键盘，芯片必须有 USB Device 能力。**
- ESP32 原版：有 BR/EDR，但**没有 USB OTG** → 不能直接当 USB 键盘，需要外挂 USB HID 芯片（CH9329），或换 Pico W。
- ESP32-S3：有 USB OTG（能当 USB 键盘），但**只有 BLE，没有 BR/EDR** → 收不了 Zero 2 手柄模式。
- ESP32-C3：既没有 BR/EDR，也没有完整 USB OTG（只有 USB Serial/JTAG）→ 两条都不行，**直接排除**。
- Pico W / Pico 2 W：CYW43 支持经典蓝牙（Bluepad32 的 Pico 平台明确链接 `pico_btstack_classic`），
  RP2040 有原生 USB Device → **单板即可完成「经典蓝牙主机 + USB HID 键盘」**。

> 这一条是很多网上教程没讲清的坑：看到「ESP32-S3 自带 USB，能当键盘」就以为可以，
> 但 Zero 2 根本不是 BLE 手柄，S3 连不上它。

### 1.2 架构：dongle 到底转什么

两种输入接收方式，二选一：

| | 输入方式 | 需要 | 优点 | 缺点 |
|---|---|---|---|---|
| **A. 手柄模式（推荐）** | Zero 2 用 **Start+X**（Windows/X-input）等 gamepad 模式开机，dongle 当蓝牙经典 HID 主机收手柄报告 | 支持经典蓝牙的主机（Pico W / ESP32 原版）+ Bluepad32 或 HID Remapper | Bluepad32 对 8BitDo Zero 2 有**官方支持**（明确列在测试机型里）；gamepad API 稳定、文档全；按键可按实体丝印精确定义 | 需要重新配对；Zero 2 不再以「键盘」身份出现（但输出端是键盘，目的达到） |
| **B. 键盘模式** | Zero 2 用 R+Start 键盘模式，dongle 收 HID 键盘 scancode（c~o）再重映射 | 同左，但需要 HID host 解析键盘报告 | 保留键盘模式，映射表就是「字母→快捷键」 | Zero 2 键盘模式是 BLE 还是经典 HID **尚未最终确认**（队友 hw-re 在查）；若为 BLE，S3 也行但需要另一套 BLE HID host 代码；Bluepad32 的键盘支持是 **beta**（[Supported keyboards](https://bluepad32.readthedocs.io/en/latest/supported_keyboards/)） |

**本仓库的固件实现走 A（手柄模式）**：不依赖尚未确认的键盘模式协议，且 Bluepad32 明确支持 Zero 2。
映射表按**实体丝印**命名，固件内部完成任天堂布局 → Xbox 位置语义的换算（细节见
[`../../esp32-dongle/README.md`](../../esp32-dongle/README.md)）。

### 1.3 方案 1A：Pico W + HID Remapper（零代码，最快）

HID Remapper 是开源的「可编程 HID 转接器」：输入 HID 设备（键鼠/手柄），输出 USB 键盘/鼠标/手柄，
配置在 Chrome 网页里完成、存在板子上。主仓库：
<https://github.com/jfedor2/hid-remapper>，手册：<https://www.remapper.org/manual/>。

关键点：
- 官方 BLUETOOTH.md 的 nRF52840 蓝牙版**只支持 BLE**（不是经典）——所以**不要**买 nRF52840 板。
- 作者 2026-08 起在 `dev` 分支做了**Pico W 蓝牙经典版**，2026-11-06 发布 pre-release，
  帖子里列出的已测设备**包含 8bitdo zero 2**：
  <https://forum.remapper.org/t/bluetooth-classic-on-pico-w-2026-edition/359>
- 固件文件：`remapper_bt.uf2`（Pico W）、`remapper_bt_pico2_w.uf2`（Pico 2 W）：
  <https://github.com/jfedor2/hid-remapper/releases/tag/r2026-11-06-test1>
- 输出：USB 键盘/鼠标（可被 PC/iPad/Android 当标准 HID 键盘）；配置用 WebHID（桌面版 Chrome/Edge）。

步骤、映射表、LED 状态、限制都写在 [`../../esp32-dongle/picow/README.md`](../../esp32-dongle/picow/README.md)。
**风险**：实验性 pre-release，可能断连/不稳定，作者也没承诺会进正式版 → 适合先花半小时验证，别当唯一方案。

### 1.4 方案 1B：ESP32 原版 + CH9329 + 自写固件（本仓库实现，推荐长期用）

> **先澄清 Bluepad32 的能力边界**（任务里点名要查的）：
> - Bluepad32 是**输入侧**（Bluetooth HID **host**）：把手柄/键盘/鼠标收进来，给应用读；
>   它**本身不提供 USB HID 输出**。所谓「Bluepad32 支持键盘」指的是**接收**键盘输入
>   （`ctl->isKeyboard()`，把键盘当控制器用），不是把东西**输出成**键盘。
> - 所以「Bluepad32 支持 ESP32-S3 的 USB HID 输出吗」的答案是：**不支持**（它没有输出功能），
>   而且 ESP32-S3 没有 BR/EDR 连 Zero 2 手柄模式都收不到（[FAQ](https://bluepad32.readthedocs.io/en/latest/FAQ/)）；
>   要 USB HID 输出必须自己在上面加 TinyUSB（S3/Pico W）或外挂 CH9329（ESP32 原版）。
> - 「能不能改成键盘」：可以，但正确姿势是「Bluepad32 收输入 + 自己写映射 + 另加 USB HID 输出」，
>   即本方案；不要指望配置一下 Bluepad32 就变成键盘 dongle。
> - 顺手排除几个常见误解：Arduino 的 `ESP32-BLE-Keyboard` 类库是**反方向**（把 ESP32 变成 BLE 键盘外设，
>   不是收手柄）；ESP-IDF 官方的 `esp_hidh` 是 HID **host**（BLE/经典都支持），能力对，但还要自己接
>   Zero 2 的按键数据 + 加 USB HID 输出，工作量不比本方案小。

```
Zero 2 --(经典蓝牙 gamepad)--> ESP32 原版 --UART 9600--> CH9329 --USB HID 键盘--> 主机
```

- 输入：Bluepad32（Arduino 板包）对 8BitDo Zero 2 官方支持；Zero 2 用 **Start+X** 开机。
- 转换：`mapping.h`（由 `mapping.json` 生成）定义「按钮 → HID 修饰键 + 键码」，按住类动作用修饰键实现。
- 输出：CH9329 串口转 USB HID 键盘芯片，主机看到的是一只标准 USB 键盘，免驱。
- 成本：ESP32 原版 DevKit ¥18–30 + CH9329 模块 ¥10–20 ≈ **¥30–45**。
- 工期：接线 20 min + Arduino 环境 30–60 min + 配对调试 1–2 h。
- 优点：映射表在本地，想怎么改怎么改；不依赖第三方预发布固件；单条 USB 出去就是键盘。
- 缺点：多一块板/四根线；CH9329 默认 9600 波特率带来 ~15 ms 串口延迟（快捷键场景无感；
  可用 WCH 工具改 115200，延迟降到 ~1–2 ms，见 §1.10）。

完整 BOM、接线、编译烧录、配对、默认绘图映射、故障排查：
[`../../esp32-dongle/README.md`](../../esp32-dongle/README.md)。

### 1.5 方案 1C：Pico W + 自写固件（Bluepad32 + TinyUSB HID）

> 关于「Pico W 用 BTstack/CYW43 做 BLE HID 主机 + TinyUSB HID 键盘」的说法要修正一下：
> Pico W 的 CYW43439 和 Pico SDK 的 BTstack 集成**同时支持 BLE 和蓝牙经典**——Bluepad32 的
> Pico 示例 CMake 直接链接 `pico_btstack_classic`（见
> [plat_picow](https://bluepad32.readthedocs.io/en/latest/plat_picow/)）。但**只做 BLE HOGP 主机收不了
> Zero 2 手柄模式**（Classic），所以 Pico W 方案必须走「经典蓝牙主机」这条路径；
> TinyUSB HID 键盘部分则完全可行（Pico SDK 提供 `tinyusb_device`，写标准 boot keyboard 描述符即可）。
> HID Remapper 的 Pico W 经典蓝牙预发布固件（方案 1A）已经证明了「经典主机 + USB HID 输出」在 Pico W 上跑得通。

Pico W 是唯一「单板同时满足经典蓝牙 + USB HID」的便宜板子，自写固件的路径：

1. Pico SDK 2.3+ + Bluepad32（其 Pico 示例 CMake 已链接 `pico_btstack_classic`、`pico_cyw43_arch_none`）：
   <https://bluepad32.readthedocs.io/en/latest/plat_picow/>
2. 关掉 USB stdio（`pico_enable_stdio_usb(0)`、`pico_enable_stdio_uart(1)`），把 USB 让给 HID；
   链接 Pico SDK 的 `tinyusb_device` / `tinyusb_board`，加一份 boot keyboard HID 描述符。
3. 在 `my_platform_on_controller_data()` 里把 `uni_gamepad_t` 的按钮按映射表转成 8 字节键盘报告，
   用 `tud_hid_report()` 发出即可。
4. 工作量：熟悉 CMake/Pico SDK 的话 1–2 天（含 HID 描述符/枚举调试）。

适合「想单板、想全掌控、能接受 Pico SDK 门槛」的人；否则用 1A/1B 更省事。

### 1.6 方案 1D：直接收「键盘模式」的 scancode 再重发，是否更简单？

**现成库/项目盘点**（回答「BLE HID host 现成库」调研项）：

| 项目/库 | 角色 | 对本需求 |
|---|---|---|
| **Bluepad32** | ESP32/Pico W 的蓝牙 HID **host**（经典 + BLE），支持手柄/键盘/鼠标作为**输入** | 输入侧直接可用（Zero 2 在官方支持列表）；不提供 USB 输出，需搭配 CH9329/TinyUSB |
| **esp_hidh**（ESP-IDF 官方组件） | HID **host**，支持 BLE + 经典，带示例 `esp_hid_host` | 能力对，但还要自己写映射 + USB HID 设备端（TinyUSB），工作量偏大 |
| NimBLE（ESP-IDF） | BLE 协议栈 | 只提供 HOGP 底层，HID host 要自己实现，不如 esp_hidh |
| ESP32-BLE-Keyboard / BleKeyboard（Arduino） | ESP32 当 BLE **键盘外设**（输出侧） | **反方向**：不能收 Zero 2；但可作为「dongle 无线输出到 iPad」的进阶方向（本仓库未实现） |
| CH9329（沁恒芯片） | UART → USB HID 键盘/鼠标 | 本仓库的输出侧方案，免驱、免配置 |
| **HID Remapper** | 完整成品固件：USB→USB，以及（Pico W 预发布）蓝牙经典→USB | 方案 1A 直接用 |

**结论：理论上可以，但作为首选不划算。** 分析：
- 如果 Zero 2 键盘模式是**经典 HID**：
  - ESP32 原版可以用 Bluepad32 的键盘支持收（`ctl->isKeyboard()` + `ctl->isKeyPressed(KeyboardKey)`，
    [Arduino API](https://bluepad32.readthedocs.io/en/latest/programmers_guide_arduino/)），
    再按 c~o → 快捷键的映射表经 CH9329 发出。映射表比分发手柄模式更直观。
  - 但 Bluepad32 的键盘支持标为 **beta**，且官方「已测键盘」列表里没有 Zero 2 键盘模式。
- 如果 Zero 2 键盘模式是 **BLE HOGP**：
  - ESP32-S3（原生 USB OTG + BLE）单板就能做：ESP-IDF 的 `esp_hidh` 支持 HID host（BLE/经典都支持），
    USB 侧用 TinyUSB HID；或用 Bluepad32（BLE 键盘） + Arduino USB HID。
    路线更「现代」，但代码量、HID 描述符/配对（加密、bonding）细节更多，且依赖未确认的事实。
- 更省事的判断：**收手柄模式**有 Bluepad32 的官方支持兜底，出错概率低；收键盘模式目前是「赌协议 + beta API」。
- 另外，8BitDo 官方蓝牙接收器（USB 无线适配器）虽然能接 Zero 2（FAQ 写明支持），
  但它输出的是**手柄协议**（给 Switch/PC 用），不是键盘 → 帮不上「自定义键盘」。

> 备注：Zero 2 键盘模式到底走 BLE 还是经典 HID，等队友 hw-re 的硬件结论；
> 但对本仓库的 dongle 方案没有影响（我们走手柄模式）。

### 1.7 BlueRetro 为什么不是答案

BlueRetro（<https://github.com/darthcloud/BlueRetro>）是面向**复古/现役主机的多手柄转接器**：
输入是蓝牙手柄，输出是各主机（NGC/N64/PS1/PS2/Saturn/DC 等）的**有线手柄协议**；
它的蓝牙主机栈正是 Bluepad32。评价：

- 定位是「把手柄变成主机手柄」，不是「把手柄变成键盘」；没有「按键 → 任意键盘快捷键」的映射能力。
- 硬件通常围绕 ESP32-WROOM / 定制板，不是通用 USB HID 键盘 dongle。
- 唯一可借鉴的是它的平台适配和 Bluepad32 集成方式（也说明「ESP32 原版走经典蓝牙」是成熟路线）。
- 结论：**不适合直接满足本需求**，不推荐为了键盘功能专门做 BlueRetro 板。

### 1.8 板卡对比（国内好买、¥10–40 量级）

| 板卡 | 参考价 | 蓝牙经典 BR/EDR | USB Device（HID 键盘） | 能否单独做 dongle | 备注 |
|---|---|---|---|---|---|
| **ESP32 原版 DevKit**（ESP32-WROOM-32） | ¥18–30 | ✅ | ❌（无 USB OTG） | 需 + CH9329（¥10–20） | 与 CH9329 组合即本仓库方案；淘宝/立创都白菜价 |
| **Pico W**（RP2040 + CYW43439） | 官方 ¥60–75 / 克隆 ¥25–35 | ✅（Bluepad32 Pico 平台用 `pico_btstack_classic`） | ✅ 原生 USB Device | ✅ 单板 | 跑 HID Remapper 预发布固件零代码；自写固件需 Pico SDK |
| **Pico 2 W** | ¥50–80 | ✅ | ✅ | ✅ | 同上，性能更好 |
| ESP32-S3（含 ESP32-S3-Zero） | ¥20–40 | ❌ 只有 BLE | ✅ | ❌ 收不了 Zero 2 手柄模式 | 只有收 BLE 键盘模式（协议未确认）时才可能用 |
| ESP32-C3 SuperMini | ¥12–20 | ❌ | ❌（只有 USB Serial/JTAG） | ❌ | 两条硬约束都不满足，**直接排除** |
| nRF52840 板（Xiao/Feather） | ¥50–120 | ✅ 双模 | ✅ | 可跑 HID Remapper 官方蓝牙版，但官方版**只支持 BLE 输入** | Zero 2 手柄模式是经典 → 官方固件不适用；不推荐为了省钱买 |

> 价格以 2026-11 前期电商/评测站价格为量级参考（Zero 2 本站报价参考价 ¥99、京东 ¥79，
> [ZOL 产品页](https://detail.zol.com.cn/gamepad/index1370762.shtml)），实际以渠道为准。

### 1.9 接线与供电（汇总）

| 方案 | 接线 | 供电 |
|---|---|---|
| Pico W + HID Remapper | 无（单板，USB 直插主机） | USB 总线供电 |
| Pico W 自写固件 | 无（单板） | USB 总线供电 |
| ESP32 + CH9329 | ESP32 3V3/5V、GND、GPIO17(TX2)→CH9329 RXD、GPIO16(RX2)←TXD（可不接）；两板共 GND；CH9329 USB 接目标主机 | ESP32 用自身 USB 供电（也用于串口调试）；CH9329 由目标主机 USB 供电 |

- CH9329 是 3.3V TTL 串口，与 ESP32 直连即可；模块 VCC 常见 3.3–5V（看丝印）。
- ESP32 的 USB 与 CH9329 的 USB 可以插同一台 PC（一个供电/调试、一个当键盘），不冲突；
  若目标主机是 iPad，则 ESP32 用充电器/充电宝供电，CH9329 接 iPad。
- 电池：Zero 2 自身 180 mAh / 约 8 小时；dongle 由 USB 供电，不用额外电池。

### 1.10 延迟预估

| 环节 | 典型量级 | 说明 |
|---|---|---|
| Zero 2 → 蓝牙主机（直连） | 15–30 ms | 蓝牙经典 HID 常见量级（手柄/键盘类设备） |
| Zero 2 → Pico W（BR/EDR，HID Remapper） | 15–30 ms | 同上；HID Remapper USB 侧 1000 Hz 轮询（<1 ms） |
| Zero 2 → ESP32（BR/EDR，Bluepad32） | 15–30 ms | 同上 |
| ESP32 → CH9329（默认 9600 8N1） | 5–20 ms | 14 字节帧 ≈ 15 ms；连续改键才明显 |
| ESP32 → CH9329（改 115200） | < 2 ms | 需 WCH 配置工具改模块波特率并同步改固件宏 |
| **端到端（CH9329 9600）** | **约 25–50 ms** | 快捷键场景无感；不适合音游/格斗 |
| **端到端（CH9329 115200 / Pico W）** | **约 20–40 ms** | 同上 |

> 数量级估算，未在真机实测；Zero 2 本身蓝牙报告周期也会贡献波动。

### 1.11 外挂 dongle 的风险/坑清单

1. **买错芯片**：ESP32-S3 / C3 是 BLE-only，收不了 Zero 2 手柄模式（本文最重要的排雷）。
2. **买错板型**：nRF52840 板跑 HID Remapper 官方蓝牙版只支持 BLE，零 2 不适用。
3. **配对模式搞错**：R+Start 是键盘模式；dongle 方案要用 **Start+X**（Windows）等 gamepad 模式。
   两种身份在主机端看到的设备名都叫 "8BitDo Zero 2 gamepad"，容易混淆。
4. **预发布固件风险**：HID Remapper Pico W 经典蓝牙版是实验性版本，作者未承诺进正式版。
5. **CH9329 波特率**：出厂 9600，别忘改固件宏或用 WCH 工具改模块；写错串口（TX/RX 反接）时主机毫无反应。
6. **iPad 连接方式**：dongle 输出是 USB，iPad 需要 USB-C 直连/转接；想无线连 iPad 需要 dongle 自己做 BLE HID 键盘外设
   （Pico W 上「经典主机 + BLE 外设」同时跑属于进阶未验证方向，不建议一期做）。
7. **映射表与实体丝印**：8BitDo 是任天堂布局，Bluepad32 是位置语义，A/B、X/Y 会「看起来反了」；
   本仓库固件已按丝印换算，自己写固件时务必注意。
8. **多主机切换**：Zero 2 只记上次配对的主机；换主机要重新配对（本仓库固件提供 L+R+Select 长按清配对）。
9. **许可（只对想做成商品的人）**：Bluepad32 是 Apache 2.0，但它依赖 BTstack——开源项目免费，
   商业闭源产品需向 BlueKitchen 购买 BTstack 授权（Pico W 上已含 Raspberry Pi 的 BTstack 授权，见
   Bluepad32 README 的 License 段）。自己玩/open source 不受影响。

---

## 2. 主机端软件改键矩阵（零硬件成本）

### 2.1 先讲边界（很重要）

- 主机端改键 = 改「**这台电脑上的软件看到按键后做什么**」，它**不会改变 Zero 2 发出的东西**。
  所以：
  - **换一台电脑/游戏机/iPad，映射全部失效**；
  - **无法把「改好的键盘」发给别的设备**（这正是外挂 dongle 存在的理由）；
  - 对 iPad 这类没有全局改键 API 的系统，主机端方案**完全不存在**（只能 App 内自定义快捷键）。
- 另一个通用坑：Zero 2 键盘模式发出的是普通字母 c~o，**操作系统层面无法区分**它和你的真实键盘
  （Windows PowerToys 官方 FAQ 原话：*"Can I have different key mappings across multiple
  keyboards? Currently, no."*，[PowerToys 文档](https://learn.microsoft.com/en-us/windows/powertoys/keyboard-manager)）。
  因此 Windows 上的全局映射必然干扰正常打字 —— 必须配开关，或选能按设备区分的平台/工具。

### 2.2 各平台矩阵

> 设备形态前提：Zero 2 键盘模式在 Windows/macOS/Linux 上就是一个**普通蓝牙 HID 键盘**
> （Windows 设备管理器里是「HID Keyboard Device / 蓝牙键盘」，会直接打出 c~o）。
> AHK / PowerToys 等工具拦截的是**键盘钩子/扫描码**层面的输入，所以能改；
> 但也因此完全区分不出按键来自 Zero 2 还是真实键盘（见 §2.1）。

| 平台 | 工具 | 按设备区分 | 键→组合键 | 主要边界 |
|---|---|---|---|---|
| Windows | **AutoHotkey v2** | ❌（键钩子拿不到设备） | ✅ 任意 Send 序列 | 需常驻；目标程序提权时脚本也要提权；少数 raw input 程序不认合成键 |
| Windows | **PowerToys Keyboard Manager** | ❌（官方明确不支持） | ✅ 键→键/组合键/文本，可按目标 app | 需 PowerToys 后台；官方建议游戏别用（影响帧率）；Win+L 等保留键不可改 |
| Windows | **reWASD** | ✅（按设备/配置） | ✅ 手柄→键鼠强 | **付费**；面向手柄，Zero 2 需用 X-input 模式（不是键盘模式）；对「键盘模式字母重映射」不适用 |
| Windows | **Steam Input** | ✅（Steam 内设备） | ✅ 手柄→键盘/鼠标 | 需 Steam 运行、游戏经 Steam 启动；桌面布局有局限；只对 Steam 场景有效 |
| Windows | **JoyToKey** | 部分（按设备支持弱） | ✅ 手柄→键盘 | 老工具、全局生效；需 Zero 2 用 X-input/D-input 模式；对键盘模式无用 |
| macOS | **Karabiner-Elements** | ✅（device_if 按设备） | ✅ 复杂修改/任意组合键 | 最接近「理想改键」；需授权输入监控；仅 macOS |
| Linux | **input-remapper** | ✅（按设备） | ✅ 键→宏/组合键 | 需 root 装服务；X11/Wayland 兼容性看发行版 |
| Linux | **keyd** | ✅（可按设备配置） | ✅ | 需 root 装守护进程；偏键盘布局层 |
| Linux | **udev hwdb** | ✅（按设备匹配） | 有限（scancode→keycode） | 只能改键码映射，做不了复杂组合宏 |
| Android | **Key Mapper**（[GitHub](https://github.com/sds100/KeyMapper)） | ✅（按键级触发器） | ✅ 宏/组合 | 需开启无障碍服务；非 root 无法在系统底层拦截，部分 App/游戏 raw input 不生效；Android 11+ 对无障碍/后台限制更严，国产 ROM 可能要白名单 |
| iPadOS | 无全局方案 | — | — | 只能：① 设置→通用→键盘→硬件键盘→修饰键（只改 Caps/Control/Option/Command/Globe）；② **App 内自定义快捷键**（CSP、Procreate 等）；③ 用外挂 dongle 输出标准键盘，让 App 的固定快捷键可用 |

### 2.3 分场景建议

- **只在 Windows 的绘图软件里用**：AHK 脚本（本仓库 `windows/`）+ 窗口作用域 + ScrollLock 开关；
  如果绘图软件自己支持改快捷键（CSP 可把功能绑到单键），优先直接在软件里绑，零依赖。
- **macOS**：Karabiner-Elements 可以只对 Zero 2 生效（按设备），是最干净的主机端方案：
  在 Simple Modifications 里选中 8BitDo 设备，把 c~o 改成想要的快捷键，不影响真实键盘。
- **Linux 桌面**：input-remapper（图形化、按设备，ANKI/游戏社区常用）或 keyd（配置文件、按设备）。
- **Android**：Key Mapper 需无障碍权限；只适合平板/电视盒子上「能用映射 App」的场景，
  不适合需要原始输入的 App；不能替代 dongle。
- **iPad**：接受「App 内自定义快捷键」就到头了；要跨 App 固定组合键，唯一现实路线是 dongle。

### 2.4 可直接用的 Windows 实现

- 脚本：[`../../windows/zero2_keyboard_remap.ahk`](../../windows/zero2_keyboard_remap.ahk)
- 说明（含 Zero 2 键盘模式键位实测方法、默认映射、限制）：
  [`../../windows/README.md`](../../windows/README.md)

---

## 3. 省事替代：要不要直接买 8BitDo Micro

### 3.1 官方规格（来自 8BitDo 官网/说明书）

- 产品：**8BitDo Micro** 蓝牙手柄（2023），72×40.7×14.1 mm、24.8 g，16 个按键（含 L2/R2）。
- 工作模式：**Keyboard 模式**、D-input、Switch 模式（模式开关实体切换）。
- 兼容性：Switch / Switch 2 / Android 9+；**键盘模式下支持 Android、iOS、iPadOS、macOS、Windows**。
  （[8BitDo 中文产品页](https://www.8bitdo.cn/micro/)、[英文产品页](https://www.8bitdo.com/micro/)）
- 连接：**蓝牙 + USB 有线**；说明书里「键盘模式」既有蓝牙配对页，也有**USB 有线连接页**
  （[蓝牙键盘模式](https://manual.8bitdo.com/micro/micro-keyboard-bluetooth.html)、
  [有线键盘模式](https://manual.8bitdo.com/micro/micro-keyboard-wired.html)）。
- **支持手机版「精英软件」在键盘模式下改键：单个按键、组合键都能自由设置**
  （官方中文页原文：「手柄的键盘模式，支持 iOS，Android 版本精英软件。通过手机 APP，可随时随地设置按键映射，不管是键盘上的单个按键，还是组合键，都可自由设置」）。
- 官方还写明：手柄开机后可**随时切换成键盘模式**并自动重连上一个设备；适合画画、翻页、背单词等。

### 3.2 价格/渠道（2026-11 量级，购买前以实际为准）

- 8BitDo Micro：京东/天猫常见 **¥99**（促销），日常约 ¥99–149；
  参考导购页：<https://guangdiu.com/detail.php?id=30256797>（「99元」）。
- 对比：Zero 2 参考价 ¥99、京东 ¥79（[ZOL](https://detail.zol.com.cn/gamepad/index1370762.shtml)）。

### 3.3 评估结论

| 维度 | 8BitDo Micro | Zero 2 + dongle |
|---|---|---|
| 自定义键盘 | ✅ 官方支持（手机 App 改单键/组合键） | ✅ 自己定义任意 HID 键（本仓库固件） |
| 无线/有线 | ✅ 蓝牙键盘模式（iPad 可用）+ USB 有线键盘模式 | 无线进、有线出（USB 键盘） |
| 目标设备 | iOS/iPadOS/Android/macOS/Windows（键盘模式） | 任何接受 USB 键盘的主机（PC/iPad USB-C/Android OTG/部分电视盒） |
| 成本 | ¥99–149 | ¥30–45（DIY）|
| 时间 | 10–30 min | 3–6 h（+ 等快递/接线/调试） |
| 风险 | 官方产品，低 | 模块/固件/配对坑，中 |
| 可玩性/掌控 | App 内有限配置 | 源码级任意映射（还能加宏、按住修饰键） |

**结论**：如果目标就是「一个可自定义按键的掌上小键盘」且预算允许，**买 Micro 是最省事、成功率最高的选择**；
如果必须复用现有 Zero 2、或要完全掌控映射/不想再买手柄，用 dongle。

> 注意：8BitDo 官方「蓝牙接收器 / USB 无线适配器 2」虽然支持 Zero 2（Zero 2 FAQ 写明），
> 但它输出的是**手柄协议**（给 Switch/PC 当手柄），不输出键盘，不能解决本需求。

---

## 4. 综合对比表（成本 / 延迟 / 兼容性 / 折腾程度）

| 方案 | 硬件成本 | 端到端延迟 | 目标设备覆盖 | 映射自由度 | 折腾程度 | 主要风险 |
|---|---|---|---|---|---|---|
| Zero 2 直连（键盘模式，不改键） | ¥0 | 15–30 ms | 任意蓝牙主机 | ❌ 固定 c~o | 极低 | 无法自定义 |
| **主机端软件改键**（AHK/Karabiner/input-remapper…） | ¥0 | 15–30 ms（软件额外 <5 ms） | 仅该主机/系统 | 高（组合键/宏） | 低 | 换设备失效；Windows 不能按设备区分，干扰真实键盘 |
| **Pico W + HID Remapper**（1A） | ¥25–75 | 20–40 ms | 所有 USB 键盘主机（PC/iPad USB-C/Android OTG） | 高（网页配置，任意映射） | **低**（刷 UF2 + 网页配置） | **预发布固件**稳定性 |
| **ESP32 + CH9329**（1B，本仓库） | ¥30–45 | 25–50 ms（可优化到 20–35） | 同上 | 高（改 JSON/头文件重编译） | 中（接线 + Arduino + 配对） | 模块/波特率/配对坑 |
| Pico W 自写固件（1C） | ¥25–75 | 20–40 ms | 同上 | 最高（源码级） | 高（Pico SDK + HID 描述符） | HID/USB 调试成本 |
| 直收键盘模式 scancode（1D） | ¥20–75 | 20–40 ms | 同上 | 高 | 高 | 键盘模式协议/API beta |
| **8BitDo Micro（换设备）** | ¥99–149 | 15–30 ms | iOS/iPadOS/Android/macOS/Windows（键盘模式） | 中高（手机 App 配单键/组合） | **最低** | 官方 App 能力上限 |

---

## 5. 推荐决策树

```
目标设备是什么？
├─ iPad / iPhone / 想要无线、愿意花 ~¥100
│    └─ 买 8BitDo Micro（键盘模式 + 手机精英软件改键）。★ 最省事
├─ 只要在 Windows 的绘图软件里用
│    ├─ 软件本身支持改快捷键（CSP 等）→ 直接在 App 内把功能绑到 c~o（零成本、最稳）
│    └─ 否则 → AHK 脚本（¥0，注意窗口作用域 + ScrollLock 开关）
│             不够用再上 dongle
├─ 想要「任何主机插上就是自定义键盘」（PC/iPad USB-C/Android/电视盒…）
│    ├─ 先试 Pico W + HID Remapper 预发布固件（0.5–2 h，¥25–75，零代码）
│    └─ 要求稳定/可控 → ESP32 原版 + CH9329（本仓库固件，¥30–45，3–6 h）
└─ macOS 桌面 → Karabiner-Elements 按设备改键（¥0，最干净的主机端方案）
```

**工期估计**（含采购等待除外）：
- HID Remapper：下载固件 5 min + 烧录 5 min + 配对/配置 30–60 min。
- ESP32+CH9329：接线 20 min + Arduino 板包安装 30–60 min + 编译烧录 10 min + 配对/调试 1–2 h。
- AHK：装 AHK 10 min + 改映射表/测试 20–60 min。
- Micro：开箱 + 精英软件配对/改键 10–30 min。

---

## 6. 交付物索引

| 路径 | 内容 |
|---|---|
| [`../../esp32-dongle/README.md`](../../esp32-dongle/README.md) | dongle 方案总说明：选型依据、BOM、接线、编译烧录、配对、延迟、故障排查 |
| [`../../esp32-dongle/arduino/zero2_kb_dongle/`](../../esp32-dongle/arduino/zero2_kb_dongle/) | Arduino 固件（`.ino` + `mapping.h`） |
| [`../../esp32-dongle/arduino/mapping.example.json`](../../esp32-dongle/arduino/mapping.example.json) | 可编辑映射表（JSON），默认一套绘图快捷键 |
| [`../../esp32-dongle/arduino/tools/gen_mapping.py`](../../esp32-dongle/arduino/tools/gen_mapping.py) | JSON → `mapping.h` 生成器（Python 3.8+，仅标准库） |
| [`../../esp32-dongle/picow/README.md`](../../esp32-dongle/picow/README.md) | Pico W + HID Remapper 零代码路线：固件下载、烧录、网页配置、映射表、限制 |
| [`../../windows/zero2_keyboard_remap.ahk`](../../windows/zero2_keyboard_remap.ahk) | AutoHotkey v2 改键脚本（窗口作用域 + ScrollLock 开关 + 调试模式） |
| [`../../windows/README.md`](../../windows/README.md) | Windows 零成本方案：配对、键位验证、映射、限制、其他工具对比 |

---

## 7. 无硬件条件下的验证清单（拿到设备后按序做）

1. **确认零 2 各模式**：R+Start（键盘模式）/ Start+X（Windows）/ Start+Y（Switch）/ Start+B（Android）/ Start+A（macOS），
   用手机蓝牙扫描看设备名与 LED 闪法是否与说明书一致。
   （[Zero 2 Windows 模式说明书](https://manual.8bitdo.com/zero2/zero2_windows.html)、
   [键盘模式说明书](https://manual.8bitdo.com/zero2/zero2_keyboard_mode.html)）
2. **验键盘模式键位**：配对到 Windows/macOS，在记事本里逐个按键，确认是不是 `c,d,e,f,g,h,i,j,k,m,n,o`
   （对照附录 A）。若不同，以实测为准，AHK 映射表按实测改。
3. **确认键盘模式的蓝牙类型**（BLE vs 经典）：Windows 设置/设备管理器看设备归属，
   或手机装 nRF Connect 扫描：能扫到 = BLE；扫不到 = 经典。
4. **dongle 验证**：
   - 先空板烧固件、看串口日志 `=== Zero2 -> USB HID keyboard dongle ===`；
   - Zero 2 Start+X 配对后，按按钮看日志 `mask=...` 变化；
   - CH9329 插主机，用记事本 / 在线键盘测试页确认按键；
   - 逐条核对默认映射表。
5. **延迟体感**：在绘图软件里连续按撤销，看是否跟手；不满意就把 CH9329 改 115200。
6. **稳定性**：连续用 30–60 min，检查是否断连、是否粘键。

---

## 8. 参考链接

**8BitDo 官方**
- Zero 2 常见问题：<http://support.8bitdo.cn/faq/zero2.html>
- Zero 2 键盘模式配对：<https://manual.8bitdo.com/zero2/zero2_keyboard_mode.html>
- Zero 2 Windows 模式：<https://manual.8bitdo.com/zero2/zero2_windows.html>
- Zero 2 Switch 模式：<https://manual.8bitdo.com/zero2/zero2_switch.html>
- 8BitDo Micro 产品页：<https://www.8bitdo.cn/micro/>、<https://www.8bitdo.com/micro/>
- Micro 键盘模式（蓝牙）：<https://manual.8bitdo.com/micro/micro-keyboard-bluetooth.html>
- Micro 键盘模式（有线）：<https://manual.8bitdo.com/micro/micro-keyboard-wired.html>

**Bluepad32 / 蓝牙栈**
- 文档首页：<https://bluepad32.readthedocs.io/en/latest/>
- 支持的 gamepads（含 8BitDo Zero 2，协议 BR/EDR）：<https://bluepad32.readthedocs.io/en/latest/supported_gamepads/>
- FAQ（ESP32-S3/C3 不支持 BR/EDR）：<https://bluepad32.readthedocs.io/en/latest/FAQ/>
- 支持的键盘（beta）：<https://bluepad32.readthedocs.io/en/latest/supported_keyboards/>
- Arduino API（`isKeyboard()`/`isGamepad()` 等）：<https://bluepad32.readthedocs.io/en/latest/programmers_guide_arduino/>
- Pico W 平台：<https://bluepad32.readthedocs.io/en/latest/plat_picow/>
- BlueRetro（同为 Bluepad32 生态的复古主机转接器）：<https://github.com/darthcloud/BlueRetro>

**HID Remapper（Pico W 经典蓝牙预发布）**
- 仓库：<https://github.com/jfedor2/hid-remapper>
- 手册：<https://www.remapper.org/manual/> / 配置页：<https://www.remapper.org/config/>
- 蓝牙版说明（官方版仅 BLE）：<https://github.com/jfedor2/hid-remapper/blob/master/BLUETOOTH.md>
- Pico W 经典蓝牙版发布帖（作者实测含 Zero 2）：<https://forum.remapper.org/t/bluetooth-classic-on-pico-w-2026-edition/359>
- 预发布固件：<https://github.com/jfedor2/hid-remapper/releases/tag/r2026-11-06-test1>

**CH9329**
- 沁恒产品页：<https://www.wch.cn/products/CH9329.html>
- 协议实现参考（命令码/帧格式/校验，One-KVM 项目）：
  <https://github.com/mofeng-git/One-KVM/blob/main/src/hid/ch9329_proto.rs>

**主机端改键**
- PowerToys Keyboard Manager 文档：<https://learn.microsoft.com/en-us/windows/powertoys/keyboard-manager>
- AutoHotkey v2：<https://www.autohotkey.com/>
- Karabiner-Elements：<https://karabiner-elements.pqrs.org/>
- input-remapper：<https://github.com/sezanzeb/input-remapper>
- keyd：<https://github.com/rvaiya/keyd>
- Key Mapper（Android）：<https://github.com/sds100/KeyMapper>
- 8BitDo Zero 2 键盘模式改键实录（Linux/macOS，含键位表）：
  <https://gist.github.com/emleddin/d25eb8493e16a7e262d156e7c8f53e77>

**ESP-IDF（备选 1D 路线的官方 HID host）**
- HID Host API（BLE + 经典）：<https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/bluetooth/esp_hidh.html>

---

## 附录 A：Zero 2 键盘模式键位表

社区整理 + 实测截图（队友 hw-re 抓取的 HackMD 图，本地路径
`../hardware/assets/hackmd_zero2_keyboard_mode_keys.png`）给出的对应关系：

![Zero 2 键盘模式键位图](../hardware/assets/hackmd_zero2_keyboard_mode_keys.png)

| 实体按钮 | 输出字母 | 实体按钮 | 输出字母 |
|---|---|---|---|
| 十字 ↑ | `c` | 实体 A（右） | `g` |
| 十字 ↓ | `d` | 实体 B（下） | `j` |
| 十字 ← | `e` | 实体 X（上） | `h` |
| 十字 → | `f` | 实体 Y（左） | `i` |
| L | `k` | Select | `n` |
| R | `m` | Start | `o` |

- 输出全是**小写字母**；键盘模式本身不发 Ctrl/Shift 等组合（所以要在主机端或 dongle 端重映射）。
- 字母 `l` 不被使用；`n`/`o` 分别对应 Select/Start。
- 另有多份资料（[ANKI 改键 gist](https://gist.github.com/emleddin/d25eb8493e16a7e262d156e7c8f53e77)）
  交叉验证了 c~k、m 这些键，与上图一致。
- 证据等级：**社区实测（中高）**。拿到设备后请按 §7 第 2 步复核；若你的固件版本不同，以实测为准。

## 附录 B：HID 键值速查（写映射表时用）

| 键 | Usage ID | 键 | Usage ID |
|---|---|---|---|
| A–Z | 0x04–0x1D | Space | 0x2C |
| 1–9,0 | 0x1E–0x27 | Tab | 0x2B |
| `[` / `]` | 0x2F / 0x30 | Esc | 0x29 |
| `,` / `.` / `/` | 0x36 / 0x37 / 0x38 | Enter | 0x28 |
| `-` / `=` | 0x2D / 0x2E | Backspace | 0x2A |
| 方向键 右/左/下/上 | 0x4F/0x50/0x51/0x52 | F1–F12 | 0x3A–0x45 |

修饰键位（键盘报告第 0 字节）：`Ctrl=0x01`、`Shift=0x02`、`Alt=0x04`、`GUI=0x08`（左键位）。

CH9329 发键盘数据的帧格式（[协议实现参考](https://github.com/mofeng-git/One-KVM/blob/main/src/hid/ch9329_proto.rs)）：

```
57 AB  00  02  08  [modifier] [reserved] [key1..key6]  [checksum]
帧头   地址 命令 长度   8 字节 HID 键盘报告             校验=前面所有字节和 & 0xFF
```

## 附录 C：证据等级说明

| 结论 | 证据 | 等级 |
|---|---|---|
| Zero 2 无有线数据模式 | 8BitDo 官方 FAQ 原文 | 高 |
| 键盘模式固定输出 c~o | 社区实测图 + 多份改键教程交叉验证 | 中高（待真机复核） |
| Zero 2 手柄模式为 BR/EDR | Bluepad32 官方支持列表 + FAQ | 高 |
| ESP32-S3/C3 不支持 BR/EDR | Bluepad32 FAQ + Espressif 芯片规格 | 高 |
| Pico W 可做经典蓝牙 HID 主机 | Bluepad32 Pico 平台 CMake 链接 `pico_btstack_classic` + HID Remapper 作者实测 | 高 |
| HID Remapper 经典蓝牙版实测过 Zero 2 | 作者论坛帖原文 | 高（但为实验版本） |
| CH9329 帧格式/命令码/默认 9600 | One-KVM 开源实现（含测试用例） | 高 |
| 延迟数字 | 组件典型量级估算 | 低（未实测，仅数量级参考） |
| 键盘模式是 BLE 还是经典 HID | 尚未确认（队友 hw-re 在查） | 待定 |
