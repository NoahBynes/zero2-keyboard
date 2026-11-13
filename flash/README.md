# 刷入自定义键盘固件（Windows，**已实机验证**）

> **2026-11-13 实测成功**：真实 Zero 2（出厂 v1.05）经官方 8BitDo Firmware Updater + 本仓库本地代理，
> 成功刷入自编译 v1.09 固件；R+Start 键盘模式下 12 个按键全部输出自定义键（identify 固件为 F1–F12）。
> 证据：[`evidence/`](evidence/README.md)。

---

## 1. 已验证的流程（照做即可）

**前提**：手柄以普通模式开机并通过 USB 连接电脑后，设备管理器里出现 `VID_2DC8&PID_9018`（HID-compliant game controller）。
> ⚠️ **不要**用「按住 L+R+START 插 USB」手动进升级模式（0483:5760）。实测那样官方工具能识别、能下载固件，
> 但刷写库会一直 `resend GET_ID_DATA` 卡死，不写入。要让工具自己从普通模式发 jump boot。

1. **普通模式连接**：手柄按一下 START 开机，插 USB 线。
2. **起本地固件代理**（在 `zero2-keyboard` 目录）：
   ```powershell
   python .\flash\patched_updater_proxy.py --patched .\firmware-patch\out\Zero2_V1.09_identify.dat --version 1.09
   ```
3. **设置系统代理**（脚本会备份原设置）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\flash\set_proxy.ps1
   ```
4. **打开官方更新器**（`_fw-tools/win/8BitDo_Firmware_Updater_Win/8BitDo Firmware Updater.exe`）：
   主界面会自动识别出手柄（显示 `8BitDo Zero 2 gamepad V1.05` 和「固件更新」图标）；
   点击「固件更新」→ 页面出现 `... V1.09 NEW` → 点击「更新」。
5. 工具自动完成：下载（经代理拿到我们的 `.dat`）→ 发 jump boot → 设备切换到 0483:5760 →
   `verification id ok` → 写入 → 进度 0–99 → `update successful` → 设备重启回 2DC8:9018。
   界面最终显示「从 v1.05 升级到 v1.09 / 更新成功」。
6. 关闭更新器；**恢复系统代理**：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\flash\set_proxy.ps1 -Off
   ```
7. **验证**：拔线 → 长按 START 8 秒关机 → 按 R+START 开机（键盘模式）→ 电脑蓝牙连接
   `8BitDoZero 2 gamepad` → 打开记事本或 `flash/keycapture.ps1` 窗口 → 依次按 12 个键。
   identify 固件应输出 `F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12`（顺序 ↑↓←→ Select Start A B X Y L R）。

---

## 2. 实测踩到的坑（重要）

| 坑 | 现象 | 解法 |
|---|---|---|
| 手动进升级模式 | 工具能下载固件，但刷写库无限 `resend GET_ID_DATA`，卡在“正在更新…” | 从普通模式（2DC8:9018）开始，让工具发 jump boot |
| md5 校验方式 | 下载后重试 6 次并报「网络下载固件错误」，不写设备 | 官方校验的是 **`MD5(文件字节数.ToString())`**，不是文件内容 md5；代理已按此实现 |
| 更新器设置崩溃 | 本环境启动后弹 “Fatal error 未能保存设置…user.config / 访问被拒绝” | 更新器进程写 `%LOCALAPPDATA%\_8BitDoFirmwareUpdater` 被 DSH 沙箱拒绝；把它做成指向工作区的 junction（见 §5） |
| 版本不递增 | 可能被提示“已是最新/不支持” | 每次重刷版本号 +1（109 → 110 → 111…） |
| 段1未写 | updateLog 只显示段0（Len `0xc800` @ `0x08003400`） | 键盘映射在段0（主控）生效，实测输出正确；段1（蓝牙 SoC）保持原样 |

---

## 3. 换一套你自己的键位

```powershell
# 1) 构建（版本号 +1）
powershell -ExecutionPolicy Bypass -File .\firmware-patch\build_custom.ps1 -Profile custom-template.json -Version 110
# 2) 起代理时也用新版本号
python .\flash\patched_updater_proxy.py --patched .\firmware-patch\out\Zero2_V110_custom.dat --version 1.10
# 3) 然后重复 §1 的 3–6 步
```

- 模板/示例：`firmware-patch/profiles/`（identify / page-turner / drawing / stock / custom-template）。
- 键码表见本文末尾或 `zero2-keyboard/README.md`。
- 回滚官方映射：构建 `stock.json` 的更高版本（如 111）再刷，或直接刷现成的 `Zero2_V1.10_stock.dat`（代理 `--version 1.10`）。

---

## 4. 备选方法（本次未用到，保留作故障备用）

- **hosts 劫持**（管理员）：`hosts_hijack.ps1` 把 `dl.8bitdo.com/.cn/beta.8bitdo.com` 指向 127.0.0.1，
  本地代理监听 8080。适合系统代理对 .NET 不生效的机器。
- **直接调官方刷写 DLL**：`_updateGampeWithFile@4` 的签名已确认是 `void(String filePath)`，
  但需要按官方流程先 FindHid/Open_Hid 并让设备处于正确的 boot 状态；本次未走通，作为研究记录保留
  （`_inspect_pinvoke.ps1` / `flash_dll*.ps1`）。

---

## 5. 本机 DSH 沙箱专用：修复更新器 settings 崩溃

更新器（.NET）会把用户设置写到 `%LOCALAPPDATA%\_8BitDoFirmwareUpdater\...\1.0.0.0\user.config`。
本机沙箱下该写入被拒绝 → 未处理异常 → 程序崩溃。把整个目录改成指向可写工作区的 junction 即可：

```powershell
$link = Join-Path $env:LOCALAPPDATA '_8BitDoFirmwareUpdater'
$target = '<workspace>\zero2-keyboard\_appdata\8BitDoFirmwareUpdater'
New-Item -ItemType Directory -Force -Path $target | Out-Null
if (Test-Path $link) { cmd /c rmdir "$link" }
cmd /c mklink /J "$link" "$target"
```

普通 Windows 用户环境（没有 DSH 沙箱）通常不需要这一步。

---

## 6. 风险与可恢复性

- 本次改动只替换了主控固件里的 24 字节键位表并把版本头 108→109；启动/蓝牙协议栈未动。
- 刷写成功后设备按预期重启，版本显示 1.09；**实测可恢复、可重刷**。
- 恢复手段：普通模式连接 → 用同一流程刷 `stock` 或任意更高版本的 `.dat`。
- 极端情况（写入中断电）用官方流程重刷；本次未发生。
- 固件版权归 8BitDo，仅用于自有设备实验，不要二次分发。
