#Requires AutoHotkey v2.0
#SingleInstance Force
; =============================================================================
; zero2_keyboard_remap.ahk -- 零成本方案：把 8BitDo Zero 2 的「键盘模式」改键
;
; 适用场景：
;   Zero 2 用 R+Start 开机 = 蓝牙键盘模式（HID 键盘）。
;   在 Windows 上它就是一个普通蓝牙键盘，按键固定输出小写字母 c~o，
;   本脚本把这些字母重新映射成绘图软件快捷键，且只在指定绘图软件窗口内生效。
;
; Zero 2 键盘模式的默认输出（实体丝印 -> 字母，社区实测）：
;   D-pad：上=C  下=D  左=E  右=F
;   实体按键：A(右)=G  B(下)=J  X(上)=H  Y(左)=I
;   L=K   R=M   Select=N   Start=O
;   （字母 L 不被 Zero 2 使用；N/O 对应 Select/Start）
;
; 重要限制（为什么必须加开关 / 为什么默认只在绘图软件里生效）：
;   1) 键盘模式发出的就是普通字母 c d e f g h i j k m n o，Windows / AHK
;      无法区分该按键来自 Zero 2 还是真实键盘（PowerToys 官方也明确不支持
;      按设备区分）。所以全局映射会破坏正常打字。
;   2) 本脚本默认只在绘图软件窗口（见 DRAWING_PROCESSES）且开关打开时生效，
;      用 ScrollLock 作为总开关；其它窗口/开关关闭时按键原样通过。
;   3) 这种主机端改键只在 Windows 有效，不能跨设备（iPad 没有任何全局改键方案），
;      跨设备/跨主机请用外挂 dongle 方案。
;
; 依赖：AutoHotkey v2.0+（https://www.autohotkey.com/）
; 用法：双击运行；在绘图软件窗口内确认托盘提示为「已启用」；
;       按真实键盘的 ScrollLock 可以随时启用/禁用。
; =============================================================================

; ------------------------- 用户配置区 -------------------------

; 在哪些软件窗口内生效（进程名，任务管理器「详细信息」里能看到）。
; 按需增删；填错不会报错，只是不生效。
DRAWING_PROCESSES := [
    "Photoshop.exe",
    "ClipStudioPaint.exe",
    "Krita.exe",
    "SAI2.exe",
    "Illustrator.exe",
    "painter.exe"
]

; 脚本启动时是否启用。配合 ScrollLock 随时切换。
DEFAULT_ENABLED := true

; 映射表：左 = Zero 2 键盘模式输出的字母，右 = 要发送的按键（AHK Send 语法）。
;   "["、"]" 是普通字符；"^z" = Ctrl+Z；"^+z" = Ctrl+Shift+Z；"{Tab}" = Tab；"{Esc}" = Esc。
MAPPING := Map(
    "c", "[",           ; 十字上 -> 笔刷变小
    "d", "]",           ; 十字下 -> 笔刷变大
    "e", "^[",          ; 十字左 -> Ctrl+[（图层下移）
    "f", "^]",          ; 十字右 -> Ctrl+]（图层上移）
    "g", "^z",          ; 实体 A(右) -> Ctrl+Z 撤销
    "h", "b",           ; 实体 X(上) -> B 画笔工具
    "i", "e",           ; 实体 Y(左) -> E 橡皮擦
    "j", "^+z",         ; 实体 B(下) -> Ctrl+Shift+Z 重做
    "k", "{Tab}",       ; L -> Tab 显示/隐藏面板
    "m", "{Esc}",       ; R -> Esc 取消
    "n", "^s",          ; Select -> Ctrl+S 保存
    "o", "x"            ; Start -> X 交换前景/背景色（PS/CSP）
)

; 调试模式热键：Ctrl+Alt+F12 切换；开启后每次改键弹 ToolTip。
DEBUG_HOTKEY := "^!F12"

; ------------------------- 以下通常无需修改 -------------------------

; 顶层赋值即全局变量
g_Enabled := DEFAULT_ENABLED
g_Debug := false

; 安装键盘钩子（AHK 用钩子才能在不吞掉真实键盘修饰键组合的前提下精确改键）
InstallKeybdHook()

; 建立窗口组
for proc in DRAWING_PROCESSES
    GroupAdd("ZERO2_DRAWING", "ahk_exe " proc)

; 动态注册映射热键：只在「开关打开 且 当前窗口属于绘图软件」时激活；
; 条件不满足时热键不生效，按键原样传给系统。
; 不加 "*" 前缀，避免把真实键盘的 Ctrl+C / Shift+C 等组合一起吞掉。
HotIf(IsDrawingContext)
for srcKey, dst in MAPPING
    Hotkey("$" srcKey, SendMapped.Bind(dst))
HotIf()   ; 重置 HotIf 条件

; 调试开关热键（普通 Hotkey 函数调用，不属于标签）
Hotkey(DEBUG_HOTKEY, ToggleDebug)

; 托盘菜单
A_TrayMenu.Add()
A_TrayMenu.Add("启用 / 禁用 (ScrollLock)", (*) => ToggleEnabled())
A_TrayMenu.Add("调试信息 (" DEBUG_HOTKEY ")", (*) => ToggleDebug())
A_TrayMenu.Add()
A_TrayMenu.Add("重新加载", (*) => Reload())
A_TrayMenu.Add("退出", (*) => ExitApp())

; 启动提示（3 秒后自动消失）
TrayTip("已启动；" . (g_Enabled ? "当前已启用" : "当前已禁用") . "。按 ScrollLock 切换。", "Zero2 键盘改键")

; ============================================================================
; 热键标签：必须放在所有“自动执行”语句之后
; ============================================================================

; ScrollLock：总开关（只切换脚本内部状态，不把 ScrollLock 发给系统）
ScrollLock::ToggleEnabled()

; ============================================================================
; 函数定义
; ============================================================================

; 映射热键的生效条件
IsDrawingContext() {
    global g_Enabled
    if (!g_Enabled)
        return false
    return WinActive("ahk_group ZERO2_DRAWING") ? true : false
}

; 真正发送按键：bound 后第一个参数是目标 Send 串，第二个是 AHK 传入的热键名
SendMapped(dst, thisHotkey := "") {
    global g_Debug
    if (g_Debug)
        ShowTip("Zero2 按键「" . thisHotkey . "」 =>  发送「" . dst . "」")
    Send(dst)
}

ToggleEnabled() {
    global g_Enabled
    g_Enabled := !g_Enabled
    TrayTip(g_Enabled ? "已启用（仅在绘图软件窗口内改键）" : "已禁用（按键原样输出）", "Zero2 键盘")
}

ToggleDebug() {
    global g_Debug
    g_Debug := !g_Debug
    ToolTip()
    TrayTip(g_Debug ? "调试信息已打开" : "调试信息已关闭", "Zero2 键盘")
}

ShowTip(text) {
    ToolTip(text, 20, 20)
    SetTimer(() => ToolTip(), -1500)
}
