const COLORS = {
    paper: "#f7f2ea",
    panel: "#fffdfa",
    ink: "#19232d",
    muted: "#67717c",
    border: "#d9d1c5",
    grid: "#e6ddd1",
    cherry: "#bf3d4a",
    navy: "#264b66",
    teal: "#3f97a3",
    sage: "#7b9a74",
    gold: "#cb9643",
    plum: "#7c68aa",
    blueSoft: "#dbe9f4",
    tealSoft: "#d9f0ef",
    greenSoft: "#e5f2e4",
    amberSoft: "#f7ead7",
    roseSoft: "#f7dfe1",
    lilacSoft: "#ece5f8",
    sandSoft: "#efe6db",
    white: "#ffffff",
    success: "#2d8a5b",
    warning: "#c58b33",
    danger: "#c14855",
};

const FONT_HEAD = '"Bahnschrift","Microsoft YaHei UI","Microsoft YaHei","Segoe UI",sans-serif';
const FONT_SANS = '"Microsoft YaHei UI","Microsoft YaHei","Segoe UI",sans-serif';
const FONT_MONO = '"Consolas","Cascadia Mono","Courier New",monospace';

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
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="28" fill="${fill}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="10" height="${h}" rx="10" fill="${accent}"/>
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
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="28" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
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
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="24" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="${w}" height="54" rx="24" fill="${accent}"/>
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
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="24" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="${w}" height="10" rx="10" fill="${accent}"/>
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
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="28" fill="${COLORS.panel}" stroke="${COLORS.border}" stroke-width="2"/>
        <rect x="${x}" y="${y}" width="${w}" height="54" rx="28" fill="${COLORS.sandSoft}"/>
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
