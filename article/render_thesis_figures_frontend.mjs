import { execFile as execFileCallback } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

import { FIGURES } from "./frontend_figures/manifest.mjs";
import { renderFigureSvg } from "./frontend_figures/renderers.mjs";

const execFile = promisify(execFileCallback);

const __filename = fileURLToPath(import.meta.url);
const ROOT = path.dirname(__filename);
const OUTPUT_ROOT = path.join(ROOT, "generated_figures_frontend");
const SVG_DIR = path.join(OUTPUT_ROOT, "svg");
const HTML_DIR = path.join(OUTPUT_ROOT, "html");
const PNG_DIR = path.join(OUTPUT_ROOT, "png");
const EDGE_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

function wrapHtml(svg) {
    return `<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
        html, body {
            margin: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: #f7f2ea;
        }

        body {
            display: grid;
            place-items: center;
        }

        svg {
            display: block;
            width: 100vw;
            height: 100vh;
        }
    </style>
</head>
<body>
${svg}
</body>
</html>`;
}

async function ensureDirs() {
    await Promise.all([
        fs.mkdir(OUTPUT_ROOT, { recursive: true }),
        fs.mkdir(SVG_DIR, { recursive: true }),
        fs.mkdir(HTML_DIR, { recursive: true }),
        fs.mkdir(PNG_DIR, { recursive: true }),
    ]);
}

async function renderFigureAssets(figure) {
    const svg = renderFigureSvg(figure);
    const svgPath = path.join(SVG_DIR, figure.imageName.replace(/\.png$/i, ".svg"));
    const htmlPath = path.join(HTML_DIR, figure.imageName.replace(/\.png$/i, ".html"));
    const pngPath = path.join(PNG_DIR, figure.imageName);

    await fs.writeFile(svgPath, svg, "utf8");
    await fs.writeFile(htmlPath, wrapHtml(svg), "utf8");

    const pageUrl = pathToFileURL(htmlPath).href;
    const { width, height } = figure.size;

    await execFile(
        EDGE_PATH,
        [
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--run-all-compositor-stages-before-draw",
            "--force-device-scale-factor=1",
            `--window-size=${width},${height}`,
            "--virtual-time-budget=1200",
            `--screenshot=${pngPath}`,
            pageUrl,
        ],
        { windowsHide: true, timeout: 30000 },
    );

    return {
        ...figure,
        svgPath,
        htmlPath,
        pngPath,
    };
}

function previewHtml(items) {
    const cards = items
        .map(
            (item) => `
            <article class="card">
                <img src="./png/${item.imageName}" alt="${item.caption}" />
                <div class="meta">
                    <div class="id">${item.caption}</div>
                    <div class="sub">${item.headline}</div>
                </div>
            </article>
        `,
        )
        .join("");

    return `<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
        :root {
            --paper: #f7f2ea;
            --panel: #fffdfa;
            --ink: #19232d;
            --muted: #67717c;
            --border: #d9d1c5;
            --accent: #bf3d4a;
        }

        * { box-sizing: border-box; }

        html, body {
            margin: 0;
            background:
                radial-gradient(circle at 10% 10%, rgba(191, 61, 74, 0.12), transparent 24%),
                radial-gradient(circle at 88% 14%, rgba(63, 151, 163, 0.16), transparent 24%),
                var(--paper);
            color: var(--ink);
            font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
        }

        body {
            padding: 56px 48px 72px;
        }

        h1 {
            margin: 0;
            font-size: 40px;
            line-height: 1.1;
        }

        p {
            margin: 12px 0 0;
            color: var(--muted);
            font-size: 18px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 24px;
            margin-top: 36px;
        }

        .card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 18px 40px rgba(49, 36, 24, 0.08);
        }

        img {
            display: block;
            width: 100%;
            aspect-ratio: 16 / 10;
            object-fit: cover;
            background: var(--paper);
        }

        .meta {
            padding: 16px 18px 18px;
        }

        .id {
            font-size: 18px;
            font-weight: 700;
        }

        .sub {
            margin-top: 8px;
            font-size: 15px;
            line-height: 1.4;
            color: var(--muted);
        }
    </style>
</head>
<body>
    <h1>论文配图前端重绘预览</h1>
    <p>20 张图片已统一为同一视觉语言，并按原始 docx 的 media 映射导出。</p>
    <section class="grid">${cards}</section>
</body>
</html>`;
}

async function renderPreview(items) {
    const htmlPath = path.join(OUTPUT_ROOT, "preview.html");
    const pngPath = path.join(OUTPUT_ROOT, "preview.png");
    await fs.writeFile(htmlPath, previewHtml(items), "utf8");

    await execFile(
        EDGE_PATH,
        [
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--run-all-compositor-stages-before-draw",
            "--force-device-scale-factor=1",
            "--window-size=2200,3600",
            "--virtual-time-budget=1500",
            `--screenshot=${pngPath}`,
            pathToFileURL(htmlPath).href,
        ],
        { windowsHide: true, timeout: 30000 },
    );

    return { htmlPath, pngPath };
}

async function main() {
    await ensureDirs();
    const rendered = [];

    for (const figure of FIGURES) {
        rendered.push(await renderFigureAssets(figure));
    }

    const preview = await renderPreview(rendered);
    const manifestPath = path.join(OUTPUT_ROOT, "manifest.json");
    await fs.writeFile(
        manifestPath,
        JSON.stringify(
            {
                generatedAt: new Date().toISOString(),
                preview,
                figures: rendered.map(({ id, imageName, caption, headline, pngPath, svgPath, htmlPath }) => ({
                    id,
                    imageName,
                    caption,
                    headline,
                    pngPath,
                    svgPath,
                    htmlPath,
                })),
            },
            null,
            2,
        ),
        "utf8",
    );

    console.log(JSON.stringify({ outputRoot: OUTPUT_ROOT, preview, manifestPath }, null, 2));
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});
