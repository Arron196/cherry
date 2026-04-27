from __future__ import annotations

import math
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
DOCX_PATH = ROOT / "论文——模板编辑_按规范排版_配图版_v16_自动目录可跳转.docx"
OUT_DOCX_PATH = ROOT / "论文——模板编辑_按规范排版_配图版_v16_自动目录可跳转_流程图重画版.docx"
ASSET_DIR = ROOT / "generated_figures"

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

BG = "#F6FAFD"
GRID = "#E4EEF5"
TITLE = "#13324B"
TEXT = "#294559"
MUTED = "#688199"
STROKE = "#A8BFCE"
DARK = "#203648"
WHITE = "#FFFFFF"

TEAL = "#49C3B1"
BLUE = "#7FAEF4"
INDIGO = "#6976F5"
ORANGE = "#F39A4B"
GREEN = "#4DBA76"
RED = "#EE6B67"
GOLD = "#F1C75B"
PINK = "#F5B9C2"
PURPLE = "#B59BE9"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def text_size(fnt: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    if not text:
        return 0, 0
    box = fnt.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        current = ""
        for ch in para:
            trial = ch if not current else current + ch
            if text_size(fnt, trial)[0] <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def rounded_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    *,
    fill: str = WHITE,
    outline: str = STROKE,
    radius: int = 26,
    width: int = 2,
):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    *,
    fill: str,
    fg: str = WHITE,
    pad_x: int = 18,
    pad_y: int = 9,
    fnt: ImageFont.FreeTypeFont | None = None,
) -> tuple[int, int, int, int]:
    fnt = fnt or font(20, bold=True)
    tw, th = text_size(fnt, text)
    box = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    rounded_box(draw, box, fill=fill, outline=fill, radius=(box[3] - box[1]) // 2, width=1)
    draw.text((x + pad_x, y + pad_y - 2), text, font=fnt, fill=fg)
    return box


def add_grid(draw: ImageDraw.ImageDraw, width: int, height: int):
    for x in range(0, width, 48):
        draw.line([(x, 0), (x, height)], fill=GRID, width=1)
    for y in range(0, height, 48):
        draw.line([(0, y), (width, y)], fill=GRID, width=1)


def add_header(
    draw: ImageDraw.ImageDraw,
    width: int,
    title: str,
    subtitle: str | None = None,
):
    draw.text((52, 34), title, font=font(36, bold=True), fill=TITLE)
    if subtitle:
        draw.text((52, 84), subtitle, font=font(18), fill=MUTED)
    draw.rounded_rectangle((52, 124, width - 52, 128), radius=2, fill="#DCE7EE", outline=None)


def add_footer_note(draw: ImageDraw.ImageDraw, width: int, note: str):
    box = (52, 848, width - 52, 895)
    rounded_box(draw, box, fill="#FFFFFFCC", outline="#D6E3EB", radius=16, width=1)
    draw.text((70, 862), note, font=font(16), fill=MUTED)


def draw_box_title(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title_text: str,
    *,
    color: str,
):
    x1, y1, _, _ = box
    pill(draw, x1 + 18, y1 + 16, title_text, fill=color, fnt=font(19, bold=True))


def draw_body_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    *,
    top: int = 58,
    size: int = 18,
    color: str = TEXT,
    line_gap: int = 8,
):
    x1, y1, x2, _ = box
    fnt = font(size)
    lines = wrap_text(text, fnt, x2 - x1 - 36)
    y = y1 + top
    for line in lines:
        draw.text((x1 + 18, y), line, font=fnt, fill=color)
        y += text_size(fnt, line)[1] + line_gap


def center_of(box: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    return (x1 + x2) // 2, (y1 + y2) // 2


def point_on_box(box: tuple[int, int, int, int], side: str) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    if side == "left":
        return x1, (y1 + y2) // 2
    if side == "right":
        return x2, (y1 + y2) // 2
    if side == "top":
        return (x1 + x2) // 2, y1
    return (x1 + x2) // 2, y2


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = BLUE,
    width: int = 4,
    dash: bool = False,
):
    if dash:
        draw_dashed_line(draw, start, end, color=color, width=width)
    else:
        draw.line([start, end], fill=color, width=width)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    angle = math.atan2(dy, dx)
    length = 15
    wing = 7
    p1 = (
        end[0] - length * math.cos(angle) + wing * math.sin(angle),
        end[1] - length * math.sin(angle) - wing * math.cos(angle),
    )
    p2 = (
        end[0] - length * math.cos(angle) - wing * math.sin(angle),
        end[1] - length * math.sin(angle) + wing * math.cos(angle),
    )
    draw.polygon([end, p1, p2], fill=color)


def elbow_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    via: tuple[int, int] | None = None,
    color: str = BLUE,
    width: int = 4,
    dash: bool = False,
):
    if via is None:
        via = (end[0], start[1])
    segments = [start, via, end]
    if dash:
        draw_dashed_line(draw, segments[0], segments[1], color=color, width=width)
        draw_dashed_line(draw, segments[1], segments[2], color=color, width=width)
    else:
        draw.line(segments, fill=color, width=width)
    arrow(draw, via, end, color=color, width=width)


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str,
    width: int = 3,
    dash_len: int = 12,
    gap_len: int = 8,
):
    x1, y1 = start
    x2, y2 = end
    dist = math.hypot(x2 - x1, y2 - y1)
    if dist == 0:
        return
    dx = (x2 - x1) / dist
    dy = (y2 - y1) / dist
    step = dash_len + gap_len
    count = int(dist // step) + 1
    for i in range(count):
        s = i * step
        e = min(s + dash_len, dist)
        sx = x1 + dx * s
        sy = y1 + dy * s
        ex = x1 + dx * e
        ey = y1 + dy * e
        draw.line([(sx, sy), (ex, ey)], fill=color, width=width)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, color: str = MUTED):
    draw.text(xy, text, font=font(16), fill=color)


def diamond(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str = STROKE,
):
    x1, y1, x2, y2 = box
    pts = [
        ((x1 + x2) // 2, y1),
        (x2, (y1 + y2) // 2),
        ((x1 + x2) // 2, y2),
        (x1, (y1 + y2) // 2),
    ]
    draw.polygon(pts, fill=fill, outline=outline)


def make_canvas(width: int = 1600, height: int = 920) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(image)
    add_grid(draw, width, height)
    return image, draw


def figure_3_3() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "核心数据表 ER 关系图", "围绕 events 主表组织幂等、锚定、设备、质量与审计实体")

    boxes = {
        "devices": (70, 190, 360, 330),
        "keys": (70, 360, 360, 515),
        "ingest": (430, 255, 700, 400),
        "events": (760, 205, 1110, 465),
        "submissions": (1180, 180, 1515, 335),
        "receipts": (1180, 365, 1515, 500),
        "quality": (430, 560, 700, 700),
        "alerts": (760, 560, 1035, 700),
        "audits": (1100, 560, 1375, 700),
    }
    fills = {
        "devices": "#EDF8F6",
        "keys": "#EEF3FE",
        "ingest": "#EEF5FE",
        "events": "#E9FBF6",
        "submissions": "#F2EDFF",
        "receipts": "#FFF2E8",
        "quality": "#EEF9F0",
        "alerts": "#FFF4F3",
        "audits": "#FFF8E9",
    }
    titles = {
        "devices": ("managed_devices", TEAL),
        "keys": ("managed_device_keys", BLUE),
        "ingest": ("ingest_requests", INDIGO),
        "events": ("events", GREEN),
        "submissions": ("anchor_submissions", PURPLE),
        "receipts": ("anchor_receipts", ORANGE),
        "quality": ("quality_results", GREEN),
        "alerts": ("alerts", RED),
        "audits": ("audits", GOLD),
    }
    bodies = {
        "devices": "PK id\nUNIQUE device_id\nstatus / disabled_at\n1 个设备可绑定多把历史密钥",
        "keys": "PK id\nFK device_id -> managed_devices.id\nUNIQUE key_id\nalgorithm / public_key\nstatus=active|retired",
        "ingest": "PK id\nUNIQUE idempotency_key\npayload_hash\ningest_status / retry_count\nFK event_id -> events.id",
        "events": "PK id\ndevice_id / batch_id / timestamp\nsensor_payload / signature_envelope\nUNIQUE canonical_hash\nsupply_chain_stage / created_at",
        "submissions": "PK id\nFK event_id -> events.id\ntransaction_hash\ncanonical_hash\nstatus=PENDING|FINALIZED|REORGED",
        "receipts": "PK id\nFK event_id -> events.id\nnetwork\nUNIQUE transaction_hash\nreceipt_payload / anchored_at",
        "quality": "PK id\nFK event_id -> events.id\ncheck_name\nstatus / score\n细粒度品质评估结果",
        "alerts": "PK id\nFK event_id -> events.id (nullable)\nalert_type / severity\nstatus=open|ack|resolved",
        "audits": "PK id\nFK event_id -> events.id (nullable)\nactor / action / target\nmetadata / created_at",
    }

    for key, box in boxes.items():
        rounded_box(draw, box, fill=fills[key])
        draw_box_title(draw, box, titles[key][0], color=titles[key][1])
        draw_body_text(draw, box, bodies[key], top=62, size=18)

    arrow(draw, point_on_box(boxes["devices"], "bottom"), point_on_box(boxes["keys"], "top"), color=BLUE)
    label(draw, (160, 336), "1 : N", color=BLUE)

    elbow_arrow(draw, point_on_box(boxes["ingest"], "right"), point_on_box(boxes["events"], "left"), via=(730, 327), color=INDIGO)
    label(draw, (715, 296), "N : 1", color=INDIGO)

    elbow_arrow(draw, point_on_box(boxes["events"], "right"), point_on_box(boxes["submissions"], "left"), via=(1140, 275), color=PURPLE)
    elbow_arrow(draw, point_on_box(boxes["events"], "right"), point_on_box(boxes["receipts"], "left"), via=(1140, 432), color=ORANGE)
    elbow_arrow(draw, point_on_box(boxes["events"], "bottom"), point_on_box(boxes["quality"], "top"), via=(565, 515), color=GREEN)
    elbow_arrow(draw, point_on_box(boxes["events"], "bottom"), point_on_box(boxes["alerts"], "top"), via=(898, 515), color=RED)
    elbow_arrow(draw, point_on_box(boxes["events"], "bottom"), point_on_box(boxes["audits"], "top"), via=(1235, 515), color=GOLD)

    elbow_arrow(
        draw,
        point_on_box(boxes["devices"], "right"),
        point_on_box(boxes["events"], "top"),
        via=(610, 158),
        color=TEAL,
        dash=True,
    )
    label(draw, (515, 140), "逻辑关联: events.device_id -> managed_devices.device_id", color=TEAL)
    add_footer_note(draw, image.width, "图中突出 9 张核心表及其主外键关系；events.canonical_hash 与 ingest_requests.idempotency_key 分别承担内容唯一性与请求幂等控制。")
    return image


def figure_3_5() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "系统安全架构图", "认证、授权、设备密钥管理与审计闭环")

    left = (70, 190, 315, 675)
    gateway = (365, 190, 660, 675)
    service = (715, 190, 1045, 675)
    storage = (1100, 190, 1520, 675)
    zones = [
        (left, "#EDF8F6", "访问主体", TEAL),
        (gateway, "#EEF4FE", "接入与认证", BLUE),
        (service, "#EEF8F1", "核心服务", GREEN),
        (storage, "#FFF5EC", "数据与存证", ORANGE),
    ]
    for box, fill, name, color in zones:
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, name, color=color)

    draw_body_text(draw, left, "管理员\n监管员\n消费者\n边缘设备节点\nATECC608A 私钥硬件保护", top=78, size=22)
    draw_body_text(draw, gateway, "HTTPS / TLS\nJWT HS256 验签\nexp / iss / roles 校验\nRBAC Depends 统一拦截\nProblem Details 错误返回", top=78, size=21)
    draw_body_text(draw, service, "Ingest API\n公开 Trace API\nAdmin 设备管理\nAnchoring / Alerts\n验证服务优先查 DB，兼容回退 env key", top=78, size=21)
    draw_body_text(draw, storage, "PostgreSQL\nmanaged_devices / keys\naudits / alerts\nanchor_submissions / receipts\nEVM / Mock 锚定适配器", top=78, size=21)

    arrow(draw, point_on_box(left, "right"), point_on_box(gateway, "left"), color=TEAL)
    arrow(draw, point_on_box(gateway, "right"), point_on_box(service, "left"), color=BLUE)
    arrow(draw, point_on_box(service, "right"), point_on_box(storage, "left"), color=GREEN)

    control1 = (160, 725, 465, 815)
    control2 = (515, 725, 845, 815)
    control3 = (895, 725, 1450, 815)
    for box, fill in [(control1, "#FFFFFFD9"), (control2, "#FFFFFFD9"), (control3, "#FFFFFFD9")]:
        rounded_box(draw, box, fill=fill, outline="#D3E0E8", radius=20, width=1)
    draw.text((180, 748), "JWT 声明: sub / roles / iss / exp", font=font(20, bold=True), fill=TITLE)
    draw.text((180, 782), "常时比较防时序攻击", font=font(18), fill=TEXT)
    draw.text((535, 748), "RBAC: admin / operator / regulator", font=font(20, bold=True), fill=TITLE)
    draw.text((535, 782), "接口按角色精确放行", font=font(18), fill=TEXT)
    draw.text((915, 748), "密钥管理: 一对一绑定 + 轮换 + 禁用保护 + 审计记录", font=font(20, bold=True), fill=TITLE)
    draw.text((915, 782), "managed_device_keys 优先；未注册历史设备才回退 INGEST_SIGNING_KEYS", font=font(18), fill=TEXT)
    add_footer_note(draw, image.width, "身份认证、授权、设备密钥治理和链上锚定日志共同构成可信边界；任何禁用设备都会在接入层被直接拒绝。")
    return image


def figure_4_1() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "STM32H743 最小系统原理框图", "围绕主控的供电、时钟、复位、启动与调试接口")

    mcu = (560, 210, 1040, 610)
    rounded_box(draw, mcu, fill="#EEF5FE")
    draw_box_title(draw, mcu, "STM32H743VIT6", color=BLUE)
    draw_body_text(draw, mcu, "LQFP-100\n480 MHz Cortex-M7\n3.3V 单电源\nVDD / VDDA 分域\n外设: I2C / UART / SPI / HASH", top=90, size=26)

    power = (95, 220, 420, 360)
    xtal = (610, 140, 995, 200)
    reset = (110, 420, 420, 575)
    swd = (1140, 225, 1475, 375)
    bus = (1115, 455, 1490, 605)
    for box, fill, title_text, color in [
        (power, "#EEF9F0", "电源去耦", GREEN),
        (xtal, "#FFF6E9", "8 MHz 外部晶振", GOLD),
        (reset, "#FFF3F2", "复位 / BOOT0", RED),
        (swd, "#EEF4FE", "SWD 调试接口", BLUE),
        (bus, "#EDF8F6", "外设总线引出", TEAL),
    ]:
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, title_text, color=color)

    draw_body_text(draw, power, "5V 输入 -> AMS1117-3.3\nVDD / VDDA 各配 100nF + 10uF\nVDDA 侧增加 2.2uH + 10uF LC 滤波", top=62, size=20)
    draw_body_text(draw, xtal, "HSE 8 MHz + 22pF 负载电容\n晶振区域远离高速线，外壳接地", top=18, size=18)
    draw_body_text(draw, reset, "NRST: 100nF 滤波 + 可选按键\nBOOT0: 10k 下拉至 GND\n正常启动从 Flash 运行", top=62, size=20)
    draw_body_text(draw, swd, "SWDIO / SWDCLK / GND\n2.54 mm 排针\nST-Link 在线调试与烧录", top=62, size=20)
    draw_body_text(draw, bus, "I2C1: SHT31 + ATECC608A\nUSART1/2: 传感器 / Wi-Fi\nSPI1: SX1278\nHASH: SHA-256 摘要加速", top=62, size=20)

    arrow(draw, point_on_box(power, "right"), point_on_box(mcu, "left"), color=GREEN)
    arrow(draw, point_on_box(xtal, "bottom"), point_on_box(mcu, "top"), color=GOLD)
    arrow(draw, point_on_box(reset, "right"), point_on_box(mcu, "left"), color=RED)
    arrow(draw, point_on_box(mcu, "right"), point_on_box(swd, "left"), color=BLUE)
    arrow(draw, point_on_box(mcu, "right"), point_on_box(bus, "left"), color=TEAL)
    add_footer_note(draw, image.width, "该图按论文描述重构最小系统组成关系，用于版式展示；如需与 PCB 电气细节一一对应，应继续导出 CAD 原理图。")
    return image


def figure_4_2() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "多传感器接口与总线连接图", "I2C / UART / SPI 多总线协同采集")

    mcu = (610, 210, 1000, 590)
    rounded_box(draw, mcu, fill="#EEF5FE")
    draw_box_title(draw, mcu, "STM32H743", color=BLUE)
    draw_body_text(draw, mcu, "I2C1: PB8 / PB9\nI2C2: 预留振动传感器\nUSART1: MH-Z19B\nUSART2: ESP8266\nSPI1: SX1278\nHASH: 摘要计算", top=88, size=24)

    sht = (90, 180, 385, 305)
    atecc = (90, 335, 385, 460)
    mhz = (95, 500, 385, 655)
    esp = (1120, 200, 1450, 340)
    lora = (1120, 395, 1450, 570)
    note = (1120, 605, 1480, 745)
    for box, fill, title_text, color in [
        (sht, "#EDF8F6", "SHT31 温湿度", TEAL),
        (atecc, "#F1EDFE", "ATECC608A 安全芯片", PURPLE),
        (mhz, "#FFF6EA", "MH-Z19B CO₂", ORANGE),
        (esp, "#EEF4FE", "ESP8266 Wi-Fi", BLUE),
        (lora, "#EEF9F0", "SX1278 LoRa", GREEN),
        (note, "#FFFFFFD9", "总线要点", DARK),
    ]:
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, title_text, color=color)

    draw_body_text(draw, sht, "3.3V 供电\nI2C1 地址 0x44\n公共 4.7k 上拉\n读取 6 字节并校验 CRC", top=58, size=20)
    draw_body_text(draw, atecc, "与 SHT31 共用 I2C1\n地址 0x60\nNever-Read 私钥槽\n完成 ECDSA 签名", top=58, size=20)
    draw_body_text(draw, mhz, "5V 供电\nUSART1 9600 8N1\n响应帧 9 字节\n预热 3 分钟后参与评分", top=58, size=20)
    draw_body_text(draw, esp, "USART2 115200\nAT 指令建立 HTTPS\n证书指纹固定\n主上传通道", top=58, size=20)
    draw_body_text(draw, lora, "SPI1 + DIO0 中断\n433 MHz / SF7 / 125 kHz\n大于 255B 载荷时分片\nWi-Fi 失败后接管上传", top=58, size=20)
    draw_body_text(draw, note, "I2C1 解决地址共存\nUART 直接 3.3V 连接\nSX1278 额外引出 NSS/RESET/DIO0", top=58, size=19)

    arrow(draw, point_on_box(sht, "right"), point_on_box(mcu, "left"), color=TEAL)
    arrow(draw, point_on_box(atecc, "right"), point_on_box(mcu, "left"), color=PURPLE)
    arrow(draw, point_on_box(mhz, "right"), point_on_box(mcu, "left"), color=ORANGE)
    arrow(draw, point_on_box(mcu, "right"), point_on_box(esp, "left"), color=BLUE)
    arrow(draw, point_on_box(mcu, "right"), point_on_box(lora, "left"), color=GREEN)
    label(draw, (430, 242), "I2C1 @ 400kHz", color=TEAL)
    label(draw, (432, 395), "I2C1 / 安全签名", color=PURPLE)
    label(draw, (430, 572), "USART1 @ 9600", color=ORANGE)
    label(draw, (1018, 246), "USART2 @ 115200", color=BLUE)
    label(draw, (1038, 478), "SPI1 + GPIO", color=GREEN)
    add_footer_note(draw, image.width, "本图按论文接口描述整理为总线连接示意，突出各外设与主控之间的电压域、协议类型与关键配置。")
    return image


def figure_4_3() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "ATECC608A 连接与签名流程图", "从数据帧构造到 DER 编码上传的硬件签名链路")

    slot = (70, 185, 425, 525)
    flow = (495, 185, 1530, 525)
    note = (120, 595, 1480, 775)
    rounded_box(draw, slot, fill="#F2EDFF")
    rounded_box(draw, flow, fill="#EEF6FE")
    rounded_box(draw, note, fill="#FFFFFFD9", outline="#D3E0E8", radius=18, width=1)
    draw_box_title(draw, slot, "ATECC608A 槽位配置", color=PURPLE)
    draw_box_title(draw, flow, "设备端签名主流程", color=BLUE)
    draw_body_text(draw, slot, "Slot 0: ECDSA P-256 私钥\nNever-Read，仅允许 Sign\nSlot 1~3: 预留\nSlot 4~7: 证书哈希 / 设备标识\nConfiguration Lock + Data Lock", top=62, size=21)

    step_boxes = [
        ((535, 250, 715, 420), TEAL, "1 数据帧构造", "SensorTask\n采集温湿度/CO₂/振动\n组装 JSON"),
        ((760, 250, 940, 420), BLUE, "2 摘要计算", "SignTask\n规范化序列化\nHASH-SHA256"),
        ((985, 250, 1165, 420), PURPLE, "3 ATECC 签名", "Wakeup -> Sign(0x41)\n等待 tEXEC\n读回 64B (r,s)"),
        ((1210, 250, 1390, 420), ORANGE, "4 DER 编码", "原始 (r,s)\n转 ASN.1 DER\n得到 70~72B"),
        ((1435, 250, 1510, 420), GREEN, "5", "上传"),
    ]
    for box, fill, title_text, body in step_boxes:
        rounded_box(draw, box, fill="#FFFFFF", outline="#D3E4ED", radius=20, width=2)
        pill(draw, box[0] + 16, box[1] + 16, title_text, fill=fill, fnt=font(19, bold=True))
        draw_body_text(draw, box, body, top=64, size=18)
    for i in range(len(step_boxes) - 1):
        arrow(
            draw,
            point_on_box(step_boxes[i][0], "right"),
            point_on_box(step_boxes[i + 1][0], "left"),
            color=BLUE,
        )

    draw.text((150, 630), "I2C 时序要点", font=font(22, bold=True), fill=TITLE)
    draw.text((150, 668), "唤醒序列 -> 命令帧(Length/OpCode/Param/Data/CRC16) -> 等待执行 -> 读响应 -> Sleep", font=font(20), fill=TEXT)
    draw.text((150, 708), "Sign 命令参数: OpCode=0x41, Param1=0x80(外部摘要), Param2=0x00(Slot 0)", font=font(20), fill=TEXT)
    draw.text((150, 748), "典型签名耗时约 7 ms；完整采集至上传约 15~25 ms", font=font(20), fill=TEXT)
    add_footer_note(draw, image.width, "ATECC608A 负责私钥不可读的硬件签名，SignTask 只接收 32 字节摘要，不直接接触私钥材料。")
    return image


def figure_4_4() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "Wi-Fi / LoRa 通信组网图", "双通道上行与后端聚合")

    node = (95, 300, 410, 525)
    wifi = (525, 185, 800, 330)
    gateway = (870, 420, 1180, 560)
    lora = (520, 485, 805, 650)
    backend = (1240, 250, 1510, 505)
    fallback = (520, 710, 1120, 790)

    for box, fill, title_text, color, body in [
        (node, "#EEF5FE", "边缘节点", BLUE, "STM32H743\nSHT31 / MH-Z19B / ATECC608A\nCommTask 统一出站"),
        (wifi, "#EDF8F6", "ESP8266 + Wi-Fi", TEAL, "AT+CWJAP 连接热点\nAT+CIPSTART 建 HTTPS\nCertificate Pinning"),
        (lora, "#EEF9F0", "SX1278 + LoRa", GREEN, "433 MHz\n超过 255B 时分 2 包\n网关重组后转发"),
        (gateway, "#FFF5EB", "LoRa 网关", ORANGE, "接收分片\n按序重组\n转 HTTP 到后端"),
        (backend, "#F2EDFF", "后端服务", PURPLE, "Ingest API\nJWT / 幂等校验\n数据库 + 锚定引擎"),
    ]:
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, title_text, color=color)
        draw_body_text(draw, box, body, top=62, size=21)

    rounded_box(draw, fallback, fill="#FFFFFFD9", outline="#D3E0E8", radius=16, width=1)
    draw.text((550, 736), "切换策略: CommTask 优先走 Wi-Fi；若 30 秒内连接失败或 ACK 超时，则自动切换 LoRa 备用通道。", font=font(22), fill=TITLE)

    arrow(draw, point_on_box(node, "right"), point_on_box(wifi, "left"), color=TEAL)
    arrow(draw, point_on_box(node, "right"), point_on_box(lora, "left"), color=GREEN)
    arrow(draw, point_on_box(wifi, "right"), point_on_box(backend, "left"), color=BLUE)
    arrow(draw, point_on_box(lora, "right"), point_on_box(gateway, "left"), color=GREEN)
    arrow(draw, point_on_box(gateway, "right"), point_on_box(backend, "left"), color=ORANGE)
    label(draw, (430, 318), "主链路", color=TEAL)
    label(draw, (430, 560), "备用链路", color=GREEN)
    add_footer_note(draw, image.width, "Wi-Fi 适用于仓储 / 分拣中心等固定网络场景；LoRa 适用于田间或山区运输等弱网环境。")
    return image


def figure_4_5() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "电源管理原理框图", "太阳能 + 锂电池混合供电与低功耗策略")

    solar = (80, 250, 330, 410)
    battery = (80, 465, 330, 625)
    mppt = (410, 335, 655, 535)
    rail5 = (750, 235, 980, 355)
    rail3 = (750, 430, 980, 560)
    loads = (1080, 215, 1495, 610)
    lowp = (170, 700, 1435, 790)
    for box, fill, title_text, color, body in [
        (solar, "#FFF7E9", "10W 太阳能板", GOLD, "有光照时为系统补能"),
        (battery, "#FFF3F2", "18650 3.7V / 3000mAh", RED, "夜间与阴天主供电"),
        (mppt, "#EEF9F0", "MPPT 充电控制器", GREEN, "太阳能充电管理\n兼顾充放电保护"),
        (rail5, "#EEF4FE", "5V 电源轨", BLUE, "供给 MH-Z19B 等 5V 负载"),
        (rail3, "#EDF8F6", "AMS1117-3.3 输出", TEAL, "为 MCU / 传感器 / 无线模组供电"),
        (loads, "#F2EDFF", "系统负载", PURPLE, "STM32H743\nSHT31 / ATECC608A\nESP8266 / SX1278\n模拟电源 VDDA 经 LC 滤波"),
    ]:
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, title_text, color=color)
        draw_body_text(draw, box, body, top=62, size=21)

    rounded_box(draw, lowp, fill="#FFFFFFD9", outline="#D3E0E8", radius=18, width=1)
    draw.text((205, 725), "低功耗策略: FreeRTOS Tickless Idle + STM32 Stop 模式 + 外设时钟门控 + ESP8266 深度睡眠 + SX1278 休眠待命", font=font(22), fill=TITLE)

    arrow(draw, point_on_box(solar, "right"), point_on_box(mppt, "left"), color=GOLD)
    arrow(draw, point_on_box(battery, "right"), point_on_box(mppt, "left"), color=RED)
    arrow(draw, point_on_box(mppt, "right"), point_on_box(rail5, "left"), color=BLUE)
    arrow(draw, point_on_box(mppt, "right"), point_on_box(rail3, "left"), color=TEAL)
    arrow(draw, point_on_box(rail5, "right"), (1080, 285), color=BLUE)
    arrow(draw, point_on_box(rail3, "right"), (1080, 500), color=TEAL)
    add_footer_note(draw, image.width, "论文原文给出的是电源架构与功耗策略，本图采用结构化框图表达，适合论文版式展示。")
    return image


def figure_5_1() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "FreeRTOS 任务调度与数据通路图", "初始化后由三任务 + 两队列构成稳态流水线")

    init = (70, 210, 365, 520)
    sensor = (455, 240, 695, 445)
    queue1 = (735, 285, 860, 400)
    sign = (915, 240, 1155, 445)
    queue2 = (1195, 285, 1320, 400)
    comm = (1365, 240, 1525, 445)
    bottom = (210, 610, 1410, 785)
    for box, fill, title_text, color, body in [
        (init, "#EEF5FE", "系统初始化", BLUE, "HAL_Init\nSystemClock_Config\nI2C/UART/SPI/HASH Init\n创建 3 个任务 + 2 个队列\nvTaskStartScheduler"),
        (sensor, "#EDF8F6", "SensorTask", TEAL, "每 30s 采集一帧\nSHT31 / 振动 / CO₂\n上电前 3 分钟 CO₂ 标记 -1"),
        (queue1, "#FFF7E9", "sensorQueue", GOLD, "深度 4"),
        (sign, "#F2EDFF", "SignTask", PURPLE, "规范化 -> SHA-256\nATECC608A Sign\nDER 编码\n构建 signature_envelope"),
        (queue2, "#FFF3F2", "signedQueue", RED, "深度 4"),
        (comm, "#EEF9F0", "CommTask", GREEN, "优先 Wi-Fi HTTPS\n失败后 LoRa 分片上传"),
    ]:
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, title_text, color=color)
        draw_body_text(draw, box, body, top=62, size=20 if box not in (queue1, queue2) else 24)

    rounded_box(draw, bottom, fill="#FFFFFFD9", outline="#D3E0E8", radius=18, width=1)
    draw.text((245, 640), "稳态数据流", font=font(26, bold=True), fill=TITLE)
    draw.text((245, 688), "采集帧 frame -> sensorQueue -> 规范化/签名 -> signedQueue -> SerializeJSON -> Wi-Fi 或 LoRa 出站", font=font(22), fill=TEXT)
    draw.text((245, 732), "调度特征: 任务之间通过队列解耦；空闲期可进入 Tickless Idle / Stop 模式节省功耗。", font=font(22), fill=TEXT)

    arrow(draw, point_on_box(init, "right"), point_on_box(sensor, "left"), color=BLUE)
    arrow(draw, point_on_box(sensor, "right"), point_on_box(queue1, "left"), color=TEAL)
    arrow(draw, point_on_box(queue1, "right"), point_on_box(sign, "left"), color=GOLD)
    arrow(draw, point_on_box(sign, "right"), point_on_box(queue2, "left"), color=PURPLE)
    arrow(draw, point_on_box(queue2, "right"), point_on_box(comm, "left"), color=RED)
    add_footer_note(draw, image.width, "该图对应论文中的初始化顺序与三任务伪代码，实现上由消息队列隔离采集、签名和通信三段工作。")
    return image


def figure_5_4() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "签名验证流程图", "入库前对签名、密钥来源与设备状态进行分层校验")

    boxes = {
        "start": (650, 160, 950, 230),
        "extract": (585, 270, 1015, 360),
        "db": (565, 400, 1035, 490),
        "fallback": (1085, 400, 1450, 490),
        "hash": (585, 540, 1015, 630),
        "verify": (585, 680, 1015, 770),
        "ok": (1045, 690, 1365, 760),
        "fail": (200, 690, 520, 760),
    }
    rounded_box(draw, boxes["start"], fill="#EDF8F6")
    pill(draw, 740, 178, "开始", fill=TEAL, fnt=font(20, bold=True))

    for key, fill, title_text, color, body in [
        ("extract", "#EEF5FE", "1 提取信封", BLUE, "algorithm / key_id / signature / public_key"),
        ("db", "#F2EDFF", "2 查询 managed_device_keys", PURPLE, "校验 device_id + key_id\n确认设备未禁用\n算法必须匹配"),
        ("fallback", "#FFF7E9", "兼容回退", GOLD, "仅当设备未注册时\n回退 INGEST_SIGNING_KEYS\n只支持 HMAC"),
        ("hash", "#EEF9F0", "3 重新计算 canonical_hash", GREEN, "去除签名字段后执行规范化算法"),
        ("verify", "#FFF3F2", "4 执行签名验证", RED, "ECDSA-P256 或 HMAC-SHA256"),
        ("ok", "#EEF9F0", "通过", GREEN, "进入后续入库 / 幂等处理"),
        ("fail", "#FFF3F2", "拒绝", RED, "401 Unauthorized"),
    ]:
        box = boxes[key]
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, title_text, color=color)
        draw_body_text(draw, box, body, top=56, size=20)

    decision1 = (1065, 532, 1260, 638)
    decision2 = (305, 532, 500, 638)
    decision3 = (585, 800, 1015, 860)
    diamond(draw, decision1, fill="#FFF7E9")
    diamond(draw, decision2, fill="#FFF3F2")
    rounded_box(draw, decision3, fill="#FFFFFFD9", outline="#D3E0E8", radius=16, width=1)
    draw.text((1105, 570), "DB 中有\n活动密钥?", font=font(20, bold=True), fill=TITLE)
    draw.text((343, 570), "签名/\nMAC 有效?", font=font(20, bold=True), fill=TITLE)
    draw.text((615, 816), "要点: 已注册设备若密钥不匹配或设备被禁用，直接拒绝，不走回退分支。", font=font(18), fill=MUTED)

    arrow(draw, point_on_box(boxes["start"], "bottom"), point_on_box(boxes["extract"], "top"), color=TEAL)
    arrow(draw, point_on_box(boxes["extract"], "bottom"), point_on_box(boxes["db"], "top"), color=BLUE)
    arrow(draw, point_on_box(boxes["db"], "right"), point_on_box(decision1, "left"), color=PURPLE)
    arrow(draw, point_on_box(decision1, "right"), point_on_box(boxes["fallback"], "left"), color=GOLD)
    arrow(draw, point_on_box(decision1, "bottom"), point_on_box(boxes["hash"], "right"), color=GREEN)
    label(draw, (1155, 506), "否", color=GOLD)
    label(draw, (1130, 645), "是", color=GREEN)
    arrow(draw, point_on_box(boxes["fallback"], "left"), point_on_box(boxes["hash"], "right"), color=GOLD)
    arrow(draw, point_on_box(boxes["hash"], "bottom"), point_on_box(boxes["verify"], "top"), color=GREEN)
    arrow(draw, point_on_box(boxes["verify"], "left"), point_on_box(decision2, "right"), color=RED)
    arrow(draw, point_on_box(decision2, "left"), point_on_box(boxes["fail"], "right"), color=RED)
    arrow(draw, point_on_box(decision2, "right"), point_on_box(boxes["ok"], "left"), color=GREEN)
    label(draw, (240, 648), "否", color=RED)
    label(draw, (520, 648), "是", color=GREEN)
    return image


def figure_5_6() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "四阶段 Rollout 策略图", "从 rollback_safe 到 full 的渐进式上线与自动回滚")

    stages = [
        ((75, 220, 360, 410), TEAL, "rollback_safe", "100% Mock\n零 Gas\n默认模式"),
        ((435, 220, 720, 410), BLUE, "shadow", "主路径仍走 Mock\n副本并发发往 EVM\n只看日志与指标"),
        ((795, 220, 1080, 410), ORANGE, "canary", "5% 真流量走 EVM\n95% 继续走 Mock\n风险面受控"),
        ((1155, 220, 1440, 410), GREEN, "full", "100% EVM\nMock 退出主路径"),
    ]
    for box, color, title_text, body in stages:
        rounded_box(draw, box, fill="#FFFFFF", outline="#D3E4ED", radius=24, width=2)
        pill(draw, box[0] + 22, box[1] + 18, title_text, fill=color, fnt=font(22, bold=True))
        draw_body_text(draw, box, body, top=78, size=24)
    for i in range(len(stages) - 1):
        arrow(draw, point_on_box(stages[i][0], "right"), point_on_box(stages[i + 1][0], "left"), color=BLUE)

    monitor = (300, 520, 1220, 700)
    rollback = (1030, 730, 1465, 820)
    rounded_box(draw, monitor, fill="#FFFFFFD9", outline="#D3E0E8", radius=18, width=1)
    rounded_box(draw, rollback, fill="#FFF3F2", outline="#F0C4C1", radius=18, width=1)
    draw.text((330, 550), "canary 期持续监控 SLO", font=font(28, bold=True), fill=TITLE)
    draw.text((330, 600), "成功率 >= 99%    死信率 <= 0.5%    P95 完成时间 <= 120 s", font=font(24), fill=TEXT)
    draw.text((330, 645), "若任一指标连续违规超过 600 s，则 Rollout 控制器自动降级至 rollback_safe。", font=font(22), fill=TEXT)
    draw.text((1060, 760), "自动回滚到 rollback_safe", font=font(24, bold=True), fill=RED)

    arrow(draw, point_on_box(stages[2][0], "bottom"), point_on_box(monitor, "top"), color=ORANGE)
    elbow_arrow(draw, (1220, 700), (1160, 730), via=(1280, 730), color=RED)
    elbow_arrow(draw, (1160, 730), (218, 410), via=(218, 730), color=RED)
    add_footer_note(draw, image.width, "阶段切换由 ANCHOR_EVM_ROLLOUT_MODE 及监控指标共同驱动；canary 使用确定性哈希采样保证分流可复现。")
    return image


def figure_5_7() -> Image.Image:
    image, draw = make_canvas()
    add_header(draw, image.width, "前端页面结构与关键界面示意图", "Next.js App Router 下的登录、管理端与公开溯源页")

    route = (70, 185, 450, 735)
    dashboard = (530, 185, 980, 455)
    trace = (1025, 185, 1495, 455)
    login = (655, 515, 1365, 760)
    for box, fill, title_text, color in [
        (route, "#EEF5FE", "应用路由结构", BLUE),
        (dashboard, "#EDF8F6", "管理端 Dashboard", TEAL),
        (trace, "#EEF9F0", "公开 Trace 页面", GREEN),
        (login, "#FFF6EA", "登录页", ORANGE),
    ]:
        rounded_box(draw, box, fill=fill)
        draw_box_title(draw, box, title_text, color=color)

    draw_body_text(draw, route, "/\n├─ /login\n├─ /(dashboard)\n│   ├─ /\n│   ├─ /batches\n│   ├─ /events\n│   ├─ /alerts\n│   ├─ /admin/anchoring\n│   ├─ /admin/devices\n│   └─ /api-tools\n└─ /trace/public/[batchId]", top=70, size=22)

    draw_body_text(draw, dashboard, "卡片概览: 总批次 / 活跃设备 / 平均品质 / 告警\n图表: 温度趋势 / 品质分布 / 阶段分布\n业务入口: 批次、事件、告警、设备、锚定任务", top=72, size=20)
    dash_mini = [
        (560, 320, 655, 390, "#E6FBF4"),
        (675, 320, 770, 390, "#EEF4FE"),
        (790, 320, 885, 390, "#FFF7E9"),
        (905, 320, 950, 390, "#FFF3F2"),
    ]
    for x1, y1, x2, y2, fill in dash_mini:
        rounded_box(draw, (x1, y1, x2, y2), fill=fill, outline="#D8E5EC", radius=14, width=1)

    draw_body_text(draw, trace, "首屏: 批次信息 + 品质等级徽章 + 锚定状态\n中段: 供应链时间线\n下段: 温度/湿度/CO₂/振动曲线\n附加: 复制原始数据并自行验 hash", top=72, size=20)
    rounded_box(draw, (1060, 312, 1160, 408), fill="#FFFFFF", outline="#D7E5EB", radius=10, width=1)
    draw.text((1185, 330), "QR / 批次概览", font=font(20, bold=True), fill=TITLE)
    draw.text((1185, 365), "时间线 + 传感器图表", font=font(18), fill=TEXT)

    draw_body_text(draw, login, "左侧品牌介绍与能力摘要\n右侧账号密码表单\n演示账号说明\n成功后跳转控制台首页", top=72, size=22)
    rounded_box(draw, (1195, 560, 1325, 710), fill="#FFFFFF", outline="#D7E5EB", radius=14, width=1)
    draw.text((1218, 590), "用户名", font=font(18), fill=MUTED)
    draw.rounded_rectangle((1218, 618, 1300, 644), radius=7, outline="#D0DCE5", fill="#F8FBFD")
    draw.text((1218, 660), "密码", font=font(18), fill=MUTED)
    draw.rounded_rectangle((1218, 688, 1300, 714), radius=7, outline="#D0DCE5", fill="#F8FBFD")

    add_footer_note(draw, image.width, "路由结构与页面重点均来自当前前端代码目录，图中保留了论文描述中的三类关键界面：登录、管理控制台、公开溯源页。")
    return image


FIGURES = {
    "/word/media/image3.png": figure_3_3,
    "/word/media/image5.png": figure_3_5,
    "/word/media/image6.png": figure_4_1,
    "/word/media/image7.png": figure_4_2,
    "/word/media/image8.png": figure_4_3,
    "/word/media/image9.png": figure_4_4,
    "/word/media/image10.png": figure_4_5,
    "/word/media/image11.png": figure_5_1,
    "/word/media/image14.png": figure_5_4,
    "/word/media/image16.png": figure_5_6,
    "/word/media/image17.png": figure_5_7,
}


def save_figure_assets() -> dict[str, bytes]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    blobs: dict[str, bytes] = {}
    for media_path, builder in FIGURES.items():
        image = builder().convert("RGB")
        out_path = ASSET_DIR / Path(media_path).name
        image.save(out_path, format="PNG", optimize=True)
        blobs[media_path] = out_path.read_bytes()
    return blobs


def replace_docx_images(image_blobs: dict[str, bytes]):
    doc = Document(DOCX_PATH)
    replaced: set[str] = set()
    for rel in doc.part.rels.values():
        target = getattr(rel, "_target", None)
        partname = str(getattr(target, "partname", ""))
        if partname in image_blobs:
            target._blob = image_blobs[partname]
            replaced.add(partname)
    missing = sorted(set(image_blobs) - replaced)
    if missing:
        raise RuntimeError(f"未在 docx 中找到这些图片槽位: {missing}")
    doc.save(OUT_DOCX_PATH)


def main():
    if not DOCX_PATH.exists():
        raise FileNotFoundError(DOCX_PATH)
    blobs = save_figure_assets()
    replace_docx_images(blobs)
    print(f"Generated assets: {ASSET_DIR}")
    print(f"Output docx: {OUT_DOCX_PATH}")


if __name__ == "__main__":
    main()
