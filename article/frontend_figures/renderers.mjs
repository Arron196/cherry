const COLORS = {
    paper: "#ffffff",
    panel: "#ffffff",
    ink: "#212529",
    muted: "#6c757d",
    border: "#ced4da",
    grid: "#e9ecef",
    cherry: "#000000",
    navy: "#212529",
    teal: "#343a40",
    sage: "#495057",
    gold: "#495057",
    plum: "#495057",
    blueSoft: "#f8f9fa",
    tealSoft: "#e9ecef",
    greenSoft: "#f8f9fa",
    amberSoft: "#e9ecef",
    roseSoft: "#f8f9fa",
    lilacSoft: "#e9ecef",
    sandSoft: "#f8f9fa",
    white: "#ffffff",
    success: "#212529",
    warning: "#495057",
    danger: "#212529",
};

const FONT_HEAD = '"Times New Roman", Times, serif';
const FONT_SANS = 'Arial, Helvetica, sans-serif';
const FONT_MONO = '"Courier New", Courier, monospace';

function esc(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function textBlock({
    x,
    y,
    lines,
    fontSize = 28,
    fill = COLORS.ink,
    weight = 500,
    family = FONT_SANS,
    anchor = "start",
    lineGap = 1.35,
    opacity = 1,
}) {
    const dy = Math.round(fontSize * lineGap);
    return `<text x="${x}" y="${y}" fill="${fill}" font-size="${fontSize}" font-weight="${weight}" font-family="${family}" text-anchor="${anchor}" opacity="${opacity}">${lines
        .map((line, index) => `<tspan x="${x}" dy="${index === 0 ? 0 : dy}">${esc(line)}</tspan>`)
        .join("")}</text>`;
}

function pill({ x, y, w, h, label, fill, textFill = COLORS.white, size = 20, mono = false }) {
    return `<g>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}" fill="${fill}"/>
        ${textBlock({
            x: x + w / 2,
            y: y + h / 2 + size * 0.34,
            lines: [label],
            fontSize: size,
            fill: textFill,
            weight: 700,
            family: mono ? FONT_MONO : FONT_SANS,
            anchor: "middle",
        })}
    </g>`;
}

function card({
    x,
    y,
    w,
    h,
    title,
    lines = [],
    accent = COLORS.navy,
    fill = COLORS.panel,
    titleSize = 34,
    lineSize = 24,
    badge,
    mono = false,
}) {
    const badgeMarkup = badge
        ? pill({
              x: x + 26,
              y: y + 22,
              w: Math.max(88, badge.length * 20),
              h: 34,
              label: badge,
              fill: accent,
              textFill: COLORS.white,
              size: 18,
          })
        : "";
    const titleY = badge ? y + 84 : y + 58;
    return `<g filter="url(#shadow)">
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="0" fill="${fill}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="10" height="${h}" rx="0" fill="${accent}"/>
        ${badgeMarkup}
        ${textBlock({
            x: x + 32,
            y: titleY,
            lines: [title],
            fontSize: titleSize,
            fill: COLORS.ink,
            weight: 700,
            family: mono ? FONT_MONO : FONT_HEAD,
        })}
        ${textBlock({
            x: x + 32,
            y: titleY + 44,
            lines,
            fontSize: lineSize,
            fill: COLORS.muted,
            weight: 500,
            family: mono ? FONT_MONO : FONT_SANS,
        })}
    </g>`;
}

function noteCard({ x, y, w, h, title, bullets, accent = COLORS.gold }) {
    return `<g filter="url(#shadow)">
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        <circle cx="${x + 30}" cy="${y + 34}" r="10" fill="${accent}"/>
        ${textBlock({
            x: x + 52,
            y: y + 44,
            lines: [title],
            fontSize: 28,
            fill: COLORS.ink,
            weight: 700,
            family: FONT_HEAD,
        })}
        ${bullets
            .map(
                (bullet, index) =>
                    `${textBlock({
                        x: x + 36,
                        y: y + 92 + index * 38,
                        lines: [`${index + 1}. ${bullet}`],
                        fontSize: 22,
                        fill: COLORS.muted,
                        weight: 500,
                    })}`,
            )
            .join("")}
    </g>`;
}

function tableCard({ x, y, w, h, name, fields, accent = COLORS.navy }) {
    const lineHeight = 28;
    return `<g filter="url(#shadow)">
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="${w}" height="54" rx="0" fill="${accent}"/>
        <rect x="${x}" y="${y + 30}" width="${w}" height="24" fill="${accent}"/>
        ${textBlock({
            x: x + 24,
            y: y + 38,
            lines: [name],
            fontSize: 24,
            fill: COLORS.white,
            weight: 700,
            family: FONT_MONO,
        })}
        ${fields
            .map(
                (field, index) =>
                    `${index > 0 ? `<line x1="${x + 22}" y1="${y + 72 + index * lineHeight}" x2="${x + w - 22}" y2="${y + 72 + index * lineHeight}" stroke="${COLORS.grid}" stroke-width="1.5"/>` : ""}
                    ${textBlock({
                        x: x + 24,
                        y: y + 94 + index * lineHeight,
                        lines: [field],
                        fontSize: 18,
                        fill: index === 0 ? COLORS.ink : COLORS.muted,
                        weight: index === 0 ? 700 : 500,
                        family: FONT_MONO,
                    })}`,
            )
            .join("")}
    </g>`;
}

function arrow({ x1, y1, x2, y2, color = COLORS.navy, width = 5, dashed = false, label, labelX, labelY }) {
    return `<g>
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${width}" stroke-linecap="round" ${dashed ? 'stroke-dasharray="10 8"' : ""} marker-end="url(#arrow-${color.slice(1)})"/>
        ${label
            ? textBlock({
                  x: labelX ?? (x1 + x2) / 2,
                  y: labelY ?? (y1 + y2) / 2 - 12,
                  lines: [label],
                  fontSize: 20,
                  fill: color,
                  weight: 700,
                  anchor: "middle",
              })
            : ""}
    </g>`;
}

function elbowArrow({ points, color = COLORS.navy, width = 5, label, labelX, labelY, dashed = false }) {
    const polyline = points.map((point) => `${point[0]},${point[1]}`).join(" ");
    const end = points[points.length - 1];
    return `<g>
        <polyline points="${polyline}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" ${dashed ? 'stroke-dasharray="10 8"' : ""} marker-end="url(#arrow-${color.slice(1)})"/>
        ${label
            ? textBlock({
                  x: labelX ?? end[0],
                  y: labelY ?? end[1] - 12,
                  lines: [label],
                  fontSize: 20,
                  fill: color,
                  weight: 700,
                  anchor: "middle",
              })
            : ""}
    </g>`;
}

function lane({ x, y, w, h, title, accent }) {
    return `<g>
        ${pill({ x, y, w, h: 42, label: title, fill: accent, size: 20 })}
        <line x1="${x + w / 2}" y1="${y + 52}" x2="${x + w / 2}" y2="${h}" stroke="${COLORS.grid}" stroke-width="2.5" opacity="0.9"/>
    </g>`;
}

function metricCard({ x, y, w, h, value, label, accent = COLORS.cherry }) {
    return `<g filter="url(#shadow)">
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="${w}" height="10" rx="0" fill="${accent}"/>
        ${textBlock({
            x: x + 24,
            y: y + 62,
            lines: [value],
            fontSize: 38,
            fill: COLORS.ink,
            weight: 700,
            family: FONT_HEAD,
        })}
        ${textBlock({
            x: x + 24,
            y: y + 98,
            lines: [label],
            fontSize: 22,
            fill: COLORS.muted,
            weight: 500,
        })}
    </g>`;
}

function browserMock({ x, y, w, h, title, accent, tags = [], content = "" }) {
    return `<g filter="url(#shadow)">
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="${w}" height="54" rx="0" fill="${COLORS.sandSoft}"/>
        <rect x="${x}" y="${y + 28}" width="${w}" height="26" fill="${COLORS.sandSoft}"/>
        <circle cx="${x + 28}" cy="${y + 28}" r="7" fill="${COLORS.cherry}"/>
        <circle cx="${x + 50}" cy="${y + 28}" r="7" fill="${COLORS.gold}"/>
        <circle cx="${x + 72}" cy="${y + 28}" r="7" fill="${COLORS.sage}"/>
        ${textBlock({
            x: x + 104,
            y: y + 35,
            lines: [title],
            fontSize: 22,
            fill: COLORS.ink,
            weight: 700,
            family: FONT_HEAD,
        })}
        ${tags
            .map((tag, index) =>
                pill({
                    x: x + 24 + index * 118,
                    y: y + 74,
                    w: 104,
                    h: 30,
                    label: tag.label,
                    fill: tag.fill ?? accent,
                    size: 16,
                }),
            )
            .join("")}
        ${content}
    </g>`;
}

function sparkline(points, { x, y, w, h, color }) {
    const max = Math.max(...points);
    const min = Math.min(...points);
    const coords = points
        .map((point, index) => {
            const px = x + (index / (points.length - 1)) * w;
            const py = y + h - ((point - min) / Math.max(1, max - min)) * h;
            return `${px},${py}`;
        })
        .join(" ");
    return `<polyline points="${coords}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>`;
}

function defs() {
    const marker = (color) => `<marker id="arrow-${color.slice(1)}" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
        <path d="M0,0 L12,6 L0,12 Z" fill="${color}"/>
    </marker>`;

    return `<defs>
        <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="${COLORS.grid}" stroke-width="1"/>
        </pattern>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="160%">
            <feDropShadow dx="0" dy="16" stdDeviation="18" flood-color="#312418" flood-opacity="0.11"/>
        </filter>
        <linearGradient id="hero-wash" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#fff7f0"/>
            <stop offset="55%" stop-color="#f7f2ea"/>
            <stop offset="100%" stop-color="#f1ebe1"/>
        </linearGradient>
        <radialGradient id="bloom-a" cx="18%" cy="14%" r="45%">
            <stop offset="0%" stop-color="#f5d7db" stop-opacity="0.95"/>
            <stop offset="100%" stop-color="#f5d7db" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="bloom-b" cx="90%" cy="18%" r="38%">
            <stop offset="0%" stop-color="#d9ecef" stop-opacity="0.95"/>
            <stop offset="100%" stop-color="#d9ecef" stop-opacity="0"/>
        </radialGradient>
        ${[
            COLORS.cherry,
            COLORS.navy,
            COLORS.teal,
            COLORS.sage,
            COLORS.gold,
            COLORS.plum,
            COLORS.success,
            COLORS.warning,
            COLORS.danger,
        ]
            .map(marker)
            .join("")}
    </defs>`;
}

function baseFigure(figure, content) {
    const { width, height } = figure.size;
    const chipWidth = Math.max(170, figure.section.length * 26);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
        ${defs()}
        <rect width="${width}" height="${height}" fill="url(#hero-wash)"/>
        <rect width="${width}" height="${height}" fill="url(#grid)" opacity="0.72"/>
        <circle cx="${Math.round(width * 0.18)}" cy="${Math.round(height * 0.12)}" r="${Math.round(height * 0.26)}" fill="url(#bloom-a)"/>
        <circle cx="${Math.round(width * 0.88)}" cy="${Math.round(height * 0.18)}" r="${Math.round(height * 0.23)}" fill="url(#bloom-b)"/>
        ${pill({ x: 80, y: 56, w: chipWidth, h: 40, label: figure.section, fill: COLORS.cherry, size: 19 })}
        ${textBlock({
            x: 80,
            y: 166,
            lines: [figure.headline],
            fontSize: width > 1800 ? 68 : 56,
            fill: COLORS.ink,
            weight: 700,
            family: FONT_HEAD,
        })}
        ${textBlock({
            x: 80,
            y: width > 1800 ? 216 : 208,
            lines: [figure.subhead],
            fontSize: 26,
            fill: COLORS.muted,
            weight: 500,
            family: FONT_SANS,
        })}
        ${content}
    </svg>`;
}

function renderPlaceholder(figure) {
    return baseFigure(
        figure,
        card({
            x: figure.size.width * 0.16,
            y: figure.size.height * 0.38,
            w: figure.size.width * 0.68,
            h: figure.size.height * 0.24,
            title: figure.caption,
            lines: ["renderer pending"],
            accent: COLORS.cherry,
            fill: COLORS.panel,
        }),
    );
}

function renderSystemLayers(figure) {
    const layers = [
        {
            title: "感知层",
            accent: COLORS.teal,
            fill: COLORS.tealSoft,
            chips: ["STM32H743", "SHT31", "MH-Z19B", "ADXL345", "ATECC608A", "ESP8266 / SX1278"],
        },
        {
            title: "接入层",
            accent: COLORS.navy,
            fill: COLORS.blueSoft,
            chips: ["HTTPS / LoRa", "设备认证", "签名信封", "批次标识", "边缘缓冲"],
        },
        {
            title: "服务层",
            accent: COLORS.plum,
            fill: "#e9e8f7",
            chips: ["验签", "canonical_hash", "品质评分", "告警中心", "Trace / Admin API"],
        },
        {
            title: "存证层",
            accent: COLORS.sage,
            fill: COLORS.greenSoft,
            chips: ["PostgreSQL", "Anchor Worker", "Receipt", "EVM 合约", "公开验证"],
        },
    ];

    const rows = layers
        .map((layer, index) => {
            const y = 282 + index * 235;
            const chips = layer.chips
                .map((label, chipIndex) => {
                    const col = chipIndex % 3;
                    const row = Math.floor(chipIndex / 3);
                    return pill({
                        x: 430 + col * 300,
                        y: y + 42 + row * 72,
                        w: 246,
                        h: 50,
                        label,
                        fill: COLORS.white,
                        textFill: COLORS.ink,
                        size: 21,
                        mono: /hash|API|Worker|EVM|STM32|SHT31|MH-Z19B|ADXL345|ATECC608A|ESP8266/.test(label),
                    });
                })
                .join("");

            return `<g filter="url(#shadow)">
                <rect x="90" y="${y}" width="1650" height="180" rx="0" fill="${layer.fill}" stroke="${COLORS.border}" stroke-width="2"/>
                <rect x="116" y="${y + 24}" width="240" height="132" rx="0" fill="${layer.accent}"/>
                ${textBlock({
                    x: 236,
                    y: y + 102,
                    lines: [layer.title],
                    fontSize: 40,
                    fill: COLORS.white,
                    weight: 700,
                    family: FONT_HEAD,
                    anchor: "middle",
                })}
                ${chips}
            </g>`;
        })
        .join("");

    const flows = [0, 1, 2]
        .map((index) =>
            arrow({
                x1: 915,
                y1: 462 + index * 235,
                x2: 915,
                y2: 500 + index * 235,
                color: COLORS.navy,
                width: 8,
            }),
        )
        .join("");

    const actors = ["管理员", "监管员", "消费者"]
        .map((label, index) =>
            pill({
                x: 1826,
                y: 398 + index * 90,
                w: 210,
                h: 48,
                label,
                fill: [COLORS.blueSoft, COLORS.amberSoft, COLORS.roseSoft][index],
                textFill: COLORS.ink,
                size: 22,
            }),
        )
        .join("");

    const side = `<g filter="url(#shadow)">
        <rect x="1790" y="312" width="310" height="750" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${textBlock({ x: 1850, y: 392, lines: ["访问角色"], fontSize: 40, fill: COLORS.ink, weight: 700, family: FONT_HEAD })}
        ${actors}
        ${textBlock({
            x: 1840,
            y: 722,
            lines: ["上行链路", "采样 -> 签名 -> 上传", "", "下行链路", "查询 -> 展示 -> 验证"],
            fontSize: 24,
            fill: COLORS.muted,
            weight: 500,
        })}
    </g>
    ${arrow({ x1: 1748, y1: 735, x2: 1790, y2: 735, color: COLORS.cherry, width: 7 })}
    ${arrow({ x1: 1790, y1: 834, x2: 1748, y2: 834, color: COLORS.teal, width: 7 })}`;

    const footer = noteCard({
        x: 94,
        y: 1280,
        w: 880,
        h: 124,
        title: "设计重点",
        bullets: ["设备侧先签名，再进入服务层验签", "链上仅写入哈希与回执，降低成本", "公开查询与运维后台共享同一可信数据源"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${rows}${flows}${side}${footer}`);
}

function renderDataFlow(figure) {
    const ingest = [
        ["S1", "采样节点", COLORS.teal, "传感采样 / 批次归属"],
        ["S2", "签名封装", COLORS.navy, "ATECC608A / envelope"],
        ["S3", "无线发送", COLORS.plum, "ESP8266 / SX1278"],
        ["S4", "接入验签", COLORS.navy, "FastAPI / canonicalize"],
        ["S5", "业务处理", COLORS.gold, "评分 / 告警 / 聚合"],
        ["S6", "锚定引擎", COLORS.cherry, "adapter / worker"],
        ["S7", "链上存证", COLORS.sage, "EVM / receipt"],
    ];
    const query = [
        ["Q1", "扫码查询", COLORS.cherry, "批次 ID / 二维码"],
        ["Q2", "公开接口", COLORS.navy, "GET /v1/public/trace"],
        ["Q3", "查询聚合", COLORS.plum, "质量 / 状态 / 哈希"],
        ["Q4", "前端展示", COLORS.teal, "时间线 / 指标 / 曲线"],
        ["Q5", "独立验证", COLORS.sage, "tx_hash / verifyAnchor"],
    ];

    const topCards = ingest
        .map(([step, title, accent, caption], index) => {
            const x = 94 + index * 294;
            return card({
                x,
                y: 302,
                w: 262,
                h: 156,
                title,
                lines: [caption],
                accent,
                fill: COLORS.panel,
                badge: step,
                titleSize: 32,
                lineSize: 22,
            });
        })
        .join("");

    const topArrows = ingest
        .slice(0, -1)
        .map((_, index) =>
            arrow({
                x1: 356 + index * 294,
                y1: 380,
                x2: 386 + index * 294,
                y2: 380,
                color: COLORS.navy,
                width: 6,
            }),
        )
        .join("");

    const bottomCards = query
        .map(([step, title, accent, caption], index) => {
            const x = 190 + index * 370;
            return card({
                x,
                y: 808,
                w: 320,
                h: 150,
                title,
                lines: [caption],
                accent,
                badge: step,
                titleSize: 32,
                lineSize: 22,
            });
        })
        .join("");

    const bottomArrows = query
        .slice(0, -1)
        .map((_, index) =>
            arrow({
                x1: 510 + index * 370,
                y1: 882,
                x2: 560 + index * 370,
                y2: 882,
                color: COLORS.navy,
                width: 6,
            }),
        )
        .join("");

    const diagonal = arrow({
        x1: 1470,
        y1: 458,
        x2: 980,
        y2: 806,
        color: COLORS.teal,
        width: 6,
        label: "查询阶段回读数据库与链上回执",
        labelX: 1260,
        labelY: 646,
    });

    const band = `<g filter="url(#shadow)">
        <rect x="94" y="558" width="2010" height="44" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${textBlock({
            x: 120,
            y: 589,
            lines: ["上行链路先完成采集、验签、评分与锚定，再将可信结果暴露给查询端"],
            fontSize: 22,
            fill: COLORS.muted,
            weight: 600,
        })}
    </g>`;

    const closure = noteCard({
        x: 1680,
        y: 1054,
        w: 418,
        h: 212,
        title: "完整性闭环",
        bullets: ["设备先签名，入口先验签", "服务层生成唯一 canonical_hash", "链上回执与公开查询共享同一证据"],
        accent: COLORS.sage,
    });

    return baseFigure(figure, `${topCards}${topArrows}${band}${bottomCards}${bottomArrows}${diagonal}${closure}`);
}

function renderCoreEr(figure) {
    const tables = [
        tableCard({
            x: 74,
            y: 250,
            w: 300,
            h: 270,
            name: "devices",
            accent: COLORS.teal,
            fields: ["PK  id", "UK  device_id", "status", "current_key_id", "last_seen_at", "registered_at"],
        }),
        tableCard({
            x: 498,
            y: 228,
            w: 360,
            h: 350,
            name: "events",
            accent: COLORS.cherry,
            fields: ["PK  id", "FK  device_id", "batch_id", "canonical_hash  UK", "ingest_status", "quality_grade", "recorded_at"],
        }),
        tableCard({
            x: 954,
            y: 246,
            w: 302,
            h: 258,
            name: "ingest_requests",
            accent: COLORS.navy,
            fields: ["PK  id", "FK  event_id", "idempotency_key  UK", "signature_ok", "request_at"],
        }),
        tableCard({
            x: 1278,
            y: 152,
            w: 248,
            h: 220,
            name: "quality_results",
            accent: COLORS.gold,
            fields: ["PK  id", "FK  event_id", "score", "grade", "calculated_at"],
        }),
        tableCard({
            x: 1004,
            y: 592,
            w: 312,
            h: 230,
            name: "anchor_submissions",
            accent: COLORS.plum,
            fields: ["PK  id", "FK  event_id", "transaction_hash", "status", "submitted_at"],
        }),
        tableCard({
            x: 1348,
            y: 564,
            w: 236,
            h: 220,
            name: "anchor_receipts",
            accent: COLORS.sage,
            fields: ["PK  id", "FK  event_id", "block_number", "anchored_at", "confirmations"],
        }),
    ].join("");

    const links = [
        arrow({ x1: 374, y1: 386, x2: 498, y2: 386, color: COLORS.teal, width: 5, label: "1 : N", labelY: 350 }),
        arrow({ x1: 858, y1: 378, x2: 954, y2: 378, color: COLORS.navy, width: 5, label: "1 : 1", labelY: 346 }),
        arrow({ x1: 858, y1: 304, x2: 1278, y2: 262, color: COLORS.gold, width: 5, label: "1 : 1", labelX: 1086, labelY: 250 }),
        elbowArrow({
            points: [
                [678, 578],
                [678, 706],
                [1004, 706],
            ],
            color: COLORS.plum,
            width: 5,
            label: "1 : N",
            labelX: 828,
            labelY: 666,
        }),
        arrow({ x1: 1316, y1: 706, x2: 1348, y2: 706, color: COLORS.sage, width: 5, label: "1 : N", labelY: 674 }),
    ].join("");

    const note = noteCard({
        x: 92,
        y: 612,
        w: 820,
        h: 182,
        title: "建模主线",
        bullets: ["events 是全链路核心事实表，贯穿采集、评分与锚定", "ingest_requests 负责请求级幂等与签名入库痕迹", "anchor_submissions 与 anchor_receipts 拆分提交态与确认态，便于恢复"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${tables}${links}${note}`);
}

function renderStatusMachine(figure) {
    const states = [
        card({ x: 120, y: 350, w: 420, h: 150, title: "RECEIVED", lines: ["已接收 / 等待锚定"], accent: COLORS.navy, fill: COLORS.blueSoft, mono: true }),
        card({ x: 860, y: 350, w: 470, h: 150, title: "ANCHORING", lines: ["提交锚定 / 等待确认"], accent: COLORS.teal, fill: COLORS.tealSoft, mono: true }),
        card({ x: 1610, y: 280, w: 420, h: 150, title: "ANCHORED", lines: ["成功终态"], accent: COLORS.success, fill: COLORS.greenSoft, mono: true }),
        card({ x: 860, y: 810, w: 470, h: 150, title: "FAILED_RETRYING", lines: ["可恢复失败 / 等待重试"], accent: COLORS.warning, fill: COLORS.amberSoft, mono: true }),
        card({ x: 120, y: 880, w: 420, h: 150, title: "DEAD_LETTER", lines: ["不可恢复失败"], accent: COLORS.danger, fill: COLORS.roseSoft, mono: true }),
    ].join("");

    const arrows = [
        arrow({ x1: 540, y1: 425, x2: 860, y2: 425, color: COLORS.navy, width: 7, label: "开始锚定", labelY: 394 }),
        arrow({ x1: 1330, y1: 398, x2: 1610, y2: 355, color: COLORS.success, width: 7, label: "确认成功", labelX: 1480, labelY: 330 }),
        arrow({ x1: 1095, y1: 500, x2: 1095, y2: 810, color: COLORS.warning, width: 7, label: "异常 / timeout", labelX: 1200, labelY: 662 }),
        arrow({ x1: 860, y1: 912, x2: 540, y2: 955, color: COLORS.danger, width: 7, label: "retry 次数耗尽", labelX: 684, labelY: 900 }),
        arrow({ x1: 330, y1: 880, x2: 330, y2: 500, color: COLORS.navy, width: 7, label: "管理员 requeue", labelX: 190, labelY: 704 }),
        arrow({ x1: 540, y1: 426, x2: 1600, y2: 720, color: COLORS.teal, width: 6, dashed: true, label: "命中幂等旁路时直接返回既有结果", labelX: 1180, labelY: 650 }),
    ].join("");

    const aside = noteCard({
        x: 1630,
        y: 640,
        w: 446,
        h: 228,
        title: "幂等旁路",
        bullets: ["命中 idempotency_key 直接返回既有 event_id", "命中 canonical_hash 冲突时复用已有事件", "避免重复进入状态机造成链上重复提交"],
        accent: COLORS.teal,
    });

    const legend = `<g filter="url(#shadow)">
        <rect x="1280" y="1068" width="820" height="136" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${textBlock({ x: 1320, y: 1120, lines: ["状态含义"], fontSize: 30, fill: COLORS.ink, weight: 700, family: FONT_HEAD })}
        ${[
            ["处理中", COLORS.navy],
            ["等待确认", COLORS.teal],
            ["成功终态", COLORS.success],
            ["可重试", COLORS.warning],
            ["失败终态", COLORS.danger],
        ]
            .map(
                ([label, color], index) =>
                    `${pill({ x: 1320 + index * 150, y: 1142, w: 120, h: 34, label, fill: color, size: 16 })}`,
            )
            .join("")}
    </g>`;

    return baseFigure(figure, `${states}${arrows}${aside}${legend}`);
}

function renderSecurityArchitecture(figure) {
    const columns = [
        card({
            x: 84,
            y: 268,
            w: 300,
            h: 470,
            title: "设备身份",
            lines: ["ATECC608A 私钥", "device_id / key_id", "签名信封", "防伪造源头"],
            accent: COLORS.cherry,
            fill: COLORS.roseSoft,
        }),
        card({
            x: 444,
            y: 268,
            w: 300,
            h: 470,
            title: "接入控制",
            lines: ["HTTPS", "JWT 会话", "RBAC", "Idempotency-Key"],
            accent: COLORS.navy,
            fill: COLORS.blueSoft,
        }),
        card({
            x: 804,
            y: 268,
            w: 300,
            h: 470,
            title: "服务防线",
            lines: ["ECDSA 验签", "canonical_hash", "质量评分", "告警联动"],
            accent: COLORS.teal,
            fill: COLORS.tealSoft,
        }),
        card({
            x: 1164,
            y: 268,
            w: 300,
            h: 470,
            title: "审计存证",
            lines: ["审计日志", "anchor_submission", "anchor_receipt", "EVM 公开验证"],
            accent: COLORS.sage,
            fill: COLORS.greenSoft,
        }),
    ].join("");

    const top = `<g>
        ${pill({ x: 110, y: 178, w: 118, h: 34, label: "管理员", fill: COLORS.blueSoft, textFill: COLORS.ink, size: 17 })}
        ${pill({ x: 242, y: 178, w: 118, h: 34, label: "监管员", fill: COLORS.amberSoft, textFill: COLORS.ink, size: 17 })}
        ${pill({ x: 374, y: 178, w: 118, h: 34, label: "消费者", fill: COLORS.roseSoft, textFill: COLORS.ink, size: 17 })}
        ${textBlock({ x: 534, y: 204, lines: ["统一通过前端门户与服务 API 访问可信数据"], fontSize: 22, fill: COLORS.muted, weight: 600 })}
    </g>`;

    const links = [
        arrow({ x1: 384, y1: 502, x2: 444, y2: 502, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 744, y1: 502, x2: 804, y2: 502, color: COLORS.navy, width: 6 }),
        arrow({ x1: 1104, y1: 502, x2: 1164, y2: 502, color: COLORS.teal, width: 6 }),
    ].join("");

    const footer = noteCard({
        x: 430,
        y: 768,
        w: 740,
        h: 120,
        title: "安全原则",
        bullets: ["身份在设备侧建立，权限在平台侧收口", "所有可信写入都以验签与哈希校验为前提", "链上回执为公开查询与监管稽核提供外部证据"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${top}${columns}${links}${footer}`);
}

function renderStm32Minimal(figure) {
    const center = card({
        x: 590,
        y: 244,
        w: 420,
        h: 300,
        title: "STM32H743",
        lines: ["Cortex-M7 / 480 MHz", "主控核心", "时序与总线调度"],
        accent: COLORS.navy,
        fill: COLORS.blueSoft,
    });

    const parts = [
        card({ x: 118, y: 252, w: 250, h: 124, title: "8 MHz HSE", lines: ["主时钟输入"], accent: COLORS.gold, fill: COLORS.amberSoft }),
        card({ x: 118, y: 438, w: 250, h: 124, title: "NRST", lines: ["复位网络"], accent: COLORS.cherry, fill: COLORS.roseSoft }),
        card({ x: 1180, y: 252, w: 260, h: 124, title: "SWD", lines: ["下载 / 调试"], accent: COLORS.teal, fill: COLORS.tealSoft }),
        card({ x: 1180, y: 438, w: 260, h: 124, title: "BOOT0", lines: ["启动模式选择"], accent: COLORS.plum, fill: COLORS.lilacSoft }),
        card({ x: 512, y: 626, w: 250, h: 124, title: "3.3 V", lines: ["主供电"], accent: COLORS.sage, fill: COLORS.greenSoft }),
        card({ x: 838, y: 626, w: 260, h: 124, title: "去耦阵列", lines: ["多点旁路"], accent: COLORS.gold, fill: COLORS.amberSoft }),
    ].join("");

    const links = [
        arrow({ x1: 368, y1: 314, x2: 590, y2: 314, color: COLORS.gold, width: 6 }),
        arrow({ x1: 368, y1: 500, x2: 590, y2: 500, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 1010, y1: 314, x2: 1180, y2: 314, color: COLORS.teal, width: 6 }),
        arrow({ x1: 1010, y1: 500, x2: 1180, y2: 500, color: COLORS.plum, width: 6 }),
        arrow({ x1: 638, y1: 544, x2: 638, y2: 626, color: COLORS.sage, width: 6 }),
        arrow({ x1: 924, y1: 544, x2: 924, y2: 626, color: COLORS.gold, width: 6 }),
    ].join("");

    const note = `<g filter="url(#shadow)">
        <rect x="188" y="786" width="1224" height="90" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${textBlock({
            x: 238,
            y: 840,
            lines: ["最小系统由主控、时钟、复位、调试与稳定供电五部分构成，为后续多传感与通信模块提供统一底座"],
            fontSize: 24,
            fill: COLORS.muted,
            weight: 600,
        })}
    </g>`;

    return baseFigure(figure, `${center}${parts}${links}${note}`);
}

function renderSensorBuses(figure) {
    const center = card({
        x: 622,
        y: 280,
        w: 340,
        h: 210,
        title: "STM32H743",
        lines: ["I2C1 / I2C2", "UART4 / USART3", "SPI1 + DIO0"],
        accent: COLORS.navy,
        fill: COLORS.blueSoft,
    });

    const nodes = [
        { x: 140, y: 210, w: 240, h: 120, title: "SHT31", lines: ["温湿度"], accent: COLORS.teal, fill: COLORS.tealSoft },
        { x: 140, y: 380, w: 240, h: 120, title: "ADXL345", lines: ["振动 / 冲击"], accent: COLORS.plum, fill: COLORS.lilacSoft },
        { x: 138, y: 554, w: 260, h: 120, title: "MH-Z19B", lines: ["CO₂ / UART4"], accent: COLORS.gold, fill: COLORS.amberSoft },
        { x: 1100, y: 210, w: 270, h: 120, title: "ATECC608A", lines: ["安全芯片 / I2C2"], accent: COLORS.cherry, fill: COLORS.roseSoft },
        { x: 1086, y: 386, w: 284, h: 120, title: "ESP8266", lines: ["Wi-Fi / USART3"], accent: COLORS.teal, fill: COLORS.tealSoft },
        { x: 1086, y: 560, w: 284, h: 120, title: "SX1278", lines: ["LoRa / SPI1"], accent: COLORS.sage, fill: COLORS.greenSoft },
    ]
        .map((node) => card(node))
        .join("");

    const links = [
        arrow({ x1: 380, y1: 270, x2: 622, y2: 320, color: COLORS.teal, width: 6, label: "I2C1" }),
        arrow({ x1: 380, y1: 440, x2: 622, y2: 392, color: COLORS.plum, width: 6, label: "I2C1" }),
        arrow({ x1: 398, y1: 614, x2: 622, y2: 444, color: COLORS.gold, width: 6, label: "UART4", labelX: 492, labelY: 526 }),
        arrow({ x1: 962, y1: 320, x2: 1100, y2: 270, color: COLORS.cherry, width: 6, label: "I2C2" }),
        arrow({ x1: 962, y1: 392, x2: 1086, y2: 446, color: COLORS.teal, width: 6, label: "USART3" }),
        arrow({ x1: 962, y1: 444, x2: 1086, y2: 620, color: COLORS.sage, width: 6, label: "SPI1 + DIO0", labelX: 1080, labelY: 534 }),
    ].join("");

    const footer = noteCard({
        x: 430,
        y: 746,
        w: 752,
        h: 112,
        title: "总线划分",
        bullets: ["环境感知集中到 I2C 与 UART", "无线通信独立占用串口 / SPI", "安全芯片单独挂载，避免与普通外设混用"],
        accent: COLORS.navy,
    });

    return baseFigure(figure, `${center}${nodes}${links}${footer}`);
}

function renderSecureElementSigning(figure) {
    const left = `<g>
        ${card({ x: 90, y: 274, w: 340, h: 280, title: "MCU ↔ ATECC608A", lines: ["SCL / SDA", "WAKE", "3.3 V", "私钥不可导出"], accent: COLORS.cherry, fill: COLORS.roseSoft })}
        ${pill({ x: 196, y: 580, w: 128, h: 36, label: "I2C2", fill: COLORS.cherry, size: 18 })}
    </g>`;

    const steps = [
        ["01", "采样帧", "temperature / humidity / co₂ / shock"],
        ["02", "摘要计算", "挑选参与签名的关键字段"],
        ["03", "硬件签名", "ATECC608A 内部完成 ECDSA"],
        ["04", "DER 编码", "signature / key_id / algorithm"],
        ["05", "信封输出", "payload + signature_envelope"],
    ]
        .map(([step, title, desc], index) =>
            card({
                x: 540 + (index % 2) * 450,
                y: 280 + Math.floor(index / 2) * 176,
                w: 360,
                h: 128,
                title,
                lines: [desc],
                accent: [COLORS.navy, COLORS.gold, COLORS.cherry, COLORS.plum, COLORS.sage][index],
                badge: step,
            }),
        )
        .join("");

    const arrows = [
        arrow({ x1: 430, y1: 416, x2: 540, y2: 344, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 900, y1: 344, x2: 990, y2: 344, color: COLORS.navy, width: 6 }),
        arrow({ x1: 720, y1: 408, x2: 720, y2: 456, color: COLORS.gold, width: 6 }),
        arrow({ x1: 1170, y1: 408, x2: 1170, y2: 456, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 900, y1: 520, x2: 990, y2: 520, color: COLORS.plum, width: 6 }),
    ].join("");

    const footer = noteCard({
        x: 538,
        y: 670,
        w: 858,
        h: 156,
        title: "设备侧签名价值",
        bullets: ["签名发生在安全芯片内部，私钥不暴露给 MCU 与网络侧", "信封同时携带 payload、algorithm 与 key_id，便于后端验签与密钥轮换", "后端只接受能通过设备级验签的采样数据"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${left}${steps}${arrows}${footer}`);
}

function renderNetworkTopology(figure) {
    const scenes = [
        card({ x: 86, y: 286, w: 240, h: 116, title: "果园采摘点", lines: ["LoRa 优先"], accent: COLORS.sage, fill: COLORS.greenSoft }),
        card({ x: 86, y: 448, w: 240, h: 116, title: "冷库 / 中转仓", lines: ["Wi-Fi 直连"], accent: COLORS.teal, fill: COLORS.tealSoft }),
        card({ x: 86, y: 610, w: 240, h: 116, title: "冷链运输", lines: ["Wi-Fi 失败转 LoRa"], accent: COLORS.gold, fill: COLORS.amberSoft }),
    ].join("");

    const device = card({
        x: 448,
        y: 368,
        w: 310,
        h: 220,
        title: "现场采集终端",
        lines: ["STM32H743", "ESP8266", "SX1278", "signature_envelope"],
        accent: COLORS.cherry,
        fill: COLORS.roseSoft,
    });

    const wifi = card({
        x: 890,
        y: 250,
        w: 240,
        h: 116,
        title: "Wi-Fi AP",
        lines: ["HTTPS 上传"],
        accent: COLORS.teal,
        fill: COLORS.tealSoft,
    });
    const lora = card({
        x: 890,
        y: 612,
        w: 240,
        h: 116,
        title: "LoRa 网关",
        lines: ["长距备用链路"],
        accent: COLORS.sage,
        fill: COLORS.greenSoft,
    });
    const api = card({
        x: 1220,
        y: 366,
        w: 284,
        h: 126,
        title: "FastAPI 接入层",
        lines: ["验签 / 幂等 / 评分"],
        accent: COLORS.navy,
        fill: COLORS.blueSoft,
    });
    const storage = card({
        x: 1220,
        y: 544,
        w: 284,
        h: 126,
        title: "数据库与锚定",
        lines: ["PostgreSQL + EVM"],
        accent: COLORS.plum,
        fill: COLORS.lilacSoft,
    });

    const links = [
        arrow({ x1: 326, y1: 344, x2: 448, y2: 430, color: COLORS.sage, width: 6 }),
        arrow({ x1: 326, y1: 506, x2: 448, y2: 480, color: COLORS.teal, width: 6 }),
        arrow({ x1: 326, y1: 668, x2: 448, y2: 536, color: COLORS.gold, width: 6 }),
        arrow({ x1: 758, y1: 432, x2: 890, y2: 308, color: COLORS.teal, width: 6, label: "主链路" }),
        arrow({ x1: 758, y1: 522, x2: 890, y2: 670, color: COLORS.sage, width: 6, label: "备链路", labelX: 824, labelY: 624 }),
        arrow({ x1: 1130, y1: 308, x2: 1220, y2: 428, color: COLORS.teal, width: 6 }),
        arrow({ x1: 1130, y1: 670, x2: 1220, y2: 428, color: COLORS.sage, width: 6 }),
        arrow({ x1: 1362, y1: 492, x2: 1362, y2: 544, color: COLORS.navy, width: 6 }),
    ].join("");

    const footer = noteCard({
        x: 430,
        y: 746,
        w: 850,
        h: 112,
        title: "组网策略",
        bullets: ["有基础设施场景走 Wi-Fi 低时延直连", "野外与运输场景保留 LoRa 长距备份", "两条链路在服务侧统一收敛为同一验签入口"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${scenes}${device}${wifi}${lora}${api}${storage}${links}${footer}`);
}

function renderPowerManagement(figure) {
    const blocks = [
        card({ x: 84, y: 360, w: 220, h: 124, title: "5 V 输入", lines: ["USB / 适配器"], accent: COLORS.cherry, fill: COLORS.roseSoft }),
        card({ x: 354, y: 360, w: 220, h: 124, title: "输入保护", lines: ["保险丝 / TVS"], accent: COLORS.gold, fill: COLORS.amberSoft }),
        card({ x: 624, y: 360, w: 250, h: 124, title: "Buck 3.3 V", lines: ["主系统供电"], accent: COLORS.navy, fill: COLORS.blueSoft }),
        card({ x: 924, y: 220, w: 250, h: 124, title: "模拟 LDO", lines: ["传感器安静电源"], accent: COLORS.sage, fill: COLORS.greenSoft }),
        card({ x: 924, y: 500, w: 250, h: 124, title: "数字电源", lines: ["MCU / 无线 / 安全芯片"], accent: COLORS.teal, fill: COLORS.tealSoft }),
        card({ x: 1240, y: 220, w: 250, h: 124, title: "传感器组", lines: ["SHT31 / MH-Z19B / ADXL345"], accent: COLORS.sage, fill: COLORS.greenSoft }),
        card({ x: 1240, y: 500, w: 250, h: 124, title: "核心负载", lines: ["STM32 / ESP8266 / SX1278 / ATECC608A"], accent: COLORS.teal, fill: COLORS.tealSoft }),
    ].join("");

    const arrows = [
        arrow({ x1: 304, y1: 422, x2: 354, y2: 422, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 574, y1: 422, x2: 624, y2: 422, color: COLORS.gold, width: 6 }),
        elbowArrow({ points: [[874, 422], [924, 422], [924, 282]], color: COLORS.sage, width: 6, label: "低噪声支路", labelX: 1048, labelY: 382 }),
        elbowArrow({ points: [[874, 422], [924, 422], [924, 562]], color: COLORS.teal, width: 6, label: "主数字支路", labelX: 1048, labelY: 460 }),
        arrow({ x1: 1174, y1: 282, x2: 1240, y2: 282, color: COLORS.sage, width: 6 }),
        arrow({ x1: 1174, y1: 562, x2: 1240, y2: 562, color: COLORS.teal, width: 6 }),
    ].join("");

    const footer = noteCard({
        x: 190,
        y: 690,
        w: 1210,
        h: 126,
        title: "供电设计原则",
        bullets: ["入口先保护再降压，避免现场接入波动影响主控", "模拟与数字电源分离，降低传感噪声", "无线模块与安全芯片共享稳定 3.3 V 主电源，减少压降引起的异常复位"],
        accent: COLORS.navy,
    });

    return baseFigure(figure, `${blocks}${arrows}${footer}`);
}

function renderFreertosPipeline(figure) {
    const tasks = [
        { x: 120, title: "SensorTask", accent: COLORS.teal, fill: COLORS.tealSoft, lines: ["1 s 采样", "温湿度 / CO₂ / 振动"] },
        { x: 420, title: "SignTask", accent: COLORS.cherry, fill: COLORS.roseSoft, lines: ["ATECC608A 签名", "生成 envelope"] },
        { x: 720, title: "QualityTask", accent: COLORS.gold, fill: COLORS.amberSoft, lines: ["计算评分", "触发阈值告警"] },
        { x: 1020, title: "CommTask", accent: COLORS.navy, fill: COLORS.blueSoft, lines: ["Wi-Fi 主发", "LoRa 兜底上传"] },
    ]
        .map((task) =>
            card({
                x: task.x,
                y: 284,
                w: 220,
                h: 200,
                title: task.title,
                lines: task.lines,
                accent: task.accent,
                fill: task.fill,
                mono: true,
            }),
        )
        .join("");

    const queues = [
        card({ x: 252, y: 576, w: 188, h: 96, title: "sampleQueue", lines: ["原始采样"], accent: COLORS.teal, fill: COLORS.panel, titleSize: 24, lineSize: 20, mono: true }),
        card({ x: 552, y: 576, w: 188, h: 96, title: "signedQueue", lines: ["已签名帧"], accent: COLORS.cherry, fill: COLORS.panel, titleSize: 24, lineSize: 20, mono: true }),
        card({ x: 852, y: 576, w: 188, h: 96, title: "uplinkQueue", lines: ["待发载荷"], accent: COLORS.navy, fill: COLORS.panel, titleSize: 24, lineSize: 20, mono: true }),
    ].join("");

    const arrows = [
        arrow({ x1: 230, y1: 484, x2: 346, y2: 576, color: COLORS.teal, width: 6 }),
        arrow({ x1: 440, y1: 624, x2: 420, y2: 484, color: COLORS.teal, width: 6 }),
        arrow({ x1: 530, y1: 484, x2: 646, y2: 576, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 740, y1: 624, x2: 720, y2: 484, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 830, y1: 484, x2: 946, y2: 576, color: COLORS.navy, width: 6 }),
        arrow({ x1: 1040, y1: 624, x2: 1020, y2: 484, color: COLORS.navy, width: 6 }),
        arrow({ x1: 1240, y1: 384, x2: 1420, y2: 384, color: COLORS.sage, width: 6, label: "HTTPS / LoRa" }),
    ].join("");

    const right = `<g>
        ${metricCard({ x: 1320, y: 282, w: 210, h: 110, value: "1 s", label: "采样节拍", accent: COLORS.teal })}
        ${metricCard({ x: 1320, y: 416, w: 210, h: 110, value: "< 8 ms", label: "单帧签名延迟", accent: COLORS.cherry })}
        ${metricCard({ x: 1320, y: 550, w: 210, h: 110, value: "双通道", label: "上传策略", accent: COLORS.navy })}
    </g>`;

    const footer = noteCard({
        x: 132,
        y: 742,
        w: 1210,
        h: 108,
        title: "调度要点",
        bullets: ["任务之间通过队列解耦，避免重逻辑阻塞采样节拍", "签名、评分与通信各自独立，便于定位时延瓶颈", "异常上传不会阻塞下一轮采样，只影响 uplinkQueue 累积"],
        accent: COLORS.navy,
    });

    return baseFigure(figure, `${tasks}${queues}${arrows}${right}${footer}`);
}

function renderHashCanonicalization(figure) {
    const rawCard = `<g filter="url(#shadow)">
        <rect x="92" y="314" width="500" height="822" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${pill({ x: 130, y: 352, w: 142, h: 40, label: "输入事件", fill: COLORS.navy, size: 18 })}
        ${textBlock({
            x: 132,
            y: 448,
            lines: [
                "{",
                '  "device_id": "node-01",',
                '  "batch_id": "CH2026-008",',
                '  "temperature": 2.1,',
                '  "humidity": 88,',
                '  "co2": 620,',
                '  "timestamp": "2026-03-28T08:30:00+08:00",',
                '  "meta": { "location": "冷库A", "stage": "warehouse" }',
                "}",
            ],
            fontSize: 34,
            fill: COLORS.ink,
            weight: 500,
            family: FONT_MONO,
            lineGap: 1.42,
        })}
        ${textBlock({
            x: 132,
            y: 1058,
            lines: ["不同语言默认序列化差异会直接导致哈希值漂移"],
            fontSize: 24,
            fill: COLORS.muted,
            weight: 600,
        })}
    </g>`;

    const steps = [
        ["01", "字段排序", "对象键按固定次序输出", COLORS.navy],
        ["02", "时间标准化", "统一换算成 UTC ISO 8601", COLORS.plum],
        ["03", "空白裁剪", "去除无效空格与换行", COLORS.teal],
        ["04", "ASCII 转义", "非 ASCII 统一写入 \\uXXXX", COLORS.gold],
        ["05", "紧凑序列化", "使用无空格分隔符输出", COLORS.cherry],
        ["06", "SHA-256", "得到 64 位十六进制摘要", COLORS.sage],
    ]
        .map(([step, title, desc, accent], index) =>
            card({
                x: 732 + (index % 2) * 362,
                y: 374 + Math.floor(index / 2) * 192,
                w: 320,
                h: 120,
                title,
                lines: [desc],
                accent,
                badge: step,
                fill: COLORS.panel,
            }),
        )
        .join("");

    const route = [
        elbowArrow({ points: [[1052, 430], [1112, 430], [1112, 622], [1094, 622]], color: COLORS.navy, width: 6 }),
        elbowArrow({ points: [[732, 672], [672, 672], [672, 810], [732, 810]], color: COLORS.teal, width: 6 }),
        elbowArrow({ points: [[1052, 810], [1112, 810], [1112, 1002], [1094, 1002]], color: COLORS.navy, width: 6 }),
    ].join("");

    const hash = `<g filter="url(#shadow)">
        <rect x="1700" y="314" width="404" height="818" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${pill({ x: 1738, y: 352, w: 152, h: 40, label: "输出结果", fill: COLORS.sage, size: 18 })}
        ${textBlock({ x: 1740, y: 486, lines: ["canonical_hash"], fontSize: 56, fill: COLORS.ink, weight: 700, family: FONT_MONO })}
        ${textBlock({
            x: 1740,
            y: 594,
            lines: ["94f3bb18f1b0a9d...", "3e1204b7f5a6c261...", "1f8f4fd22fb6d7aa"],
            fontSize: 44,
            fill: COLORS.success,
            weight: 700,
            family: FONT_MONO,
            lineGap: 1.28,
        })}
        ${textBlock({
            x: 1740,
            y: 846,
            lines: ["一致性目标", "Python 后端 = TypeScript 前端", "相同事件 -> 相同哈希", "可直接用于幂等与链上锚定"],
            fontSize: 28,
            fill: COLORS.muted,
            weight: 600,
            lineGap: 1.45,
        })}
    </g>`;

    const footer = noteCard({
        x: 704,
        y: 1210,
        w: 860,
        h: 104,
        title: "规范化的核心价值",
        bullets: ["消除跨语言、跨平台与跨时区的哈希漂移", "让链上验证与前端自验拥有同一份内容指纹", "使相同内容天然具备可复用的幂等键"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${rawCard}${steps}${route}${hash}${footer}`);
}

function renderIdempotencySequence(figure) {
    const lanes = [
        ["客户端", COLORS.teal, 92],
        ["API / ingest", COLORS.navy, 506],
        ["ingest_requests", COLORS.teal, 930],
        ["events", COLORS.plum, 1352],
        ["响应", COLORS.sage, 1772],
    ]
        .map(([label, accent, x]) => lane({ x, y: 272, w: 260, h: 1120, title: label, accent }))
        .join("");

    const messages = [
        arrow({ x1: 220, y1: 422, x2: 636, y2: 422, color: COLORS.navy, width: 6, label: "POST /v1/events + Idempotency-Key", labelY: 390 }),
        arrow({ x1: 636, y1: 560, x2: 1060, y2: 560, color: COLORS.teal, width: 6, label: "查询 idempotency_key 是否已存在", labelY: 528 }),
        arrow({ x1: 1060, y1: 632, x2: 636, y2: 632, color: COLORS.teal, width: 6, label: "不存在 -> 继续处理", labelY: 600 }),
        arrow({ x1: 636, y1: 782, x2: 1478, y2: 782, color: COLORS.navy, width: 6, label: "生成 canonical_hash 并尝试写入 events", labelY: 748 }),
        arrow({ x1: 1478, y1: 866, x2: 636, y2: 866, color: COLORS.success, width: 6, label: "内容唯一 -> 写入成功", labelY: 834 }),
        arrow({ x1: 636, y1: 948, x2: 1060, y2: 948, color: COLORS.teal, width: 6, label: "回填 idempotency_key -> event_id", labelY: 916 }),
        arrow({ x1: 636, y1: 1048, x2: 1902, y2: 1048, color: COLORS.success, width: 6, label: "返回 201 Created", labelY: 1016 }),
        arrow({ x1: 1478, y1: 866, x2: 1060, y2: 1208, color: COLORS.gold, width: 6, label: "若 canonical_hash 冲突，复用已有 event", labelX: 1326, labelY: 1060 }),
        arrow({ x1: 1060, y1: 560, x2: 936, y2: 1160, color: COLORS.gold, width: 6, label: "若命中重复 key，直接返回既有结果", labelX: 892, labelY: 850 }),
    ].join("");

    const notes = [
        noteCard({
            x: 80,
            y: 1182,
            w: 860,
            h: 190,
            title: "重复请求分支",
            bullets: ["同一 idempotency_key 的重放请求直接返回既有 event_id", "客户端可安全重试，避免网络抖动导致多次入库", "请求级幂等专门防重放"],
            accent: COLORS.teal,
        }),
        noteCard({
            x: 1040,
            y: 1182,
            w: 980,
            h: 190,
            title: "并发安全要点",
            bullets: ["同一内容如果以不同 key 重复上传，由 canonical_hash UNIQUE 收口", "先写 events 再回填 ingest_requests，避免先查后写的竞态窗口", "两层幂等分别覆盖重放请求与重复内容"],
            accent: COLORS.cherry,
        }),
    ].join("");

    return baseFigure(figure, `${lanes}${messages}${notes}`);
}

function renderSignatureVerification(figure) {
    const left = card({
        x: 90,
        y: 292,
        w: 300,
        h: 360,
        title: "signature_envelope",
        lines: ["payload", "signature", "algorithm", "key_id"],
        accent: COLORS.cherry,
        fill: COLORS.roseSoft,
        mono: true,
    });

    const steps = [
        ["01", "解析信封", "拆出 payload / signature / key_id", COLORS.navy],
        ["02", "加载公钥", "按 key_id 读取设备在册公钥", COLORS.teal],
        ["03", "复建消息", "按约定字段顺序生成 digest", COLORS.gold],
        ["04", "ECDSA 验签", "通过则进入可信写入链路", COLORS.cherry],
    ]
        .map(([step, title, desc, accent], index) =>
            card({
                x: 508,
                y: 266 + index * 146,
                w: 412,
                h: 110,
                title,
                lines: [desc],
                accent,
                badge: step,
            }),
        )
        .join("");

    const right = [
        card({
            x: 1110,
            y: 316,
            w: 360,
            h: 180,
            title: "Accepted",
            lines: ["写入 events / ingest_requests", "继续评分与锚定"],
            accent: COLORS.success,
            fill: COLORS.greenSoft,
            mono: true,
        }),
        card({
            x: 1110,
            y: 554,
            w: 360,
            h: 180,
            title: "Rejected",
            lines: ["返回 401 / 422", "审计保留失败原因"],
            accent: COLORS.danger,
            fill: COLORS.roseSoft,
            mono: true,
        }),
    ].join("");

    const arrows = [
        arrow({ x1: 390, y1: 470, x2: 508, y2: 322, color: COLORS.cherry, width: 6 }),
        arrow({ x1: 920, y1: 322, x2: 1110, y2: 406, color: COLORS.success, width: 6, label: "验证通过", labelX: 1018, labelY: 348 }),
        arrow({ x1: 920, y1: 614, x2: 1110, y2: 644, color: COLORS.danger, width: 6, label: "验证失败", labelX: 1012, labelY: 590 }),
    ].join("");

    const audit = noteCard({
        x: 452,
        y: 764,
        w: 916,
        h: 116,
        title: "审计留痕",
        bullets: ["成功与失败都记录 key_id、event_id、原因码", "失败事件不会进入评分与锚定链路", "验签服务是整套可信链路的第一道硬门槛"],
        accent: COLORS.navy,
    });

    return baseFigure(figure, `${left}${steps}${right}${arrows}${audit}`);
}

function renderAnchorSequence(figure) {
    const lanes = [
        ["anchor_worker", COLORS.navy, 90],
        ["数据库", COLORS.plum, 500],
        ["AnchorAdapter", COLORS.teal, 910],
        ["EVM 节点", COLORS.sage, 1320],
        ["retry_worker", COLORS.gold, 1730],
    ]
        .map(([label, accent, x]) => lane({ x, y: 280, w: 250, h: 1120, title: label, accent }))
        .join("");

    const messages = [
        arrow({ x1: 215, y1: 430, x2: 625, y2: 430, color: COLORS.navy, width: 6, label: "查询 RECEIVED / FAILED_RETRYING 事件", labelY: 398 }),
        arrow({ x1: 625, y1: 516, x2: 215, y2: 516, color: COLORS.plum, width: 6, label: "返回待锚定事件", labelY: 486 }),
        arrow({ x1: 215, y1: 610, x2: 625, y2: 610, color: COLORS.navy, width: 6, label: "写入 PENDING submission", labelY: 580 }),
        arrow({ x1: 215, y1: 706, x2: 1035, y2: 706, color: COLORS.teal, width: 6, label: "adapter.anchor_event()", labelY: 676 }),
        arrow({ x1: 1035, y1: 818, x2: 1445, y2: 818, color: COLORS.teal, width: 6, label: "提交交易 / 获取 tx_hash", labelY: 788 }),
        arrow({ x1: 1445, y1: 900, x2: 1035, y2: 900, color: COLORS.sage, width: 6, label: "返回 tx_hash", labelY: 870 }),
        arrow({ x1: 1035, y1: 980, x2: 625, y2: 980, color: COLORS.plum, width: 6, label: "持久化 transaction_hash + status=PENDING", labelY: 950 }),
        arrow({ x1: 215, y1: 1080, x2: 1035, y2: 1080, color: COLORS.navy, width: 6, label: "轮询 get_receipt()", labelY: 1050 }),
        arrow({ x1: 1035, y1: 1160, x2: 1445, y2: 1160, color: COLORS.teal, width: 6, label: "查询 receipt / confirmations", labelY: 1130 }),
        arrow({ x1: 1445, y1: 1240, x2: 1035, y2: 1240, color: COLORS.sage, width: 6, label: "返回回执", labelY: 1210 }),
        arrow({ x1: 1035, y1: 1320, x2: 625, y2: 1320, color: COLORS.sage, width: 6, label: "写入 receipt 并更新事件为 ANCHORED", labelY: 1290 }),
        arrow({ x1: 1855, y1: 1082, x2: 1035, y2: 1290, color: COLORS.gold, width: 6, label: "失败时由 retry_worker 拉起重试", labelX: 1630, labelY: 1120 }),
    ].join("");

    const notes = [
        noteCard({
            x: 92,
            y: 1190,
            w: 840,
            h: 170,
            title: "崩溃恢复",
            bullets: ["提交交易前先写 submission 记录", "即使 worker 异常退出，也能根据 transaction_hash 继续补全回执", "让链上提交与本地状态保持最终一致"],
            accent: COLORS.navy,
        }),
        noteCard({
            x: 1642,
            y: 580,
            w: 430,
            h: 240,
            title: "失败重试分支",
            bullets: ["锚定异常 -> FAILED_RETRYING", "retry_worker 周期拉起重试", "达到阈值后转入 DEAD_LETTER 并告警"],
            accent: COLORS.gold,
        }),
    ].join("");

    return baseFigure(figure, `${lanes}${messages}${notes}`);
}

function renderRolloutStrategy(figure) {
    const stages = [
        ["rollback_safe", "只保留本地验签与监控", COLORS.navy, COLORS.blueSoft],
        ["shadow", "双写模拟，链上结果不对外", COLORS.teal, COLORS.tealSoft],
        ["canary", "小流量真上链并观测 SLO", COLORS.gold, COLORS.amberSoft],
        ["full", "满足阈值后全量切换", COLORS.sage, COLORS.greenSoft],
    ]
        .map(([title, desc, accent, fill], index) =>
            card({
                x: 94 + index * 366,
                y: 318,
                w: 310,
                h: 220,
                title,
                lines: [desc],
                accent,
                fill,
                mono: true,
            }),
        )
        .join("");

    const arrows = [
        arrow({ x1: 404, y1: 428, x2: 460, y2: 428, color: COLORS.navy, width: 6 }),
        arrow({ x1: 770, y1: 428, x2: 826, y2: 428, color: COLORS.teal, width: 6 }),
        arrow({ x1: 1136, y1: 428, x2: 1192, y2: 428, color: COLORS.gold, width: 6 }),
        elbowArrow({
            points: [
                [981, 538],
                [981, 660],
                [250, 660],
                [250, 538],
            ],
            color: COLORS.danger,
            width: 6,
            label: "指标越界立即回滚到 rollback_safe",
            labelX: 622,
            labelY: 630,
        }),
    ].join("");

    const metrics = [
        metricCard({ x: 148, y: 706, w: 250, h: 118, value: "P95 < 80 ms", label: "延迟阈值", accent: COLORS.navy }),
        metricCard({ x: 450, y: 706, w: 250, h: 118, value: "错误率 = 0", label: "发布门槛", accent: COLORS.cherry }),
        metricCard({ x: 752, y: 706, w: 250, h: 118, value: "确认窗 10 分钟", label: "Canary 观察期", accent: COLORS.gold }),
        metricCard({ x: 1054, y: 706, w: 250, h: 118, value: "切换可审计", label: "状态变更记录", accent: COLORS.sage }),
    ].join("");

    const footer = noteCard({
        x: 144,
        y: 168,
        w: 1180,
        h: 92,
        title: "发布哲学",
        bullets: ["先证明可控，再放大流量；任何一步异常都应具备自动回退能力", "Shadow 阶段看兼容，Canary 阶段看真实链路", "全部通过后才允许进入 Full"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${footer}${stages}${arrows}${metrics}`);
}

function renderFrontendStructure(figure) {
    const map = `<g filter="url(#shadow)">
        <rect x="84" y="248" width="410" height="592" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${textBlock({ x: 120, y: 312, lines: ["信息架构"], fontSize: 38, fill: COLORS.ink, weight: 700, family: FONT_HEAD })}
        ${[
            ["Dashboard", "统计总览 / 质量分布", COLORS.navy],
            ["Batches", "批次列表 / 详情入口", COLORS.teal],
            ["Trace", "完整时间线 / 锚定状态", COLORS.plum],
            ["Public Trace", "公开查询 / 质量与回执", COLORS.sage],
            ["Admin Anchoring", "任务查看 / requeue / run once", COLORS.cherry],
            ["Admin Devices", "注册、密钥轮换、测试事件", COLORS.gold],
        ]
            .map(
                ([title, desc, accent], index) =>
                    `${card({
                        x: 112,
                        y: 352 + index * 78,
                        w: 350,
                        h: 62,
                        title,
                        lines: [desc],
                        accent,
                        fill: COLORS.panel,
                        titleSize: 22,
                        lineSize: 17,
                        mono: /Dashboard|Trace|Admin/.test(title),
                    })}`,
            )
            .join("")}
    </g>`;

    const dashboard = browserMock({
        x: 562,
        y: 238,
        w: 306,
        h: 292,
        title: "Dashboard",
        accent: COLORS.navy,
        tags: [
            { label: "Stats", fill: COLORS.navy },
            { label: "Quality", fill: COLORS.teal },
        ],
        content: `
            <rect x="590" y="328" width="118" height="78" rx="0" fill="${COLORS.blueSoft}"/>
            <rect x="722" y="328" width="118" height="78" rx="0" fill="${COLORS.tealSoft}"/>
            <rect x="590" y="426" width="250" height="72" rx="0" fill="${COLORS.sandSoft}"/>
            ${sparkline([12, 18, 16, 28, 24, 34, 30], { x: 608, y: 446, w: 210, h: 34, color: COLORS.cherry })}
        `,
    });

    const publicTrace = browserMock({
        x: 900,
        y: 238,
        w: 306,
        h: 292,
        title: "Public Trace",
        accent: COLORS.sage,
        tags: [
            { label: "Batch", fill: COLORS.sage },
            { label: "QR", fill: COLORS.teal },
        ],
        content: `
            <rect x="926" y="330" width="110" height="110" rx="0" fill="${COLORS.greenSoft}"/>
            <rect x="1052" y="330" width="128" height="22" rx="0" fill="${COLORS.sandSoft}"/>
            <rect x="1052" y="364" width="128" height="22" rx="0" fill="${COLORS.sandSoft}"/>
            <rect x="1052" y="398" width="128" height="22" rx="0" fill="${COLORS.sandSoft}"/>
            <rect x="926" y="456" width="254" height="42" rx="0" fill="${COLORS.blueSoft}"/>
        `,
    });

    const admin = browserMock({
        x: 1238,
        y: 238,
        w: 306,
        h: 292,
        title: "Admin",
        accent: COLORS.cherry,
        tags: [
            { label: "Anchoring", fill: COLORS.cherry },
            { label: "Devices", fill: COLORS.gold },
        ],
        content: `
            <rect x="1264" y="330" width="254" height="44" rx="0" fill="${COLORS.roseSoft}"/>
            <rect x="1264" y="390" width="254" height="44" rx="0" fill="${COLORS.amberSoft}"/>
            <rect x="1264" y="450" width="254" height="44" rx="0" fill="${COLORS.tealSoft}"/>
        `,
    });

    const links = [
        arrow({ x1: 494, y1: 420, x2: 562, y2: 384, color: COLORS.navy, width: 6 }),
        arrow({ x1: 494, y1: 520, x2: 900, y2: 384, color: COLORS.sage, width: 6 }),
        arrow({ x1: 494, y1: 620, x2: 1238, y2: 384, color: COLORS.cherry, width: 6 }),
    ].join("");

    const footer = noteCard({
        x: 560,
        y: 584,
        w: 986,
        h: 218,
        title: "界面设计重点",
        bullets: ["公共查询页面强调批次、质量与链上回执的直接可读性", "后台把 anchoring 与 devices 拆成独立运维面板，减少操作干扰", "Dashboard 负责总览趋势，Trace 页面负责单批次深挖"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${map}${dashboard}${publicTrace}${admin}${links}${footer}`);
}

function renderHardwareTestRig(figure) {
    const rig = [
        card({ x: 88, y: 292, w: 250, h: 130, title: "恒温冷箱", lines: ["0–4°C 环境模拟"], accent: COLORS.navy, fill: COLORS.blueSoft }),
        card({ x: 88, y: 470, w: 250, h: 130, title: "CO₂ 标定源", lines: ["500 / 1000 / 1500 ppm"], accent: COLORS.gold, fill: COLORS.amberSoft }),
        card({ x: 88, y: 648, w: 250, h: 130, title: "可编程电源", lines: ["5 V 输入"], accent: COLORS.cherry, fill: COLORS.roseSoft }),
        card({ x: 490, y: 378, w: 330, h: 230, title: "樱桃节点样机", lines: ["STM32H743", "传感器 + 安全芯片", "Wi-Fi / LoRa"], accent: COLORS.teal, fill: COLORS.tealSoft }),
        card({ x: 982, y: 292, w: 250, h: 130, title: "串口记录器", lines: ["日志 / CRC / 帧率"], accent: COLORS.plum, fill: COLORS.lilacSoft }),
        card({ x: 982, y: 470, w: 250, h: 130, title: "上位机", lines: ["采样可视化 / 校准记录"], accent: COLORS.sage, fill: COLORS.greenSoft }),
        card({ x: 982, y: 648, w: 250, h: 130, title: "API 模拟端", lines: ["接收 envelope / 回写 ACK"], accent: COLORS.navy, fill: COLORS.blueSoft }),
    ].join("");

    const cables = [
        arrow({ x1: 338, y1: 356, x2: 490, y2: 432, color: COLORS.navy, width: 6, label: "环境模拟" }),
        arrow({ x1: 338, y1: 534, x2: 490, y2: 492, color: COLORS.gold, width: 6, label: "气体校准", labelX: 416, labelY: 498 }),
        arrow({ x1: 338, y1: 712, x2: 490, y2: 552, color: COLORS.cherry, width: 6, label: "供电", labelX: 392, labelY: 666 }),
        arrow({ x1: 820, y1: 432, x2: 982, y2: 356, color: COLORS.plum, width: 6, label: "UART" }),
        arrow({ x1: 820, y1: 492, x2: 982, y2: 534, color: COLORS.sage, width: 6, label: "USB / Dashboard" }),
        arrow({ x1: 820, y1: 552, x2: 982, y2: 712, color: COLORS.navy, width: 6, label: "HTTP Mock", labelX: 904, labelY: 648 }),
    ].join("");

    const footer = noteCard({
        x: 408,
        y: 724,
        w: 492,
        h: 130,
        title: "测试目标",
        bullets: ["校准传感精度", "观察签名与上传稳定性", "在不同环境条件下复现完整数据链路"],
        accent: COLORS.cherry,
    });

    return baseFigure(figure, `${rig}${cables}${footer}`);
}

function renderE2eValidation(figure) {
    const strip = [
        ["设备上报", COLORS.teal, "event accepted"],
        ["质量评分", COLORS.gold, "grade = A"],
        ["链上锚定", COLORS.cherry, "status = ANCHORED"],
        ["公开查询", COLORS.sage, "tx_hash visible"],
    ]
        .map(([title, accent, desc], index) =>
            card({
                x: 96 + index * 360,
                y: 266,
                w: 300,
                h: 128,
                title,
                lines: [desc],
                accent,
                fill: COLORS.panel,
            }),
        )
        .join("");

    const arrows = [
        arrow({ x1: 396, y1: 330, x2: 456, y2: 330, color: COLORS.teal, width: 6 }),
        arrow({ x1: 756, y1: 330, x2: 816, y2: 330, color: COLORS.gold, width: 6 }),
        arrow({ x1: 1116, y1: 330, x2: 1176, y2: 330, color: COLORS.cherry, width: 6 }),
    ].join("");

    const trace = browserMock({
        x: 110,
        y: 472,
        w: 548,
        h: 320,
        title: "Trace Timeline",
        accent: COLORS.navy,
        tags: [
            { label: "Batch", fill: COLORS.navy },
            { label: "Anchor", fill: COLORS.sage },
        ],
        content: `
            <line x1="168" y1="568" x2="168" y2="730" stroke="${COLORS.border}" stroke-width="4"/>
            <circle cx="168" cy="590" r="10" fill="${COLORS.teal}"/>
            <circle cx="168" cy="648" r="10" fill="${COLORS.gold}"/>
            <circle cx="168" cy="706" r="10" fill="${COLORS.cherry}"/>
            <rect x="210" y="570" width="390" height="30" rx="0" fill="${COLORS.tealSoft}"/>
            <rect x="210" y="628" width="390" height="30" rx="0" fill="${COLORS.amberSoft}"/>
            <rect x="210" y="686" width="390" height="30" rx="0" fill="${COLORS.roseSoft}"/>
        `,
    });

    const publicPage = browserMock({
        x: 720,
        y: 472,
        w: 784,
        h: 320,
        title: "Public Trace Result",
        accent: COLORS.sage,
        tags: [
            { label: "A 级", fill: COLORS.sage },
            { label: "已锚定", fill: COLORS.cherry },
        ],
        content: `
            <rect x="754" y="558" width="220" height="168" rx="0" fill="${COLORS.greenSoft}"/>
            <rect x="998" y="558" width="468" height="44" rx="0" fill="${COLORS.sandSoft}"/>
            <rect x="998" y="618" width="468" height="44" rx="0" fill="${COLORS.blueSoft}"/>
            <rect x="998" y="678" width="468" height="44" rx="0" fill="${COLORS.roseSoft}"/>
        `,
    });

    const footer = `<g filter="url(#shadow)">
        <rect x="210" y="814" width="1180" height="72" rx="0" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        ${textBlock({
            x: 248,
            y: 858,
            lines: ["同一批次可同时在后台时间线与公开页面看到一致的质量与锚定结果，端到端验证关注的是链路完整性，不只是一条接口返回成功"],
            fontSize: 24,
            fill: COLORS.muted,
            weight: 600,
        })}
    </g>`;

    return baseFigure(figure, `${strip}${arrows}${trace}${publicPage}${footer}`);
}

function renderCanaryRollback(figure) {
    const top = [
        card({ x: 86, y: 260, w: 260, h: 122, title: "rollback_safe", lines: ["关闭真实上链"], accent: COLORS.navy, fill: COLORS.blueSoft, mono: true }),
        card({ x: 420, y: 260, w: 260, h: 122, title: "shadow", lines: ["双写观测"], accent: COLORS.teal, fill: COLORS.tealSoft, mono: true }),
        card({ x: 754, y: 260, w: 260, h: 122, title: "canary", lines: ["小流量真上链"], accent: COLORS.gold, fill: COLORS.amberSoft, mono: true }),
        card({ x: 1088, y: 260, w: 260, h: 122, title: "full", lines: ["全量切换"], accent: COLORS.sage, fill: COLORS.greenSoft, mono: true }),
    ].join("");

    const topArrows = [
        arrow({ x1: 346, y1: 322, x2: 420, y2: 322, color: COLORS.navy, width: 6 }),
        arrow({ x1: 680, y1: 322, x2: 754, y2: 322, color: COLORS.teal, width: 6 }),
        arrow({ x1: 1014, y1: 322, x2: 1088, y2: 322, color: COLORS.gold, width: 6 }),
    ].join("");

    const board = browserMock({
        x: 86,
        y: 452,
        w: 930,
        h: 360,
        title: "Canary Monitor",
        accent: COLORS.navy,
        tags: [
            { label: "Latency", fill: COLORS.navy },
            { label: "Errors", fill: COLORS.cherry },
            { label: "Confirm", fill: COLORS.gold },
        ],
        content: `
            <rect x="118" y="550" width="274" height="88" rx="0" fill="${COLORS.blueSoft}"/>
            <rect x="410" y="550" width="274" height="88" rx="0" fill="${COLORS.roseSoft}"/>
            <rect x="702" y="550" width="274" height="88" rx="0" fill="${COLORS.amberSoft}"/>
            <rect x="118" y="666" width="858" height="110" rx="0" fill="${COLORS.sandSoft}"/>
            ${sparkline([12, 14, 16, 15, 18, 19, 24, 48, 66], { x: 150, y: 694, w: 378, h: 54, color: COLORS.navy })}
            ${sparkline([0, 0, 0, 0, 1, 0, 0, 5, 8], { x: 554, y: 694, w: 378, h: 54, color: COLORS.cherry })}
        `,
    });

    const alert = noteCard({
        x: 1090,
        y: 470,
        w: 416,
        h: 248,
        title: "自动回滚条件",
        bullets: ["P95 延迟超阈值", "错误率抬升", "Canary 确认时间异常拉长"],
        accent: COLORS.cherry,
    });

    const rollback = elbowArrow({
        points: [
            [1220, 734],
            [1220, 862],
            [216, 862],
            [216, 382],
        ],
        color: COLORS.danger,
        width: 7,
        label: "指标恶化 -> 立即回退到 rollback_safe",
        labelX: 720,
        labelY: 834,
    });

    const summary = metricCard({ x: 1090, y: 742, w: 416, h: 118, value: "自动切换完成", label: "发布决策由监控指标驱动", accent: COLORS.sage });

    return baseFigure(figure, `${top}${topArrows}${board}${alert}${rollback}${summary}`);
}

const RENDERERS = {
    systemLayers: renderSystemLayers,
    dataFlow: renderDataFlow,
    coreEr: renderCoreEr,
    statusMachine: renderStatusMachine,
    securityArchitecture: renderSecurityArchitecture,
    stm32Minimal: renderStm32Minimal,
    sensorBuses: renderSensorBuses,
    secureElementSigning: renderSecureElementSigning,
    networkTopology: renderNetworkTopology,
    powerManagement: renderPowerManagement,
    freertosPipeline: renderFreertosPipeline,
    hashCanonicalization: renderHashCanonicalization,
    idempotencySequence: renderIdempotencySequence,
    signatureVerification: renderSignatureVerification,
    anchorSequence: renderAnchorSequence,
    rolloutStrategy: renderRolloutStrategy,
    frontendStructure: renderFrontendStructure,
    hardwareTestRig: renderHardwareTestRig,
    e2eValidation: renderE2eValidation,
    canaryRollback: renderCanaryRollback,
};

export function renderFigureSvg(figure) {
    const renderer = RENDERERS[figure.renderer] ?? renderPlaceholder;
    return renderer(figure);
}
