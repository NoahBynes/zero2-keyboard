# 8BitDo Zero 2 硬件与 Keyboard 模式事实核查

> 任务：task-2（RE：8BitDo Zero 2 硬件拆解/芯片/键盘模式 HID 事实核查）
> 核查日期：2026-11-13；核查方式：官方产品页/FAQ/说明书 + 社区拆解照片 + FCC 数据库 + 固件文件头静态分析（本机**没有** Zero 2 实物，未做电气测量）。
> 结论按置信度标注：**A**=官方文档/数据库直读，**A-**=高分辨率照片直读，**B**=社区实测/多来源一致，**C**=推断，**U**=未确认。

---

## 0. 结论速览（TL;DR）

| 问题 | 结论 | 置信度 |
|---|---|---|
| 主控 MCU 型号 | **未确认具体型号**。固件头显示主控为 ARM Cortex-M 架构（目标地址 `0x08003400`，STM32/类 STM32 的 Flash 映射），板上为**双芯片**：一颗 MCU + 一颗独立蓝牙 SoC；照片分辨率不足、且 Zero 2 没有 FCC 内部照片，无法读丝印。**不要**把它写成 nRF52/nRF51。 | 架构 A / 具体型号 U |
| 蓝牙方案 | **Bluetooth Classic（BR/EDR）**，非 BLE：游戏模式有实测 pairing 日志（HID UUID `0x1124` + Modalias），同平台 Micro 的 FCC 测试也是 BT3.0 经典蓝牙；Keyboard 模式没抓到单独抓包，但共用同一蓝牙芯片/栈，推断同为 Classic（见第 3 节）。 | A-/B |
| 有线（Micro-USB）能否通信 | **不能当手柄/键盘用**，官方 FAQ 明确「USB 只能升级固件和充电」。但 D+/D- 必然接到芯片（固件升级走 USB 升级模式），即「硬件上 USB 数据线是通的，功能上被固件限制为升级通道」。 | A |
| Keyboard 模式键位 | R+Start 开机；固定输出英文字母：↑C ↓D ←E →F、A=G、X=H、Y=I、B=J、L=K、R=M、Select=N、Start=O（跳过 L）。**不能改键**，也没有任何官方 App/组合键可改。 | A-（官方说明书图）/B（实测一致） |
| 官方/隐藏改键渠道 | **不存在**。Ultimate Software V2/V1 支持列表均不含 Zero 2；官方只提供固件更新器（只更新模式/兼容性），无映射配置功能。 | A |
| 8BitDo Micro 是否可替代 | **是，当前最省事**：Micro 键盘模式可用**手机版 Ultimate Software**自定义单键/组合键（仅键盘模式），且支持 **USB-C 有线键盘模式**（插线即 USB 键盘）。代价：无 X-input、改键必须用手机 App、无桌面版软件。 | A |
| 跨型号刷固件 | **没有先例、不建议**。官方 `.dat` 每段带目标地址与 model/USB-PID 字段，Micro 与 Zero 2 的固件/硬件不同；跨刷即使成功也给不了「可改键」（Micro 的映射是 App 侧配置）。 | B |
| 社区是否有人成功改键/换固件 | 未检索到任何 Zero 2 自定义键盘映射或第三方固件成功案例（中/英/日）。社区只做**主机端重映射**（input-remapper / Karabiner / Joy2Key / AHK 等）和**飞线换按键**（做街机摇杆，不是改键）。 | B |

**对后续方案的关键含义**：Zero 2 是「Classic 蓝牙 HID + 固定字母输出」的设备，所以 (1) 主机端重映射可行（键盘模式在 PC/iPad 上就是普通键盘）；(2) 想做「通用自定义键盘 dongle」，蓝牙主机必须是支持 **BR/EDR** 的芯片（原版 ESP32 / Pico W；**ESP32-S3/C3 只有 BLE，接不了 Zero 2**，Bluepad32 明确写入 FAQ）；(3) 如果只想改键、不折腾硬件，**买 8BitDo Micro** 是官方现成解。

---

## 1. 官方模式与配对事实（核对产品页/FAQ/说明书）

### 1.1 产品页口径

- 中文页：<https://www.8bitdo.cn/zero2/>；英文页：<https://www.8bitdo.com/zero2/>
  - 宣传语：**「5 大模式：Switch、Windows、Android、Keyboard」**（原文如此，实际列出 4 个；第 5 个是说明书里的 **macOS 模式**——英文页注明「additional system support requires downloading and installing firmware」，即 macOS 支持靠固件更新解锁）。
  - 工作模式（Tech Specs）：`X-input, D-input, Switch mode, Keyboard`；连接方式：仅 Wireless Bluetooth；尺寸 73×36.5×14.7 mm / 20.7 g（英文页 20 g）；电池 180mAh、续航 8h、充电 1–2h。
  - 不支持 Switch 的 NFC 扫描、振动、体感（中文页脚注）。
- 官方 FAQ 关键条目（中文 <https://support.8bitdo.cn/faq/zero2.html> / 英文 <https://support.8bitdo.com/faq/zero2.html>）：
  - 「**可以有线使用吗？不可以，有线连接只能用来升级固件。**」
  - 「如何配合画画软件：先 **R + Start** 开机，连接 iPad，然后在软件设置里定义键盘（即手柄按键）的功能」；官方推荐 Clip Studio Paint。
  - 「支持八位堂蓝牙接收器」。
  - 组合键：`Select+Down` = Home（Switch/Windows）；`Select+Start` = ZL+ZR（Switch Online 菜单）；十字键默认映射左摇杆，`上+Select` 5 秒还原、`左+Select` 左摇杆、`右+Select` 右摇杆（红灯闪确认、掉电不丢）。
  - 死机：长按 Start 8 秒强制关机，再按 Start 开机。
  - Zero 2 与 Zero 一代差异：Zero 2 支持固件升级、支持 Switch；**没有**拍照模式/iCade 模式（Zero 1 有）。

### 1.2 五种模式的进入方式与指示灯（官方说明书逐页核对）

来源：<https://manual.8bitdo.com/zero2/>（中文同站 <https://manual.8bitdo.cn/zero2/>）；说明书 PDF 原件已存 `assets/Zero2_Official_Manual.pdf`。

| 模式 | 开机组合（按住不放，开机） | 指示灯（每周期闪烁次数） | 配对/设备名 | 平台/备注 |
|---|---|---|---|---|
| X-input（Windows） | **X + Start** | 2 次 | 配对名 `8BitDo Zero 2 gamepad`；配对：长按 Select 3 秒至快闪 | Windows 7+ / BT4.0；`Select+↓`=HOME |
| D-input（Android） | **B + Start** | 1 次 | `8BitDoZero 2 gamepad`（说明书 Android 页写法） | Android 4.0+ / Raspberry Pi 等 |
| macOS | **A + Start** | 3 次 | `Wireless Controller` | 需先装固件更新解锁 macOS 支持 |
| Switch | **Y + Start** | 4 次 | Switch 首页「手柄 → 更改握法/顺序」配对 | 模拟 Pro 手柄；`Select+↓`=HOME、`Select+Start`=ZL+ZR |
| **Keyboard** | **R + Start** | **5 次** | **`8BitDoZero 2 gamepad`（无空格）**，在系统蓝牙里会以键盘身份出现 | iOS/iPadOS/macOS/Windows/Linux；**设备输入语言必须是英文**；所有按键输出英文字母 |

补充：配对都是「长按 Select 3 秒 → 灯快闪」；配对成功后下次「按一下 Start 自动回连」。
（说明书/FAQ 里键盘模式设备名有的写 `8BitDo Zero 2 gamepad`、有的写 `8BitDoZero 2 gamepad`——iOS 上也有用户报告显示 `8BitDo Zero 2`，命名随固件/宿主略有差异，属正常现象。）

---

## 2. Keyboard 模式键位表（核心事实）

Keyboard 模式下每个按键输出**固定英文字母**，官方说明书没有文字版映射表，但零售版说明书配图、社区实测三方一致：

| 物理按键（Switch 布局） | 输出键（美国英文布局） | 备注 |
|---|---|---|
| 十字键 ↑ | `C` | |
| 十字键 ↓ | `D` | |
| 十字键 ← | `E` | |
| 十字键 → | `F` | |
| A（右） | `G` | |
| X（上） | `H` | |
| Y（左） | `I` | |
| B（下） | `J` | |
| L（左肩） | `K` | |
| R（右肩） | `M` | |
| Select（-） | `N` | |
| Start（+） | `O` | 长按 Start 会关机（正常特性） |

要点：

1. 字母序列本质是 HID 键码 `0x06`～`0x12` 顺排 12 个键（c…o），**刻意跳过 `L`**（所以 L 肩=K、R 肩=M）。
2. **没有任何方向键、回车、空格、Esc、Tab、修饰键（Shift/Ctrl/Alt）输出**——这也是用户抱怨「PPT 翻页都不行」的原因。
3. 组合键（如 Select+Start）同时按下时输出对应多个字母（N+O），属推断（未实测；键位本身固定）。
4. 必须把宿主输入法切到**英文**，否则中文输入法会拦截字母（官方手册注）。
5. 映射**不可改**：没有长按切映射、没有隐藏组合键、没有 App（见第 4 节）。
6. Zero 2 无操作约 **15 分钟自动关机**（社区文章实测提醒）；键盘模式不例外。

来源与截图：
- 零售版日文说明书 PDF（`assets/zero2_manual_jp.pdf`，下载自 <https://yourtreasure.jp/wp-content/uploads/2023/12/8Bitdo-ZERO2-%e3%83%af%e3%82%a4%e3%83%a4%e3%83%ac%e3%82%b9%e3%82%b3%e3%83%b3%e3%83%88%e3%83%ad%e3%83%bc%e3%83%a9%e3%83%bc-%e6%97%a5%e6%9c%ac%e8%aa%9e%e8%aa%ac%e6%98%8e%e6%9b%b8.pdf>）第 2 页键位图：`assets/jp_manual_button_labels.jpg`、`assets/jp_manual_keyboard_mode_keymap.jpg`。
- 日本 HackMD 教程《XPadLauncher と SendKey で 8BitDo zero2 を左手デバイス化する方法》：<https://hackmd.io/@piksware/LeftDevice8Bit>，其键位图（含 Select=N、Start=O）已存 `assets/hackmd_zero2_keyboard_mode_keys.png`。
- 长毛象实测：「（上下左右、ABXYLR、Select、Start）键位，分别对应着字母 cdefghikmno，不支持改键」——<https://mastodon.fivest.one/@fivestone/113124490270142724>（原帖漏写 j，与配图互补）。
- Anki 教程 gist（实测 10 键，缺 Select/Start）：<https://gist.github.com/emleddin/d25eb8493e16a7e262d156e7c8f53e77>。

---

## 3. Keyboard 模式是 BLE HID 还是蓝牙经典 HID？

**结论：Bluetooth Classic（BR/EDR）HID，不是 BLE HOGP。置信度 A-/B。**

证据链：

1. **Bluetooth SDP 日志直读**：日本笔记站 scrapbox 的 Raspberry Pi 配对日志里，Zero 2 连接后 `bluetoothctl` 显示
   `UUIDs: 00001124-0000-1000-8000-00805f9b34fb`（HID Profile，Classic）与 `00001200-...`（PnP Information），并报告 `Modalias: usb:v2DC8p3230d0100`（VID 0x2DC8=8BitDo，PID 0x3230）。
   来源：<https://scrapbox.io/saitotetsuya/8BitDo_Zero_2>（API 全文：<https://scrapbox.io/api/pages/saitotetsuya/8BitDo_Zero_2/text>）。
   —— 若为 BLE 键盘，应出现 `00001812`（HID over GATT）服务而不会走 HIDP 的 `00001124`。
2. **Bluepad32 官方支持列表**明确写 8BitDo 家族（含 Zero 2）协议为 **BR/EDR**，且「All 8BitDo modes are supported: Switch, Android, Windows and macOS」：
   <https://bluepad32.readthedocs.io/en/stable/supported_gamepads/>。其 FAQ 也明确「ESP32-S3/C3 不支持 Classic，所以接不了 8BitDo」：<https://bluepad32.readthedocs.io/en/stable/FAQ/>。
3. **同平台 FCC 测试报告**：8BitDo Micro（FCC ID `2AOWF-MICRO`）的测试报告工程路径为 `FCC-BT3.0`、测试项为 BT3.0 1Mbps GFSK（DSS/Part15 经典蓝牙），说明书站也把 Micro 与 Zero 2 并列为同系列小块手柄：
   <https://fccid.io/2AOWF-MICRO/Test-Report/test-report-6751361>。
4. 产品页「Bluetooth 4.0」只是说自己兼容 BT4.0 主机（双模芯片常见写法），**不能**据此推断 BLE。

**遗留不确定性**：没有抓到「Keyboard 模式」连接瞬间的 btmon/SDP 抓包（现有日志是 D-input/Android 模式）。键盘模式与游戏模式共用同一蓝牙芯片/固件栈，Classic 概率很高，但仍建议按第 8 节做 10 分钟验证。

### Windows/iPad 上的设备名与 VID/PID 线索

| 场景 | 设备名 | VID/PID | 来源/置信度 |
|---|---|---|---|
| X-input（Windows 游戏模式） | `8BitDo Zero 2 gamepad`（蓝牙） | `2DC8:9018` | InputConfig 控制器 ID 数据库 + Zero 2 固件第二段 model 字段 `0x9018`，B |
| D-input（Android/RPi 等） | `8BitDo Zero 2 gamepad` | `2DC8:3230`（`usb:v2DC8p3230d0100`） | bluetoothctl 实测日志，B |
| Keyboard | `8BitDoZero 2 gamepad`（部分系统显示带空格） | **未实测**（推断为另一组 8BitDo PID，可能不同于 9018/3230） | U |
| Windows 设备管理器呈现 | 键盘模式会作为 **蓝牙键盘**（HID Keyboard）出现，可直接被任何接受键盘输入的程序使用 | — | 官方 FAQ「把控制器设为 keyboard 使用」+ 社区教程，A-/B |

数据库出处：<https://inputconfig.com/tools/controller-id-lookup>（8BitDo Zero 2 一行列出 `2dc8:9018, 2dc8:3230`）。

---

## 4. 官方/隐藏「改键」办法核查（没有）

| 渠道 | 结论 | 依据 |
|---|---|---|
| 8BitDo Ultimate Software V2（桌面/手机） | **不支持 Zero 2**。官方下载页的设备清单里没有 Zero 2；V2 面向 Ultimate/Pro3/64/Retro 等新设备，V1 面向 SN30 Pro+/Pro 2 等旧设备，手机版清单里有 Micro，**均无 Zero 2** | <https://app.8bitdo.com/> |
| 组合键切换映射 | 只有系统级映射（十字键=左摇杆/右摇杆、`Select+↓`=HOME、`Select+Start`=ZL+ZR），**没有**切换键盘键位的组合 | 官方 FAQ / 说明书 |
| 长按/隐藏模式 | 只用于配对（Select 3s）、关机（Start 8s）、D-pad 模式切换（+Select 5s）；无隐藏改键 | 官方文档/社区 |
| 官方固件更新 | 只更新模式/兼容性（例如加入 macOS 支持），**不提供映射配置** | 官方 Upgrade tool 页 <https://support.8bitdo.com/firmware-updater.html> |
| 接收器/App 配置 | 8BitDo 蓝牙接收器只做「接收器→主机」转接，无映射配置 | 官方 FAQ |

社区共识同结论：「不支持改键」（长毛象实测帖、Anki/gist 教程都改用「键盘模式 + 主机端重映射软件」）。

---

## 5. 硬件与拆解事实

### 5.1 已确认的硬件信息

| 项目 | 事实 | 来源与置信度 |
|---|---|---|
| 外观/尺寸/重量 | 73×36.5×14.7 mm；20.7 g（英文页写 20 g） | 官方产品页，A |
| 电池 | 锂聚合物 **402030 3.7V 180mAh**（拆机照片电池丝印直读）；续航 8h、充电 1–2h | `assets/ohirune52_zero2_open.jpg`（日本维修博客 <http://ohirune52.sblo.jp/article/190132491.html>），A- |
| 充电/数据口 | **Micro-USB**（拆机照片直读）；仅充电+固件升级，不做 HID | 官方 FAQ，A；照片 A- |
| 按键结构 | 十字键+ABXY 为导电胶/锅仔片接触式；L/R 为贴片轻触开关；Select/Start 在前壳上有独立圆形键帽；主板靠电池压住固定，外壳为**卡扣+胶**（拆解需撬，易留痕） | 维修博客/拆机照片，A- |
| 主控架构 | **双芯片方案**：固件 `.dat` 内含**两段镜像**（见 5.3），板上照片也可见**两颗 QFN**——一颗较大（约 8 焊盘/边）、一颗较小（约 7 焊盘/边），外加金属封装晶振、PCB 天线、Micro-USB 座、电池焊盘 | 固件头 A + 照片 A- |
| 主控具体型号 | **未确认**。照片分辨率不足以读芯片丝印（放大增强后仍不可读），且 Zero 2 无 FCC 内部照片 | U |
| SWD/JTAG/UART 测试点 | **未确认**。照片可见若干圆形过孔/测试点，但没有丝印标注的调试排针/焊盘；无法从照片判定是否为 SWD/UART | U |
| Micro-USB 的 D+/D- 是否接 MCU | **是（功能上）**：官方固件升级必须经 USB，说明数据线接入了可编程芯片；但**不能**当 HID 用（固件层限制） | A（官方 FAQ + 升级事实） |
| 充电 IC | 未确认（照片无法辨认；估计为 SOT-23-5/6 封装充电管理） | U |

拆机照片（`assets/reddit_zero_vs_zero2_pcb.jpg`，原图 3008×2000）直读信息：
- 上排是 **Zero 2 主板**：青绿色 PCB、丝印 `KB-6160`（板号）、两颗 QFN、金属晶振、Micro-USB、L/R 贴片开关、按键触点。
- 下排是 **Zero 1 主板**（对照）：更大的绿色 PCB，已被改造成街机摇杆，飞线焊接。
- 来源：Reddit r/8bitdo《8bitdo Zero and Zero 2 PCB》(u/igotchees21, 2020-08-25)：<https://www.reddit.com/r/8bitdo/comments/ighlet/8bitdo_zero_and_zero_2_pcb/>（原图直链 <https://i.redd.it/igmhnwbqv6j51.jpg>）。

### 5.2 FCC 备案情况（重要：Zero 2 没有）

| 设备 | FCC ID | 内部照片 | 结论 |
|---|---|---|---|
| Zero 1（2017） | `2AH7N-ZERO` | 有（可下载） | 可看到 Zero 1 主板（绿色 PCB、QFN 主控、Micro-USB、天线），但**不是** Zero 2 |
| Zero 2（2019） | **未找到** | 无 | 在 `2AH7N`（12 个 ID）与 `2AOWF`（57 个 ID）两个 grantee 名下均无 Zero 2 备案；FCC ID 搜索「8bitdo zero」只返回 Zero 1 与键盘类产品 |
| Micro（2023） | `2AOWF-MICRO` | 有 | 内部照片可见双板结构+单颗 QFN SoC+PCB 天线；测试报告证明为 **BT3.0 经典蓝牙**（工程路径 `FCC-BT3.0`，GFSK 1Mbps） |

- Zero 1 FCC 页：<https://fccid.io/2AH7N-ZERO>（内部照片 `assets/zero1_fcc_internal_pcb.jpg`、原件 `assets/zero1_fcc_internal_photos.pdf`）
- Micro FCC 页：<https://fccid.io/2AOWF-MICRO>（内部照片/PCB 特写 `assets/micro_fcc_internal_photos_p1.png`、`assets/micro_fcc_pcb_closeup_p1.png`）
- 8BitDo grantee 列表：<https://fccid.io/2AH7N>、<https://fccid.io/2AOWF>
- **影响**：无法从官方渠道获得 Zero 2 芯片级照片，MCU 型号只能靠实物拆机读丝印（本机无实物）。

### 5.3 固件文件头分析（与 task-1 的固件分析交叉核对，只读引用）

本地文件（由 task-1 下载，位于 `zero2-keyboard/firmware-patch/`）：
`Zero2_V1.06.dat`（123,960 B）、`Zero2_V1.08.dat`（124,472 B）。`.dat` 头为 **28 字节**（格式与 8BitDo 其他型号一致：版本/内部版本/目标地址/长度/model·PID/校验/保留）：

| 段 | 版本 | 目标地址 | 载荷长度 | model 字段 | 解读 |
|---|---|---|---|---|---|
| sec0 | v1.06 / v1.08 | `0x08003400` | 51,200 B | `0x0000` | 主控 MCU 固件；目标地址落在 `0x08000000` Flash 区，是 **STM32/类 STM32（ARM Cortex-M）** 的典型映射，**不是** Nordic nRF（nRF 从 0x00000000 起）→ 主控架构为 Cortex-M |
| sec1 | v1.06 / v1.08 | `0x01018000` | 72,704 / 73,216 B | `0x9018` | 第二颗处理器（蓝牙 SoC）固件；`0x9018` 恰好等于 Zero 2 在 X-input 模式的 USB PID `2DC8:9018`，与该机型 PID 表吻合 |

补充：
- 载荷高熵（16KB 采样 256 种字节值全出现），与 8BitDo 的固件加密相符；社区 8CryptDo 项目已逆向其「链式 + 自定义流密码 + 种子表」加密算法，提供解密/重加密脚本：<https://github.com/aeromodes/8cryptdo>。这说明固件**可被解包研究**，但不等于能安全改键（见第 7 节风险）。
- 旧型号固件目录（可对照头部格式）：<https://github.com/fwupd/8bitdo-firmware>。
- 结论：Zero 2 = **Cortex-M MCU + 独立 Classic 蓝牙 SoC 的双芯片架构**（A/强推断），与「板上两颗 QFN」互相印证；具体料号（MCU 是 STM32F0/F1 还是 ST 兼容片、蓝牙 SoC 是哪家）需实物读丝印或继续解密固件里的字符串才能定。

---

## 6. 对比：8BitDo Micro（2023）能不能当「买替代品」

### 6.1 规格对比（官方数据）

| 项目 | Zero 2（2019） | Micro（2023） | 备注 |
|---|---|---|---|
| 尺寸/重量 | 73×36.5×14.7 mm / 20.7 g | 72×40.7×14.1 mm / 24.8 g | 几乎一样大，Micro 略宽略重 |
| 电池/续航 | 180mAh，8h | 180mAh，**12h** | 同为 1–2h 充电 |
| 充电/数据口 | Micro-USB | **USB-C** | |
| 模式 | X-input / D-input / Switch / macOS（固件解锁）/ **Keyboard** | **D-input / Switch / Keyboard**，实体开关 S/D/K | Micro **没有 X-input**（现代 PC 游戏只认 XInput，Micro 不行；D-input 仅部分老游戏/模拟器可用）；Zero 2 有 X-input |
| 按键数 | 12 | **16**（增加 L2/R2、Home、Screenshot/Star 等） | |
| Keyboard 模式可改键 | **否**（固定 c…o） | **是**：用 **手机版 8BitDo Ultimate Software**（iOS/Android）改单键/组合键，仅键盘模式 | 官方英文页：「Map any button you like using 8BitDo Ultimate Software on your iOS or Android device in Keyboard Mode」 |
| Keyboard 模式有线 | 否（USB 仅升级/充电） | **是**：模式开关拨到 K，**USB-C 直连即被识别为 USB 键盘**（说明书有独立页） | 对「自定义键盘」是巨大优势：不用蓝牙、不受 BLE/Classic 限制 |
| 固件更新 | Firmware Updater | Firmware Updater / Ultimate Software | |
| 官方价 | 美区约 US$19.99 | 美区 MSRP **US$24.99**（街价约 $15–25）；国内京东促销曾见 **99 元**（比价站收录，未直连核实） | 价格仅供参考，渠道价波动大 |

Micro 官方页：<https://www.8bitdo.cn/micro/>（<https://www.8bitdo.com/micro/>）；FAQ：<https://support.8bitdo.com/faq/micro.html>；
说明书键盘模式（蓝牙/有线）：<https://manual.8bitdo.com/micro/micro-keyboard-bluetooth.html>、<https://manual.8bitdo.com/micro/micro-keyboard-wired.html>；
Ultimate Software 支持列表：<https://app.8bitdo.com/>（Micro 在「Ultimate Software（V1 旧设备）iOS/Android 手机版」清单中，**不在** V2 桌面/手机清单中——请向用户纠正「V2 可改键」的说法，实际是**手机版**）。

### 6.2 Micro 是不是同源？跨型号刷固件有没有先例？

- **外观/尺寸**：同系列（官方共用「Micro/Zero 2 手机支架」配件），尺寸接近，但 Micro 多按键、USB-C、实体模式开关，**不是同一块板**。
- **主控/固件**：Micro 的 FCC 测试报告证明其无线电为 **BT3.0 经典蓝牙**（与 Zero 2 同技术路线），但两者固件按型号/目标地址区分（Zero 2 的 `.dat` 是双段；Micro 有独立 FCC ID 与独立更新链路）。**没有任何公开证据**表明二者 MCU/固件同源或可互刷。
- **跨型号刷固件先例**：未检索到任何 Zero 2 ↔ Micro 互刷案例。8BitDo 官方 `.dat` 头部含目标地址与 model/PID 字段，官方更新器按设备型号下发；社区「让官方更新器刷任意 .dat」的项目（<https://github.com/fanatic75/8bitdo-mac-flash>）明确警告：**只刷你的确切型号**，模型不匹配是最可能造成真实损坏的方式。
- **即使刷成功也没用**：Micro 的「可改键」是 **App 写入设备的配置**，不是固件功能；而且两款按键矩阵/数量不同（Micro 有 L2/R2、Home 等），Zero 2 刷 Micro 固件不可能凭空得到 Micro 的按键配置能力，大概率直接变砖。
- 结论：**跨型号刷固件不可行、不建议**；`U`（无成功先例，风险高，价值低）。

### 6.3 「买 Micro」的取舍（给方案决策用）

- ✅ 官方支持自定义键盘映射（手机 App；单键/组合键都行），键盘模式有线/无线两种，插线就是标准 USB 键盘 —— 对 PC/iPad 的「自定义键盘」需求**直接满足**，不用写 dongle、不用主机端软件。
- ⚠️ 改键只能手机 App（iOS/Android），**没有**桌面版；配置存在设备里、可迁移但改起来要手机。
- ⚠️ 无 X-input：只当键盘/2D 手柄用没问题，当**现代 PC 游戏**手柄不行（D-input 仅老游戏/模拟器可用）。
- 💰 价格约 $25 / 国内百元级，比继续折腾 Zero 2 的硬件方案便宜。
- 结论：**如果用户要的是「自定义键盘输出」，Micro 是当前最优解**；Zero 2 保留给「不介意固定 c…o 字母 + 主机端重映射」的场景。

---

## 7. 社区改键/换固件/飞线记录（中/英/日）

| 类型 | 记录 | 结果/教训 | 来源 |
|---|---|---|---|
| 主机端重映射（Linux/macOS） | Anki 遥控教程：键盘模式 + input-remapper（Linux）/ Karabiner-Elements（macOS）把 c/d/e/f… 改成想要的键 | 可用；键盘模式本身固定，改的是系统层 | <https://gist.github.com/emleddin/d25eb8493e16a7e262d156e7c8f53e77> |
| 主机端重映射（Windows，手柄模式+软件） | 日文 HackMD 左手设备方案：**不用键盘模式**，改用 X-input + XPadLauncher/SendKey 把按键映射成任意快捷键；也提到 15 分钟自动关机 | 可用；说明「键盘模式映射固定」不满足需求时，社区走主机软件路线 | <https://hackmd.io/@piksware/LeftDevice8Bit> |
| 用户吐槽/选型 | 长毛象用户实测键盘模式字母 cdefghikmno「不支持改键」，并提到 Micro 可自定义键、大小差不多但更贵 | 与官方信息一致 | <https://mastodon.fivest.one/@fivestone/113124490270142724> |
| 飞线改按键（不是改键） | Reddit：把 Zero 2 主板拆出来做「旅行街机摇杆」，飞线接 A/B/X/Y、十字键、L/R/Start/Select | **可焊但极难**：Zero 2 **不是公共地**（Zero 1 是），需要分 3 组共地；走线 30AWG 仍偏粗；作者建议用 Lite/FocusAttack PCB 更省事 | <https://www.reddit.com/r/8bitdo/comments/ighlet/8bitdo_zero_and_zero_2_pcb/> |
| 第三方固件/自定义固件 | 未检索到任何 Zero 2 自定义固件、改键固件、成功换固件案例（中英日）；8CryptDo 只解决「8BitDo 固件加解密」，不含 Zero 2 改键 | 无成功先例；固件可解包但改键需要重写 HID 映射逻辑+重新加密+通过升级校验，风险极高 | <https://github.com/aeromodes/8cryptdo>、<https://github.com/fwupd/8bitdo-firmware> |
| 让官方工具刷任意 .dat | fanatic75/8bitdo-mac-flash：替换官方 macOS 更新器要下载的固件，可刷「任意 .dat」；.dat 头含 model 字段；**只刷确切型号**，模型不符最危险 | 证明「刷非官方固件」在机制上可行，但没有 Zero 2 可用固件；模型不匹配会真损坏 | <https://github.com/fanatic75/8bitdo-mac-flash> |
| 手柄模式被 Bluepad32 支持 | Bluepad32（ESP32/Pico W）支持 Zero 2 的 Switch/Android/Windows/macOS 模式，协议 BR/EDR；键盘模式不在其「已测键盘」清单 | 对 dongle 方案：**必须用支持 Classic 的芯片**（原版 ESP32/Pico W），ESP32-S3/C3 不行 | <https://bluepad32.readthedocs.io/en/stable/supported_gamepads/>、<https://bluepad32.readthedocs.io/en/stable/supported_keyboards/> |

**失败/风险案例小结**：没有「Zero 2 改键成功」的公开案例；失败/放弃案例集中在「想用固定键盘模式做自定义快捷键 → 只能主机端重映射」和「飞线改按键板 → 非公共地导致难度高」。

---

## 8. 未确认项 + 建议的验证实验（给后续任务）

### 8.1 未确认（U）

1. MCU 具体料号与蓝牙 SoC 厂商/型号（需拆机读丝印，或解密固件里的初始化字符串/版本 banner）。
2. Keyboard 模式连接瞬间的 HID Profile 直接抓包（现有日志为 D-input 模式；Classic 结论为强推断）。
3. Keyboard 模式的 VID/PID（推断不是 9018/3230，需 Windows 实测）。
4. Select/Start 输出 N/O：配图 + 实测帖一致，但唯一英文 gist 未覆盖；建议实物按一遍。
5. 充电 IC、是否有 SWD/UART 测试点、Micro-USB D+/D- 具体走线到哪颗芯片（照片不可辨）。
6. Micro 的主控/固件与 Zero 2 是否同源（无公开资料；跨刷无先例）。
7. 国内实时价格（天猫/京东反爬，未取得官方旗舰店现价）。
8. 「组合键同时输出多字母」的具体按键时序（推断）。

### 8.2 建议验证清单（有实物时，10–30 分钟）

1. **传输层**：Linux 下键盘模式配对，`bluetoothctl info <MAC>` 看是否出现 `00001124`（Classic HID）还是 `00001812`（BLE HOGP）；同时 `sudo btmon` 抓配对过程。
2. **键位**：键盘模式连任意文本编辑器，逐个按键记录输出（含 Select/Start、Select+Start 组合）。
3. **VID/PID**：Windows「设备和打印机 → 属性」或 Linux `btmon`/`lsusb`（有线升级模式）记录两组 ID。
4. **D-pad 组合键**：确认 `+Select`/`←+Select`/`→+Select` 在键盘模式是否无效（预期仅游戏模式生效）。
5. **USB 实测**：插 USB 到 PC，确认只充电/进升级模式，不出现 HID 键盘（印证官方说法）。
6. **拆机（谨慎）**：撬壳后给两颗 QFN 拍微距、读丝印；同时看 Micro-USB 的 D+/D- 走线与测试点。

---

## 9. 来源清单

### 官方

1. Zero 2 中文产品页 — <https://www.8bitdo.cn/zero2/>
2. Zero 2 英文产品页 — <https://www.8bitdo.com/zero2/>
3. Zero 2 FAQ 中文 — <https://support.8bitdo.cn/faq/zero2.html>
4. Zero 2 FAQ 英文 — <https://support.8bitdo.com/faq/zero2.html>
5. Zero 2 说明书（键盘模式中文） — <https://manual.8bitdo.cn/zero2/zero2_keyboard_mode.html>
6. Zero 2 说明书英文各页 — <https://manual.8bitdo.com/zero2/zero2_keyboard_mode.html>、`zero2_windows.html`、`zero2_switch.html`、`zero2_android.html`、`zero2_macos.html`
7. 官方说明书 PDF — <https://download.8bitdo.com/Manual/Controller/Zero2/Zero2_Manual.pdf>（本地 `assets/Zero2_Official_Manual.pdf`）
8. 升级工具 — <https://support.8bitdo.com/firmware-updater.html>
9. Micro 中文产品页 — <https://www.8bitdo.cn/micro/>
10. Micro 英文产品页 — <https://www.8bitdo.com/micro/>
11. Micro FAQ — <https://support.8bitdo.com/faq/micro.html>
12. Micro 键盘模式（蓝牙/有线） — <https://manual.8bitdo.com/micro/micro-keyboard-bluetooth.html>、<https://manual.8bitdo.com/micro/micro-keyboard-wired.html>
13. Ultimate Software 支持列表 — <https://app.8bitdo.com/>

### 数据库/拆解/固件

14. FCC 2AH7N-ZERO（Zero 1） — <https://fccid.io/2AH7N-ZERO>
15. FCC 2AOWF-MICRO（Micro） — <https://fccid.io/2AOWF-MICRO>
16. FCC grantee 列表（确认 Zero 2 无备案） — <https://fccid.io/2AH7N>、<https://fccid.io/2AOWF>
17. Reddit《8bitdo Zero and Zero 2 PCB》 — <https://www.reddit.com/r/8bitdo/comments/ighlet/8bitdo_zero_and_zero_2_pcb/>（原图 <https://i.redd.it/igmhnwbqv6j51.jpg>）
18. 日本维修博客（拆机电池照） — <http://ohirune52.sblo.jp/article/190132491.html>
19. Bluetooth 日志（Classic HID UUID/VID/PID） — <https://scrapbox.io/saitotetsuya/8BitDo_Zero_2>
20. InputConfig 控制器 ID 数据库 — <https://inputconfig.com/tools/controller-id-lookup>
21. fanatic75/8bitdo-mac-flash（.dat 格式/刷任意固件/警告） — <https://github.com/fanatic75/8bitdo-mac-flash>
22. fwupd/8bitdo-firmware（旧固件目录） — <https://github.com/fwupd/8bitdo-firmware>
23. aeromodes/8cryptdo（固件加密逆向） — <https://github.com/aeromodes/8cryptdo>
24. Bluepad32 支持列表/FAQ（8BitDo=BR/EDR；S3/C3 不支持） — <https://bluepad32.readthedocs.io/en/stable/supported_gamepads/>、<https://bluepad32.readthedocs.io/en/stable/FAQ/>
25. Bluepad32 支持的键盘 — <https://bluepad32.readthedocs.io/en/stable/supported_keyboards/>

### 社区/教程

26. 日文 HackMD 左手设备教程（键位图） — <https://hackmd.io/@piksware/LeftDevice8Bit>
27. 日文零售说明书 PDF（键位图页） — <https://yourtreasure.jp/wp-content/uploads/2023/12/8Bitdo-ZERO2-%e3%83%af%e3%82%a4%e3%83%a4%e3%83%ac%e3%82%b9%e3%82%b3%e3%83%b3%e3%83%88%e3%83%ad%e3%83%bc%e3%83%a9%e3%83%bc-%e6%97%a5%e6%9c%ac%e8%aa%9e%e8%aa%ac%e6%98%8e%e6%9b%b8.pdf>
28. Anki 教程 gist — <https://gist.github.com/emleddin/d25eb8493e16a7e262d156e7c8f53e77>
29. 长毛象实测/吐槽 — <https://mastodon.fivest.one/@fivestone/113124490270142724>
30. FSU 医学院 Anki 配置说明（Zero 2/Micro 配对） — <https://fsumed.teamdynamix.com/TDClient/2884/Portal/KB/Article/167439/How-to-pair-and-configure-8bitdo-Zero-2-and-Micro-remote-for-Anki-Windows>
31. 价格参考：Amazon Zero 2 <https://www.amazon.com/dp/B081HML6MP>、Amazon Micro <https://www.amazon.com/dp/B0CDG5HCCH>；京东促销 99 元（比价站收录）<https://guangdiu.com/detail.php?id=30256797>

---

## 10. 本地资产清单（`zero2-keyboard/research/hardware/assets/`）

| 文件 | 内容 | 来源 | 置信度 |
|---|---|---|---|
| `Zero2_Official_Manual.pdf` | 官方 Zero 2 说明书 PDF（7.7MB，矢量图，未渲染成图片） | download.8bitdo.com | A |
| `zero2_manual_jp.pdf` | 日文零售版说明书（含键位图） | yourtreasure.jp | A- |
| `jp_manual_keyboard_mode_keymap.jpg` | **键盘模式键位图**：K/M、C/D/E/F、H/I/J/G | 同上 PDF 内嵌图 | A- |
| `jp_manual_button_labels.jpg` | 手柄按键命名图（十字键/L/R/Select/Start/ABXY/X/Y） | 同上 | A- |
| `jp_manual_paint_app_shortcuts.jpg` | 官方宣传的「画画软件快捷键」示意（撤销/钢笔/笔刷大小等） | 同上 | A- |
| `hackmd_zero2_keyboard_mode_keys.png` | 社区键位图，含 **Select=N、Start=O** | HackMD 教程 | B |
| `reddit_zero_vs_zero2_pcb.jpg` | Zero 1（下）与 Zero 2（上）主板对照照片，3008×2000 | Reddit u/igotchees21 | A- |
| `crop_zero2_two_qfn_photo.jpg` | Zero 2 主板放大：可见两颗 QFN、晶振、外围 | 同上裁切 | A-（丝印不可读） |
| `ohirune52_zero2_open.jpg` | 拆机照：402030 180mAh 电池、青绿 PCB、Micro-USB | 日本维修博客 | A- |
| `zero1_fcc_internal_pcb.jpg` | Zero 1 FCC 内部照片（对照用） | fccid.io/2AH7N-ZERO | A |
| `zero1_fcc_internal_photos.pdf` | Zero 1 FCC 内部照片原件 | 同上 | A |
| `micro_fcc_internal_photos_p1.png` | Micro FCC 内部照片（双板结构、QFN、PCB 天线） | fccid.io/2AOWF-MICRO | A |
| `micro_fcc_pcb_closeup_p1.png` | Micro PCB 特写（单颗 QFN SoC + 天线馈点） | 同上 | A |

---

## 11. 核查方法与限制

- 本机无 Zero 2/Micro 实物，未做电气测量与真实 pairing；所有硬件结论来自照片、FCC 文件与固件头。
- 沙箱内 `pwsh` 直连 HTTPS 被拦截（schannel 失败），改用工作区自带 Python `urllib` 下载图片/PDF；FCC 官方站点被 Akamai 拒绝，改用 fccid.io 镜像；Reddit 主站 403，改用 redlib 镜像取正文 + `i.redd.it` 直链取原图。
- 尝试 `pip install pymupdf` 渲染官方 PDF 成截图未成功（安装超时），故本目录只保存 PDF 原件与官方说明书截图/日文说明书内嵌图；官方中文/英文说明书网页内容已逐页人工抄录于第 1、2 节。
- 固件 `.dat` 头部数据引自 task-1 下载的 `zero2-keyboard/firmware-patch/Zero2_V1.06.dat`、`Zero2_V1.08.dat`，本任务仅只读头部做交叉核对，未修改固件目录任何文件。
- 与 task-1（固件/DFU 逆向）、task-3（外挂 dongle/主机端方案）的接口：本文件第 3/5.3/7 节的结论（Classic BR/EDR、双芯片、需 Classic 蓝牙主机、跨型号刷机无价值）请直接采信，避免重复验证。
