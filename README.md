# 8BitDo Zero 2 自定义键盘：可行性调查与实作（设备级改键）

> 目标：让 **8BitDo Zero 2** 的 Keyboard 模式输出**你自定义的键**，而不只是官方固件里那套固定的 `c/d/e/f/n/o/g/j/h/i/k/m`。
>
> ✅ **2026-11-13 已在真实手柄上跑通**（出厂 v1.05 → 刷入自编译 v1.09 identify 固件）：
> 官方更新器显示「从 v1.05 升级到 v1.09 / 更新成功」，设备重启后报告 Version 1.09；
> R+Start 键盘模式配对 PC 后实测 12 个按键依次输出 **F1–F12**，与刷入的映射表完全一致。
> 证据：[`flash/evidence/`](flash/evidence/README.md)、刷写流程 [`flash/README.md`](flash/README.md)。
>
> 结论：**设备级改键可行且已验证**——官方固件没签名、加密已被社区逆出（8cryptdo），
> 我们把固件解密→改 12 字节键位表→重加密（与官方逐字节可复现）→借官方工具的明文 HTTP 下载通道刷入。

---

## 0.5 实机验证结果（2026-11-13）

| 步骤 | 结果 |
|---|---|
| 初始固件 | v1.05（普通模式 USB `VID_2DC8&PID_9018`，HID gamepad） |
| 刷入 | 自编译 `Zero2_V1.09_identify.dat`（版本头 109，12 键→F1…F12） |
| 刷写日志 | `verification id ok` → `SendFirmwareHeader` → `desVersion is 109` → progress 0–99 → `update successful` |
| 刷后 | 设备重启回 `2DC8:9018`，更新器显示「从 v1.05 升级到 v1.09 / 更新成功」，工具检测 Version 1.09 |
| 键盘模式实测 | R+Start 配对 PC，按 ↑↓←→ Select Start A B X Y L R → 输出 **F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12**（12/12） |

**实机踩到的两个关键坑**（已在 `flash/README.md` 写明）：
1. 必须先让手柄以**普通模式**（`2DC8:9018`）连 USB，由官方工具自己发 jump boot；
   手动按住 L+R+START 进升级模式时，工具能下载固件但刷写库会无限 `resend GET_ID_DATA`（不写入）。
2. 官方更新器的“下载完整性校验”其实是 **`MD5(文件字节数.ToString())`**（不是文件内容 md5）；
   代理里的 `md5` 字段必须按这个规则填，否则会重试 6 次后报「网络下载固件错误」。

---

## 0. 一句话回答你的三个疑问

| 你的猜想 | 结论 |
|---|---|
| 制作第三方固件烧进设备？ | **可行，且不用从零写固件**。官方 `.dat` 可解密（GD32 + Yichip 两段），键位表就是两段各 12 字节；改完用同一套加密重打包即可。本仓库已生成成品：`firmware-patch/out/`。 |
| MicroUSB 口通信？ | 普通模式**不通**（官方 FAQ：有线只能升级固件，不能当键盘/手柄）；但刷写时设备进 boot 模式后就是标准 HID，官方工具通过 HID 报告擦写。我们做的是"劫持官方工具的固件下载"，让它把我们重加密的固件写进去。 |
| 官方不支持键盘模式自定义？ | 对，官方 Ultimate Software/升级工具都不支持 Zero 2 改键；但这条限制在**固件二进制层面**可以绕开（本文档），在**接收端**也可以绕过（外挂 dongle / 主机端改键，见 [`research/alternatives`](research/alternatives/README.md)）。 |

---

## 1. 先把事实钉死（这些决定了方案选型）

- **Zero 2 有 Keyboard 模式**：`R + Start` 开机，LED 5 闪/周期，蓝牙名 `8BitDoZero 2 gamepad`，所有按键输出英文字符，需英文输入法（[官方键盘模式教程](https://manual.8bitdo.com/zero2/zero2_keyboard_mode.html)）。
- **键位固定**（官方值 + 社区两份独立实测一致，12/12 吻合）：

  | 按键 | ↑ | ↓ | ← | → | Select | Start | A | B | X | Y | L | R |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 输出 | C | D | E | F | N | O | G | J | H | I | K | M |
  | HID 码 | 0x06 | 0x07 | 0x08 | 0x09 | 0x11 | 0x12 | 0x0A | 0x0D | 0x0B | 0x0C | 0x0E | 0x10 |

- **传输层是蓝牙经典 BR/EDR HID**，不是 BLE（键盘模式实测 `UUID 0x1124`、`Modalias usb:v2DC8p3230d0100`；X-input 运行时 PID `2DC8:9018`）。对"外挂 dongle"路线是硬约束：ESP32-S3/C3 只有 BLE，**连不上** Zero 2，必须原版 ESP32 或 Pico W。
- **USB 口只用于充电 + 固件升级**（[官方 FAQ](https://support.8bitdo.cn/faq/zero2.html)），不存在"插线变键盘"。
- **硬件是双芯片**：`.dat` 两段头（段0 目标 `0x08003400`，STM32 类主控；段1 目标 `0x01018000`，蓝牙 SoC，model/PID `0x9018`）与拆机两块 QFN 互证；具体料号未确认，8cryptdo 记录近期拆机为 **YC3121**。Zero 2 无 FCC 备案、板上无丝印 SWD/JTAG 测试点。
- **官方升级工具**：Windows .NET WinForms + 原生 HID 刷写 DLL；固件走**明文 HTTP** `http://dl.8bitdo.com:8080`，**无签名、无下载完整性校验**（API 自报 md5 与实际文件都不符），"高级模式"实际是"手动选型号+从服务器下载"，**没有本地文件选择器**。

详细证据见 [`research/firmware`](research/firmware/README.md)（刷写工具/协议/校验点）与 [`research/hardware`](research/hardware/README.md)（拆解/键位/HID 传输层）。

---

## 2. 四条路线总表

| # | 路线 | 成本 | 折腾度 | 状态 | 适合 |
|---|---|---|---|---|---|
| **A** | **设备级改固件**（本仓库核心）：解密官方固件→改 12 字节键位表→重加密→借官方工具刷入 | ¥0 | 中高 | ✅ **已实机验证**（v1.05→v1.09，键盘输出 12/12 正确） | 想"手柄本身就是自定义键盘"，换任何宿主都有效 |
| B | 外挂 dongle：Zero 2 走手柄模式，接收端重映射后输出 USB HID 键盘（Pico W + HID Remapper 零代码；或 ESP32 原版 + CH9329 自写固件） | ¥25–75 | 中 | 方案/代码已备（见 [`esp32-dongle/`](esp32-dongle/README.md)） | 不想动固件、要即插即用 USB 键盘（iPad/PC/电视盒子都行） |
| C | 主机端软件改键（Windows AHK/PowerToys、macOS Karabiner、Linux keyd/input-remapper、Android Key Mapper） | ¥0 | 低 | 脚本已备（[`windows/`](windows/README.md)） | 只在某一台电脑上用；iPadOS 没有全局方案 |
| D | 买 8BitDo Micro（官方支持键盘模式 + 手机版精英软件自定义映射，USB-C 有线也能当键盘） | ¥99–149 | 最低 | 调研完成 | 只想快速解决、不想折腾 |

---

## 2.9 首次使用：下载官方固件（仓库不再包含固件二进制）

由于 8BitDo 固件的版权原因，仓库**不提供**官方 `.dat` 文件。首次构建/刷写前先在仓库根目录运行：

```bash
python firmware-patch/download_official_firmware.py
```

脚本会：
- `POST http://dl.8bitdo.com:8080/firmware/select`（Headers: `Beta: 1`, `Type: 30`）取 Zero 2 的 v1.08 条目；
- 从 `http://dl.8bitdo.com:8080/firmwareFile/upload/<uuid>.dat` 下载到 `firmware-patch/Zero2_V1.08.dat`；
- 校验大小 `124472` 与内容 `sha256=43a31356…609da808`（官方 API 里的 `md5` 字段是 `MD5(str(fileSize))`，不是内容哈希）；
- 下载失败时打印手动下载指引；也可以从官方更新器页面自己下 v1.08，放到该路径。

GUI 首次启动时如果发现缺少固件，也会自动尝试下载（`gui/fwlib.py` 调用同一个模块）。

---

## 3. 我们实际做了什么（证据链）

### 3.1 拿到官方固件（而不是"从官网下载"——官网已不提供直链）
8BitDo 官方升级工具走一个未公开 API：

```
POST http://dl.8bitdo.com:8080/firmware/select      Headers: Beta: 1, Type: 30
  -> {"msgState":1,"error":"","list":[{"fileName":"Zero 2 gamepad","version":1.08,
      "fileSize":124472,"filePathName":"/firmwareFile/upload/69749f0f-...dat","md5":"..."}]}
GET  http://dl.8bitdo.com:8080/firmwareFile/upload/69749f0f-...dat
```

> 坑：设备表里的 `type=29` 是旧值，**固件 API 实际用 Type=30** 才返回 Zero 2。
> 已取得 v1.08（2025-06，124,472 B，`sha256=43a31356…609da808`）与 v1.06。

### 3.2 解密 → 改表 → 重加密，并证明管线正确
- 用 [8cryptdo](https://github.com/aeromodes/8cryptdo)（AeroModes，MIT）解出两段明文：段0 GD32 cipher、段1 Yichip cipher；每段头 28 字节（version/addr/len/pid）。
- **关键验证**：把解密出的明文用原参数重新加密，得到的文件与官方 v1.08 **逐字节完全相同（sha256 一致）** → 加密管线可信，改完重加密不会破坏结构。
- 定位键位表：两段里各有一份 **12 字节**、内容为 `06 07 08 09 11 12 0a 0d 0b 0c 0e 10` 的表（v1.08 在段0 `0xaf6c`、段1 `0x103a7`；v1.06 位置不同，所以工具按**内容模式**定位，不写死偏移）。这正是键盘模式"按键→HID 键码"查找表，索引顺序 = ↑↓←→ Select Start A B X Y L R（与官方值 + 社区实测 12/12 对齐）。
- 打补丁：两段各改 12 字节 → 重建文件；**文件大小 124,472 B 不变、addr/len/pid 不变、只改 24 字节**；版本头从 108 调到 109（避开官方工具"版本不新"的检查）。自检：重新解密补丁文件、逐字节比对，确认无其他改动。

### 3.3 刷写通道（已实机跑通）
官方工具的"高级模式"不吃本地文件，所以：本机起一个小 HTTP 代理 → 系统代理指过去 →
官方工具在**普通模式**（`2DC8:9018`）识别到手柄 → 点「固件更新」→ 代理返回"v1.09 + 我们的文件" →
工具自动 **jump boot → 校验 → 写入 → 设备重启**。实测日志与截图见 [`flash/evidence/`](flash/evidence/README.md)。

关键细节（都踩过）：
- **从普通模式开始**，不要手动进 boot 模式；jump boot 由官方工具完成。
- 代理返回的固件列表 `md5` = `MD5(str(fileSize))`（官方校验的就是长度字符串），不是内容 md5。
- 每次重刷版本号 +1；本环境更新器写 `%LOCALAPPDATA%` 被拒会崩溃，用 junction 绕过（普通用户环境一般不需要）。

hosts 劫持/DLL 直调作为备用方案保留在 [`flash/README.md`](flash/README.md)。

### 3.4 已经验证 vs 还没验证
| 项 | 状态 |
|---|---|
| 官方固件获取（v1.06/v1.08） | ✅ 由 `download_official_firmware.py` 从官方接口下载并校验 sha256 |
| 解密 / 重加密管线（与官方逐字节一致） | ✅ 已证明 |
| 键位表定位、索引↔按键对应 | ✅ 官方值 + 社区实测 12/12 吻合 |
| 补丁文件结构自检（大小/头部/仅 24 字节差异） | ✅ 通过 |
| 本地代理逻辑（select 返回 1.09、dat 返回补丁字节） | ✅ selftest 通过 |
| **实机刷写**（v1.05 → 自编译 v1.09） | ✅ **已成功**（2026-11-13，日志/截图见 `flash/evidence/`） |
| **刷后键盘模式输出自定义键** | ✅ **12/12 键实测 F1–F12 正确** |
| **GUI 自动刷写**（官方 1.08 基线 → `1.08.1` 翻页器） | ✅ **已成功**（2026-11-13 21:52/21:53，自动完成生成→代理→更新器→写入→重启，版本校验 108） |
| **`1.08.1` 翻页器键盘输出** | ✅ **12/12 键实测**（PageUp/PageDown/Home/End/Esc/Enter/Space/Tab/Backspace/Delete/Left/Right，见 `flash/evidence/04_*`、`05_*`） |
| 刷坏/卡升级模式后的恢复 | ✅ 官方更新器直接刷回官方 1.08（实测可行，无需拆机） |
| 段1（蓝牙 SoC 固件）是否被写入 | ⚠️ updateLog 只显示段0（主控 0xc800 @0x08003400）被写；键盘映射由段0生效，输出正确 |

### 3.5 现在的状态与下一步
0. 首次使用先运行 `python firmware-patch/download_official_firmware.py` 下载官方 v1.08（仓库不含固件）；
1. 设备当前跑的是 **`1.08.1` 翻页器固件**（官方 1.08 基线 + 12 字节键位表改动）；想换布局随时再刷；
2. **推荐用图形界面**（[`gui/`](gui/README.md)）：双击 `gui/启动.bat` → 选预设/改键 → 点「刷写到手柄」，自动生成并刷入；标签自动 `1.08.2`、`1.08.3`…
3. 版本规则：标签 `1.08.N`；固件头保持 `108`（官方基线），对更新器报 `1.08 + N/1000`，所以更新器界面显示 `V1.08` 但数值递增、可连续刷；
4. 出问题/恢复：**直接打开官方更新器，用官方固件刷回 1.08**（已实测；不要手动进 boot 模式，也不用手动拆机）。

### 3.6 图形界面（gui/，一键改键+刷写）
- 入口：`gui/启动.bat`（在普通 Windows 会话双击运行；不要在 DSH 沙箱里跑刷写）。
- 功能：**点左侧官方手柄渲染图上的按键** → 右侧选输出键；「我的设定」可命名保存/载入整套键位；「生成固件」或「刷写到手柄」；刷写自动完成"生成 .dat → 本地代理 → 官方更新器 → 高级模式选 Zero 2 → 更新 → 校验下载/版本"；成功后标签 +1 并写回 `gui/config.json`。
- 关键加固：只给更新器写临时 `app.config` 代理（不改系统代理/注册表）；刷前删除更新器下载缓存（防复用旧固件）；刷完校验 updateLog 版本；失败不杀进程。
- 前置：手柄普通模式（按 START 开机）插 USB，顶部状态显示「已连接」。
- 截图：`gui/_gui_shot.png`；CLI：`python gui/zero2_kb_gui.py --flash --preset 翻页器 --patch 1`。

---

## 4. 目录结构

```
zero2-keyboard/
├─ README.md                 ← 本文件（总结+证据链）
├─ firmware-patch/           ← 设备级改键的核心
│  ├─ Zero2_V1.08.dat        ← 官方固件（运行下载脚本后生成；仓库不含、已 gitignore）
│  ├─ download_official_firmware.py ← 从官方接口下载 v1.08 并校验
│  ├─ official_firmware.py   ← 下载/校验模块（GUI 的 fwlib 也会调用）
│  ├─ patch_fw.py            ← 解密/定位表/打补丁/重加密/自检工具
│  ├─ validate_patch.py      ← 补丁差异验证
│  ├─ analyze_fw.py / deep_analyze.py / table_context.py / refs.py  ← 逆向分析脚本
│  ├─ build_custom.ps1       ← 一键构建
│  ├─ profiles/              ← identify / page-turner / drawing / custom-template / stock
│  └─ out/                   ← 成品固件（v1.09 ×3 + v1.10 stock）
├─ flash/                    ← 刷写通道（已实机验证）
│  ├─ patched_updater_proxy.py   ← 本地"固件服务器/代理"（--selftest 可自测）
│  ├─ flash_with_proxy.ps1       ← 一键：代理+官方工具
│  ├─ keycapture.ps1             ← 键盘输出捕获窗口（验证用）
│  ├─ evidence/                  ← 本次刷写日志/截图/按键捕获证据
│  ├─ set_proxy.ps1 / hosts_hijack.ps1 / flash_dll.ps1 / verify_proxy.ps1
│  └─ README.md              ← 刷写手册（已验证流程/风险/回滚/排障）
├─ gui/                      ← 图形界面：改键 + 一键自动刷写（推荐入口）
├─ research/
│  ├─ firmware/README.md     ← 官方工具/DFU 逆向报告（fw-re）
│  ├─ hardware/README.md     ← 拆解/芯片/键位/HID 证据（hw-re，含说明书 PDF/拆机照）
│  └─ alternatives/README.md ← 外挂 dongle/主机端/Micro 全路线调研（alt-build）
├─ esp32-dongle/             ← ESP32+CH9329 固件工程、Pico W+HID Remapper 指南
├─ windows/                  ← AutoHotkey v2 零成本改键脚本
└─ _fw-tools/                ← 官方升级工具解包、固件、fwupd/libebitdo 源码、8cryptdo 工具
```

---

## 5. 风险与边界（务必读）

- **这是社区魔改，不是官方支持**；固件版权属 8BitDo，仅用于你自己的设备做互操作/维修实验，不要二次分发固件。
- 刷写有变砖风险（极低但不为零）：改动不碰启动/蓝牙协议栈，只改 24 字节键位表和版本号；
  已实测刷写成功且设备正常重启（v1.09 与 1.08.1）。**刷坏/卡在升级模式的恢复：直接打开官方更新器用官方固件刷回 1.08**（2026-11-13 实测可行，不用拆机）。
- 版本号策略：GUI 用 `1.08.N` 标签（固件头保持 108，对更新器报 1.08+N/1000，可连续刷）；`build_custom.ps1` 仍支持整数版本号。
- **不要手动进 boot 模式刷**（L+R+START 进的那个状态官方刷写库握手会卡 `GET_ID_DATA`）；jump boot 交给官方工具自动做。
- **不要在一次刷写进行到一半时杀掉更新器进程**（会把设备留在半刷状态，只能靠官方更新器重刷恢复）。
- 修饰键组合（Ctrl+Z 之类）依赖宿主把 HID 键码数组里的 `0xE0/0xE1` 识别为 Ctrl/Shift；绝大多数系统可以，个别宿主不认就退回单键映射。
- 主机端方案（AutoHotkey 等）**不能**让手柄在被映射的电脑之外使用；iPadOS 无全局改键，只能 App 内快捷键。

---

## 6. 参考与致谢

- [8cryptdo](https://github.com/aeromodes/8cryptdo)（AeroModes）：8BitDo 固件加密逆向 + `cryptdo8.py`，本文档能改固件的基础。
- [fwupd/8bitdo-firmware](https://github.com/fwupd/8bitdo-firmware)：官方固件 API 调用方式与旧固件归档。
- [fwupd ebitdo 插件](https://github.com/fwupd/fwupd/tree/main/plugins/ebitdo)：老 8BitDo HID 刷写协议/无签名证据。
- 8BitDo 官方：[Zero 2 产品页](https://www.8bitdo.cn/zero2/)、[Zero 2 FAQ](https://support.8bitdo.cn/faq/zero2.html)、[键盘模式教程](https://manual.8bitdo.com/zero2/zero2_keyboard_mode.html)、[固件升级助手页](https://support.8bitdo.cn/firmware-updater.html)。
- 社区键位实测：[emleddin 的 Anki gist](https://gist.github.com/emleddin/d25eb8493e16a7e262d156e7c8f53e77)（Linux/Mac 用 input-remapper/Karabiner 改键）。
- 外挂 dongle 依据：[Bluepad32 FAQ（BR/EDR）](https://bluepad32.readthedocs.io/en/latest/FAQ/)、[HID Remapper](https://github.com/jfedor2/hid-remapper)、[Pico W 经典蓝牙预发布](https://forum.remapper.org/t/bluetooth-classic-on-pico-w-2026-edition/359)。

---

## 7. 免责声明

本项目所有固件/脚本/说明均为**研究性质**，按"现状"提供、不保证无风险。刷机前请确认固件版本、保留官方原件；因刷写导致的设备损坏、数据丢失或保修失效由操作者自行承担。请勿用于商业分发或规避版权。
