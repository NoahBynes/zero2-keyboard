# firmware-patch — 设备级改键核心

这个目录负责"官方固件 → 解密 → 改 12 字节键位表 → 重新加密"。

## 首次使用：下载官方固件

仓库**不包含** 8BitDo 官方固件（版权原因）。先运行：

```bash
python download_official_firmware.py
```

它会从官方接口（`POST http://dl.8bitdo.com:8080/firmware/select`，Headers `Beta: 1` / `Type: 30`）
取 Zero 2 的 v1.08 条目并下载到 `Zero2_V1.08.dat`，然后校验：

- 文件大小 `124472`
- 内容 SHA-256 `43A313564AC1125DF1DE9C5B47C393FB5EBFC4D9FF70790E519FB72E609DA808`

> 注意：官方 API 返回的 `md5` 字段是 `MD5(str(fileSize))`（官方更新器的校验规则），
> 不是文件内容哈希，所以脚本不拿它校验内容。

下载失败时的备用办法：从 8BitDo 官方更新器页面手动下载 Zero 2 的 v1.08 固件，
重命名为 `Zero2_V1.08.dat` 放到本目录即可。

## 文件

| 文件 | 说明 |
|---|---|
| `download_official_firmware.py` | 下载官方 v1.08 固件并校验 |
| `official_firmware.py` | 下载/校验模块（GUI 的 `gui/fwlib.py` 也会调用） |
| `patch_fw.py` | 解密/定位键位表/打补丁/重加密/自检 |
| `build_custom.ps1` | 一键构建（旧流程） |
| `profiles/` | identify / page-turner / drawing / stock 等预设 |
| `validate_patch.py` | 补丁差异验证 |
| `Zero2_V1.08.dat` | 运行下载脚本后生成（`.gitignore` 已忽略） |

## 注意

固件版权归 8BitDo，仅用于自有设备的互操作/维修研究，请勿分发官方固件或用于商业用途。
