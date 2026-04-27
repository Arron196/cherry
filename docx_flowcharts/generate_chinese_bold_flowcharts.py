from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


OUTPUT_DIR = Path(r"C:\Users\benja\Dropbox\毕业论文\流程图_微软雅黑加粗")
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"


PALETTE = {
    "bg": "#ffffff",
    "line": "#3f4a58",
    "text": "#172033",
    "start": "#dff4e8",
    "process": "#eaf2ff",
    "queue": "#efeaff",
    "decision": "#fff3c7",
    "error": "#ffe5e5",
    "green": "#4c9b73",
    "blue": "#5f86d6",
    "purple": "#866ec7",
    "yellow": "#c49d2f",
    "red": "#d46666",
}


@dataclass
class Node:
    x: int
    y: int
    w: int
    h: int
    shape: str
    text: str

    @property
    def left(self) -> int:
        return self.x

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def top(self) -> int:
        return self.y

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


class Chart:
    def __init__(self, width: int = 1800, height: int = 3200) -> None:
        self.width = width
        self.height = height
        self.image = Image.new("RGB", (width, height), PALETTE["bg"])
        self.draw = ImageDraw.Draw(self.image)
        self.font = ImageFont.truetype(FONT_BOLD, 44)
        self.small_font = ImageFont.truetype(FONT_BOLD, 34)
        self.max_y = 0

    def _wrap(self, text: str, max_width: int, font: ImageFont.FreeTypeFont | None = None) -> list[str]:
        font = font or self.font
        lines: list[str] = []
        current = ""
        for char in text:
            if char == "\n":
                lines.append(current)
                current = ""
                continue
            trial = current + char
            if self.draw.textlength(trial, font=font) <= max_width or not current:
                current = trial
            else:
                lines.append(current.rstrip())
                current = char.lstrip()
        if current:
            lines.append(current.rstrip())
        return lines

    def _draw_text_centered(self, box: Node, max_width: int) -> None:
        lines = self._wrap(box.text, max_width)
        bbox = self.draw.textbbox((0, 0), "测", font=self.font)
        line_h = bbox[3] - bbox[1] + 16
        total_h = line_h * len(lines)
        y = box.cy - total_h // 2 - 4
        for line in lines:
            w = self.draw.textlength(line, font=self.font)
            self.draw.text((box.cx - w / 2, y), line, font=self.font, fill=PALETTE["text"])
            y += line_h

    def node(self, x: int, y: int, w: int, h: int, text: str, shape: str = "process") -> Node:
        node = Node(x, y, w, h, shape, text)
        fill = {
            "start": PALETTE["start"],
            "process": PALETTE["process"],
            "queue": PALETTE["queue"],
            "decision": PALETTE["decision"],
            "error": PALETTE["error"],
        }[shape]
        stroke = {
            "start": PALETTE["green"],
            "process": PALETTE["blue"],
            "queue": PALETTE["purple"],
            "decision": PALETTE["yellow"],
            "error": PALETTE["red"],
        }[shape]
        if shape == "decision":
            points = [(node.cx, node.top), (node.right, node.cy), (node.cx, node.bottom), (node.left, node.cy)]
            self.draw.polygon(points, fill=fill, outline=stroke)
            self.draw.line(points + [points[0]], fill=stroke, width=4, joint="curve")
            text_width = int(w * 0.58)
        elif shape == "start":
            self.draw.rounded_rectangle([node.left, node.top, node.right, node.bottom], radius=h // 2, fill=fill, outline=stroke, width=4)
            text_width = w - 80
        else:
            self.draw.rounded_rectangle([node.left, node.top, node.right, node.bottom], radius=24, fill=fill, outline=stroke, width=4)
            text_width = w - 80
        self._draw_text_centered(node, text_width)
        self.max_y = max(self.max_y, node.bottom)
        return node

    def _arrowhead(self, x1: int, y1: int, x2: int, y2: int) -> None:
        angle = math.atan2(y2 - y1, x2 - x1)
        length = 24
        spread = math.radians(26)
        p1 = (x2 - length * math.cos(angle - spread), y2 - length * math.sin(angle - spread))
        p2 = (x2 - length * math.cos(angle + spread), y2 - length * math.sin(angle + spread))
        self.draw.polygon([(x2, y2), p1, p2], fill=PALETTE["line"])

    def arrow(self, points: Iterable[tuple[int, int]], label: str | None = None, offset: tuple[int, int] = (0, 0)) -> None:
        pts = list(points)
        self.draw.line(pts, fill=PALETTE["line"], width=5, joint="curve")
        self._arrowhead(*pts[-2], *pts[-1])
        if label:
            x, y = pts[len(pts) // 2]
            x += offset[0]
            y += offset[1]
            box = self.draw.textbbox((x, y), label, font=self.small_font)
            self.draw.rounded_rectangle([box[0] - 14, box[1] - 7, box[2] + 14, box[3] + 7], radius=12, fill="#ffffff", outline="#d5ddea", width=2)
            self.draw.text((x, y), label, font=self.small_font, fill=PALETTE["text"])

    def down(self, a: Node, b: Node, label: str | None = None) -> None:
        self.arrow([(a.cx, a.bottom), (b.cx, b.top)], label=label, offset=(22, -22))

    def save(self, path: Path) -> None:
        out = self.image.crop((0, 0, self.width, min(self.height, self.max_y + 110)))
        out.save(path, dpi=(300, 300))


def vertical(path: Path, steps: list[tuple[str, str]], w: int = 1050, h: int = 124, gap: int = 58) -> None:
    c = Chart()
    x = (c.width - w) // 2
    nodes: list[Node] = []
    y = 70
    for text, shape in steps:
        extra = 38 if len(text) > 18 else 0
        nodes.append(c.node(x, y, w, h + extra, text, shape))
        y += h + extra + gap
    for a, b in zip(nodes, nodes[1:]):
        c.down(a, b)
    c.save(path)


def sensor(path: Path) -> None:
    c = Chart()
    x, w, h, gap = 390, 1020, 124, 56
    y = 60
    start = c.node(x, y, w, h, "开始：传感采集任务", "start"); y += h + gap
    init = c.node(x, y, w, h, "初始化传感器与循环计数", "process"); y += h + gap
    loop = c.node(x, y, w, h, "进入三十秒采集周期", "queue"); y += h + gap
    read = c.node(x, y, w, h + 20, "读取温湿度与振动幅值", "process"); y += h + gap + 20
    decision = c.node(x + 190, y, 640, 215, "是否已过预热期？", "decision"); y += 215 + gap
    left = c.node(150, y, 650, h, "读取二氧化碳浓度", "process")
    right = c.node(1000, y, 650, h, "二氧化碳字段记为无效", "process")
    y += h + 95
    meta = c.node(x, y, w, h + 28, "补充时间戳、设备编号与批次编号", "process"); y += h + gap + 28
    send = c.node(x, y, w, h, "发送数据帧到传感数据队列", "queue"); y += h + gap
    delay = c.node(x, y, w, h + 20, "计数加一，延时后进入下一轮", "process")
    for a, b in [(start, init), (init, loop), (loop, read), (read, decision)]:
        c.down(a, b)
    c.arrow([(decision.left + 55, decision.cy), (left.cx, decision.cy), (left.cx, left.top)], "是", (-80, -45))
    c.arrow([(decision.right - 55, decision.cy), (right.cx, decision.cy), (right.cx, right.top)], "否", (45, -45))
    c.arrow([(left.cx, left.bottom), (left.cx, meta.top - 25), (meta.cx, meta.top - 25), (meta.cx, meta.top)])
    c.arrow([(right.cx, right.bottom), (right.cx, meta.top - 25), (meta.cx, meta.top - 25), (meta.cx, meta.top)])
    c.down(meta, send)
    c.down(send, delay)
    c.arrow([(delay.right, delay.cy), (1665, delay.cy), (1665, loop.cy), (loop.right, loop.cy)], "循环", (16, -45))
    c.save(path)


def communication(path: Path) -> None:
    c = Chart()
    x, w, h, gap = 390, 1020, 124, 56
    y = 60
    start = c.node(x, y, w, h, "开始：通信上传任务", "start"); y += h + gap
    wait = c.node(x, y, w, h, "等待已签名数据队列", "queue"); y += h + gap
    pack = c.node(x, y, w, h, "打包为上传报文", "process"); y += h + gap
    net = c.node(x + 190, y, 640, 215, "无线网络是否可用？", "decision"); y += 215 + gap
    post = c.node(145, y, 690, h + 20, "通过无线模块发送加密请求", "process")
    far = c.node(965, y, 690, h + 20, "远距离无线分片发送", "process")
    y += h + 100
    ok = c.node(185, y, 610, 205, "上传是否成功？", "decision")
    done = c.node(1015, y + 40, 610, h, "完成本次上传", "start")
    c.down(start, wait); c.down(wait, pack); c.down(pack, net)
    c.arrow([(net.left + 55, net.cy), (post.cx, net.cy), (post.cx, post.top)], "是", (-80, -45))
    c.arrow([(net.right - 55, net.cy), (far.cx, net.cy), (far.cx, far.top)], "否", (45, -45))
    c.down(post, ok)
    c.arrow([(ok.right - 55, ok.cy), (done.left, done.cy)], "是", (25, -45))
    c.arrow([(ok.cx, ok.bottom), (ok.cx, far.bottom + 55), (far.cx, far.bottom + 55), (far.cx, far.bottom)], "否", (20, 10))
    c.arrow([(far.right, far.cy), (1690, far.cy), (1690, done.cy), (done.right, done.cy)])
    c.arrow([(done.right, done.cy), (1710, done.cy), (1710, wait.cy), (wait.right, wait.cy)], "循环", (10, -45))
    c.save(path)


def normalize(path: Path, first: str, digest: str) -> None:
    c = Chart()
    x, w, h, gap = 390, 1020, 124, 56
    y = 60
    start = c.node(x, y, w, h, first, "start"); y += h + gap
    walk = c.node(x, y, w, h, "递归遍历输入数据", "queue"); y += h + gap
    dec = c.node(x + 190, y, 640, 215, "当前值类型？", "decision"); y += 250
    b1 = c.node(105, y, 470, h + 70, "键值集合：按键名排序后递归", "process")
    b2 = c.node(665, y, 470, h + 70, "列表：逐项递归处理", "process")
    b3 = c.node(1225, y, 470, h + 70, "时间或文本：统一格式并去除空白", "process")
    y += h + 138
    merge = c.node(x, y, w, h, "得到规范化对象", "queue"); y += h + gap
    text = c.node(x, y, w, h, "生成紧凑数据文本", "process"); y += h + gap
    dig = c.node(x, y, w, h, digest, "process"); y += h + gap
    out = c.node(x, y, w, h, "输出小写摘要字符串", "start")
    c.down(start, walk); c.down(walk, dec)
    c.arrow([(dec.left + 45, dec.cy), (b1.cx, dec.cy), (b1.cx, b1.top)], "分支", (-116, -45))
    c.arrow([(dec.cx, dec.bottom), (b2.cx, b2.top)])
    c.arrow([(dec.right - 45, dec.cy), (b3.cx, dec.cy), (b3.cx, b3.top)], "分支", (35, -45))
    for b in [b1, b2, b3]:
        c.arrow([(b.cx, b.bottom), (b.cx, merge.top - 25), (merge.cx, merge.top - 25), (merge.cx, merge.top)])
    c.down(merge, text); c.down(text, dig); c.down(dig, out)
    c.save(path)


def conflict(path: Path) -> None:
    c = Chart()
    x, w, h, gap = 390, 1020, 124, 56
    y = 60
    start = c.node(x, y, w, h, "新追溯事件准备入库", "start"); y += h + gap
    add = c.node(x, y, w, h, "乐观写入新记录", "process"); y += h + gap
    flush = c.node(x, y, w, h, "提交前触发唯一性检查", "process"); y += h + gap
    dec = c.node(x + 190, y, 640, 215, "规范哈希是否重复？", "decision"); y += 215 + gap
    ok = c.node(155, y, 650, h, "无冲突：写入成功", "start")
    rollback = c.node(995, y, 650, h, "有冲突：回滚事务", "error")
    y += h + gap
    query = c.node(995, y, 650, h + 40, "按规范哈希查询已有记录", "process"); y += h + gap + 40
    ret = c.node(995, y, 650, h, "返回已有记录", "start")
    c.down(start, add); c.down(add, flush); c.down(flush, dec)
    c.arrow([(dec.left + 55, dec.cy), (ok.cx, dec.cy), (ok.cx, ok.top)], "否", (-80, -45))
    c.arrow([(dec.right - 55, dec.cy), (rollback.cx, dec.cy), (rollback.cx, rollback.top)], "是", (45, -45))
    c.down(rollback, query); c.down(query, ret)
    c.save(path)


def signature(path: Path) -> None:
    c = Chart()
    x, w, h, gap = 390, 1020, 124, 56
    y = 60
    start = c.node(x, y, w, h + 20, "输入公钥、签名与规范哈希", "start"); y += h + gap + 20
    load = c.node(x, y, w, h, "加载公钥", "process"); y += h + gap
    bytes_ = c.node(x, y, w, h, "将规范哈希转换为摘要字节", "process"); y += h + gap
    verify = c.node(x, y, w, h + 28, "按椭圆曲线签名规则验证", "process"); y += h + gap + 28
    dec = c.node(x + 190, y, 640, 215, "验证是否通过？", "decision"); y += 215 + gap
    yes = c.node(175, y, 610, h, "返回验证通过", "start")
    no = c.node(1015, y, 610, h, "返回验证失败", "error")
    c.down(start, load); c.down(load, bytes_); c.down(bytes_, verify); c.down(verify, dec)
    c.arrow([(dec.left + 55, dec.cy), (yes.cx, dec.cy), (yes.cx, yes.top)], "是", (-80, -45))
    c.arrow([(dec.right - 55, dec.cy), (no.cx, dec.cy), (no.cx, no.top)], "否", (45, -45))
    c.save(path)


def mac(path: Path) -> None:
    c = Chart()
    x, w, h, gap = 390, 1020, 124, 56
    y = 60
    start = c.node(x, y, w, h + 28, "输入密钥、规范哈希与收到的认证码", "start"); y += h + gap + 28
    calc = c.node(x, y, w, h, "重新计算消息认证码", "process"); y += h + gap
    compare = c.node(x, y, w, h, "执行常时比较", "process"); y += h + gap
    dec = c.node(x + 190, y, 640, 215, "比较是否一致？", "decision"); y += 215 + gap
    yes = c.node(175, y, 610, h, "返回验证通过", "start")
    no = c.node(1015, y, 610, h, "返回验证失败", "error")
    c.down(start, calc); c.down(calc, compare); c.down(compare, dec)
    c.arrow([(dec.left + 55, dec.cy), (yes.cx, dec.cy), (yes.cx, yes.top)], "是", (-80, -45))
    c.arrow([(dec.right - 55, dec.cy), (no.cx, dec.cy), (no.cx, no.top)], "否", (45, -45))
    c.save(path)


def anchor(path: Path) -> None:
    c = Chart()
    x, w, h, gap = 390, 1020, 116, 50
    y = 55
    start = c.node(x, y, w, h, "输入待锚定事件", "start"); y += h + gap
    status = c.node(x, y, w, h, "状态置为锚定中并保存", "process"); y += h + gap
    record = c.node(x, y, w, h + 20, "创建待确认提交记录", "process"); y += h + gap + 20
    tx = c.node(x, y, w, h + 20, "调用链上写入接口获得交易标识", "process"); y += h + gap + 20
    receipt = c.node(x, y, w, h, "查询交易回执", "process"); y += h + gap
    reorg = c.node(x + 190, y, 640, 210, "是否发生链重组？", "decision"); y += 210 + gap
    yes = c.node(140, y, 700, h + 30, "提交标为已重组，事件回到待处理", "error")
    no = c.node(960, y, 700, h + 30, "提交标为已确认，事件置为已锚定", "start")
    y += h + 110
    exc = c.node(x + 190, y, 640, 210, "锚定过程是否异常？", "decision"); y += 210 + gap
    retry = c.node(x, y, w, h, "重试次数加一", "process"); y += h + gap
    retry_dec = c.node(x + 190, y, 640, 210, "是否达到三次？", "decision"); y += 210 + gap
    retrying = c.node(140, y, 700, h, "进入失败重试", "process")
    dead = c.node(960, y, 700, h, "进入死信队列", "error")
    c.down(start, status); c.down(status, record); c.down(record, tx); c.down(tx, receipt); c.down(receipt, reorg)
    c.arrow([(reorg.left + 55, reorg.cy), (yes.cx, reorg.cy), (yes.cx, yes.top)], "是", (-80, -45))
    c.arrow([(reorg.right - 55, reorg.cy), (no.cx, reorg.cy), (no.cx, no.top)], "否", (45, -45))
    c.arrow([(tx.right, tx.cy), (1665, tx.cy), (1665, exc.cy), (exc.right, exc.cy)], "异常", (15, -45))
    c.down(exc, retry, "是")
    c.down(retry, retry_dec)
    c.arrow([(retry_dec.left + 55, retry_dec.cy), (retrying.cx, retry_dec.cy), (retrying.cx, retrying.top)], "否", (-80, -45))
    c.arrow([(retry_dec.right - 55, retry_dec.cy), (dead.cx, retry_dec.cy), (dead.cx, dead.top)], "是", (45, -45))
    c.save(path)


def make_contact_sheet(files: list[Path]) -> None:
    thumbs = []
    for file in files:
        img = Image.open(file).convert("RGB")
        img.thumbnail((330, 520), Image.Resampling.LANCZOS)
        thumbs.append((file, img.copy()))
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 390, rows * 585), "white")
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT_BOLD, 26)
    for idx, (file, img) in enumerate(thumbs):
        col, row = idx % cols, idx // cols
        x = col * 390 + (390 - img.width) // 2
        y = row * 585 + 46
        sheet.paste(img, (x, y))
        d.text((col * 390 + 18, row * 585 + 10), file.stem, font=font, fill="#172033")
    sheet.save(OUTPUT_DIR / "流程图预览总览.png", dpi=(200, 200))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = [
        ("01_传感采集任务流程图.png", sensor),
        ("02_签名任务流程图.png", lambda p: vertical(p, [
            ("开始：签名任务", "start"),
            ("等待传感数据队列", "queue"),
            ("按统一规则序列化", "process"),
            ("计算二百五十六位安全摘要", "process"),
            ("唤醒安全芯片并执行硬件签名", "process"),
            ("安全芯片进入休眠", "process"),
            ("将原始签名编码为传输格式", "process"),
            ("构建签名信封", "process"),
            ("发送到已签名数据队列并循环", "queue"),
        ])),
        ("03_通信上传流程图.png", communication),
        ("04_后端规范哈希流程图.png", lambda p: normalize(p, "输入后端数据对象", "计算安全摘要")),
        ("05_前端规范哈希流程图.png", lambda p: normalize(p, "输入前端数据对象", "调用浏览器摘要能力")),
        ("06_规范哈希冲突处理流程图.png", conflict),
        ("07_椭圆曲线签名验证流程图.png", signature),
        ("08_消息认证码验证流程图.png", mac),
        ("09_链上锚定任务流程图.png", anchor),
    ]
    outputs: list[Path] = []
    for filename, maker in specs:
        path = OUTPUT_DIR / filename
        maker(path)
        outputs.append(path)
    make_contact_sheet(outputs)
    print("saved:")
    for path in outputs:
        print(path)
    print(OUTPUT_DIR / "流程图预览总览.png")


if __name__ == "__main__":
    main()
