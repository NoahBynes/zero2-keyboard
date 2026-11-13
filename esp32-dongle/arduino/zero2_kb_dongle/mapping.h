// =============================================================================
// mapping.h -- 由 tools/gen_mapping.py 根据 JSON 自动生成，请不要手改这个文件。
// 想改映射：编辑 JSON 后重新生成，或直接改 mapping.json 再编译。
//
// 生成命令（在 zero2-keyboard/esp32-dongle/arduino/ 下）:
//   python tools/gen_mapping.py mapping.example.json --out zero2_kb_dongle/mapping.h
// =============================================================================
#pragma once

#include <stdint.h>

#define ZERO2_MAPPING_VERSION "1"
#define ZERO2_BUTTON_COUNT 12

// mod 位定义（对应 USB HID 键盘报告第 0 字节的修饰键位）
#define Z2_MOD_LCTRL  0x01
#define Z2_MOD_LSHIFT 0x02
#define Z2_MOD_LALT   0x04
#define Z2_MOD_LGUI   0x08

typedef struct {
    const char *id;     // 逻辑 id（与固件按钮 bit 位一一对应）
    const char *label;  // 实体丝印
    uint8_t     mod;    // 同时按住的修饰键位掩码
    uint8_t     key;    // HID Usage ID，0 表示只按修饰键
    const char *desc;   // 用途说明
} zero2_map_entry_t;

// 顺序固定 == 固件按钮 bit 顺序：up,down,left,right,a,b,x,y,l,r,select,start
static const zero2_map_entry_t kZero2Mapping[ZERO2_BUTTON_COUNT] = {
    { "up", "十字上", 0x00, 0x2F, "笔刷变小" },  // HID 0x2F ([)
    { "down", "十字下", 0x00, 0x30, "笔刷变大" },  // HID 0x30 (])
    { "left", "十字左", 0x01, 0x2F, "图层下移 (Ctrl+[)" },  // HID 0x2F ([)
    { "right", "十字右", 0x01, 0x30, "图层上移 (Ctrl+])" },  // HID 0x30 (])
    { "a", "A (右)", 0x01, 0x1D, "撤销 (Ctrl+Z)" },  // HID 0x1D (z)
    { "b", "B (下)", 0x03, 0x1D, "重做 (Ctrl+Shift+Z)" },  // HID 0x1D (z)
    { "x", "X (上)", 0x02, 0x00, "按住 Shift：约束比例 / 加选 / 柔化组合" },  // mod only
    { "y", "Y (左)", 0x00, 0x2C, "按住空格：临时抓手（平移画布）" },  // HID 0x2C (space)
    { "l", "L", 0x01, 0x00, "按住 Ctrl：组合修饰键" },  // mod only
    { "r", "R", 0x04, 0x00, "按住 Alt：吸管 / 临时切换" },  // mod only
    { "select", "Select", 0x00, 0x2B, "显示/隐藏面板" },  // HID 0x2B (tab)
    { "start", "Start", 0x00, 0x29, "取消选择 / 退出变换" },  // HID 0x29 (esc)
};
