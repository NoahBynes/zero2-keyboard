# 实机刷写证据（2026-11-13）

设备：8BitDo Zero 2，出厂固件 **v1.05**，普通模式 USB `VID_2DC8&PID_9018`。
操作：本仓库 `firmware-patch/out/Zero2_V1.09_identify.dat`（版本头 109，12 键映射为 F1–F12），
经官方 8BitDo Firmware Updater v2.52 + 本地代理（`flash/patched_updater_proxy.py`）刷入。

## 文件

| 文件 | 说明 |
|---|---|
| `00_update_page_v109.png` | 更新器识别到设备后，代理提供 v1.09 固件列表 |
| `01_update_success.png` | 更新器最终界面：「从 v1.05 升级到 v1.09 / 更新成功」 |
| `02_key_capture.log` | R+Start 键盘模式配对 PC 后，按键捕获窗口记录的实际输出 |
| `03_update_log_excerpt.txt` | 官方刷写库 `data/updateLog.txt` 的刷写过程摘录（verification id ok → SendFirmwareHeader → progress 0–99 → update successful） |

## 关键日志

```
2026-11-13 20:43:20 -  ------------------------------UsbUpdateProcessV2
2026-11-13 20:43:20 -  Open_Hid \\?\hid#vid_0483&pid_5760#... 
2026-11-13 20:43:20 -  verification id ok
2026-11-13 20:43:20 -  firmware_type 1
2026-11-13 20:43:20 -  Version: 109 , Len: c800 desAddress:8003400 file_offset:0
2026-11-13 20:43:20 -  SendFirmwareHeader
2026-11-13 20:43:22 -  desVersion is 109
2026-11-13 20:43:22 -  update file is 0xc800
2026-11-13 20:43:22 -  progress 0
...
2026-11-13 20:43:32 -  progress 99
2026-11-13 20:43:32 -  update successful
2026-11-13 20:43:32 -  firmware version: e0000000
2026-11-13 20:43:32 -  Exit Usb_UpdateThread: 1
2026-11-13 20:43:35 -  Open_Hid \\?\hid#vid_2dc8&pid_9018#...   ← 重启回普通模式
```

`debugLog.txt` 随后显示 `find device: Vid:2dc8 Pid:9018 Version:1.09`，更新器界面
显示「从 v1.05 升级到 v1.09 / 更新成功」。

## 键盘模式实测

R+Start 键盘模式配对 Windows 后，用 `flash/keycapture.ps1` 捕获（焦点窗口的 KeyDown）：

| 手柄按键 | ↑ | ↓ | ← | → | Select | Start | A | B | X | Y | L | R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 捕获输出 | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 | F9 | F10 | F11 | F12 |

与 `profiles/identify.json` 完全一致 → **设备级自定义键盘已跑通**。

> 注意：本次 updateLog 显示只写入了段0（主控 0xc800 @ 0x08003400），段1（蓝牙 SoC）
> 未写入；但键盘模式输出已经由段0的映射表决定，说明键盘模式按键映射在主控固件里。

---

## 追加：GUI 自动刷写 + 1.08.1 翻页器（2026-11-13 21:52–22:00）

| 文件 | 说明 |
|---|---|
| `04_keycapture_page_turner.png` | 键盘模式捕获窗口（v2）里 12 个键的实际输出 |
| `05_keys_page_turner.log` | 对应原始捕获日志（`_keys.log`） |

- 固件：`gui/` 生成的 `Zero2_1.08.1_page-turner.dat`（官方 1.08 基线，固件头 108，键位表 `4b4e4a4d29282c2b2a4c504f`）。
- 刷写：`python gui/zero2_kb_gui.py --flash --preset 翻页器 --patch 1`，自动完成生成→代理→更新器→写入；
  updateLog `update successful`，`Version: 108`，固件头比对一致；设备重启回 `2DC8:9018`。
- 键盘模式实测 12/12：

| 手柄按键 | ↑ | ↓ | ← | → | Select | Start | A | B | X | Y | L | R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 捕获输出 | PageUp | PageDown | Home | End | Esc | Enter | Space | Tab | Backspace | Delete | Left | Right |

> 经验：WinForms 捕获窗口默认会把 **Tab** 当导航键吞掉，B 键（Tab）看起来"没按出来"；
> 用 `ProcessCmdKey` 重写的 `keycapture.ps1`（v2）才能完整捕获 Tab/Esc/Enter 等命令键。
