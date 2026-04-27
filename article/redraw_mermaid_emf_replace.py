from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document


ROOT = Path(__file__).resolve().parent
SOURCE_DOCX = ROOT / "最终文字修改版图片待修改.docx"
OUTPUT_DOCX = ROOT / "最终文字修改版图片待修改_Mermaid_EMF替换版.docx"
OUT_DIR = ROOT / "mermaid_emf_figures"

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
EMF_CONTENT_TYPE = "image/x-emf"


FIGURE_RIDS = {
    "figure_3_3": "rId12",
    "figure_3_4": "rId13",
    "figure_4_3": "rId19",
    "figure_5_1": "rId22",
    "figure_5_2": "rId23",
    "figure_5_3": "rId24",
    "figure_5_4": "rId25",
    "figure_5_5": "rId26",
    "figure_5_6": "rId27",
}

FIGURE_MEDIA = {
    "figure_3_3": "mermaid_figure_3_3.emf",
    "figure_3_4": "mermaid_figure_3_4.emf",
    "figure_4_3": "mermaid_figure_4_3.emf",
    "figure_5_1": "mermaid_figure_5_1.emf",
    "figure_5_2": "mermaid_figure_5_2.emf",
    "figure_5_3": "mermaid_figure_5_3.emf",
    "figure_5_4": "mermaid_figure_5_4.emf",
    "figure_5_5": "mermaid_figure_5_5.emf",
    "figure_5_6": "mermaid_figure_5_6.emf",
}

MERMAID_CONFIG = {
    "theme": "base",
    "themeVariables": {
        "fontFamily": "Microsoft YaHei, SimSun, Arial",
        "fontSize": "18px",
        "primaryColor": "#FFFFFF",
        "primaryTextColor": "#1F2D3D",
        "primaryBorderColor": "#2F6DB2",
        "lineColor": "#526D82",
        "secondaryColor": "#EDF4FB",
        "tertiaryColor": "#F7F9FB",
        "background": "#FFFFFF",
        "mainBkg": "#FFFFFF",
        "clusterBkg": "#F8FCFE",
        "clusterBorder": "#D7E3EC",
        "edgeLabelBackground": "#FFFFFF",
        "actorBkg": "#FFFFFF",
        "actorBorder": "#2F6DB2",
        "actorTextColor": "#1F2D3D",
        "activationBkgColor": "#EDF4FB",
        "activationBorderColor": "#2F6DB2",
        "sequenceNumberColor": "#FFFFFF",
    },
    "flowchart": {
        "htmlLabels": False,
        "useMaxWidth": False,
        "curve": "basis",
        "nodeSpacing": 38,
        "rankSpacing": 58,
    },
    "sequence": {
        "useMaxWidth": False,
        "showSequenceNumbers": True,
        "diagramMarginX": 42,
        "diagramMarginY": 32,
        "actorMargin": 70,
        "messageMargin": 48,
        "boxMargin": 12,
        "boxTextMargin": 8,
        "noteMargin": 12,
    },
    "state": {
        "useMaxWidth": False,
    },
}


MERMAID_SOURCES = {
    "figure_3_3": r"""
flowchart LR
  subgraph G1[设备治理域]
    devices[(managed_devices\nPK id\nUNIQUE device_id\nstatus / disabled_at)]
    keys[(managed_device_keys\nPK id\nFK device_id -> managed_devices.id\nUNIQUE key_id\nalgorithm / status)]
  end

  subgraph G2[事件与处理域]
    ingest[(ingest_requests\nPK id\nUNIQUE idempotency_key\npayload_hash\ningest_status / retry_count\nFK event_id -> events.id)]
    events[(events\nPK id\ndevice_id / batch_id / timestamp\nsensor_payload / signature_envelope\nUNIQUE canonical_hash)]
    quality[(quality_results\nPK id\nFK event_id\ncheck_name / score\nstatus)]
    alerts[(alerts\nPK id\nFK event_id\nalert_type / severity\nstatus)]
  end

  subgraph G3[锚定与审计域]
    subs[(anchor_submissions\nPK id\nFK event_id\ntransaction_hash\ncanonical_hash\nstatus)]
    receipts[(anchor_receipts\nPK id\nFK event_id\nnetwork\ntransaction_hash\nreceipt_payload)]
    audits[(audits\nPK id\nFK event_id\nactor / action / target)]
  end

  note[双层幂等：ingest_requests.idempotency_key 处理请求重放，events.canonical_hash 处理内容重复。]

  devices -->|1:N| keys
  ingest -->|N:1| events
  devices -. device_id 逻辑关联 .-> events
  events --> quality
  events --> alerts
  events --> subs
  events --> receipts
  events --> audits
  ingest -.-> note
  events -.-> note

  classDef db fill:#FFFFFF,stroke:#2F6DB2,color:#1F2D3D,stroke-width:1.6px;
  classDef note fill:#FFF7ED,stroke:#F97316,color:#1F2D3D,stroke-width:1.4px;
  class devices,keys,ingest,events,quality,alerts,subs,receipts,audits db;
  class note note;
""",
    "figure_3_4": r"""
stateDiagram-v2
  direction LR
  [*] --> RECEIVED: 事件接收
  RECEIVED --> ANCHORING: 开始锚定
  ANCHORING --> ANCHORED: 成功确认
  ANCHORING --> FAILED_RETRYING: 失败且 retry < 3
  FAILED_RETRYING --> RECEIVED: retry_worker 重新触发
  FAILED_RETRYING --> DEAD_LETTER: retry >= 3
  DEAD_LETTER --> RECEIVED: 管理员 requeue
  RECEIVED --> RECEIVED: 命中 idempotency_key / canonical_hash\n直接返回已有记录

  note right of RECEIVED
    已接收 / 待处理
    幂等旁路不重复入状态机
  end note
  note right of ANCHORING
    提交锚定 / 等待确认
    anchor_worker 轮询 receipt
  end note
  note right of FAILED_RETRYING
    可恢复失败 / 等待重试
    告警联动与退避重试
  end note
  note right of DEAD_LETTER
    不可恢复失败
    人工排查后可回收
  end note
""",
    "figure_4_3": r"""
flowchart LR
  subgraph CFG[安全芯片配置]
    slot[ATECC608A 槽位策略\nSlot 0: ECDSA P-256 私钥\nNever-Read，仅允许 Sign\nConfig Lock + Data Lock]
    i2c[I2C 命令时序\nWakeup -> 命令帧\nLength / OpCode / Param / Data / CRC16\n等待执行 -> 读响应 -> Sleep]
  end

  f1[1 数据帧构造\nSensorTask 采集并组装 JSON]
  f2[2 摘要计算\n规范化序列化\nHASH-SHA256]
  f3[3 芯片签名\nWakeup -> Sign 指令 0x41\n等待 tEXEC\n取回 64B 签名值 r,s]
  f4[4 DER 编码\n原始 r,s\n转 ASN.1 DER]
  f5[5 上传\nsignature_envelope\n经 HTTPS 发送]
  note[性能备注：ATECC608A 签名实测约 7 ms；从采集到封装上传整个路径约 15~25 ms。]

  slot --> f3
  i2c --> f3
  f1 --> f2 --> f3 --> f4 --> f5
  f3 -.-> note

  classDef cfg fill:#F8FCFE,stroke:#D7E3EC,color:#1F2D3D;
  classDef step fill:#FFFFFF,stroke:#2F6DB2,color:#1F2D3D,stroke-width:1.6px;
  classDef secure fill:#F5F3FF,stroke:#7C3AED,color:#1F2D3D,stroke-width:1.6px;
  classDef note fill:#FFF7ED,stroke:#F97316,color:#1F2D3D;
  class slot,i2c cfg;
  class f1,f2,f4,f5 step;
  class f3 secure;
  class note note;
""",
    "figure_5_1": r"""
flowchart LR
  subgraph BOOT[Boot / Init]
    init[系统初始化\nHAL / Clock / 外设 Init\n创建任务与队列]
    sched[调度启动\nvTaskStartScheduler]
  end

  subgraph SENSOR[SensorTask]
    sensor[采集一帧\n30 s 周期\n前 3 分钟 CO2 = -1]
    q1[(sensorQueue\n深度 4)]
  end

  subgraph SIGN[SignTask]
    sign[签名流水\n规范化 -> SHA-256\nATECC608A Sign\nDER 编码]
    q2[(signedQueue\n深度 4)]
  end

  subgraph COMM[CommTask]
    comm[上传决策\n优先 Wi-Fi\n失败后切 LoRa]
  end

  subgraph NET[外设 / 网络]
    wifi[ESP8266 HTTPS]
    lora[SX1278 LoRa]
  end

  hint[采集、签名与通信通过队列解耦；空闲阶段可进入低功耗模式。]

  init --> sched --> sensor --> q1 --> sign --> q2 --> comm
  comm --> wifi
  comm -. 备用链路 .-> lora
  q1 -. 解耦 .-> hint
  q2 -. 背压缓冲 .-> hint

  classDef process fill:#FFFFFF,stroke:#2F6DB2,color:#1F2D3D,stroke-width:1.6px;
  classDef queue fill:#FEF3C7,stroke:#F59E0B,color:#1F2D3D,stroke-width:1.6px;
  classDef net fill:#ECFDF5,stroke:#16A34A,color:#1F2D3D,stroke-width:1.6px;
  classDef note fill:#F8FCFE,stroke:#A9B7C4,color:#1F2D3D;
  class init,sched,sensor,sign,comm process;
  class q1,q2 queue;
  class wifi,lora net;
  class hint note;
""",
    "figure_5_2": r"""
flowchart LR
  input[输入事件 JSON\ndevice_id: node-01\nbatch_id: CH2026-0008\ntemperature: 2.1\nhumidity: 88\nco2: 620\ntimestamp: 2026-03-28T08:30:00+08:00\nmeta: 冷库A / warehouse]
  s1[01 字段递归排序\n对象键按字典序稳定排序]
  s2[02 时间标准化\n统一转为 UTC ISO8601]
  s3[03 字符串 trim\n去除前后空白与无效换行]
  s4[04 ASCII 转义\n非 ASCII 字符统一 unicode 转义]
  s5[05 紧凑序列化\n使用无空格分隔符]
  s6[06 SHA-256 哈希\n得到 64 位十六进制摘要]
  output[输出 canonical_hash\n9f4f3bb18f1b0a9d...\n3e1204b7f5a6c261...\n1f8f4fd22fb6d7aa]
  goal[一致性目标\nPython 后端 = TypeScript 前端\n相同事件 -> 相同哈希\n用于幂等与链上锚定]

  input --> s1 --> s2 --> s3 --> s4 --> s5 --> s6 --> output --> goal

  classDef input fill:#EFF6FF,stroke:#2563EB,color:#1F2D3D,stroke-width:1.6px;
  classDef step fill:#FFFFFF,stroke:#2F6DB2,color:#1F2D3D,stroke-width:1.6px;
  classDef output fill:#ECFDF5,stroke:#16A34A,color:#1F2D3D,stroke-width:1.6px;
  class input input;
  class s1,s2,s3,s4,s5,s6 step;
  class output,goal output;
""",
    "figure_5_3": r"""
sequenceDiagram
  autonumber
  participant C as 客户端
  participant API as API / ingest
  participant IR as ingest_requests
  participant EV as events
  participant R as 响应

  C->>API: POST /v1/events + idempotency_key
  API->>IR: 查询 idempotency_key 是否存在
  alt 命中 idempotency_key
    IR-->>API: 返回已有 event_id
    API-->>R: 200 OK / 返回已有记录
  else 未命中
    IR-->>API: 不存在，继续处理
    API->>API: 计算 canonical_hash
    API->>EV: 尝试 INSERT events(canonical_hash)
    alt canonical_hash 唯一
      EV-->>API: 写入成功
      API->>IR: 记录 idempotency_key -> event_id
      API-->>R: 201 Created
    else canonical_hash 冲突
      EV-->>API: IntegrityError
      API->>EV: 回查已有事件
      API->>IR: 补记 idempotency_key -> existing event_id
      API-->>R: 200 OK / 返回已有记录
    end
  end

  Note over IR,EV: UNIQUE(idempotency_key) 防重放；UNIQUE(canonical_hash) 防内容重复。\n采用“乐观写入 + IntegrityError 捕获 + 回查”，避免先查后写的竞态窗口。
""",
    "figure_5_4": r"""
flowchart TD
  start([开始])
  extract[提取 signature_envelope\nalgorithm / key_id\nsignature / public_key]
  lookup[查询 managed_device_keys\n校验 device_id + key_id\n确认设备未禁用\n算法必须匹配]
  dbkey{DB 中有活动密钥?}
  fallback[兼容回退\n仅当设备未注册时\n回退 INGEST_SIGNING_KEYS\n只支持 HMAC]
  reject([401 Unauthorized])
  hash[重新计算 canonical_hash\n对业务数据执行规范化算法]
  verify[执行签名验证\nECDSA-P256 或 HMAC-SHA256]
  valid{签名 / MAC 有效?}
  ingest([进入后续入库 / 幂等处理])
  rule[关键规则：设备已注册但密钥不匹配直接拒绝；只有“设备尚未注册”时才允许兼容回退。]

  start --> extract --> lookup --> dbkey
  dbkey -->|是| hash
  dbkey -->|否| reject
  lookup -. 未注册 .-> fallback --> hash
  hash --> verify --> valid
  valid -->|是| ingest
  valid -->|否| reject
  fallback -.-> rule
  reject -.-> rule

  classDef ok fill:#ECFDF5,stroke:#16A34A,color:#1F2D3D,stroke-width:1.6px;
  classDef step fill:#FFFFFF,stroke:#2F6DB2,color:#1F2D3D,stroke-width:1.6px;
  classDef warn fill:#FEF3C7,stroke:#F59E0B,color:#1F2D3D,stroke-width:1.6px;
  classDef bad fill:#FEE2E2,stroke:#DC2626,color:#1F2D3D,stroke-width:1.6px;
  classDef note fill:#F8FCFE,stroke:#A9B7C4,color:#1F2D3D;
  class start,ingest ok;
  class extract,lookup,hash,verify step;
  class dbkey,valid,fallback warn;
  class reject bad;
  class rule note;
""",
    "figure_5_5": r"""
sequenceDiagram
  autonumber
  participant AW as anchor_worker
  participant DB as 数据库
  participant AD as AnchorAdapter
  participant EVM as EVM 节点
  participant RW as retry_worker

  AW->>DB: 查询 RECEIVED 事件
  DB-->>AW: 返回待锚定事件
  AW->>DB: 写入 PENDING submission
  AW->>AD: adapter.anchor_event()
  AD->>EVM: 提交交易 / 获取 tx_hash
  EVM-->>AD: 返回 tx_hash
  AD->>DB: 保存 tx_hash + status=PENDING
  AW->>AD: 轮询 get_receipt()
  AD->>EVM: 查询 receipt / confirmations
  EVM-->>AD: 返回 receipt
  AD->>DB: FINALIZED 或 REORGED

  alt 锚定异常或确认超时
    AW->>DB: 事件状态置为 FAILED_RETRYING
    RW->>DB: 取出重试任务
    RW->>AW: retry_count < 3 时再次提交
  else 超过重试阈值
    RW->>DB: 转入 DEAD_LETTER 并告警
  end

  Note over AW,DB: 提交交易前先写入 PENDING submission record；服务崩溃重启后可继续轮询同一 transaction_hash，避免重复上链。
""",
    "figure_5_6": r"""
flowchart LR
  r0[rollback_safe\n100% Mock\n零 Gas\n默认模式]
  r1[shadow\n主路径仍走 Mock\n副本并发发往 EVM\n只看日志与指标]
  r2[canary\n5% 真流量走 EVM\n95% 继续走 Mock\n风险面受控]
  r3[full\n100% EVM\nMock 退出主路径]
  metrics[canary 期持续监控 SLO\n成功率 >= 99%\n死信率 <= 0.5%\nP95 完成时间 <= 120 s]
  rollback[自动回滚\n任一指标连续违规超过 600 s\n回到 rollback_safe]

  r0 --> r1 --> r2 --> r3
  r2 --> metrics --> rollback
  rollback -. 降级保护 .-> r0

  classDef safe fill:#ECFDF5,stroke:#16A34A,color:#1F2D3D,stroke-width:1.6px;
  classDef stage fill:#FFFFFF,stroke:#2F6DB2,color:#1F2D3D,stroke-width:1.6px;
  classDef canary fill:#FFF7ED,stroke:#F97316,color:#1F2D3D,stroke-width:1.6px;
  classDef bad fill:#FEE2E2,stroke:#DC2626,color:#1F2D3D,stroke-width:1.6px;
  class r0 safe;
  class r1,r3 stage;
  class r2,metrics canary;
  class rollback bad;
""",
}


def write_sources() -> None:
    import json

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config_path = OUT_DIR / "mermaid_config.json"
    config_path.write_text(json.dumps(MERMAID_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, source in MERMAID_SOURCES.items():
        (OUT_DIR / f"{name}.mmd").write_text(source.strip() + "\n", encoding="utf-8")


def render_svgs() -> None:
    config_path = OUT_DIR / "mermaid_config.json"
    npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx.cmd"
    for name in MERMAID_SOURCES:
        mmd_path = OUT_DIR / f"{name}.mmd"
        svg_path = OUT_DIR / f"{name}.svg"
        cmd = [
            npx,
            "-y",
            "@mermaid-js/mermaid-cli",
            "-i",
            str(mmd_path),
            "-o",
            str(svg_path),
            "-c",
            str(config_path),
            "-b",
            "white",
            "-w",
            "1800",
            "-H",
            "1100",
        ]
        subprocess.run(cmd, cwd=ROOT, check=True)
        if not svg_path.exists() or svg_path.stat().st_size < 1000:
            raise RuntimeError(f"SVG render failed or too small: {svg_path}")


def convert_svgs_to_emf() -> None:
    import win32com.client

    powerpoint = win32com.client.DispatchEx("PowerPoint.Application")
    powerpoint.Visible = True
    presentation = None
    try:
        presentation = powerpoint.Presentations.Add()
        presentation.PageSetup.SlideWidth = 900
        presentation.PageSetup.SlideHeight = 550
        blank_layout = 12
        pp_shape_format_emf = 5
        for index, name in enumerate(MERMAID_SOURCES, start=1):
            svg_path = (OUT_DIR / f"{name}.svg").resolve()
            emf_path = (OUT_DIR / FIGURE_MEDIA[name]).resolve()
            slide = presentation.Slides.Add(index, blank_layout)
            shape = slide.Shapes.AddPicture(str(svg_path), False, True, 0, 0, 900, 550)
            shape.Export(str(emf_path), pp_shape_format_emf)
            if not emf_path.exists() or emf_path.stat().st_size < 1000:
                fallback_path = OUT_DIR / f"{name}_slide.emf"
                slide.Export(str(fallback_path.resolve()), "EMF", 1800, 1100)
                shutil.copy2(fallback_path, emf_path)
            if not emf_path.exists() or emf_path.stat().st_size < 1000:
                raise RuntimeError(f"EMF conversion failed or too small: {emf_path}")
    finally:
        if presentation is not None:
            presentation.Close()
        powerpoint.Quit()


def ensure_emf_content_type(content_types_root: ET.Element) -> None:
    for default in content_types_root.findall(f"{{{CT_NS}}}Default"):
        if default.attrib.get("Extension", "").lower() == "emf":
            default.set("ContentType", EMF_CONTENT_TYPE)
            return
    ET.SubElement(
        content_types_root,
        f"{{{CT_NS}}}Default",
        {"Extension": "emf", "ContentType": EMF_CONTENT_TYPE},
    )


def replace_docx_media_with_emf() -> None:
    if not SOURCE_DOCX.exists():
        raise FileNotFoundError(SOURCE_DOCX)

    required = {name: OUT_DIR / media_name for name, media_name in FIGURE_MEDIA.items()}
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing EMF files: " + ", ".join(missing))

    rels_path = "word/_rels/document.xml.rels"
    content_types_path = "[Content_Types].xml"
    skip_names = {rels_path, content_types_path}

    with zipfile.ZipFile(SOURCE_DOCX, "r") as src:
        rels_root = ET.fromstring(src.read(rels_path))
        content_types_root = ET.fromstring(src.read(content_types_path))
        ensure_emf_content_type(content_types_root)

        rid_to_figure = {rid: figure for figure, rid in FIGURE_RIDS.items()}
        replaced_targets: dict[str, str] = {}
        for rel in rels_root.findall(f"{{{REL_NS}}}Relationship"):
            rid = rel.attrib.get("Id")
            if rid not in rid_to_figure:
                continue
            if rel.attrib.get("Type") != IMAGE_REL_TYPE:
                raise RuntimeError(f"Relationship {rid} is not an image relationship")
            figure = rid_to_figure[rid]
            target = f"media/{FIGURE_MEDIA[figure]}"
            rel.set("Target", target)
            replaced_targets[rid] = target

        missing_rids = sorted(set(FIGURE_RIDS.values()) - set(replaced_targets))
        if missing_rids:
            raise RuntimeError("Missing image relationships: " + ", ".join(missing_rids))

        with zipfile.ZipFile(OUTPUT_DOCX, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                if info.filename in skip_names:
                    continue
                dst.writestr(info, src.read(info.filename))
            dst.writestr(
                content_types_path,
                ET.tostring(content_types_root, encoding="utf-8", xml_declaration=True),
            )
            dst.writestr(
                rels_path,
                ET.tostring(rels_root, encoding="utf-8", xml_declaration=True),
            )
            for figure, emf_path in required.items():
                dst.write(emf_path, f"word/media/{FIGURE_MEDIA[figure]}")


def verify_output_docx() -> None:
    with zipfile.ZipFile(OUTPUT_DOCX, "r") as docx_zip:
        names = set(docx_zip.namelist())
        for media_name in FIGURE_MEDIA.values():
            path = f"word/media/{media_name}"
            if path not in names:
                raise RuntimeError(f"Missing media part: {path}")
            if len(docx_zip.read(path)) < 1000:
                raise RuntimeError(f"Media part too small: {path}")

        content_types_root = ET.fromstring(docx_zip.read("[Content_Types].xml"))
        has_emf = any(
            default.attrib.get("Extension", "").lower() == "emf"
            and default.attrib.get("ContentType") == EMF_CONTENT_TYPE
            for default in content_types_root.findall(f"{{{CT_NS}}}Default")
        )
        if not has_emf:
            raise RuntimeError("Missing EMF content type")

        rels_root = ET.fromstring(docx_zip.read("word/_rels/document.xml.rels"))
        targets = {
            rel.attrib.get("Id"): rel.attrib.get("Target")
            for rel in rels_root.findall(f"{{{REL_NS}}}Relationship")
        }
        for figure, rid in FIGURE_RIDS.items():
            expected = f"media/{FIGURE_MEDIA[figure]}"
            if targets.get(rid) != expected:
                raise RuntimeError(f"{figure} relationship not replaced: {rid} -> {targets.get(rid)}")

    document = Document(str(OUTPUT_DOCX))
    captions = [
        "图3-3",
        "图3-4",
        "图4-3",
        "图5-1",
        "图5-2",
        "图5-3",
        "图5-4",
        "图5-5",
        "图5-6",
    ]
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    missing = [caption for caption in captions if caption not in text]
    if missing:
        print("Warning: python-docx text scan did not find captions:", ", ".join(missing), file=sys.stderr)


def main() -> int:
    write_sources()
    render_svgs()
    convert_svgs_to_emf()
    replace_docx_media_with_emf()
    verify_output_docx()
    print(f"Mermaid sources: {OUT_DIR}")
    print(f"Output DOCX: {OUTPUT_DOCX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
