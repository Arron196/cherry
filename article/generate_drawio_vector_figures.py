from __future__ import annotations

import html
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "drawio_vector_figures"
MASTER_FILE = OUT_DIR / "traceability_figures.drawio"

PAGE_W = 1600
PAGE_H = 920

BG = "#FFFFFF"
GRID = "#F4F7FA"
TEXT = "#1F2D3D"
MUTED = "#66788A"
LINE = "#A9B7C4"
LINE_D = "#7E8E9D"
WHITE = "#FFFFFF"
ACCENT = "#2F6DB2"
ACCENT_FILL = "#EDF4FB"

TEAL = WHITE
TEAL_D = ACCENT
BLUE = ACCENT_FILL
BLUE_D = ACCENT
GREEN = WHITE
GREEN_D = LINE_D
ORANGE = WHITE
ORANGE_D = LINE_D
RED = WHITE
RED_D = LINE_D
PURPLE = WHITE
PURPLE_D = LINE_D
YELLOW = WHITE
YELLOW_D = LINE_D
SLATE = "#F7F9FB"


@dataclass
class Shape:
    id: str
    kind: str
    x: int
    y: int
    w: int
    h: int
    title: str = ""
    body: str = ""
    fill: str = WHITE
    stroke: str = LINE
    font_size: int = 18
    parent: str | None = None


@dataclass
class Edge:
    source: str
    target: str
    color: str
    label: str = ""
    source_side: str = "right"
    target_side: str = "left"
    waypoints: list[tuple[int, int]] = field(default_factory=list)
    dashed: bool = False


@dataclass
class Page:
    slug: str
    name: str
    title: str
    subtitle: str
    shapes: list[Shape]
    edges: list[Edge]


def shp(shape_id: str, kind: str, x: int, y: int, w: int, h: int, *, title: str = "", body: str = "", fill: str = WHITE, stroke: str = LINE, font_size: int = 18, parent: str | None = None) -> Shape:
    return Shape(shape_id, kind, x, y, w, h, title, body, fill, stroke, font_size, parent)


def edge(source: str, target: str, color: str, *, label: str = "", source_side: str = "right", target_side: str = "left", waypoints: list[tuple[int, int]] | None = None, dashed: bool = False) -> Edge:
    return Edge(source, target, color, label, source_side, target_side, waypoints or [], dashed)


PAGES: list[Page] = [
    Page(
        slug="figure_3_3_er",
        name="图3-3 ER",
        title="核心数据表 ER 关系图",
        subtitle="核心实体、主外键关系与逻辑关联",
        shapes=[
            shp("g1", "group", 50, 170, 330, 560, title="设备治理域", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("g2", "group", 400, 170, 720, 560, title="事件与处理域", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("g3", "group", 1140, 170, 410, 560, title="锚定与审计域", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("devices", "database", 80, 240, 270, 120, title="managed_devices", body="PK id\nUNIQUE device_id\nstatus / disabled_at", fill=TEAL, stroke=TEAL_D, parent="g1"),
            shp("keys", "database", 80, 420, 270, 145, title="managed_device_keys", body="PK id\nFK device_id -> managed_devices.id\nUNIQUE key_id\nalgorithm / status", fill=BLUE, stroke=BLUE_D, parent="g1"),
            shp("ingest", "database", 440, 285, 280, 175, title="ingest_requests", body="PK id\nUNIQUE idempotency_key\npayload_hash\ningest_status / retry_count\nFK event_id -> events.id", fill=BLUE, stroke=BLUE_D, parent="g2"),
            shp("events", "database", 775, 235, 310, 225, title="events", body="PK id\ndevice_id / batch_id / timestamp\nsensor_payload / signature_envelope\nUNIQUE canonical_hash", fill=GREEN, stroke=GREEN_D, parent="g2"),
            shp("quality", "database", 470, 560, 240, 120, title="quality_results", body="PK id\nFK event_id\ncheck_name / score\nstatus", fill=GREEN, stroke=GREEN_D, parent="g2"),
            shp("alerts", "database", 790, 560, 220, 120, title="alerts", body="PK id\nFK event_id\nalert_type / severity\nstatus", fill=RED, stroke=RED_D, parent="g2"),
            shp("subs", "database", 1190, 240, 300, 145, title="anchor_submissions", body="PK id\nFK event_id\ntransaction_hash\ncanonical_hash\nstatus", fill=PURPLE, stroke=PURPLE_D, parent="g3"),
            shp("receipts", "database", 1190, 435, 300, 140, title="anchor_receipts", body="PK id\nFK event_id\nnetwork\ntransaction_hash\nreceipt_payload", fill=ORANGE, stroke=ORANGE_D, parent="g3"),
            shp("audits", "database", 1190, 620, 300, 110, title="audits", body="PK id\nFK event_id\nactor / action / target", fill=YELLOW, stroke=YELLOW_D, parent="g3"),
            shp("callout", "note", 260, 780, 1080, 70, body="双层幂等：ingest_requests.idempotency_key 处理请求重放，events.canonical_hash 处理内容重复。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("devices", "keys", BLUE_D, label="1:N", source_side="bottom", target_side="top"),
            edge("ingest", "events", BLUE_D, label="N:1"),
            edge("events", "quality", GREEN_D, source_side="bottom", target_side="top"),
            edge("events", "alerts", RED_D, source_side="bottom", target_side="top"),
            edge("events", "subs", PURPLE_D),
            edge("events", "receipts", ORANGE_D),
            edge("events", "audits", YELLOW_D, source_side="bottom", target_side="top"),
            edge("devices", "events", TEAL_D, label="device_id 逻辑关联", source_side="right", target_side="top", waypoints=[(560, 155)], dashed=True),
        ],
    ),
    Page(
        slug="figure_3_5_security",
        name="图3-5 安全架构",
        title="系统安全架构图",
        subtitle="认证、授权、设备密钥治理与存证边界",
        shapes=[
            shp("zone0", "container", 60, 190, 240, 560, title="访问主体", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("zone1", "container", 355, 190, 260, 560, title="接入与认证", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("zone2", "container", 670, 190, 320, 560, title="核心服务", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("zone3", "container", 1045, 190, 500, 560, title="数据与存证", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("admin", "actor", 110, 260, 95, 120, title="管理员", fill=TEAL, stroke=TEAL_D, parent="zone0"),
            shp("regulator", "actor", 110, 400, 95, 120, title="监管员", fill=BLUE, stroke=BLUE_D, parent="zone0"),
            shp("device", "chip", 80, 575, 185, 110, title="边缘设备节点", body="ATECC608A 私钥硬件保护", fill=PURPLE, stroke=PURPLE_D, parent="zone0"),
            shp("tls", "process", 395, 265, 180, 95, title="HTTPS / TLS", body="入口加密通道", fill=BLUE, stroke=BLUE_D, parent="zone1"),
            shp("jwt", "process", 395, 390, 180, 120, title="JWT HS256", body="iss / exp / roles\n常时比较验签", fill=BLUE, stroke=BLUE_D, parent="zone1"),
            shp("rbac", "process", 395, 565, 180, 95, title="RBAC", body="Depends 统一拦截", fill=BLUE, stroke=BLUE_D, parent="zone1"),
            shp("api", "service", 725, 250, 210, 125, title="API 层", body="Ingest / Public Trace\nAdmin / Alerts", fill=GREEN, stroke=GREEN_D, parent="zone2"),
            shp("verify", "service", 725, 430, 210, 125, title="验证服务", body="DB 优先查密钥\n历史设备兼容回退 env key", fill=GREEN, stroke=GREEN_D, parent="zone2"),
            shp("anchor", "service", 725, 610, 210, 95, title="锚定引擎", body="Mock / EVM 适配器", fill=GREEN, stroke=GREEN_D, parent="zone2"),
            shp("db", "database", 1090, 280, 190, 120, title="PostgreSQL", body="managed_devices / keys\nevents / alerts / audits", fill=ORANGE, stroke=ORANGE_D, parent="zone3"),
            shp("ledger", "cloud", 1330, 290, 160, 110, title="区块链网络", body="EVM / Mock", fill=PURPLE, stroke=PURPLE_D, parent="zone3"),
            shp("audit", "note", 1090, 520, 400, 120, body="密钥治理策略：\n1. 一对一绑定\n2. 轮换保留历史验证能力\n3. 设备禁用后直接拒绝接入\n4. 全程写入 audits", fill=WHITE, stroke=LINE, parent="zone3"),
        ],
        edges=[
            edge("admin", "tls", TEAL_D),
            edge("regulator", "tls", BLUE_D),
            edge("device", "tls", PURPLE_D),
            edge("tls", "jwt", BLUE_D, source_side="bottom", target_side="top"),
            edge("jwt", "rbac", BLUE_D, source_side="bottom", target_side="top"),
            edge("rbac", "api", GREEN_D),
            edge("api", "verify", GREEN_D, source_side="bottom", target_side="top"),
            edge("verify", "db", ORANGE_D),
            edge("api", "db", ORANGE_D),
            edge("anchor", "ledger", PURPLE_D),
            edge("api", "anchor", GREEN_D, source_side="bottom", target_side="top"),
        ],
    ),
    Page(
        slug="figure_4_1_min_system",
        name="图4-1 最小系统",
        title="STM32H743 最小系统原理框图",
        subtitle="主控、电源、时钟、复位与调试接口关系",
        shapes=[
            shp("power", "module", 90, 260, 260, 140, title="电源去耦", body="5V -> AMS1117-3.3\nVDD / VDDA: 100nF + 10uF\nVDDA: 2.2uH + 10uF", fill=GREEN, stroke=GREEN_D),
            shp("reset", "module", 90, 470, 260, 125, title="复位 / BOOT0", body="NRST: 100nF + 按键\nBOOT0: 10k 下拉至 GND", fill=RED, stroke=RED_D),
            shp("mcu", "chip", 585, 245, 360, 290, title="STM32H743VIT6", body="LQFP-100\n480 MHz Cortex-M7\n3.3V 单电源\nI2C / UART / SPI / HASH", fill=BLUE, stroke=BLUE_D),
            shp("xtal", "module", 610, 120, 310, 80, title="8 MHz 外部晶振", body="HSE 8MHz + 22pF", fill=YELLOW, stroke=YELLOW_D),
            shp("swd", "module", 1140, 250, 300, 110, title="SWD 调试接口", body="SWDIO / SWDCLK / GND\nST-Link 在线调试", fill=BLUE, stroke=BLUE_D),
            shp("buses", "module", 1120, 425, 340, 145, title="外设总线引出", body="I2C1: SHT31 + ATECC608A\nUSART: 传感器 / Wi-Fi\nSPI1: SX1278", fill=TEAL, stroke=TEAL_D),
            shp("hint", "note", 250, 760, 1050, 60, body="图中突出系统组成与连接关系；若需电气级细节，应另附 CAD 原理图。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("power", "mcu", GREEN_D),
            edge("reset", "mcu", RED_D),
            edge("xtal", "mcu", YELLOW_D, source_side="bottom", target_side="top"),
            edge("mcu", "swd", BLUE_D),
            edge("mcu", "buses", TEAL_D),
        ],
    ),
    Page(
        slug="figure_4_2_sensors",
        name="图4-2 总线连接",
        title="多传感器接口与总线连接图",
        subtitle="I2C、UART 与 SPI 总线分工",
        shapes=[
            shp("i2c_lane", "container", 60, 170, 350, 350, title="I2C 域", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("serial_lane", "container", 60, 545, 350, 190, title="串口域", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("mcu", "chip", 610, 245, 320, 260, title="STM32H743", body="I2C1 / I2C2\nUSART1 / USART2\nSPI1\nHASH", fill=BLUE, stroke=BLUE_D),
            shp("wireless_lane", "container", 1090, 180, 380, 420, title="无线模块", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("sht", "module", 100, 235, 250, 105, title="SHT31", body="I2C1 / 0x44\nPB8 / PB9\nCRC 校验", fill=TEAL, stroke=TEAL_D, parent="i2c_lane"),
            shp("atecc", "module", 100, 390, 250, 110, title="ATECC608A", body="I2C1 / 0x60\nNever-Read 私钥\n执行 ECDSA Sign", fill=PURPLE, stroke=PURPLE_D, parent="i2c_lane"),
            shp("mhz", "module", 100, 600, 250, 105, title="MH-Z19B", body="USART1 / 9600 8N1\n5V 供电\n预热 3 分钟", fill=ORANGE, stroke=ORANGE_D, parent="serial_lane"),
            shp("esp", "module", 1140, 255, 260, 110, title="ESP8266", body="USART2 / 115200\nAT + HTTPS\n主上传通道", fill=BLUE, stroke=BLUE_D, parent="wireless_lane"),
            shp("lora", "module", 1140, 430, 260, 110, title="SX1278", body="SPI1 + GPIO\n433MHz\n备用链路", fill=GREEN, stroke=GREEN_D, parent="wireless_lane"),
            shp("tip", "note", 1080, 665, 380, 95, body="总线设计要点：\nI2C1 共享但地址不同；UART 直接 3.3V 连接；LoRa 需要额外 NSS / RESET / DIO0。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("sht", "mcu", TEAL_D, label="I2C1"),
            edge("atecc", "mcu", PURPLE_D, label="I2C1"),
            edge("mhz", "mcu", ORANGE_D, label="USART1"),
            edge("mcu", "esp", BLUE_D, label="USART2"),
            edge("mcu", "lora", GREEN_D, label="SPI1"),
        ],
    ),
    Page(
        slug="figure_4_3_atecc_sign",
        name="图4-3 ATECC 签名",
        title="ATECC608A 连接与签名流程图",
        subtitle="安全芯片配置与设备端签名流水线",
        shapes=[
            shp("left", "container", 60, 185, 330, 520, title="安全芯片配置", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("slot", "module", 100, 260, 250, 170, title="ATECC608A 槽位策略", body="Slot 0: ECDSA P-256 私钥\nNever-Read，仅允许 Sign\nSlot 1~3: 预留\nConfig Lock + Data Lock", fill=PURPLE, stroke=PURPLE_D, parent="left"),
            shp("i2c", "note", 100, 485, 250, 150, body="I2C 时序：\nWakeup -> 命令帧\n(Length / OpCode / Param / Data / CRC16)\n-> 等待执行 -> 读响应 -> Sleep", fill=WHITE, stroke=LINE, parent="left"),
            shp("f1", "process", 470, 315, 170, 120, title="1 数据帧构造", body="SensorTask\n采集并组装 JSON", fill=TEAL, stroke=TEAL_D),
            shp("f2", "process", 700, 315, 160, 120, title="2 摘要计算", body="规范化序列化\nHASH-SHA256", fill=BLUE, stroke=BLUE_D),
            shp("f3", "process", 920, 315, 180, 120, title="3 芯片签名", body="Wakeup -> Sign(0x41)\n等待 tEXEC\n取回 64B (r,s)", fill=PURPLE, stroke=PURPLE_D),
            shp("f4", "process", 1160, 315, 170, 120, title="4 DER 编码", body="原始 (r,s)\n转 ASN.1 DER", fill=ORANGE, stroke=ORANGE_D),
            shp("f5", "process", 1380, 315, 150, 120, title="5 上传", body="signature_envelope\n经 HTTPS 发送", fill=GREEN, stroke=GREEN_D),
            shp("time", "note", 520, 620, 840, 70, body="性能备注：ATECC608A 签名实测约 7 ms；从采集到封装上传整个路径约 15~25 ms。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("f1", "f2", BLUE_D),
            edge("f2", "f3", BLUE_D),
            edge("f3", "f4", BLUE_D),
            edge("f4", "f5", BLUE_D),
        ],
    ),
    Page(
        slug="figure_4_4_comms",
        name="图4-4 通信组网",
        title="Wi-Fi / LoRa 通信组网图",
        subtitle="双通道上行与后端聚合拓扑",
        shapes=[
            shp("node", "chip", 90, 310, 300, 170, title="边缘节点", body="STM32H743\nSHT31 / MH-Z19B / ATECC608A\nCommTask 统一出站", fill=BLUE, stroke=BLUE_D),
            shp("wifi", "cloud", 520, 205, 250, 130, title="ESP8266 + Wi-Fi", body="AT+CWJAP\nAT+CIPSTART HTTPS\nCertificate Pinning", fill=TEAL, stroke=TEAL_D),
            shp("lora", "cloud", 520, 505, 250, 130, title="SX1278 + LoRa", body="433 MHz\n超过 255B 时分 2 包\n备用链路", fill=GREEN, stroke=GREEN_D),
            shp("gw", "service", 910, 470, 240, 120, title="LoRa 网关", body="接收分片\n按序重组\nHTTP 转发", fill=ORANGE, stroke=ORANGE_D),
            shp("backend", "cloud", 1250, 260, 250, 170, title="后端服务", body="Ingest API\nJWT / 幂等校验\n数据库 + 锚定引擎", fill=PURPLE, stroke=PURPLE_D),
            shp("switch", "note", 410, 745, 770, 70, body="链路切换策略：CommTask 优先走 Wi-Fi；若 30 秒内连接失败或 ACK 超时，则自动切换到 LoRa。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("node", "wifi", TEAL_D, label="主链路"),
            edge("node", "lora", GREEN_D, label="备用"),
            edge("wifi", "backend", BLUE_D),
            edge("lora", "gw", GREEN_D),
            edge("gw", "backend", ORANGE_D),
        ],
    ),
    Page(
        slug="figure_4_5_power",
        name="图4-5 电源管理",
        title="电源管理原理框图",
        subtitle="混合供电链路与低功耗策略",
        shapes=[
            shp("solar", "module", 90, 250, 220, 100, title="10W 太阳能板", body="有光照时为系统补能", fill=YELLOW, stroke=YELLOW_D),
            shp("battery", "module", 90, 445, 220, 110, title="18650 电池", body="3.7V / 3000mAh\n夜间与阴天主供电", fill=RED, stroke=RED_D),
            shp("mppt", "process", 440, 330, 250, 140, title="MPPT 充电控制器", body="太阳能充电管理\n兼顾充放电保护", fill=GREEN, stroke=GREEN_D),
            shp("rail5", "module", 810, 255, 230, 95, title="5V 电源轨", body="供给 MH-Z19B 等 5V 负载", fill=BLUE, stroke=BLUE_D),
            shp("rail3", "module", 810, 445, 250, 110, title="3.3V 电源轨", body="AMS1117-3.3 输出\n供 MCU / 传感器 / 无线模组", fill=TEAL, stroke=TEAL_D),
            shp("loads", "container", 1160, 230, 320, 300, title="系统负载", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("load1", "chip", 1200, 285, 110, 95, title="STM32H743", fill=BLUE, stroke=BLUE_D, parent="loads"),
            shp("load2", "module", 1330, 285, 110, 95, title="SHT31 /\nATECC608A", fill=TEAL, stroke=TEAL_D, parent="loads"),
            shp("load3", "module", 1200, 405, 110, 95, title="ESP8266", fill=BLUE, stroke=BLUE_D, parent="loads"),
            shp("load4", "module", 1330, 405, 110, 95, title="SX1278", fill=GREEN, stroke=GREEN_D, parent="loads"),
            shp("sleep", "note", 180, 720, 1220, 70, body="低功耗策略：Tickless Idle + Stop 模式 + 外设时钟门控 + ESP8266 深度睡眠 + SX1278 休眠待命。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("solar", "mppt", YELLOW_D),
            edge("battery", "mppt", RED_D),
            edge("mppt", "rail5", BLUE_D),
            edge("mppt", "rail3", TEAL_D),
            edge("rail5", "loads", BLUE_D),
            edge("rail3", "loads", TEAL_D),
        ],
    ),
    Page(
        slug="figure_5_1_freertos",
        name="图5-1 FreeRTOS",
        title="FreeRTOS 任务调度与数据通路图",
        subtitle="Boot、SensorTask、SignTask、CommTask 与队列交接关系",
        shapes=[
            shp("lane0", "swimlane", 70, 180, 260, 560, title="Boot / Init", fill=SLATE, stroke=LINE),
            shp("lane1", "swimlane", 360, 180, 260, 560, title="SensorTask", fill=TEAL, stroke=TEAL_D),
            shp("lane2", "swimlane", 650, 180, 260, 560, title="SignTask", fill=PURPLE, stroke=PURPLE_D),
            shp("lane3", "swimlane", 940, 180, 260, 560, title="CommTask", fill=GREEN, stroke=GREEN_D),
            shp("lane4", "swimlane", 1230, 180, 250, 560, title="外设 / 网络", fill=BLUE, stroke=BLUE_D),
            shp("init", "process", 115, 260, 170, 110, title="系统初始化", body="HAL / Clock / 外设 Init\n创建任务与队列", fill=WHITE, stroke=LINE, parent="lane0"),
            shp("sched", "process", 115, 470, 170, 90, title="调度启动", body="vTaskStartScheduler", fill=WHITE, stroke=LINE, parent="lane0"),
            shp("sensor", "process", 405, 290, 170, 120, title="采集一帧", body="30 s 周期\n前 3 分钟 CO₂=-1", fill=WHITE, stroke=TEAL_D, parent="lane1"),
            shp("q1", "queue", 445, 500, 90, 110, title="sensorQueue", body="深度 4", fill=WHITE, stroke=YELLOW_D, parent="lane1"),
            shp("sign", "process", 695, 290, 170, 140, title="签名流水", body="规范化 -> SHA-256\nATECC608A Sign\nDER 编码", fill=WHITE, stroke=PURPLE_D, parent="lane2"),
            shp("q2", "queue", 735, 500, 90, 110, title="signedQueue", body="深度 4", fill=WHITE, stroke=RED_D, parent="lane2"),
            shp("comm", "process", 985, 290, 170, 120, title="上传决策", body="优先 Wi-Fi\n失败后切 LoRa", fill=WHITE, stroke=GREEN_D, parent="lane3"),
            shp("wifi", "module", 1270, 280, 160, 90, title="ESP8266 HTTPS", fill=WHITE, stroke=BLUE_D, parent="lane4"),
            shp("lora", "module", 1270, 440, 160, 90, title="SX1278 LoRa", fill=WHITE, stroke=GREEN_D, parent="lane4"),
            shp("hint", "note", 240, 785, 1100, 60, body="采集、签名与通信通过队列解耦；空闲阶段可进入低功耗模式。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("init", "sched", BLUE_D, source_side="bottom", target_side="top"),
            edge("sched", "sensor", TEAL_D),
            edge("sensor", "q1", YELLOW_D, source_side="bottom", target_side="top"),
            edge("q1", "sign", PURPLE_D),
            edge("sign", "q2", RED_D, source_side="bottom", target_side="top"),
            edge("q2", "comm", GREEN_D),
            edge("comm", "wifi", BLUE_D),
            edge("comm", "lora", GREEN_D, dashed=True),
        ],
    ),
    Page(
        slug="figure_5_4_verify",
        name="图5-4 验证流程",
        title="签名验证流程图",
        subtitle="签名、密钥来源与兼容回退验证路径",
        shapes=[
            shp("lane0", "swimlane", 70, 170, 260, 620, title="请求入口", fill=SLATE, stroke=LINE),
            shp("lane1", "swimlane", 360, 170, 380, 620, title="密钥解析与哈希", fill=BLUE, stroke=BLUE_D),
            shp("lane2", "swimlane", 770, 170, 300, 620, title="验证决策", fill=YELLOW, stroke=YELLOW_D),
            shp("lane3", "swimlane", 1100, 170, 360, 620, title="结果", fill=GREEN, stroke=GREEN_D),
            shp("start", "terminator", 120, 235, 160, 60, title="开始", body="", fill=TEAL, stroke=TEAL_D, parent="lane0"),
            shp("extract", "process", 100, 360, 200, 95, title="提取信封", body="algorithm / key_id /\nsignature / public_key", fill=WHITE, stroke=LINE, parent="lane0"),
            shp("lookup", "process", 420, 255, 260, 120, title="查询 managed_device_keys", body="校验 device_id + key_id\n确认设备未禁用\n算法必须匹配", fill=WHITE, stroke=BLUE_D, parent="lane1"),
            shp("fallback", "process", 420, 470, 260, 120, title="兼容回退", body="仅当设备未注册时\n回退 INGEST_SIGNING_KEYS\n只支持 HMAC", fill=WHITE, stroke=ORANGE_D, parent="lane1"),
            shp("hash", "process", 420, 650, 260, 90, title="重新计算 canonical_hash", body="对业务数据执行规范化算法", fill=WHITE, stroke=GREEN_D, parent="lane1"),
            shp("d1", "decision", 810, 285, 170, 120, title="DB 中有\n活动密钥?", fill=YELLOW, stroke=YELLOW_D, parent="lane2"),
            shp("verify", "process", 800, 575, 190, 100, title="执行签名验证", body="ECDSA-P256 或\nHMAC-SHA256", fill=WHITE, stroke=RED_D, parent="lane2"),
            shp("d2", "decision", 810, 705, 170, 120, title="签名 / MAC\n有效?", fill=YELLOW, stroke=YELLOW_D, parent="lane2"),
            shp("reject", "terminator", 1180, 305, 180, 70, title="401 Unauthorized", body="", fill=RED, stroke=RED_D, parent="lane3"),
            shp("ingest", "terminator", 1160, 690, 220, 70, title="进入后续入库 / 幂等处理", body="", fill=GREEN, stroke=GREEN_D, parent="lane3"),
            shp("note", "note", 1135, 470, 290, 120, body="关键规则：\n设备已注册但密钥不匹配，直接拒绝；\n只有“设备尚未注册”时才允许走兼容回退。", fill=WHITE, stroke=LINE, parent="lane3"),
        ],
        edges=[
            edge("start", "extract", TEAL_D, source_side="bottom", target_side="top"),
            edge("extract", "lookup", BLUE_D),
            edge("lookup", "d1", BLUE_D),
            edge("d1", "reject", RED_D, label="否"),
            edge("d1", "hash", GREEN_D, label="是", source_side="bottom", target_side="top"),
            edge("lookup", "fallback", ORANGE_D, label="未注册", source_side="bottom", target_side="top", dashed=True),
            edge("fallback", "hash", ORANGE_D, source_side="bottom", target_side="top"),
            edge("hash", "verify", GREEN_D),
            edge("verify", "d2", RED_D, source_side="bottom", target_side="top"),
            edge("d2", "reject", RED_D, label="否", target_side="bottom", waypoints=[(1250, 765), (1250, 405)]),
            edge("d2", "ingest", GREEN_D, label="是"),
        ],
    ),
    Page(
        slug="figure_5_6_rollout",
        name="图5-6 Rollout",
        title="四阶段 Rollout 策略图",
        subtitle="渐进上线阶段、SLO 监控与自动回滚回路",
        shapes=[
            shp("stack", "container", 70, 180, 1370, 250, title="上线阶段", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("r0", "stage", 120, 260, 250, 100, title="rollback_safe", body="100% Mock\n零 Gas\n默认模式", fill=TEAL, stroke=TEAL_D, parent="stack"),
            shp("r1", "stage", 450, 260, 250, 100, title="shadow", body="主路径仍走 Mock\n副本并发发往 EVM\n只看日志与指标", fill=BLUE, stroke=BLUE_D, parent="stack"),
            shp("r2", "stage", 780, 260, 250, 100, title="canary", body="5% 真流量走 EVM\n95% 继续走 Mock\n风险面受控", fill=ORANGE, stroke=ORANGE_D, parent="stack"),
            shp("r3", "stage", 1110, 260, 250, 100, title="full", body="100% EVM\nMock 退出主路径", fill=GREEN, stroke=GREEN_D, parent="stack"),
            shp("metrics", "dashboard", 260, 520, 780, 160, title="canary 期持续监控 SLO", body="成功率 >= 99%\n死信率 <= 0.5%\nP95 完成时间 <= 120 s", fill=WHITE, stroke=LINE),
            shp("rollback", "note", 1090, 715, 310, 80, body="若任一指标连续违规超过 600 s，则自动回滚到 rollback_safe。", fill=RED, stroke=RED_D),
        ],
        edges=[
            edge("r0", "r1", BLUE_D),
            edge("r1", "r2", BLUE_D),
            edge("r2", "r3", BLUE_D),
            edge("r2", "metrics", ORANGE_D, source_side="bottom", target_side="top"),
            edge("metrics", "rollback", RED_D, source_side="right", target_side="top"),
            edge("rollback", "r0", RED_D, waypoints=[(200, 755), (200, 360)]),
        ],
    ),
    Page(
        slug="figure_5_7_frontend",
        name="图5-7 前端结构",
        title="前端页面结构与关键界面示意图",
        subtitle="站点地图与关键页面骨架",
        shapes=[
            shp("sitemap", "container", 60, 180, 400, 620, title="应用路由 / Site Map", fill="#F8FCFE", stroke="#D7E3EC"),
            shp("root", "process", 145, 250, 230, 70, title="/", body="管理员总览页", fill=BLUE, stroke=BLUE_D, parent="sitemap"),
            shp("login", "process", 90, 380, 120, 70, title="/login", body="", fill=ORANGE, stroke=ORANGE_D, parent="sitemap"),
            shp("batches", "process", 250, 380, 120, 70, title="/batches", body="", fill=TEAL, stroke=TEAL_D, parent="sitemap"),
            shp("events", "process", 90, 500, 120, 70, title="/events", body="", fill=TEAL, stroke=TEAL_D, parent="sitemap"),
            shp("alerts", "process", 250, 500, 120, 70, title="/alerts", body="", fill=TEAL, stroke=TEAL_D, parent="sitemap"),
            shp("admin", "process", 90, 620, 280, 90, title="/admin/*", body="anchoring / devices / api-tools", fill=PURPLE, stroke=PURPLE_D, parent="sitemap"),
            shp("trace", "process", 90, 735, 280, 70, title="/trace/public/[batchId]", body="", fill=GREEN, stroke=GREEN_D, parent="sitemap"),
            shp("dash_view", "browser", 540, 190, 420, 270, title="Dashboard 线框图", body="指标卡\n图表区域\n业务入口导航", fill=TEAL, stroke=TEAL_D),
            shp("trace_view", "browser", 1020, 190, 470, 270, title="Public Trace 线框图", body="批次信息 / 品质等级\n时间线\n温湿度 / CO₂ / 振动曲线\n链上验证引导", fill=GREEN, stroke=GREEN_D),
            shp("login_view", "browser", 670, 520, 690, 220, title="登录页线框图", body="左侧品牌介绍与能力摘要\n右侧账号密码表单\n演示账号说明", fill=ORANGE, stroke=ORANGE_D),
            shp("note", "note", 530, 790, 850, 60, body="页面层只保留路由结构与关键界面骨架，用于说明系统信息架构与主要交互入口。", fill=WHITE, stroke=LINE),
        ],
        edges=[
            edge("root", "login", BLUE_D, source_side="bottom", target_side="top"),
            edge("root", "batches", BLUE_D, source_side="bottom", target_side="top"),
            edge("root", "events", BLUE_D, source_side="bottom", target_side="top"),
            edge("root", "alerts", BLUE_D, source_side="bottom", target_side="top"),
            edge("root", "admin", BLUE_D, source_side="bottom", target_side="top"),
            edge("root", "trace", BLUE_D, source_side="bottom", target_side="top"),
            edge("batches", "dash_view", TEAL_D),
            edge("trace", "trace_view", GREEN_D),
            edge("login", "login_view", ORANGE_D),
        ],
    ),
]


def anchor(shape: Shape, side: str) -> tuple[int, int]:
    x = shape.x
    y = shape.y
    if shape.kind in {"container", "group", "swimlane"}:
        y += 40
    if side == "left":
        return x, y + shape.h // 2
    if side == "right":
        return x + shape.w, y + shape.h // 2
    if side == "top":
        return x + shape.w // 2, y
    return x + shape.w // 2, y + shape.h


def html_lines(title: str, body: str, font_size: int, centered: bool = False) -> str:
    align = "center" if centered else "left"
    title_html = ""
    if title:
        title_html = (
            f"<div style='font-family:Microsoft YaHei;font-size:{font_size + 2}px;font-weight:700;"
            f"color:{TEXT};margin-bottom:6px;text-align:{align}'>{html.escape(title)}</div>"
        )
    body_html = "<br/>".join(html.escape(line) for line in body.splitlines())
    return (
        f"{title_html}<div style='font-family:Microsoft YaHei;font-size:{font_size}px;color:{TEXT};"
        f"line-height:1.35;text-align:{align}'>{body_html}</div>"
    )


def shape_style(shape: Shape) -> str:
    kind = shape.kind
    if kind == "container":
        return (
            f"swimlane;html=1;rounded=1;startSize=30;fillColor={WHITE};strokeColor={shape.stroke};"
            "strokeWidth=1.5;fontStyle=1;horizontal=0;whiteSpace=wrap;container=1;collapsible=0;"
            f"fontColor={TEXT};fontSize=18;"
        )
    if kind == "swimlane":
        return (
            f"swimlane;html=1;rounded=1;startSize=38;fillColor={WHITE};strokeColor={shape.stroke};"
            "strokeWidth=1.5;fontStyle=1;horizontal=0;whiteSpace=wrap;container=1;collapsible=0;"
            f"fontColor={TEXT};fontSize=18;"
        )
    if kind == "group":
        return (
            f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor={WHITE};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontStyle=1;fontColor={TEXT};fontSize=18;spacingTop=12;"
        )
    if kind == "database":
        return (
            f"shape=mxgraph.flowchart.direct_data;html=1;whiteSpace=wrap;fillColor={shape.fill};"
            f"strokeColor={shape.stroke};strokeWidth=1.5;fontColor={TEXT};spacingTop=14;spacingLeft=18;spacingRight=18;"
        )
    if kind == "cloud":
        return (
            f"shape=cloud;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};spacingTop=18;spacingLeft=20;spacingRight=20;"
        )
    if kind == "actor":
        return (
            f"shape=umlActor;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};verticalLabelPosition=bottom;verticalAlign=top;align=center;"
        )
    if kind == "chip":
        return (
            f"shape=mxgraph.electrical.int_ic;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};spacingTop=18;spacingLeft=18;spacingRight=18;"
        )
    if kind == "queue":
        return (
            f"shape=mxgraph.flowchart.stored_data;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};align=center;verticalAlign=middle;"
        )
    if kind == "decision":
        return (
            f"shape=rhombus;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};align=center;verticalAlign=middle;"
        )
    if kind == "terminator":
        return (
            f"shape=mxgraph.flowchart.terminator;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};align=center;verticalAlign=middle;"
        )
    if kind == "browser":
        return (
            f"shape=mxgraph.mockup.containers.browserWindow;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};spacingTop=40;spacingLeft=20;spacingRight=20;"
        )
    if kind == "dashboard":
        return (
            f"shape=mxgraph.mockup.containers.rounded;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;fontColor={TEXT};spacingTop=22;spacingLeft=22;spacingRight=22;"
        )
    if kind == "stage":
        return (
            f"rounded=1;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.5;arcSize=10;fontColor={TEXT};spacingTop=14;spacingLeft=16;spacingRight=16;"
        )
    if kind == "note":
        return (
            f"shape=note;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
            f"strokeWidth=1.2;fontColor={MUTED};spacingTop=16;spacingLeft=16;spacingRight=16;"
        )
    return (
        f"rounded=1;html=1;whiteSpace=wrap;fillColor={shape.fill};strokeColor={shape.stroke};"
        f"strokeWidth=1.5;arcSize=8;fontColor={TEXT};spacingTop=18;spacingLeft=18;spacingRight=18;"
    )


def edge_style(item: Edge) -> str:
    parts = [
        "edgeStyle=orthogonalEdgeStyle",
        "rounded=0",
        "orthogonalLoop=1",
        "jettySize=auto",
        "html=1",
        "endArrow=block",
        "endFill=1",
        f"strokeColor={item.color}",
        "strokeWidth=2.2",
        "fontSize=14",
        f"fontColor={item.color}",
    ]
    if item.dashed:
        parts.append("dashed=1")
    return ";".join(parts) + ";"


def build_page(page: Page) -> ET.Element:
    diagram = ET.Element("diagram", id=uuid.uuid4().hex[:12], name=page.name)
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1200",
            "dy": "800",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": str(PAGE_W),
            "pageHeight": str(PAGE_H),
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    title_cell = ET.SubElement(root, "mxCell", id="title", value=html.escape(page.title), style=f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=30;fontStyle=1;fontColor={TEXT};", vertex="1", parent="1")
    ET.SubElement(title_cell, "mxGeometry", x="52", y="34", width="860", height="38", **{"as": "geometry"})
    sub_cell = ET.SubElement(root, "mxCell", id="subtitle", value=html.escape(page.subtitle), style=f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=14;fontColor={MUTED};", vertex="1", parent="1")
    ET.SubElement(sub_cell, "mxGeometry", x="52", y="84", width="1200", height="24", **{"as": "geometry"})

    shape_id_map: dict[str, str] = {}
    next_id = 10
    for item in page.shapes:
        shape_id_map[item.id] = str(next_id)
        next_id += 1

    for item in page.shapes:
        parent_id = "1" if item.parent is None else shape_id_map[item.parent]
        centered = item.kind in {"actor", "decision", "terminator", "queue"}
        value = item.title if item.kind in {"container", "swimlane"} else html_lines(item.title, item.body, item.font_size, centered=centered)
        cell = ET.SubElement(root, "mxCell", id=shape_id_map[item.id], value=value, style=shape_style(item), vertex="1", parent=parent_id)
        ET.SubElement(cell, "mxGeometry", x=str(item.x), y=str(item.y), width=str(item.w), height=str(item.h), **{"as": "geometry"})

    edge_base = 1000
    for i, conn in enumerate(page.edges):
        cell = ET.SubElement(
            root,
            "mxCell",
            id=str(edge_base + i),
            value=html.escape(conn.label),
            style=edge_style(conn),
            edge="1",
            parent="1",
            source=shape_id_map[conn.source],
            target=shape_id_map[conn.target],
        )
        geo = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        if conn.waypoints:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for x, y in conn.waypoints:
                ET.SubElement(arr, "mxPoint", x=str(x), y=str(y))
    return diagram


def write_drawio_files() -> None:
    mxfile = ET.Element("mxfile", host="app.diagrams.net", modified="2026-04-22T00:00:00.000Z", agent="Codex", version="25.0.2")
    for page in PAGES:
        mxfile.append(build_page(page))
    tree = ET.ElementTree(mxfile)
    ET.indent(tree, space="  ")
    tree.write(MASTER_FILE, encoding="utf-8", xml_declaration=True)

    for page in PAGES:
        single = ET.Element("mxfile", host="app.diagrams.net", modified="2026-04-22T00:00:00.000Z", agent="Codex", version="25.0.2")
        single.append(build_page(page))
        stree = ET.ElementTree(single)
        ET.indent(stree, space="  ")
        stree.write(OUT_DIR / f"{page.slug}.drawio", encoding="utf-8", xml_declaration=True)


def svg_rect(parts: list[str], x: int, y: int, w: int, h: int, fill: str, stroke: str, rx: int = 8, stroke_width: float = 1.4) -> None:
    parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{rx}' ry='{rx}' fill='{fill}' stroke='{stroke}' stroke-width='{stroke_width}' />")


def svg_text_block(parts: list[str], x: int, y: int, title: str, body: str, size: int, *, centered: bool = False, color: str = TEXT) -> None:
    anchor_text = "middle" if centered else "start"
    text_x = x
    cur_y = y
    if title:
        parts.append(f"<text x='{text_x}' y='{cur_y}' font-family='Microsoft YaHei, PingFang SC, sans-serif' font-size='{size + 2}' font-weight='700' fill='{color}' text-anchor='{anchor_text}'>{html.escape(title)}</text>")
        cur_y += size + 10
    for line in body.splitlines():
        parts.append(f"<text x='{text_x}' y='{cur_y}' font-family='Microsoft YaHei, PingFang SC, sans-serif' font-size='{size}' fill='{color}' text-anchor='{anchor_text}'>{html.escape(line)}</text>")
        cur_y += size + 8


def render_shape_svg(parts: list[str], item: Shape) -> None:
    x, y, w, h = item.x, item.y, item.w, item.h
    if item.kind in {"container", "group"}:
        svg_rect(parts, x, y, w, h, WHITE, item.stroke, 8, 1.4)
        parts.append(f"<line x1='{x}' y1='{y+30}' x2='{x+w}' y2='{y+30}' stroke='{item.stroke}' stroke-width='1' opacity='0.35' />")
        svg_text_block(parts, x + 14, y + 22, item.title, "", 17)
        return
    if item.kind == "swimlane":
        svg_rect(parts, x, y, w, h, WHITE, item.stroke, 8, 1.4)
        parts.append(f"<line x1='{x}' y1='{y+38}' x2='{x+w}' y2='{y+38}' stroke='{item.stroke}' stroke-width='1' opacity='0.45' />")
        svg_text_block(parts, x + 16, y + 24, item.title, "", 17)
        return
    if item.kind == "database":
        body_top = y + 22
        body_bottom = y + h - 22
        parts.append(f"<ellipse cx='{x + w/2}' cy='{body_top}' rx='{w/2}' ry='22' fill='{item.fill}' stroke='{item.stroke}' stroke-width='1.4' />")
        parts.append(f"<rect x='{x}' y='{body_top}' width='{w}' height='{body_bottom - body_top}' fill='{item.fill}' stroke='{item.stroke}' stroke-width='1.4' />")
        parts.append(f"<ellipse cx='{x + w/2}' cy='{body_bottom}' rx='{w/2}' ry='22' fill='{item.fill}' stroke='{item.stroke}' stroke-width='1.4' />")
        svg_text_block(parts, x + 18, y + 54, item.title, item.body, item.font_size - 1)
        return
    if item.kind == "cloud":
        parts.append(
            f"<path d='M {x+50} {y+h-35} C {x+10} {y+h-35}, {x+5} {y+35}, {x+60} {y+38} "
            f"C {x+70} {y+5}, {x+125} {y+5}, {x+142} {y+35} "
            f"C {x+205} {y-2}, {x+w-8} {y+42}, {x+w-42} {y+h-30} "
            f"L {x+50} {y+h-35} Z' fill='{item.fill}' stroke='{item.stroke}' stroke-width='1.4' />"
        )
        svg_text_block(parts, x + w / 2, y + 56, item.title, item.body, item.font_size - 1, centered=True)
        return
    if item.kind == "actor":
        cx = x + w / 2
        parts.append(f"<circle cx='{cx}' cy='{y+26}' r='18' fill='{WHITE}' stroke='{item.stroke}' stroke-width='1.4' />")
        parts.append(f"<line x1='{cx}' y1='{y+44}' x2='{cx}' y2='{y+84}' stroke='{item.stroke}' stroke-width='2' />")
        parts.append(f"<line x1='{cx-24}' y1='{y+58}' x2='{cx+24}' y2='{y+58}' stroke='{item.stroke}' stroke-width='2' />")
        parts.append(f"<line x1='{cx}' y1='{y+84}' x2='{cx-20}' y2='{y+115}' stroke='{item.stroke}' stroke-width='2' />")
        parts.append(f"<line x1='{cx}' y1='{y+84}' x2='{cx+20}' y2='{y+115}' stroke='{item.stroke}' stroke-width='2' />")
        svg_text_block(parts, cx, y + h - 6, item.title, "", item.font_size - 1, centered=True)
        return
    if item.kind == "chip":
        svg_rect(parts, x, y, w, h, item.fill, item.stroke, 6, 1.4)
        for i in range(4):
            px = x + 18 + i * ((w - 36) / 3)
            parts.append(f"<line x1='{px}' y1='{y-8}' x2='{px}' y2='{y}' stroke='{item.stroke}' stroke-width='1.4' />")
            parts.append(f"<line x1='{px}' y1='{y+h}' x2='{px}' y2='{y+h+8}' stroke='{item.stroke}' stroke-width='1.4' />")
        for i in range(3):
            py = y + 24 + i * ((h - 48) / 2)
            parts.append(f"<line x1='{x-8}' y1='{py}' x2='{x}' y2='{py}' stroke='{item.stroke}' stroke-width='1.4' />")
            parts.append(f"<line x1='{x+w}' y1='{py}' x2='{x+w+8}' y2='{py}' stroke='{item.stroke}' stroke-width='1.4' />")
        svg_text_block(parts, x + 20, y + 34, item.title, item.body, item.font_size - 1)
        return
    if item.kind == "queue":
        parts.append(f"<path d='M {x+15} {y} Q {x} {y+h/2} {x+15} {y+h} L {x+w} {y+h} L {x+w-15} {y+h/2} L {x+w} {y} Z' fill='{item.fill}' stroke='{item.stroke}' stroke-width='1.4' />")
        svg_text_block(parts, x + w / 2, y + 42, item.title, item.body, item.font_size - 1, centered=True)
        return
    if item.kind == "decision":
        cx = x + w / 2
        cy = y + h / 2
        points = f"{cx},{y} {x+w},{cy} {cx},{y+h} {x},{cy}"
        parts.append(f"<polygon points='{points}' fill='{item.fill}' stroke='{item.stroke}' stroke-width='1.4' />")
        svg_text_block(parts, cx, y + 42, item.title, "", item.font_size - 1, centered=True)
        return
    if item.kind == "terminator":
        svg_rect(parts, x, y, w, h, item.fill, item.stroke, h // 2, 1.4)
        svg_text_block(parts, x + w / 2, y + h / 2 + 6, item.title, "", item.font_size - 1, centered=True)
        return
    if item.kind == "browser":
        svg_rect(parts, x, y, w, h, WHITE, item.stroke, 8, 1.4)
        parts.append(f"<line x1='{x}' y1='{y+32}' x2='{x+w}' y2='{y+32}' stroke='{item.stroke}' stroke-width='1' opacity='0.35' />")
        for i in range(3):
            parts.append(f"<circle cx='{x+22+i*16}' cy='{y+16}' r='3.5' fill='{item.stroke}' opacity='0.45' />")
        svg_text_block(parts, x + 22, y + 58, item.title, item.body, item.font_size - 1)
        parts.append(f"<rect x='{x+24}' y='{y+110}' width='{w-48}' height='14' rx='7' ry='7' fill='{item.stroke}' opacity='0.05' />")
        parts.append(f"<rect x='{x+24}' y='{y+145}' width='{(w-68)/2}' height='{h-180}' rx='6' ry='6' fill='{WHITE}' stroke='{item.stroke}' stroke-width='1' opacity='0.9' />")
        parts.append(f"<rect x='{x+w/2+10}' y='{y+145}' width='{(w-68)/2}' height='{h-180}' rx='6' ry='6' fill='{WHITE}' stroke='{item.stroke}' stroke-width='1' opacity='0.9' />")
        return
    if item.kind == "note":
        parts.append(f"<path d='M {x} {y} L {x+w-18} {y} L {x+w} {y+18} L {x+w} {y+h} L {x} {y+h} Z' fill='{item.fill}' stroke='{item.stroke}' stroke-width='1.1' />")
        parts.append(f"<polyline points='{x+w-18},{y} {x+w-18},{y+18} {x+w},{y+18}' fill='none' stroke='{item.stroke}' stroke-width='1.1' />")
        svg_text_block(parts, x + 16, y + 28, "", item.body, item.font_size - 2, color=MUTED)
        return
    svg_rect(parts, x, y, w, h, item.fill, item.stroke, 8, 1.4)
    centered = item.kind in {"stage"}
    if centered:
        svg_text_block(parts, x + w / 2, y + 34, item.title, item.body, item.font_size - 1, centered=True)
    else:
        svg_text_block(parts, x + 18, y + 28, item.title, item.body, item.font_size - 1)


def build_svg(page: Page) -> str:
    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{PAGE_W}' height='{PAGE_H}' viewBox='0 0 {PAGE_W} {PAGE_H}'>",
        f"<rect width='{PAGE_W}' height='{PAGE_H}' fill='{BG}' />",
        "<defs>",
    ]
    for color in sorted({item.color for item in page.edges}):
        cid = color[1:]
        parts.append(
            f"<marker id='arrow-{cid}' viewBox='0 0 10 10' refX='8' refY='5' markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
            f"<path d='M 0 0 L 10 5 L 0 10 z' fill='{color}' /></marker>"
        )
    parts.append("</defs>")
    parts.append(f"<text x='52' y='58' font-family='Microsoft YaHei, PingFang SC, sans-serif' font-size='26' font-weight='700' fill='{TEXT}'>{html.escape(page.title)}</text>")
    parts.append(f"<text x='52' y='90' font-family='Microsoft YaHei, PingFang SC, sans-serif' font-size='14' fill='{MUTED}'>{html.escape(page.subtitle)}</text>")

    shape_lookup = {s.id: s for s in page.shapes}
    for conn in page.edges:
        s = anchor(shape_lookup[conn.source], conn.source_side)
        t = anchor(shape_lookup[conn.target], conn.target_side)
        points = [s] + conn.waypoints + [t]
        d = f"M {points[0][0]} {points[0][1]}"
        for px, py in points[1:]:
            d += f" L {px} {py}"
        dash = " stroke-dasharray='10 7'" if conn.dashed else ""
        parts.append(f"<path d='{d}' fill='none' stroke='{conn.color}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'{dash} marker-end='url(#arrow-{conn.color[1:]})' />")
        if conn.label:
            mx, my = points[len(points) // 2]
            parts.append(f"<text x='{mx + 8}' y='{my - 10}' font-family='Microsoft YaHei, PingFang SC, sans-serif' font-size='15' fill='{conn.color}'>{html.escape(conn.label)}</text>")
    for item in page.shapes:
        render_shape_svg(parts, item)
    parts.append("</svg>")
    return "\n".join(parts)


def write_svg_files() -> None:
    for page in PAGES:
        (OUT_DIR / f"{page.slug}.svg").write_text(build_svg(page), encoding="utf-8")


def write_readme() -> None:
    lines = [
        "# Draw.io Vector Figures",
        "",
        "本目录包含：",
        "- 单图 `.drawio` 可编辑源文件",
        "- 单图 `.svg` 矢量导出",
        "- 多页总文件 `traceability_figures.drawio`",
        "",
        "这版重画强调 draw.io 的原生优势：",
        "- 容器 / 泳道 / 决策菱形 / 数据库存储 / 云端 / 浏览器线框图",
        "- 正交连线、分区布局、阶段式表达",
        "- 更适合论文中流程图、架构图、拓扑图、站点地图的版式",
        "",
        "文件列表：",
    ]
    for page in PAGES:
        lines.append(f"- {page.name}: `{page.slug}.drawio` / `{page.slug}.svg`")
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_drawio_files()
    write_svg_files()
    write_readme()
    print(f"Output: {OUT_DIR}")
    print(f"Master: {MASTER_FILE}")


if __name__ == "__main__":
    main()
