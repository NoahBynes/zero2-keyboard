# 零成本方案：Windows 主机端改键（AutoHotkey v2）

> 完整的主机端改键矩阵（Windows/macOS/Linux/Android/iPadOS 各工具的边界）见
> [`../research/alternatives/README.md`](../research/alternatives/README.md#2-主机端软件改键矩阵零硬件成本)。
> 本目录只交付 Windows 下可直接用的实现。

## 1. 原理与适用范围

Zero 2 按 **R + Start** 开机进入「键盘模式」，此时它就是一个**标准蓝牙 HID 键盘**，
固定输出小写字母 c~o。Windows 上它和普通键盘没有区别，因此可以用 AutoHotkey（或
PowerToys）把这些字母改成绘图软件快捷键。

**这套方案只对「运行脚本的这台 Windows 电脑」有效**：
- 不能把改好的「键盘」发给 iPad/Android/另一台电脑 —— 那是外挂 dongle 干的事；
- iPad 上不存在等价的全局改键方案（只能在 App 内自定义快捷键，见第 6 节）；
- 换一台电脑要重新装/跑一次脚本。

## 2. 第一步：确认 Windows 认出了它

1. Zero 2：**R + Start** 开机（指示灯 5 下/循环）。
2. 长按 **Select 3 秒**，指示灯快闪（进入配对）。
3. Windows：设置 → 蓝牙和其他设备 → 添加设备 → 蓝牙 → 选 **「8BitDo Zero 2 gamepad」** → 连接。
   - 如果列表里出现 `DeviceShock` 之类奇怪名字：先在蓝牙设置里删除该设备，关掉 Zero 2 重来。
4. 打开**记事本**，逐个按 Zero 2 的按钮，记录实际输出的字母。按社区实测，应该是：

   | 实体按钮 | D-pad 上 | 下 | 左 | 右 | A(右) | B(下) | X(上) | Y(左) | L | R | Select | Start |
   |---|---|---|---|---|---|---|---|---|---|---|---|---|
   | 输出字母 | c | d | e | f | g | j | h | i | k | m | n | o |

   > 字母 `l` 不被使用；N/O 分别对应 Select/Start。若你的固件版本输出不同，
   > 请以记事本实测为准，改脚本顶部 `MAPPING := Map(...)` 里的键名即可。
5. 设备管理器 → 键盘 下应能看到一个「HID Keyboard Device」（可能还有「蓝牙键盘」类名称），
   这就是 Zero 2 的键盘模式。

## 3. 跑脚本

1. 安装 **AutoHotkey v2.0+**：<https://www.autohotkey.com/>
2. 双击 `zero2_keyboard_remap.ahk` 运行。托盘会出现图标。
3. 默认**只在** `DRAWING_PROCESSES` 列表中列出的绘图软件窗口内生效，
   并且用**真实键盘的 ScrollLock** 键作总开关（手边没有 ScrollLock 键的话，
   也可以右键托盘图标 → 「启用 / 禁用」）。
4. 想确认是否生效：
   - 打开绘图软件，按 Zero 2 的 A 键，应该执行「撤销」；
   - 按 `Ctrl+Alt+F12` 打开调试 ToolTip，每次按键会显示「Zero 2 按键 → 发送内容」；
   - 在记事本里（不在绘图软件窗口）按 Zero 2，应该原样打出字母（说明作用域正确）。

### 默认映射

| 实体按钮 | 输出 | 用途 |
|---|---|---|
| 十字上 (c) | `[` | 笔刷变小 |
| 十字下 (d) | `]` | 笔刷变大 |
| 十字左 (e) | Ctrl+`[` | 图层下移（PS/CSP） |
| 十字右 (f) | Ctrl+`]` | 图层上移 |
| A 右 (g) | Ctrl+Z | 撤销 |
| X 上 (h) | `b` | 画笔工具（PS） |
| Y 左 (i) | `e` | 橡皮擦（PS） |
| B 下 (j) | Ctrl+Shift+Z | 重做 |
| L (k) | Tab | 显示/隐藏面板 |
| R (m) | Esc | 取消 |
| Select (n) | Ctrl+S | 保存 |
| Start (o) | `x` | 交换前景/背景色（PS/CSP） |

改键：直接改脚本顶部 `MAPPING` 表。右侧写法是 AHK Send 语法：
`^`=Ctrl，`+`=Shift，`!`=Alt，`{Tab}`/`{Esc}` 这类是特殊键，`[`/`]`/`b` 直接写。

> 关于「用 scancode 重映射」：AHK v2 的热键本身就是**键盘钩子 + 扫描码**级别的拦截
>（`$` 前缀保证走钩子），不是按字符文本匹配；Zero 2 键盘模式发出的就是标准字母键的扫描码，
> 所以按字母名写热键即可达到 scancode 重映射的效果。如果以后要按扫描码精确匹配（比如区分
> 不同键盘布局），把脚本里的 `Hotkey("$" srcKey, ...)` 换成 `Hotkey("$SC0xx", ...)` 形式并查
> 扫描码表即可，其余逻辑不变。

## 4. 必须知道的限制

1. **无法区分设备**：Zero 2 发出的就是普通字母，AHK 只能全局拦截。如果绘图软件里
   需要输入文字（比如图层名），真实键盘打 c~o 也会被拦截 —— 所以务必使用
   窗口作用域 + ScrollLock 开关，输入文字前先按 ScrollLock 禁用。
   （PowerToys 官方 FAQ 也写明了：*"Can I have different key mappings across
   multiple keyboards? Currently, no."*）
2. **只能「按一下发一个组合键」，不能像真实键盘那样按住修饰键**。
   想「按住 Space 平移画布」这种操作，AHK 方案体验不如外挂 dongle（dongle 是真正的
   键盘设备，按住就是按住）。
3. 目标软件**以管理员权限运行**时，脚本也要以管理员身份运行，否则 Send 无效。
4. 少数软件用原始输入（raw input）或反作弊，会忽略合成按键；绘图软件一般没问题。
5. 每次开机要自己启动脚本（可把快捷方式放进「启动」文件夹，或编译成 exe 后自启）。
6. iOS/iPadOS 上这套方案**完全无效**（没有全局键盘改键 API）。

## 5. 本脚本 vs 其他 Windows 工具（简表）

| 工具 | 成本 | 能力 | 关键边界 |
|---|---|---|---|
| **AutoHotkey v2（本脚本）** | 免费 | 任意字母→任意组合键/序列；可限定窗口 | 不能区分设备；不能按住修饰键（本脚本内）；目标软件提权时需同权限 |
| PowerToys Keyboard Manager | 免费 | 键→键/组合键/文本，可按目标 app 限定 | 官方不支持多键盘区分；必须后台常驻；不用于游戏 |
| reWASD | 付费 | 按设备/按配置重映射，手柄→键鼠强 | 面向手柄（Zero 2 需 X-input 模式）；不支持键盘模式字母重映射 |
| Steam Input | 免费 | 手柄→键盘/鼠标，配置丰富 | 需要 Steam 运行且游戏经 Steam 启动；桌面布局受限 |
| JoyToKey | 免费/捐赠 | 老牌手柄→键盘 | 全局生效、按设备支持弱，需 X-input 模式 |

更完整的 macOS（Karabiner-Elements，可按设备）、Linux（keyd / input-remapper，可按设备）、
Android（Key Mapper，需无障碍）、iPadOS（不可全局改键）说明见
[`../research/alternatives/README.md`](../research/alternatives/README.md#2-主机端软件改键矩阵零硬件成本)。

## 6. 如果目标其实是 iPad / 换设备使用

- **iPad + Clip Studio Paint**：CSP 自身允许把功能绑到单键，Zero 2 键盘模式发出的 c~o
  可以直接在 CSP 的「快捷键设置」里绑定 —— 这是 8BitDo 官方 FAQ 推荐的做法，零成本。
  限制是只能用于支持自定义快捷键的 App（Procreate 等 App 的键盘快捷支持有限）。
- 想「任何 App / 任何主机都能用自定义组合键」：走外挂 dongle 路线
  （[`../esp32-dongle/README.md`](../esp32-dongle/README.md)）。
- 只是懒得折腾且愿意花 ~¥99–149：直接买 **8BitDo Micro**，官方支持键盘模式 +
  手机端精英软件自定义单键/组合键，蓝牙和有线都能当键盘用
  （[`../research/alternatives/README.md`](../research/alternatives/README.md#3-省事替代要不要直接买-8bitdo-micro)）。
