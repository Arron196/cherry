from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import win32com.client as win32


OUT_DIR = Path(r"C:\Users\benja\Dropbox\毕业论文\流程图_EMF_微软雅黑加粗")
PPTX_PATH = OUT_DIR / "流程图源文件_可编辑.pptx"

# PowerPoint constants used via COM.
PP_LAYOUT_BLANK = 12
MSO_SHAPE_ROUNDED_RECTANGLE = 5
MSO_SHAPE_DIAMOND = 4
MSO_SHAPE_OVAL = 9
MSO_CONNECTOR_STRAIGHT = 1
MSO_CONNECTOR_ELBOW = 2
MSO_GROUP = 6
MSO_ANCHOR_MIDDLE = 3
PP_ALIGN_CENTER = 2
MSO_TRUE = -1
MSO_FALSE = 0
MSO_TRIANGLE = 3
PP_SAVE_AS_OPENXML = 24
PP_SAVE_AS_EMF = 5


def rgb(hex_color: str) -> int:
    h = hex_color.strip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r + (g << 8) + (b << 16)


PALETTE = {
    "bg": rgb("#ffffff"),
    "line": rgb("#3f4a58"),
    "text": rgb("#172033"),
    "start_fill": rgb("#dff4e8"),
    "start_line": rgb("#4c9b73"),
    "process_fill": rgb("#eaf2ff"),
    "process_line": rgb("#5f86d6"),
    "queue_fill": rgb("#efeaff"),
    "queue_line": rgb("#866ec7"),
    "decision_fill": rgb("#fff3c7"),
    "decision_line": rgb("#c49d2f"),
    "error_fill": rgb("#ffe5e5"),
    "error_line": rgb("#d46666"),
}


@dataclass
class Box:
    shape: object
    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


class PptChart:
    def __init__(self, slide, width: float = 720, height: float = 1080) -> None:
        self.slide = slide
        self.width = width
        self.height = height
        self.shapes: list[object] = []

    def add_node(self, x: float, y: float, w: float, h: float, text: str, kind: str = "process", font_size: float = 18) -> Box:
        if kind == "decision":
            shape_type = MSO_SHAPE_DIAMOND
        elif kind == "start":
            shape_type = MSO_SHAPE_ROUNDED_RECTANGLE
        else:
            shape_type = MSO_SHAPE_ROUNDED_RECTANGLE
        shape = self.slide.Shapes.AddShape(shape_type, x, y, w, h)
        fill_key = f"{kind}_fill"
        line_key = f"{kind}_line"
        shape.Fill.ForeColor.RGB = PALETTE[fill_key]
        shape.Line.ForeColor.RGB = PALETTE[line_key]
        shape.Line.Weight = 1.5
        if shape_type == MSO_SHAPE_ROUNDED_RECTANGLE:
            try:
                shape.Adjustments[1] = 0.2
            except Exception:
                pass
        shape.TextFrame.MarginLeft = 8
        shape.TextFrame.MarginRight = 8
        shape.TextFrame.MarginTop = 4
        shape.TextFrame.MarginBottom = 4
        shape.TextFrame.VerticalAnchor = MSO_ANCHOR_MIDDLE
        shape.TextFrame.TextRange.Text = text
        shape.TextFrame.TextRange.ParagraphFormat.Alignment = PP_ALIGN_CENTER
        font = shape.TextFrame.TextRange.Font
        font.Name = "Microsoft YaHei"
        font.NameFarEast = "Microsoft YaHei"
        font.Bold = MSO_TRUE
        font.Size = font_size
        font.Color.RGB = PALETTE["text"]
        self.shapes.append(shape)
        return Box(shape, x, y, w, h)

    def add_label(self, x: float, y: float, text: str) -> None:
        width = max(28, len(text) * 16)
        shape = self.slide.Shapes.AddShape(MSO_SHAPE_ROUNDED_RECTANGLE, x, y, width, 24)
        shape.Fill.ForeColor.RGB = PALETTE["bg"]
        shape.Line.ForeColor.RGB = rgb("#d5ddea")
        shape.Line.Weight = 1
        shape.TextFrame.MarginLeft = 4
        shape.TextFrame.MarginRight = 4
        shape.TextFrame.MarginTop = 1
        shape.TextFrame.MarginBottom = 1
        shape.TextFrame.VerticalAnchor = MSO_ANCHOR_MIDDLE
        shape.TextFrame.TextRange.Text = text
        shape.TextFrame.TextRange.ParagraphFormat.Alignment = PP_ALIGN_CENTER
        font = shape.TextFrame.TextRange.Font
        font.Name = "Microsoft YaHei"
        font.NameFarEast = "Microsoft YaHei"
        font.Bold = MSO_TRUE
        font.Size = 12
        font.Color.RGB = PALETTE["text"]
        self.shapes.append(shape)

    def arrow(self, points: list[tuple[float, float]], label: str | None = None, label_offset: tuple[float, float] = (0, 0)) -> None:
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            line = self.slide.Shapes.AddConnector(MSO_CONNECTOR_STRAIGHT, x1, y1, x2, y2)
            line.Line.ForeColor.RGB = PALETTE["line"]
            line.Line.Weight = 1.7
            if i == len(points) - 2:
                line.Line.EndArrowheadStyle = MSO_TRIANGLE
            self.shapes.append(line)
        if label:
            x, y = points[len(points) // 2]
            self.add_label(x + label_offset[0], y + label_offset[1], label)

    def down(self, a: Box, b: Box, label: str | None = None) -> None:
        self.arrow([(a.cx, a.bottom), (b.cx, b.top)], label=label, label_offset=(10, -12))

    def export(self, path: Path) -> None:
        if not self.shapes:
            return
        names = [shape.Name for shape in self.shapes]
        group = self.slide.Shapes.Range(names).Group()
        group.Export(str(path), PP_SAVE_AS_EMF)


def clear_slide(slide) -> None:
    for i in range(slide.Shapes.Count, 0, -1):
        slide.Shapes.Item(i).Delete()


def vertical(chart: PptChart, steps: list[tuple[str, str]], w: float = 440, h: float = 50, gap: float = 28) -> None:
    x = (chart.width - w) / 2
    nodes: list[Box] = []
    y = 36
    for text, kind in steps:
        extra = 16 if len(text) > 14 else 0
        nodes.append(chart.add_node(x, y, w, h + extra, text, kind))
        y += h + extra + gap
    for a, b in zip(nodes, nodes[1:]):
        chart.down(a, b)


def chart_sensor(chart: PptChart) -> None:
    x, w, h, gap = 150, 420, 52, 28
    y = 36
    start = chart.add_node(x, y, w, h, "开始：传感采集任务", "start"); y += h + gap
    init = chart.add_node(x, y, w, h, "初始化传感器与循环计数", "process"); y += h + gap
    loop = chart.add_node(x, y, w, h, "进入三十秒采集周期", "queue"); y += h + gap
    read = chart.add_node(x, y, w, h, "读取温湿度与振动幅值", "process"); y += h + gap
    dec = chart.add_node(x + 80, y, 260, 100, "是否已过预热期？", "decision"); y += 100 + gap
    left = chart.add_node(60, y, 260, h, "读取二氧化碳浓度", "process")
    right = chart.add_node(400, y, 260, h, "二氧化碳字段记为无效", "process")
    y += h + 42
    meta = chart.add_node(x, y, w, h + 12, "补充时间戳、设备编号与批次编号", "process"); y += h + 12 + gap
    send = chart.add_node(x, y, w, h, "发送数据帧到传感数据队列", "queue"); y += h + gap
    delay = chart.add_node(x, y, w, h, "计数加一，延时后进入下一轮", "process")
    for a, b in [(start, init), (init, loop), (loop, read), (read, dec)]:
        chart.down(a, b)
    chart.arrow([(dec.left + 20, dec.cy), (left.cx, dec.cy), (left.cx, left.top)], "是", (-50, -16))
    chart.arrow([(dec.right - 20, dec.cy), (right.cx, dec.cy), (right.cx, right.top)], "否", (30, -16))
    chart.arrow([(left.cx, left.bottom), (left.cx, meta.top - 14), (meta.cx, meta.top - 14), (meta.cx, meta.top)])
    chart.arrow([(right.cx, right.bottom), (right.cx, meta.top - 14), (meta.cx, meta.top - 14), (meta.cx, meta.top)])
    chart.down(meta, send); chart.down(send, delay)
    chart.arrow([(delay.right, delay.cy), (650, delay.cy), (650, loop.cy), (loop.right, loop.cy)], "循环", (8, -16))


def chart_comm(chart: PptChart) -> None:
    x, w, h, gap = 150, 420, 52, 28
    y = 36
    start = chart.add_node(x, y, w, h, "开始：通信上传任务", "start"); y += h + gap
    wait = chart.add_node(x, y, w, h, "等待已签名数据队列", "queue"); y += h + gap
    pack = chart.add_node(x, y, w, h, "打包为上传报文", "process"); y += h + gap
    net = chart.add_node(x + 80, y, 260, 100, "无线网络是否可用？", "decision"); y += 100 + gap
    post = chart.add_node(40, y, 290, h + 12, "通过无线模块发送加密请求", "process")
    far = chart.add_node(390, y, 290, h + 12, "远距离无线分片发送", "process")
    y += h + 50
    ok = chart.add_node(80, y, 250, 90, "上传是否成功？", "decision")
    done = chart.add_node(420, y + 18, 250, h, "完成本次上传", "start")
    chart.down(start, wait); chart.down(wait, pack); chart.down(pack, net)
    chart.arrow([(net.left + 20, net.cy), (post.cx, net.cy), (post.cx, post.top)], "是", (-50, -16))
    chart.arrow([(net.right - 20, net.cy), (far.cx, net.cy), (far.cx, far.top)], "否", (30, -16))
    chart.down(post, ok)
    chart.arrow([(ok.right - 20, ok.cy), (done.left, done.cy)], "是", (20, -16))
    chart.arrow([(ok.cx, ok.bottom), (ok.cx, far.bottom + 28), (far.cx, far.bottom + 28), (far.cx, far.bottom)], "否", (12, 4))
    chart.arrow([(far.right, far.cy), (685, far.cy), (685, done.cy), (done.right, done.cy)])
    chart.arrow([(done.right, done.cy), (695, done.cy), (695, wait.cy), (wait.right, wait.cy)], "循环", (4, -16))


def chart_normalize(chart: PptChart, start_text: str, digest_text: str) -> None:
    x, w, h, gap = 150, 420, 52, 28
    y = 36
    start = chart.add_node(x, y, w, h, start_text, "start"); y += h + gap
    walk = chart.add_node(x, y, w, h, "递归遍历输入数据", "queue"); y += h + gap
    dec = chart.add_node(x + 80, y, 260, 100, "当前值类型？", "decision"); y += 120
    b1 = chart.add_node(28, y, 200, h + 28, "键值集合：按键名排序后递归", "process", 15)
    b2 = chart.add_node(260, y, 200, h + 28, "列表：逐项递归处理", "process", 15)
    b3 = chart.add_node(492, y, 200, h + 28, "时间或文本：统一格式并去除空白", "process", 15)
    y += h + 70
    merge = chart.add_node(x, y, w, h, "得到规范化对象", "queue"); y += h + gap
    compact = chart.add_node(x, y, w, h, "生成紧凑数据文本", "process"); y += h + gap
    digest = chart.add_node(x, y, w, h, digest_text, "process"); y += h + gap
    out = chart.add_node(x, y, w, h, "输出小写摘要字符串", "start")
    chart.down(start, walk); chart.down(walk, dec)
    chart.arrow([(dec.left + 20, dec.cy), (b1.cx, dec.cy), (b1.cx, b1.top)], "分支", (-55, -16))
    chart.arrow([(dec.cx, dec.bottom), (b2.cx, b2.top)])
    chart.arrow([(dec.right - 20, dec.cy), (b3.cx, dec.cy), (b3.cx, b3.top)], "分支", (25, -16))
    for b in [b1, b2, b3]:
        chart.arrow([(b.cx, b.bottom), (b.cx, merge.top - 14), (merge.cx, merge.top - 14), (merge.cx, merge.top)])
    chart.down(merge, compact); chart.down(compact, digest); chart.down(digest, out)


def chart_conflict(chart: PptChart) -> None:
    x, w, h, gap = 150, 420, 52, 28
    y = 36
    start = chart.add_node(x, y, w, h, "新追溯事件准备入库", "start"); y += h + gap
    add = chart.add_node(x, y, w, h, "乐观写入新记录", "process"); y += h + gap
    flush = chart.add_node(x, y, w, h, "提交前触发唯一性检查", "process"); y += h + gap
    dec = chart.add_node(x + 80, y, 260, 100, "规范哈希是否重复？", "decision"); y += 100 + gap
    ok = chart.add_node(58, y, 260, h, "无冲突：写入成功", "start")
    rollback = chart.add_node(402, y, 260, h, "有冲突：回滚事务", "error")
    y += h + gap
    query = chart.add_node(402, y, 260, h + 16, "按规范哈希查询已有记录", "process"); y += h + gap + 16
    ret = chart.add_node(402, y, 260, h, "返回已有记录", "start")
    chart.down(start, add); chart.down(add, flush); chart.down(flush, dec)
    chart.arrow([(dec.left + 20, dec.cy), (ok.cx, dec.cy), (ok.cx, ok.top)], "否", (-50, -16))
    chart.arrow([(dec.right - 20, dec.cy), (rollback.cx, dec.cy), (rollback.cx, rollback.top)], "是", (30, -16))
    chart.down(rollback, query); chart.down(query, ret)


def chart_signature(chart: PptChart) -> None:
    vertical(chart, [
        ("输入公钥、签名与规范哈希", "start"),
        ("加载公钥", "process"),
        ("将规范哈希转换为摘要字节", "process"),
        ("按椭圆曲线签名规则验证", "process"),
    ], w=420, h=52, gap=28)
    # Continue manually for final decision so it fans out.
    nodes = [Box(s, s.Left, s.Top, s.Width, s.Height) for s in chart.shapes if s.Type != MSO_GROUP and hasattr(s, "TextFrame") and s.TextFrame.HasText]
    last = nodes[-1]
    y = last.bottom + 28
    dec = chart.add_node(230, y, 260, 100, "验证是否通过？", "decision"); y += 100 + 28
    yes = chart.add_node(90, y, 250, 52, "返回验证通过", "start")
    no = chart.add_node(380, y, 250, 52, "返回验证失败", "error")
    chart.down(last, dec)
    chart.arrow([(dec.left + 20, dec.cy), (yes.cx, dec.cy), (yes.cx, yes.top)], "是", (-50, -16))
    chart.arrow([(dec.right - 20, dec.cy), (no.cx, dec.cy), (no.cx, no.top)], "否", (30, -16))


def chart_mac(chart: PptChart) -> None:
    x, w, h, gap = 150, 420, 52, 28
    y = 36
    start = chart.add_node(x, y, w, h + 16, "输入密钥、规范哈希与收到的认证码", "start"); y += h + gap + 16
    calc = chart.add_node(x, y, w, h, "重新计算消息认证码", "process"); y += h + gap
    compare = chart.add_node(x, y, w, h, "执行常时比较", "process"); y += h + gap
    dec = chart.add_node(x + 80, y, 260, 100, "比较是否一致？", "decision"); y += 100 + gap
    yes = chart.add_node(90, y, 250, h, "返回验证通过", "start")
    no = chart.add_node(380, y, 250, h, "返回验证失败", "error")
    chart.down(start, calc); chart.down(calc, compare); chart.down(compare, dec)
    chart.arrow([(dec.left + 20, dec.cy), (yes.cx, dec.cy), (yes.cx, yes.top)], "是", (-50, -16))
    chart.arrow([(dec.right - 20, dec.cy), (no.cx, dec.cy), (no.cx, no.top)], "否", (30, -16))


def chart_anchor(chart: PptChart) -> None:
    x, w, h, gap = 150, 420, 48, 24
    y = 28
    start = chart.add_node(x, y, w, h, "输入待锚定事件", "start"); y += h + gap
    status = chart.add_node(x, y, w, h, "状态置为锚定中并保存", "process"); y += h + gap
    record = chart.add_node(x, y, w, h, "创建待确认提交记录", "process"); y += h + gap
    tx = chart.add_node(x, y, w, h + 10, "调用链上写入接口获得交易标识", "process"); y += h + gap + 10
    receipt = chart.add_node(x, y, w, h, "查询交易回执", "process"); y += h + gap
    reorg = chart.add_node(x + 80, y, 260, 96, "是否发生链重组？", "decision"); y += 96 + gap
    yes = chart.add_node(40, y, 300, h + 16, "提交标为已重组，事件回到待处理", "error", 15)
    no = chart.add_node(380, y, 300, h + 16, "提交标为已确认，事件置为已锚定", "start", 15)
    y += h + 60
    exc = chart.add_node(x + 80, y, 260, 96, "锚定过程是否异常？", "decision"); y += 96 + gap
    retry = chart.add_node(x, y, w, h, "重试次数加一", "process"); y += h + gap
    retry_dec = chart.add_node(x + 80, y, 260, 96, "是否达到三次？", "decision"); y += 96 + gap
    retrying = chart.add_node(75, y, 270, h, "进入失败重试", "process")
    dead = chart.add_node(375, y, 270, h, "进入死信队列", "error")
    for a, b in [(start, status), (status, record), (record, tx), (tx, receipt), (receipt, reorg)]:
        chart.down(a, b)
    chart.arrow([(reorg.left + 20, reorg.cy), (yes.cx, reorg.cy), (yes.cx, yes.top)], "是", (-50, -16))
    chart.arrow([(reorg.right - 20, reorg.cy), (no.cx, reorg.cy), (no.cx, no.top)], "否", (30, -16))
    chart.arrow([(tx.right, tx.cy), (650, tx.cy), (650, exc.cy), (exc.right, exc.cy)], "异常", (8, -16))
    chart.down(exc, retry, "是")
    chart.down(retry, retry_dec)
    chart.arrow([(retry_dec.left + 20, retry_dec.cy), (retrying.cx, retry_dec.cy), (retrying.cx, retrying.top)], "否", (-50, -16))
    chart.arrow([(retry_dec.right - 20, retry_dec.cy), (dead.cx, retry_dec.cy), (dead.cx, dead.top)], "是", (30, -16))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pp = win32.Dispatch("PowerPoint.Application")
    pp.Visible = True
    pres = pp.Presentations.Add()
    pres.PageSetup.SlideWidth = 720
    pres.PageSetup.SlideHeight = 1080
    specs = [
        ("01_传感采集任务流程图.emf", chart_sensor),
        ("02_签名任务流程图.emf", lambda c: vertical(c, [
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
        ("03_通信上传流程图.emf", chart_comm),
        ("04_后端规范哈希流程图.emf", lambda c: chart_normalize(c, "输入后端数据对象", "计算安全摘要")),
        ("05_前端规范哈希流程图.emf", lambda c: chart_normalize(c, "输入前端数据对象", "调用浏览器摘要能力")),
        ("06_规范哈希冲突处理流程图.emf", chart_conflict),
        ("07_椭圆曲线签名验证流程图.emf", chart_signature),
        ("08_消息认证码验证流程图.emf", chart_mac),
        ("09_链上锚定任务流程图.emf", chart_anchor),
    ]
    outputs: list[Path] = []
    try:
        for idx, (filename, maker) in enumerate(specs, start=1):
            slide = pres.Slides.Add(idx, PP_LAYOUT_BLANK)
            clear_slide(slide)
            chart = PptChart(slide)
            maker(chart)
            path = OUT_DIR / filename
            chart.export(path)
            outputs.append(path)
        pres.SaveAs(str(PPTX_PATH), PP_SAVE_AS_OPENXML)
    finally:
        pres.Close()
        pp.Quit()
    print("saved:")
    for path in outputs:
        print(path)
    print(PPTX_PATH)


if __name__ == "__main__":
    main()
