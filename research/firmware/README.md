# 8BitDo Zero 2 固件/DFU 逆向：能否刷第三方固件（可行性报告）

> 角色：固件逆向研究员（fw-re）· 任务：task-1
> 分析日期：2026-11-13 · 工作目录：`zero2-keyboard/`
> 结论先行：**"刷入自制固件"在技术上可行，但入口不是官方工具的"高级模式选文件"，而是劫持官方工具的明文 HTTP 固件下载（或复用其原生刷写 DLL）。** 官方对固件文件无签名校验，但有设备 PID、版本与刷后 CRC 三类校验；Zero 2 官方固件本体已取得并解析（两段式，头 28 字节/段）。
> 本报告只做静态分析与验证方案，**未对任何设备执行刷写**。

---

## 1. 结论摘要

### 1.1 能否实现"自定义键盘"？

| 路线 | 可行性 | 前置条件 | 结论 |
|---|---|---|---|
| A. 劫持官方更新器下载 → 喂重加密的自定义 `.dat` | **高**（推荐） | Windows + 官方更新器 + USB 线 + 设备进 bootloader；管理员权限（改 hosts）或系统代理；待刷文件与官方 `.dat` 同结构、同 PID | 最贴近"第三方固件"的真实路径，官方工具负责进 boot/擦除/写入/CRC |
| B. 自己调用官方刷写库 `8BitDoFirmwareUpdaterTools.dll` | 中 | 需逆向导出函数参数（`_updateGampeWithFile@4` 等），x86 PE32+hidapi | 省掉网络劫持，但调用契约未完全验证 |
| C. 复用 fwupd `libebitdo`（V1 USB 协议）刷写 | 低/待实测 | 需 Zero 2 的 bootloader 兼容 V1（枚举为 `2DC8:5750` 或 `0483:5750`） | Zero 2（PID 0x9018）**不在** fwupd ebitdo 支持列表；其 boot 协议版本未知 |
| D. 从零实现 V2 HID 刷写协议 | 低（工作量大） | 需要设备抓包/进一步反汇编 | 协议命令可见但未公开文档，不建议作为首选 |

> 若要"改键"落地，A 路线依赖固件二进制补丁（Lead 负责：解密→改表→重加密）；本报告负责**刷写路径/工具/协议**与**验证实验清单**。

### 1.2 一句话风险判断

- 固件**没有密码学签名**（fwupd 对 ebitdo 直接标注 `FU_DEVICE_FLAG_UNSIGNED_PAYLOAD`；8cryptdo 可对官方固件解密并重加密）。
- 官方工具/设备侧校验 = 文件头 `pid` 必须等于设备 USB PID（Zero 2 = **0x9018**）、版本号检查、刷后 CRC 校验；这些都可**自洽通过**（补丁保留 PID/版本、按字节重算 CRC）。
- 风险集中在"刷坏后能否恢复"：Zero 2 的 boot 组合是硬件键组合（关机 → 按住 **L+R+START** 开机，灯闪），不依赖已刷固件，一般可重刷恢复；但擦除过程中断电可能进入 bootloader 也损坏的极端情况（YC3121 的 SWD 位置未见公开资料，需开壳）。

---

## 2. 证据总览（文件、哈希、URL）

### 2.1 官方更新器工具

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `_fw-tools/downloads/8BitDo_Firmware_Updater_Win.zip` | 19,148,000 | `88FD6AF7EB62A33546415DB75A40907EF9120D14F10C6CD7A4337EA59994A26F` |
| `_fw-tools/downloads/8BitDo_Firmware_Updater_macOS.zip` | 10,415,585 | `4F197854E6ECA261A77B0A0FC03DB60D9F0B860FCB511DADB8484F5D9EDEA887` |
| `_fw-tools/win/.../8BitDo Firmware Updater.exe`（.NET 主程序，appVersion 250/251） | 19,883,520 | `5880C67C092F6D6E658F5A3A10C87DD42A439D561DE75384599BEFE7B905916C` |
| `_fw-tools/win/.../8BitDoFirmwareUpdaterTools.dll`（原生刷写库，PE32 x86） | 2,045,440 | `B38FFA61B12AF29D41DC55212E5BA44E509130FACF6E3C4DB9A7141AA313F974` |
| `_fw-tools/mac/.../Contents/MacOS/8BitDo Firmware Updater`（Mach-O） | 687,216 | `966EABD911B6027951A06989D90C34BB38729CA53B22E7BF4DB9AC6E935A5D2A` |

下载 URL（均 2026-11-13 可访问）：
- `https://download.8bitdo.cn/Tools/FirmwareUpdater/8BitDo_Firmware_Updater_Win.zip`（本次实际下载）
- `https://download.8bitdo.cn/Tools/FirmwareUpdater/8BitDo_Firmware_Updater_macOS.zip`
- 官方支持页 `https://support.8bitdo.com/firmware-updater.html` 给出的同名 .com 域名地址，HEAD 返回同为 19,148,000 B，`Last-Modified: Thu, 24 Jul 2025 10:02:53 GMT`。
- 支持页原文（英文版）："2. Manually update the firmware on advanced mode."；"3. Enter controller upgrade mode automatically. This does not apply to our old or discontinued models."（Zero 2 属旧型号，需手动进 boot）

### 2.2 Zero 2 官方固件（本次取得，来源为官方 API）

设备表里 Zero 2 的 `type` 与固件 API 的 `Type` 并**不一致**（见 §4.1）：固件 API 里 **Type=30** 才是 Zero 2。

| 版本 | 日期/说明 | 文件（本地） | 大小 | SHA256 | 官方 API 声明 md5 / 实际 md5 |
|---|---|---|---:|---|---|
| v1.08 | 2025-06-09 / "Added support for Switch 2." | `_fw-tools/firmware/69749f0f-bdf5-447c-be6a-d32f1394ed1e.dat` | 124,472 | `43A313564AC1125DF1DE9C5B47C393FB5EBFC4D9FF70790E519FB72E609DA808` | `77F76375A4C041EBE9C2D774A065EEBC` / `4DFE36E1A45180393E0B22EDB1D3F2E5` ❌ |
| v1.06 | 2022-01-07 / "Fixed incorrect LED status in charging." | `_fw-tools/firmware/3832eccc-c022-4f34-9f51-f13eb33b18ef.dat` | 123,960 | `A5ABA21C926ED3FE9DF009E297EF9DB15E3E070CA6E3EDE139754597734F0DFB` | `932C3EF2A41D7F0A26296E1B725A4ED5` / `E3734E05741D092DE702B166138CADDF` ❌ |

下载地址（明文 HTTP，可直接复现）：

```
POST http://dl.8bitdo.com:8080/firmware/select
Headers: Beta: 1   Type: 30
→ {"list":[{"fileName":"Zero 2 gamepad","version":1.08,"fileSize":124472,
           "filePathName":"/firmwareFile/upload/69749f0f-bdf5-447c-be6a-d32f1394ed1e.dat",
           "md5":"77F76375...","exists":true, ...}, {v1.06...}]}
GET http://dl.8bitdo.com:8080/firmwareFile/upload/<uuid>.dat
```

关键事实（对刷写路线至关重要）：**API 返回的 md5 与实际下载文件 md5 不一致**（两个版本都不一致），说明官方工具并不强制校验下载文件完整性 —— 这直接支持"劫持 HTTP 下载喂自定义 .dat"的路线（与 fanatic75/8bitdo-mac-flash 对 Ultimate 系列 macOS 版的发现一致）。

### 2.3 工具技术栈（静态分析结论）

- **Windows**：`8BitDo Firmware Updater.exe` 为 **.NET Framework / WinForms** 托管程序（元数据流 `#~ #Strings #US #GUID #Blob` 齐全；含 `System.Windows.Forms`、`HttpWebRequest`、`MD5CryptoServiceProvider`）。刷写逻辑在原生 DLL `8BitDoFirmwareUpdaterTools.dll`（MSVC/MFC 字符串，**PE32 x86**，导出表 36 项，内嵌 **hidapi**：`hid_enumerate`/`hid_open_path`/`hid_read_timeout`/`hid_write`）。另带 `ICSharpCode.SharpZipLib.dll`、`J2i.Net.XInputWrapper.dll`、`data/Autoupdate.exe`。
- **macOS**：原生 Objective-C/AppKit 应用（含 Sparkle 自动更新框架），HID 用 `IOHIDManager`/`IOHIDDeviceSetReport`，设备表为 `Contents/Resources/S8BitdoDevice.plist`。
- 两者共用同一后端 API：`/firmware/select`、`/firmware/loadNewVersion`、`/firmware/StatisticsFirmware`、`/firmware/Activity` 与 `http://dl.8bitdo.com:8080` / `http://dl.8bitdo.cn:8080` / `http://beta.8bitdo.com:8080`。

---

## 3. 固件格式（Zero 2，实测两段）

`8cryptdo`（aeromodes）文档 + 本次实测完全一致：

- 文件由若干 **"28 字节明文头 + payload"** 段组成；头字段：`u32 version`、`u32 addr`、`u32 payload_len`、`u32 pid`（旧型号为 0）、再 12 字节 0。
- Zero 2（v1.08 / 124,472 B）：

| 段 | 文件偏移 | version | addr | payload_len | pid | 加密 |
|---|---:|---:|---|---:|---:|---|
| 0 | 0x0 | 108 (0x6C) | `0x08003400` | 51,200 (0xC800) | 0x0000 | GD32 cipher |
| 1 | 0xC81C | 108 | `0x01018000` | 73,216 (0x11E00) | **0x9018** | Yichip cipher |

- v1.06 同结构：段 1 长度 72,704 (0x11C00)，总 123,960 B。
- 段尾均无 CRC/签名尾部；`reserved` 12 字节全 0。
- 加密算法细节、种子表、重加密工具：见 `aeromodes/8cryptdo`（README + `cryptdo8.py`，已下载到 `_fw-tools/tools/cryptdo8.py`）。Zero 2 的"第一段 GD32 cipher、第二段 Yichip cipher"与 8cryptdo 的说明逐字吻合；8cryptdo 还记录 "a teardown of a recent Zero 2 device showed that it specifically uses the **YC3121**"。

> 对 Lead 的接口提示：重加密后的文件必须保持 **相同段数、相同 addr/len**，并把每段的 `pid` 保留为 `0x9018`（段 0 保持 0）；version 建议**递增**（如 109）以规避"版本不新"检查；写回后用官方工具刷入。文件结构自洽即可通过设备/U 盘侧校验（§4.4）。

---

## 4. 官方更新器：刷写路径与校验点

### 4.1 设备表与"高级模式"（Manual Update）

- Windows 版内嵌设备表（`_fw-tools/analysis/model_list.json`，62 条）：`8BitDo Zero 2 gamepad` → `type=29`, `vid=0x2DC8`, `pid=0x9018`, `className=Zero2`。
  - 注意 **Windows appVersion 250（2025-07 版）表里 type=29 是旧值**；macOS 版 `S8BitdoDevice.plist` 中同一设备为 `type=30`，而官方固件 API 实际 `Type=30` 才返回 Zero 2 固件（`Type=29` 返回空列表）。推测设备表可由服务端更新（exe 字符串有 `moreUpdatePlist`），或该表仅用于 UI。
- "高级模式"中英文对照（macOS `Localizable.strings` 实锤）：`"Update Manually" = "高级模式";`；同页另有 `"emptyFirmwaer" = "没有选中升级文件"`、`"chooseProduct" = "选择你要更新的产品"`、`"NotSupport" = "此手柄不支持该固件，请选择最新的固件"`。
- 支持页三张运行截图（`_fw-tools/analysis/page_update*.png`）显示高级模式真实流程 = **从产品网格里手动选型号（"Choose the Products"）→ 选择服务器返回的固件版本（log/NEW 标记）→ Update**。**没有本地文件选择器**：.NET 元数据里查不到 `OpenFileDialog`/`openFileDialog`/`SelectFile` 等类型或方法（`_fw-tools/analysis/dn/*.strings.txt`）。
- **结论：官方"高级模式"不接受任意本地 `.dat`，它只是"手动选型号 + 从服务器下载官方固件"。** 因此想刷自定义固件必须"骗过下载"或绕开官方前端。

### 4.2 更新流程（从官方工具自带日志取证）

随包发布的开发者日志泄漏了大量内部流程（`win/.../data/debugLog.txt`、`updateLog.txt`，SHA256 分别为 `4B015061…4733C8F` / `E5823DF8…9D0B59`）：

```
find device: Vid:2dc8 Pid:301a Version:1.01 Beta:0 IsChangeBoot:True
startUpdateFirmware: ... firmware type: 96 version:1.05 beta: fileSize:84508
Download firmware result:True
jump boot device / SwitchMode to->boot / send jump BOOT CMD vid:2dc8 pid:6xxx error ...（按候选 PID 表逐个尝试）
startUpdateFirmwareing  filePath: ...\updateFile\b71f8e81-....dat
execute update firmwate library
------------------------------UsbUpdateProcessV2
Open_Hid \\?\hid#vid_2dc8&pid_3208#...
PID: 3018
GetUpdateFileMsg → Version: 105 , Len: 14a00 desAddress:1018000 file_offset:0
desVersion is 105
startErashFlash → startErashFlash - Done
startWriteFlash OpenFile:1
progress 1..22
```

可确认：
1. 设备正常模式 PID ≠ boot 模式 PID（例：`0x3018` 运行时 → `0x3208` boot HID；官方源码外第三方 udev 规则也称 `2dc8:3208` 为多款 8BitDo 共享 boot HID）。官方工具会先尝试"自动跳 boot"，失败则按候选 PID 表逐个尝试并最终提示用户手动进 boot（Zero 2 用手动组合）。
2. 下载的固件被保存为 `updateFile\<uuid>.dat`，随后交给原生库刷写；刷完删除（字符串 `下载完成！`、`文件已删除`）。字符串 `下载文件存在！` 提示存在"文件已存在则复用"的分支 → 这是实验清单里的关键验证点（§7 E4）。
3. Windows 刷写为 **HID 输出报告**（hidapi `hid_write` / `_WriteHid_reportID@12`），带 `SendFirmwareHeader`/`SendFirmwarePacket cmd %d`/`startErashFlash`/`startWriteFlash`/`inspect Flash pass`/`BOOT_FLASH_CRC_CMD ERROR` 等步骤日志（`_fw-tools/analysis/8BitDoFirmwareUpdaterTools.dll.strings.txt`）。

### 4.3 原生刷写库导出接口（"自己写刷写器"路线的入口）

`_fw-tools/win/.../8BitDoFirmwareUpdaterTools.dll` 导出（PE32 x86，stdcall 装饰名，完整清单见 `_fw-tools/pe_exports.py` 运行结果）：

```
FindHid / FindHidPath / Open_Hid / ReadHid / WriteHid / _WriteHid_reportID@12
_ReadHidAdvance@8 / _WriteHidAdvance@8 / _setAdvanceUSB@0
dll_getBootVersion / _dll_getBootVersion_beta@0 / _dll_getProgress@0 / _dll_errorUpdate@0
dll_getType / _updateGampeWithFile@4 / dll_usbUpdateDpad
hid_enumerate / hid_open_path / hid_read_timeout / hid_write        ← 内嵌 hidapi
_enter_ArcadeStickforXbox_Boot@0 / _find_8bitdo_xbox@4 / _read_xbox_data@8 / ...
```

`_updateGampeWithFile@4` 是"给一个文件就刷"的直接入口（1 个 4 字节参数，很可能是文件路径指针/结构体）。若走此路线，需要用一个 32 位宿主程序 `LoadLibrary` + 按调用约定调用，并等待 `_dll_getProgress` / 回调；调用契约尚未完全逆向（遗留问题）。

### 4.4 校验点盘点（决定"重加密文件会不会被拒"）

| 校验 | 证据 | 影响 | 定制固件能否通过 |
|---|---|---|---|
| 文件头 pid == 设备 PID | macOS：`" pid : %x m_firmwareHeader.pid: %x "`、`SHIDBootErrorNOEqualPID:gamepadType:pid:`、`"Firmware Error: "`；Windows `updateLog.txt`：`gamepad_type != pid: 3018 301a` → `GetUpdateFile Error` | 不匹配直接拒绝 | ✅ 保留 `pid=0x9018` 即可 |
| 版本检查 | DLL 字符串 `Firmware version error!`、`Set version error`；UI `此手柄不支持该固件，请选择最新的固件` | 版本过低/相同可能被拒或提示 | ✅ 递增 version（如 109） |
| 刷后 CRC | DLL：`inspect Flash pass`、`BOOT_FLASH_CRC_CMD ERROR`；macOS：`Flash_CRC:crcIndex:`、`" crc : %x file_crc: %x "`、`CRC Error: ` | 写坏/密文错误会报错，可重刷 | ✅ 内容自洽（CRC 由写入内容算出，非签名） |
| 签名/证书 | **无**。fwupd ebitdo：`fu_device_add_flag(..., FWUPD_DEVICE_FLAG_UNSIGNED_PAYLOAD)`；8cryptdo 能重加密并明确"potentially enables creating customized firmware" | — | ✅ |
| 下载文件 md5 | API 返回 md5 与实际文件不符（§2.2）；官方工具日志只有 ` MD5 :` 记录 | 不构成拦截 | ✅ |

> 结论：**"重加密 + 保留/递增头部字段"的 `.dat` 具备被官方工具/设备接受的条件**；成败关键不在密码学，而在刷写传输与 boot 模式适配。

### 4.5 备用：开源 V1 协议（fwupd libebitdo）能覆盖到哪

- fwupd `plugins/ebitdo`（已抓取到 `_fw-tools/fwupd-ebitdo/`）：`com.8bitdo` 协议，USB 中断端点（runtime IN 0x81/OUT 0x02，bootloader IN 0x82/OUT 0x01），64B 包；命令表见 `fu-ebitdo.rs`（`FwUpdateData 0x00`/`FwUpdateHeader 0x01`/`FwUpdateOk 0x02`/`FwGetVersion 0x04`/`FwSetVersion 0x05`/`FwSetEncodeId 0x06`/`Ack 0x14`/…）；流程：写 28B 头 → 32B 块写数据 → SET_ENCODE_ID（serial^app_key_index）→ UPDATE_OK。`FU_DEVICE_FLAG_UNSIGNED_PAYLOAD` 证明老协议无签名。
- 支持列表里 bootloader VTID/PID 为 `USB\VID_2DC8&PID_5750` 与 `USB\VID_0483&PID_5750`（0483=STMicro）；设备目录见 `ebitdo.quirk`（最晚到 N30 Pro 2 `0x9015`）。**Zero 2（`0x9018`，YC3121）没有条目**。
- 因此"用 fwupd 自己刷"取决于 Zero 2 bootloader 是否枚举成 `5750` 且兼容 V1 命令 —— 只能设备到手实测（§7 E1/E2）。若不兼容，则必须走官方工具的 V2 HID 路径（A/B 路线）。

---

## 5. 可操作路线（供实现选型）

### 路线 A（推荐）：劫持官方工具的固件下载，喂"重加密后的 .dat"

原理：更新器通过**明文 HTTP** 从 `dl.8bitdo.com:8080` 下载固件，且不校验 md5；只要把 `.dat` 请求重定向到我们提供的文件，官方工具就会照常完成"跳 boot → 擦除 → 写入 → CRC 校验 → 重启"。

三种实现（按侵入性排序）：
1. **hosts + 本地 8080 服务**（需管理员）：`127.0.0.1 dl.8bitdo.com dl.8bitdo.cn beta.8bitdo.com`，本地起 HTTP 服务：对 `/firmware/select` 返回与官方同结构的 JSON（保证 fileName/version/filePathName 一致），对 `/firmwareFile/upload/<uuid>.dat` 返回我们的 `.dat`。优点：完全复刻服务器，不依赖第三方证书（HTTP 无 TLS）。
2. **系统代理（HKCU WinINET，无需管理员）**：设置 `ProxyServer=127.0.0.1:8888` + `ProxyEnable=1`，本地代理转发到 `dl.8bitdo.com:8080`，仅替换 `.dat` 响应体。取决于 .NET `HttpWebRequest` 是否使用系统代理（默认使用，但应用可能显式置空 → 需实测）。
3. **更新器缓存文件替换**（最省事，若成立）：官方把固件存到 `<安装目录>\updateFile\<uuid>.dat`；字符串 `下载文件存在！` 暗示存在复用分支。把重加密文件放到该路径（uuid 取自 API `filePathName` 的文件名），观察是否跳过下载直接刷。**此路线需实验 E4 验证**。

### 路线 B：写调用器复用 `8BitDoFirmwareUpdaterTools.dll`
- 用 x86 宿主程序（C++/C# x86）加载 DLL，调用 `FindHid`/`Open_Hid` 找设备，再调 `_updateGampeWithFile@4(path)`，轮询 `_dll_getProgress@0`；需先逆向参数与内部状态（P/Invoke 签名可能在 .NET 主程序的元数据/IL 里，可继续挖）。
- 优点：不碰官方网络栈/UI；缺点：契约未验证，DLL 升级会失效。

### 路线 C：libebitdo / 自研 V2 HID 协议
- 若 Zero 2 bootloader 兼容 V1：给 fwupd `ebitdo.quirk` 加 `USB\VID_2DC8&PID_xxxx` + 自定义 `.cab`，用 `ebitdo-tool`/`fwupdmgr` 刷（Linux 最顺）。
- 若不兼容 V2：macOS 侧已有协议方法名线索（`Generate_bootCmdPacket:Len:Offset:Total_Len:Boot_CMD_e:CMD_params:`、`addBlock:Cmd:`、`BootReadFlash:Len:Address:Total_Len:Cmd:Block:`、`eraseFlashJL:len:TotalEraseLen:`、`Flash_CRC:crcIndex:`、`SHIDBoot*`），可结合官方工具在 Linux/Wine 下的 HID 抓包（usbmon/wireshark）复刻，工作量较大。

---

## 6. 风险与恢复

| 风险 | 说明 | 缓解 |
|---|---|---|
| 变砖 | 刷写中掉电/拔线；或写入错误密文导致 CRC 失败后设备停在 boot | Zero 2 进 boot 是**硬件键组合**（关机→按住 L+R+START 开机，灯闪），与固件无关；官方工具可重刷恢复。极端情况（bootloader 区被擦且掉电）需开壳 SWD（YC3121 的 SWD 未见公开资料） |
| 版本不匹配 | 刷入他型号固件（如 Micro/Ultimate）→ pid 校验失败拒绝；强行刷可能导致不可用 | 只用 Zero 2 固件（pid=0x9018）打补丁；不要跨型号 |
| 电量 | fwupd 8bitdo-firmware README 明确警告 "Make sure the GamePad battery is NOT empty before flashing"（本任务范围内仅引用，不下结论） | 充满电、USB 直连不用 Hub |
| 工具/服务器变动 | API 与更新器为在线服务，URL/type 可能变化；本报告 API 实测于 2026-11-13 | 保留官方 v1.08 原文件与哈希；离线劫持时完全本地化 |
| 法律/授权 | 固件版权属 8BitDo；仅限自有设备互操作/维修 | 不二次分发官方固件；仓库内只放哈希与取得方式 |

---

## 7. 等设备到手后的最小验证实验清单（只读/不刷写）

> 目标：在不刷任何第三方固件的前提下，锁定 boot 协议版本、HID 报文形态、官方工具校验行为与恢复能力。**E6 涉及一次官方固件的正常升级/中断恢复测试，是唯一会写设备的步骤，需用户明确同意。**

- **E1 枚举正常模式 vs boot 模式（10 分钟，只读）**
  - Windows：UsbTreeView / PowerShell `Get-PnpDevice`；Linux：`lsusb -v`、`/sys/bus/usb/devices/*`。
  - 记录：正常模式 `2DC8:9018`；关机后按住 **L+R+START** 开机再枚举 → 记录 boot 模式 VID/PID（若为 `2DC8:5750`/`0483:5750` → V1 兼容有戏）、HID 接口 usage page/report size、端点。
- **E2 V1 协议探测（只读，风险低）**
  - 按 `fwupd/plugins/ebitdo/fu-ebitdo.rs` 组 `GET_VERSION(0x21)` 包，向 boot HID 接口发送一次读请求，看是否有 `GET_VERSION_RESPONSE(0x22)`；不响应基本可判定为 V2。用 hidraw/libusb 编写，不擦写。
- **E3 抓官方更新流量（只读）**
  - Wireshark 监听 `dl.8bitdo.com:8080`（明文 HTTP）→ 记录 `/firmware/select` 请求头（`Beta`/`Type` 实际值，确认 Zero 2 用 29 还是 30）、响应 JSON、下载 URL、是否请求 md5。
- **E4 更新器文件缓存复用测试（只读设备）**
  - 在更新器目录 `updateFile\` 放一份官方 v1.08 `.dat`（文件名用 API 返回的 uuid），启动更新流程，观察 `data/debugLog.txt` 是否出现 `下载文件存在！` 且不发下载请求 → 决定路线 A 用"缓存替换"还是"劫持"。
- **E5 高级模式行为确认（只读）**
  - 打开"高级模式"，选 Zero 2，观察是否列出 v1.06/v1.08；确认它只会下载官方文件（结合 E3 抓包）。
- **E6 恢复性验证（唯一写设备，需同意）**
  - 用官方工具正常升级 v1.06→v1.08；然后再测一次"擦除阶段中途拔线"→ 重新进 boot（L+R+START）→ 用官方 v1.08 重刷恢复。**不涉及第三方固件**，仅验证"失败可恢复"假设。
- **E7（可选）硬件取证**
  - 开壳看 PCB 丝印/主控（预期 YC3121）、找 SWD/UART 测试点；用万用表确认 MicroUSB D+/D- 走向（为最坏情况留后路）。仅在有备用/意愿时做。

---

## 8. 遗留问题 / 未证实点

1. **Zero 2 boot 模式 PID 与协议版本未知**（决定 C 路线可行性；E1/E2 可解）。
2. V2 刷写包格式（HID report 布局、块大小、擦除命令参数）未完整逆出；macOS 应用与 Windows DLL 都有线索（`SendFirmwarePacket cmd %d`、`Generate_bootCmdPacket…`），需设备抓包或进一步反汇编。
3. Windows 版设备表 `type=29` 与官方固件 API `Type=30` 的差异：疑似设备表可由服务端（`moreUpdatePlist`）更新；实际请求值需 E3 抓包确认。
4. "高级模式"是否还会做"产品型号 vs 已连接设备"的双重检查（字符串暗示会校验 pid 并提示"请选择最新的固件"）—— 影响路线 A 中是否必须伪装产品选择。
5. 路线 A 的"系统代理"是否对 .NET `HttpWebRequest` 生效未实测（默认应生效，但应用可能显式禁用代理）。
6. `_updateGampeWithFile@4` 的参数契约与依赖状态（是否需先 `dll_getType`/`FindHid`/`_setAdvanceUSB`）未验证。
7. YC3121 的 SWD 调试口位置/是否读保护：无公开资料，需开壳实测（仅最坏情况需要）。

---

## 9. 附录：证据文件索引（均在 `zero2-keyboard/_fw-tools/` 下）

| 路径 | 用途 |
|---|---|
| `downloads/8BitDo_Firmware_Updater_Win.zip` | 官方 Win 更新器原始包（SHA256 见 §2.1） |
| `downloads/8BitDo_Firmware_Updater_macOS.zip` | 官方 macOS 更新器包 |
| `win/8BitDo_Firmware_Updater_Win/` | Win 版解包：`8BitDo Firmware Updater.exe`、`8BitDoFirmwareUpdaterTools.dll`、`data/debugLog.txt`、`data/updateLog.txt` |
| `mac/8BitDo Firmware Updater.app/Contents/Resources/Base.lproj/Localizable.strings`、`zh-Hans.lproj/Localizable.strings` | 中英文 UI 文案（"Update Manually"="高级模式"等） |
| `mac/.../Contents/Resources/S8BitdoDevice.plist` | macOS 设备表（零 2：order 27 / type 30 / vid 0x2DC8 / pid 0x9018） |
| `firmware/*.dat`、`firmware/api_type30_all.json` | Zero 2 官方固件 v1.08 / v1.06 与 API 元数据 |
| `analysis/model_list.json` | 从 Win exe 抽出的 62 条设备表 |
| `analysis/ui_strings_region.txt` | exe 内 UTF-16 UI 字符串表（含 `高级模式`/`Update Manually`/`Choose the Products`/`下载文件存在！`/`firmware/select` 等） |
| `analysis/dn/*.us.txt`、`*.strings.txt` | .NET 元数据字符串与标识符（证明无 `OpenFileDialog`，有 `UpdateManually`/`selectFirmware`/`firmwareS1/2`） |
| `analysis/8BitDoFirmwareUpdaterTools.dll.strings.txt` | 原生刷写库字符串（`startErashFlash`/`BOOT_FLASH_CRC_CMD`/pid 校验等） |
| `analysis/mac/8BitDo Firmware Updater.strings.txt` | macOS Mach-O 字符串（`Generate_bootCmdPacket…`/`SHIDBoot*`/`Flash_CRC`/API 路径） |
| `analysis/page_update*.png` | 官方支持页截图（高级模式=产品选择+版本列表） |
| `fwupd-ebitdo/` | fwupd ebitdo 插件源码（`fu-ebitdo-device.c`/`fu-ebitdo.rs`/`ebitdo.quirk`/`README.md`） |
| `8bitdo-firmware/` | fwupd/8bitdo-firmware 仓库（`8bitdo-firmware.py`：官方 API 调用范例） |
| `tools/cryptdo8.py` | 8cryptdo 解密/重加密工具（MIT，来自 aeromodes/8cryptdo） |

### 引用链接

- 官方支持页（高级模式说明/工具下载）：https://support.8bitdo.com/firmware-updater.html
- 8cryptdo（8BitDo 固件加密逆向，含 Zero 2/Yichip）：https://github.com/aeromodes/8cryptdo
- fwupd ebitdo 插件：https://github.com/fwupd/fwupd/tree/main/plugins/ebitdo
- fwupd/8bitdo-firmware（官方 API 下载脚本）：https://github.com/fwupd/8bitdo-firmware
- fanatic75/8bitdo-mac-flash（官方更新器喂任意 .dat 的先例，Ultimate 系列）：https://github.com/fanatic75/8bitdo-mac-flash
- 8BitDo Firmware Updater 在 Wine 下使用 + boot HID 说明（`2dc8:3208` 共享 boot 接口）：https://gist.github.com/archeYR/d687de5e484ce7b45d6a94415a04f3dc

---

## 10. 后续实测（Lead，2026-11-13，真实 Zero 2）

原报告基于静态分析，以下为真实设备上的实测结论（v1.05 出厂固件）：

1. **固件下载劫持可行**：官方 Win 更新器（appVersion 252）识别普通模式设备（`2DC8:9018`, Version 1.05）后，
   请求 `/firmware/select`、`/firmware/loadNewVersion`、`/firmware/Activity`；把系统代理指向本地服务后，
   它从我们返回的列表里下载并接受了自编译 `.dat`。
2. **md5 校验的真实含义**：`HttpTool.HttpDownload` 里的 md5 不是文件内容 md5，而是
   `Tools.GenerateMD5(fs.Length.ToString())`，即 **`MD5(文件字节数.ToString())`**。
   官方 API 自报的 md5 与文件不符，正是因为它是"长度字符串的 md5"。列表 `md5` 必须按此填，否则下载重试 6 次后失败。
3. **必须先普通模式、由工具发 jump boot**：手动按住 L+R+START 插 USB 进 boot（`0483:5760`）时，
   工具能下载并 `Open_Hid` 到 boot 设备，但刷写库无限 `resend GET_ID_DATA`（设备不回包），不写入。
   普通模式连接后由工具发 jump boot，设备切换成功后握手正常。
4. **实测刷写日志**（`UsbUpdateProcessV2`）：`verification id ok` → `firmware_type 1` →
   `Version: 109 , Len: c800 desAddress:8003400` → `SendFirmwareHeader` → `desVersion is 109` →
   progress 0–99 → `update successful` → `firmware version: e0000000` → `Exit Usb_UpdateThread: 1`。
   设备重启回 `2DC8:9018`，工具报告 Version 1.09。
5. **只写入了段0**：本次日志只显示段0（主控，`0xc800` @ `0x08003400`）被写入；段1（蓝牙 SoC，
   `0x01018000`）未出现。但刷后键盘模式 12 键输出已全部变为我们映射的 F1–F12，说明
   **键盘模式按键映射由主控段（段0）负责**，只改段0即可达到改键目的。
6. **环境坑**：本机 DSH 沙箱下更新器写 `%LOCALAPPDATA%\_8BitDoFirmwareUpdater\...\user.config`
   被拒绝，触发未处理异常崩溃（`Settings.Save`）；把该目录做 junction 指向工作区后正常运行。
   普通 Windows 用户环境一般不需要。

结论：A 路线（劫持官方更新器下载 + 自编译 `.dat`）**已完整跑通**，成品/流程见
`zero2-keyboard/flash/` 与 `zero2-keyboard/firmware-patch/out/`。
