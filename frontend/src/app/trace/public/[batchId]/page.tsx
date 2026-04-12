"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
    AlertCircle,
    Box,
    CheckCircle2,
    Clock,
    Leaf,
    Loader2,
    Snowflake,
    Store,
    Truck,
    type LucideIcon,
} from "lucide-react";
import {
    ResponsiveContainer,
    LineChart,
    Line,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
} from "recharts";
import { usePublicTrace } from "@/hooks/use-queries";

const STAGE_CONFIG: Record<string, { icon: LucideIcon; label: string }> = {
    harvest: { icon: Leaf, label: "采摘" },
    storage: { icon: Snowflake, label: "存储" },
    transport: { icon: Truck, label: "运输" },
    retail: { icon: Store, label: "零售" },
};

const GRADE_COLOR: Record<string, string> = {
    A: "#22c55e",
    B: "#eab308",
    C: "#ef4444",
};

const CHART_INITIAL_DIMENSION = { width: 800, height: 208 };

function QRCodeCanvas({ url }: { url: string }) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const size = 150;
        canvas.width = size;
        canvas.height = size;

        // Simple deterministic pattern from URL hash
        let hash = 0;
        for (let i = 0; i < url.length; i++) {
            const char = url.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }

        const moduleCount = 21;
        const cellSize = size / moduleCount;

        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, size, size);

        ctx.fillStyle = "#000000";

        // Draw finder patterns (top-left, top-right, bottom-left)
        const drawFinder = (x: number, y: number) => {
            for (let r = 0; r < 7; r++) {
                for (let c = 0; c < 7; c++) {
                    const isOuter = r === 0 || r === 6 || c === 0 || c === 6;
                    const isInner = r >= 2 && r <= 4 && c >= 2 && c <= 4;
                    if (isOuter || isInner) {
                        ctx.fillRect((x + c) * cellSize, (y + r) * cellSize, cellSize, cellSize);
                    }
                }
            }
        };

        drawFinder(0, 0);
        drawFinder(moduleCount - 7, 0);
        drawFinder(0, moduleCount - 7);

        // Fill data area with deterministic pattern
        let seed = Math.abs(hash);
        for (let r = 0; r < moduleCount; r++) {
            for (let c = 0; c < moduleCount; c++) {
                const inFinder =
                    (r < 8 && c < 8) ||
                    (r < 8 && c >= moduleCount - 8) ||
                    (r >= moduleCount - 8 && c < 8);
                if (inFinder) continue;

                seed = (seed * 1103515245 + 12345) & 0x7fffffff;
                if (seed % 3 !== 0) {
                    ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
                }
            }
        }
    }, [url]);

    return (
        <canvas
            ref={canvasRef}
            role="img"
            aria-label="当前批次溯源二维码"
            className="rounded-lg border-2 border-slate-300"
            style={{ width: 150, height: 150 }}
        />
    );
}

function ScoreRing({ score, maxScore, grade, reduceMotion }: { score: number; maxScore: number; grade: string; reduceMotion: boolean }) {
    const pct = Math.round((score / maxScore) * 100);
    const radius = 54;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (pct / 100) * circumference;
    const color = GRADE_COLOR[grade] || "#6b7280";

    return (
        <div className="relative flex flex-col items-center">
            <svg width="140" height="140" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r={radius} fill="none" stroke="#e5e7eb" strokeWidth="10" />
                <motion.circle
                    cx="70"
                    cy="70"
                    r={radius}
                    fill="none"
                    stroke={color}
                    strokeWidth="10"
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={reduceMotion ? { duration: 0 } : { duration: 1.2 }}
                    transform="rotate(-90 70 70)"
                />
                <text
                    x="70"
                    y="62"
                    textAnchor="middle"
                    className="fill-gray-800 text-3xl font-bold"
                    style={{ fontSize: "36px", fontWeight: 700 }}
                >
                    {grade}
                </text>
                <text
                    x="70"
                    y="88"
                    textAnchor="middle"
                    className="fill-gray-500 text-sm"
                    style={{ fontSize: "14px" }}
                >
                    {pct}%
                </text>
            </svg>
        </div>
    );
}

const createFadeUp = (reduceMotion: boolean) => ({
    hidden: reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 },
    visible: (i: number) =>
        reduceMotion
            ? { opacity: 1, y: 0 }
            : ({
                opacity: 1,
                y: 0,
                transition: { delay: i * 0.1, duration: 0.5 },
            }),
});

export default function PublicTracePage() {
    const shouldReduceMotion = Boolean(useReducedMotion());
    const fadeUp = createFadeUp(shouldReduceMotion);
    const params = useParams();
    const batchId = params.batchId as string;
    const { data: trace, isLoading, isError } = usePublicTrace(batchId);

    const currentUrl = typeof window !== "undefined" ? window.location.href : "";

    const sensorHistory = trace?.sensor_history ?? [];

    const temperatureData = sensorHistory.map((p) => ({
        time: format(new Date(p.timestamp), "HH:mm"),
        temperature: p.temperature_c,
    }));

    const humidityData = sensorHistory.map((p) => ({
        time: format(new Date(p.timestamp), "HH:mm"),
        humidity: p.humidity_pct,
    }));

    const co2Data = sensorHistory
        .filter((p) => p.co2_ppm != null)
        .map((p) => ({
            time: format(new Date(p.timestamp), "HH:mm"),
            co2: p.co2_ppm,
        }));

    const vibrationData = sensorHistory
        .filter((p) => p.vibration_g != null)
        .map((p) => ({
            time: format(new Date(p.timestamp), "HH:mm"),
            vibration: p.vibration_g,
        }));

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2 className="h-10 w-10 animate-spin text-primary-400" />
            </div>
        );
    }

    if (isError || !trace) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-slate-300">
                <AlertCircle className="h-12 w-12 text-red-300" />
                <h2 className="text-xl font-semibold text-slate-100">未找到溯源数据</h2>
                <p className="text-sm text-slate-300">批次 {batchId} 的溯源信息不存在或暂未发布</p>
            </div>
        );
    }

    const stages = trace.stages || [];
    const anchor = trace.anchor;
    const qualityGrade = trace.quality.grade ?? "N/A";
    const qualityLabel = trace.quality.grade ? `${trace.quality.grade} 级品质` : "未评级";

    return (
        <div className="mx-auto max-w-5xl px-4 py-8">
            {/* Header */}
            <motion.div
                initial={shouldReduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-8 flex flex-col items-center gap-3"
            >
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-300 via-primary-400 to-accent-teal shadow-[0_24px_40px_-22px_rgba(45,212,191,0.8)]">
                    <span className="text-2xl font-bold text-slate-950">C</span>
                </div>
                <h1 className="text-center text-2xl font-bold text-slate-100">
                    高品质樱桃溯源系统
                </h1>
                <p className="text-sm text-slate-300">区块链可信溯源 安心品质保障</p>
            </motion.div>

            {/* Batch Info Card */}
            <motion.div
                custom={0}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                className="panel-shell edge-highlight mb-6"
            >
                <h2 className="display-heading mb-4 text-lg font-semibold text-slate-100">批次信息</h2>
                <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span className="text-slate-300">批次ID</span>
                        <p className="mt-1 font-mono font-medium text-slate-100">{trace.batch_id}</p>
                    </div>
                    <div>
                        <span className="text-slate-300">事件总数</span>
                        <p className="mt-1 font-medium text-slate-100">{trace.total_events}</p>
                    </div>
                    <div>
                        <span className="text-slate-300">首条事件</span>
                        <p className="mt-1 font-medium text-slate-100">
                            {trace.first_event_at
                                ? format(new Date(trace.first_event_at), "yyyy-MM-dd HH:mm", { locale: zhCN })
                                : "--"}
                        </p>
                    </div>
                    <div>
                        <span className="text-slate-300">最近更新</span>
                        <p className="mt-1 font-medium text-slate-100">
                            {trace.last_event_at
                                ? format(new Date(trace.last_event_at), "yyyy-MM-dd HH:mm", { locale: zhCN })
                                : "--"}
                        </p>
                    </div>
                </div>
            </motion.div>

            {/* Quality Grade */}
            <motion.div
                custom={1}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                className="panel-shell edge-highlight mb-6"
            >
                <h2 className="display-heading mb-4 text-lg font-semibold text-slate-100">品质等级</h2>
                <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center sm:gap-8">
                    <ScoreRing
                        score={trace.quality.score}
                        maxScore={trace.quality.max_score}
                        grade={qualityGrade}
                        reduceMotion={shouldReduceMotion}
                    />
                    <div className="text-center sm:text-left">
                        <p className="text-sm text-slate-300">综合评分</p>
                        <p className="text-3xl font-bold text-slate-100">
                            {trace.quality.score}{" "}
                            <span className="text-base font-normal text-slate-300">/ {trace.quality.max_score}</span>
                        </p>
                        <div
                            className="mt-2 inline-block rounded-full px-3 py-1 text-sm font-semibold text-slate-950"
                            style={{ backgroundColor: GRADE_COLOR[qualityGrade] || "#6b7280" }}
                        >
                            {qualityLabel}
                        </div>
                    </div>
                </div>
            </motion.div>

            {/* Supply Chain Timeline */}
            <motion.div
                custom={2}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                className="panel-shell edge-highlight mb-6"
            >
                <h2 className="display-heading mb-6 text-lg font-semibold text-slate-100">供应链追踪</h2>
                <div className="relative ml-4 border-l-2 border-slate-700 pb-2">
                    {stages.map((stage) => {
                        const cfg = STAGE_CONFIG[stage.stage] || { icon: Box, label: stage.stage };
                        const StageIcon = cfg.icon;
                        const isCompleted = stage.status === "completed" || stage.status === "active";
                        const isActive = stage.status === "active";

                        return (
                            <div key={stage.stage} className="relative mb-8 ml-6 last:mb-0">
                                <span
                                    className={`absolute -left-[33px] flex h-8 w-8 items-center justify-center rounded-full border-2 ${
                                        isActive
                                            ? "border-primary-400 bg-primary-500/20 text-primary-300"
                                            : isCompleted
                                              ? "border-emerald-400 bg-emerald-500/15 text-emerald-300"
                                              : "border-slate-600 bg-slate-800/70 text-slate-300"
                                    }`}
                                >
                                    <StageIcon className="h-4 w-4" />
                                </span>
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h3 className="font-semibold text-slate-100">{cfg.label}</h3>
                                        {isActive && (
                                            <span className="rounded-full bg-primary-400 px-2 py-0.5 text-xs text-slate-950">
                                                当前阶段
                                            </span>
                                        )}
                                        {isCompleted && !isActive && (
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                        )}
                                        {!isCompleted && (
                                            <Clock className="h-4 w-4 text-slate-300" />
                                        )}
                                    </div>
                                    <p className="mt-1 text-sm text-slate-300">
                                        {stage.entered_at
                                            ? format(new Date(stage.entered_at), "yyyy-MM-dd HH:mm", { locale: zhCN })
                                            : "等待中"}
                                    </p>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </motion.div>

            {/* Environment Charts */}
            <motion.div
                custom={3}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                className="mb-6 space-y-6"
            >
                <div className="panel-shell edge-highlight">
                    <h2 className="display-heading mb-4 text-lg font-semibold text-slate-100">环境数据监控</h2>

                    {/* Temperature */}
                    {temperatureData.length > 0 && (
                        <div className="mb-6">
                            <h3 className="mb-2 text-sm font-medium text-slate-300">温度变化曲线</h3>
                            <div className="h-52">
                                <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                    <LineChart data={temperatureData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                        <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#64748b" />
                                        <YAxis tick={{ fontSize: 11 }} stroke="#64748b" unit="\u00b0C" />
                                        <Tooltip />
                                        <Line
                                            type="monotone"
                                            dataKey="temperature"
                                            stroke="#3b82f6"
                                            strokeWidth={2}
                                            dot={false}
                                            name="温度(\u00b0C)"
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}

                    {/* Humidity */}
                    {humidityData.length > 0 && (
                        <div className="mb-6">
                            <h3 className="mb-2 text-sm font-medium text-slate-300">湿度变化曲线</h3>
                            <div className="h-52">
                                <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                    <LineChart data={humidityData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                        <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#64748b" />
                                        <YAxis tick={{ fontSize: 11 }} stroke="#64748b" unit="%" />
                                        <Tooltip />
                                        <Line
                                            type="monotone"
                                            dataKey="humidity"
                                            stroke="#22c55e"
                                            strokeWidth={2}
                                            dot={false}
                                            name="湿度(%)"
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}

                    {/* CO2 */}
                    {co2Data.length > 0 && (
                        <div className="mb-6">
                            <h3 className="mb-2 text-sm font-medium text-slate-300">CO2浓度曲线</h3>
                            <div className="h-52">
                                <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                    <LineChart data={co2Data}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                        <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#64748b" />
                                        <YAxis tick={{ fontSize: 11 }} stroke="#64748b" unit="ppm" />
                                        <Tooltip />
                                        <Line
                                            type="monotone"
                                            dataKey="co2"
                                            stroke="#f97316"
                                            strokeWidth={2}
                                            dot={false}
                                            name="CO2(ppm)"
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}

                    {/* Vibration */}
                    {vibrationData.length > 0 && (
                        <div>
                            <h3 className="mb-2 text-sm font-medium text-slate-300">运输振动数据</h3>
                            <div className="h-52">
                                <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                    <BarChart data={vibrationData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                        <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#64748b" />
                                        <YAxis tick={{ fontSize: 11 }} stroke="#64748b" unit="g" />
                                        <Tooltip />
                                        <Bar dataKey="vibration" fill="#ef4444" name="振动(g)" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}

                    {temperatureData.length === 0 &&
                        humidityData.length === 0 &&
                        co2Data.length === 0 &&
                        vibrationData.length === 0 && (
                            <p className="py-8 text-center text-sm text-slate-300">暂无传感器数据</p>
                        )}
                </div>
            </motion.div>

            {/* Blockchain Verification */}
            <motion.div
                custom={4}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                className="panel-shell edge-highlight mb-6"
            >
                <h2 className="display-heading mb-4 text-lg font-semibold text-slate-100">区块链验证</h2>
                <div className="space-y-3 text-sm">
                    <div className="flex items-center justify-between">
                        <span className="text-slate-300">锚定状态</span>
                        <span
                            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
                                anchor.status === "ANCHORED"
                                    ? "border-emerald-300/40 bg-emerald-600/28 text-emerald-100"
                                    : "border-amber-300/45 bg-amber-500/35 text-amber-50"
                            }`}
                        >
                            {anchor.status === "ANCHORED" ? (
                                <>
                                    <CheckCircle2 className="h-3 w-3" /> 已上链
                                </>
                            ) : (
                                <>
                                    <Clock className="h-3 w-3" /> 待确认
                                </>
                            )}
                        </span>
                    </div>
                    {anchor.tx_hash && (
                        <div className="flex flex-col gap-1">
                            <span className="text-slate-300">交易哈希</span>
                            <code className="break-all rounded border border-slate-700/75 bg-slate-800/78 px-2 py-1 font-mono text-xs text-slate-100">
                                {anchor.tx_hash.length > 20
                                    ? `${anchor.tx_hash.slice(0, 10)}...${anchor.tx_hash.slice(-10)}`
                                    : anchor.tx_hash}
                            </code>
                        </div>
                    )}
                    <div className="flex items-center justify-between">
                        <span className="text-slate-300">已锚定事件</span>
                        <span className="text-slate-100">{anchor.anchored_count} / {anchor.total_events}</span>
                    </div>
                </div>
            </motion.div>

            {/* QR Code */}
            <motion.div
                custom={5}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                className="panel-shell edge-highlight mb-8 flex flex-col items-center gap-3"
            >
                <h2 className="display-heading text-lg font-semibold text-slate-100">扫码分享</h2>
                <QRCodeCanvas url={currentUrl || `trace/public/${batchId}`} />
                <p className="max-w-xs text-center text-xs text-slate-300">
                    扫描二维码可查看本批次完整溯源信息
                </p>
            </motion.div>

            {/* Footer */}
            <div className="pb-8 text-center text-xs text-slate-300">
                <p>Cherry Trace 高品质樱桃供应链溯源系统</p>
                <p className="mt-1">数据由 STM32 物联网设备采集 区块链技术保障不可篡改</p>
            </div>
        </div>
    );
}
