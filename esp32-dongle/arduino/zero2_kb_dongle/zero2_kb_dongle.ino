/*
 * zero2_kb_dongle.ino -- 8BitDo Zero 2 -> 自定义 USB 键盘（外挂 dongle 固件）
 *
 * 角色分工:
 *   8BitDo Zero 2  ---(蓝牙经典 BR/EDR, gamepad 模式)--->  ESP32(本固件)  ---UART--->  CH9329  ---USB HID 键盘--->  PC / iPad / Android / ...
 *
 * 为什么是 ESP32(原版，ESP32-WROOM/DevKit) 而不是 ESP32-S3/C3?
 *   Zero 2 的 gamepad 模式是蓝牙经典(BR/EDR)。ESP32-S3 / C3 / C5 / C6 / H2 只支持 BLE，
 *   连不上 (见 Bluepad32 FAQ)；ESP32 原版同时支持 BR/EDR + BLE，且 Bluepad32 明确支持 Zero 2。
 *   而 ESP32 原版没有 USB OTG，所以用 CH9329 模块补出 USB HID 键盘。
 *
 * 依赖与版本（详见 ../README.md）:
 *   - Arduino IDE 2.x
 *   - 板管理包: "ESP32 + Bluepad32 Arduino"（第三方板包，由 Bluepad32 作者提供）
 *       板包索引: https://raw.githubusercontent.com/ricardoquesada/esp32-arduino-lib-builder/master/bluepad32_files/package_esp32_bluepad32_index.json
 *       开发板选择: "ESP32 + Bluepad32 Arduino" -> "ESP32 Dev Module"（或你自己的型号）
 *   - 库: Bluepad32（随上述板包提供，无独立库需要装）
 *   - 硬件: ESP32 原版 DevKit + CH9329 串口转 USB HID 模块
 *
 * 映射表: mapping.h（由 tools/gen_mapping.py 从 mapping.example.json 生成，不要手改）
 *
 * 按键物理丝印 -> 本固件逻辑位（顺序写死，务必与 mapping.h 一致）:
 *   0 up, 1 down, 2 left, 3 right, 4 a, 5 b, 6 x, 7 y, 8 l, 9 r, 10 select, 11 start
 *
 * 注意：这里用"实体丝印"命名按钮。Bluepad32 的按钮 API 是位置语义（a=下/南, b=右/东,
 *       x=左/西, y=上/北），而 Zero 2 是任天堂布局（A 在右、B 在下、X 在上、Y 在左），
 *       所以物理 A 会出现在 ctl->b()、物理 B 出现在 ctl->a()，固件里已做换算。
 */

#include <string.h>
#include <Bluepad32.h>
#include "mapping.h"

// 不同 Bluepad32 版本对 dpad 掩码常量的导出方式略有差异，这里给一个兜底定义。
#ifndef DPAD_UP
#define DPAD_UP    0x01
#define DPAD_DOWN  0x02
#define DPAD_RIGHT 0x04
#define DPAD_LEFT  0x08
#endif

// ------------------------- 可改配置 -------------------------

// 调试串口输出（走 ESP32 板载 USB 串口，不要占用 Serial2）
#define ZERO2_DEBUG 1

// CH9329 串口。模块出厂默认 9600 8N1；
// 想更低延迟可用 WCH 的 CH9329 配置工具把模块改成 115200，然后这里同步改成 115200。
#define CH9329_BAUD     9600
#define CH9329_TX_PIN   17   // ESP32 TX2 -> CH9329 RXD
#define CH9329_RX_PIN   16   // ESP32 RX2 <- CH9329 TXD（本固件不解析回复，可以不接）
#define CH9329_CMD_KB   0x02 // CH9329 命令码: 发送通用键盘数据（8 字节 HID 键盘报告）

// 板载 LED：DevKit 一般是 GPIO2。不想要状态灯可改成 -1。
#define STATUS_LED      2

// 长按 L + R + Select 多少毫秒清除蓝牙配对（重新配对时用）
#define FORGET_KEYS_MS  3000

// ------------------------------------------------------------

// 按钮 bit（与 mapping.h 数组顺序一致）
enum : uint32_t {
    Z2_UP     = 1u << 0,
    Z2_DOWN   = 1u << 1,
    Z2_LEFT   = 1u << 2,
    Z2_RIGHT  = 1u << 3,
    Z2_A      = 1u << 4,
    Z2_B      = 1u << 5,
    Z2_X      = 1u << 6,
    Z2_Y      = 1u << 7,
    Z2_L      = 1u << 8,
    Z2_R      = 1u << 9,
    Z2_SELECT = 1u << 10,
    Z2_START  = 1u << 11,
};

static ControllerPtr myControllers[BP32_MAX_GAMEPADS];

// 上一次发给 CH9329 的键盘报告（用于变化检测，避免每圈都发）
static uint8_t lastMod = 0;
static uint8_t lastKeys[6] = {0, 0, 0, 0, 0, 0};
static bool  lastReportValid = false;

// ============================ CH9329 驱动 ============================

static inline uint8_t ch9329_checksum(const uint8_t *buf, size_t len) {
    uint8_t sum = 0;
    for (size_t i = 0; i < len; i++) sum = (uint8_t)(sum + buf[i]);
    return sum;
}

// 发送一个标准 8 字节 HID 键盘报告: mod / reserved / 6 个 keycode
static void ch9329SendKeyboard(uint8_t mod, const uint8_t keys[6]) {
    uint8_t pkt[14];
    pkt[0] = 0x57;       // 帧头
    pkt[1] = 0xAB;       // 帧头
    pkt[2] = 0x00;       // 地址
    pkt[3] = CH9329_CMD_KB;
    pkt[4] = 0x08;       // 数据长度
    pkt[5] = mod;        // 修饰键
    pkt[6] = 0x00;       // 保留
    memcpy(&pkt[7], keys, 6);
    pkt[13] = ch9329_checksum(pkt, 13);
    Serial2.write(pkt, sizeof(pkt));
}

static void ch9329ReleaseAll() {
    uint8_t zero[6] = {0, 0, 0, 0, 0, 0};
    ch9329SendKeyboard(0, zero);
}

// ============================ 手柄输入 ============================

// 把当前所有已连接手柄的按钮汇总成一个 bit mask
static uint32_t readButtons(ControllerPtr ctl) {
    uint32_t m = 0;
    uint8_t dpad = ctl->dpad();
    if (dpad & DPAD_UP)    m |= Z2_UP;
    if (dpad & DPAD_DOWN)  m |= Z2_DOWN;
    if (dpad & DPAD_LEFT)  m |= Z2_LEFT;
    if (dpad & DPAD_RIGHT) m |= Z2_RIGHT;

    // 位置语义 -> Zero 2 实体丝印（任天堂布局）：
    //   ctl->b() = 实体 A（右）   ctl->a() = 实体 B（下）
    //   ctl->y() = 实体 X（上）   ctl->x() = 实体 Y（左）
    if (ctl->b()) m |= Z2_A;
    if (ctl->a()) m |= Z2_B;
    if (ctl->y()) m |= Z2_X;
    if (ctl->x()) m |= Z2_Y;

    if (ctl->l1()) m |= Z2_L;
    if (ctl->r1()) m |= Z2_R;
    if (ctl->miscSelect()) m |= Z2_SELECT;
    if (ctl->miscStart())  m |= Z2_START;
    return m;
}

static void maskToReport(uint32_t mask, uint8_t *outMod, uint8_t *outKeys) {
    uint8_t mod = 0;
    uint8_t keys[6] = {0, 0, 0, 0, 0, 0};
    int keyCount = 0;

    for (int i = 0; i < ZERO2_BUTTON_COUNT; i++) {
        if ((mask & (1u << i)) == 0) continue;
        mod |= kZero2Mapping[i].mod;
        uint8_t k = kZero2Mapping[i].key;
        if (k == 0) continue;                    // 只按修饰键
        bool dup = false;
        for (int j = 0; j < keyCount; j++) {
            if (keys[j] == k) { dup = true; break; }
        }
        if (!dup && keyCount < 6) keys[keyCount++] = k;  // 6KRO 上限
    }

    // 按 usage id 升序排列，兼容性更好（顺序对 host 不敏感，但排一下无妨）
    for (int i = 0; i < keyCount; i++) {
        for (int j = i + 1; j < keyCount; j++) {
            if (keys[j] < keys[i]) {
                uint8_t t = keys[i];
                keys[i] = keys[j];
                keys[j] = t;
            }
        }
    }

    *outMod = mod;
    memcpy(outKeys, keys, 6);
}

// ============================ 连接回调 ============================

static int findFreeSlot() {
    for (int i = 0; i < BP32_MAX_GAMEPADS; i++) {
        if (myControllers[i] == nullptr) return i;
    }
    return -1;
}

static void onConnectedController(ControllerPtr ctl) {
    int slot = findFreeSlot();
    if (slot < 0) {
        Serial.println("WARN: 没有空位了，忽略这个手柄");
        return;
    }
    myControllers[slot] = ctl;
    ControllerProperties props = ctl->getProperties();
    Serial.printf("已连接 [%d]: %s (VID=0x%04x PID=0x%04x)\n",
                  slot, ctl->getModelName().c_str(), props.vendor_id, props.product_id);
}

static void onDisconnectedController(ControllerPtr ctl) {
    for (int i = 0; i < BP32_MAX_GAMEPADS; i++) {
        if (myControllers[i] == ctl) {
            Serial.printf("已断开 [%d]\n", i);
            myControllers[i] = nullptr;
        }
    }
    ch9329ReleaseAll();   // 关键：断连时把按住的键全部松开，避免"卡键"
}

// ============================ 主流程 ============================

static void updateStatusLed(bool anyConnected) {
    if (STATUS_LED < 0) return;
    static bool ledOn = false;
    static uint32_t lastBlinkMs = 0;
    if (anyConnected) {
        digitalWrite(STATUS_LED, HIGH);
        ledOn = true;
    } else if (millis() - lastBlinkMs > 500) {
        lastBlinkMs = millis();
        ledOn = !ledOn;
        digitalWrite(STATUS_LED, ledOn ? HIGH : LOW);
    }
}

void setup() {
    if (STATUS_LED >= 0) pinMode(STATUS_LED, OUTPUT);

    Serial.begin(115200);
    delay(200);
    Serial.println();
    Serial.println("=== Zero2 -> USB HID keyboard dongle ===");
    Serial.print("Bluepad32: ");
    Serial.println(BP32.firmwareVersion());
    Serial.print("mapping: ");
    Serial.println(ZERO2_MAPPING_VERSION);

    // CH9329
    Serial2.begin(CH9329_BAUD, SERIAL_8N1, CH9329_RX_PIN, CH9329_TX_PIN);
    delay(300);              // 等 CH9329 上电枚举
    ch9329ReleaseAll();      // 初始松键

    // Bluepad32
    BP32.setup(&onConnectedController, &onDisconnectedController);
    BP32.enableNewConnections(true);
    BP32.enableVirtualDevice(false);
    Serial.println("等待 Zero 2：Start+X 开机（Windows/X-input 模式），长按 Select 3 秒进入配对");
}

void loop() {
    BP32.update();

    uint32_t mask = 0;
    bool anyConnected = false;

    for (int i = 0; i < BP32_MAX_GAMEPADS; i++) {
        ControllerPtr ctl = myControllers[i];
        if (ctl == nullptr) continue;
        if (!ctl->isConnected()) {
            myControllers[i] = nullptr;
            continue;
        }
        if (!ctl->isGamepad()) continue;

        anyConnected = true;
        mask |= readButtons(ctl);
    }

    // 长按 L+R+Select 3 秒：清除配对信息，方便换主机
    static uint32_t forgetStartMs = 0;
    uint32_t combo = Z2_L | Z2_R | Z2_SELECT;
    if ((mask & combo) == combo) {
        if (forgetStartMs == 0) forgetStartMs = millis();
        if (millis() - forgetStartMs > FORGET_KEYS_MS) {
            Serial.println("清除蓝牙配对信息，准备重新配对...");
            BP32.forgetBluetoothKeys();
            ch9329ReleaseAll();
            forgetStartMs = 0;
        }
    } else {
        forgetStartMs = 0;
    }

    // 计算并发送键盘报告（只在变化时发）
    uint8_t mod = 0;
    uint8_t keys[6] = {0, 0, 0, 0, 0, 0};
    maskToReport(mask, &mod, keys);

    bool changed = !lastReportValid || mod != lastMod || memcmp(keys, lastKeys, 6) != 0;
    if (changed) {
        ch9329SendKeyboard(mod, keys);
        lastMod = mod;
        memcpy(lastKeys, keys, 6);
        lastReportValid = true;
#if ZERO2_DEBUG
        Serial.printf("mask=0x%03X -> mod=0x%02X keys=%02X %02X %02X %02X %02X %02X\n",
                      mask, mod, keys[0], keys[1], keys[2], keys[3], keys[4], keys[5]);
#endif
    }

    updateStatusLed(anyConnected);
    delay(4);   // 约 250Hz 轮询，足够；Bluepad32 内部事件驱动
}
