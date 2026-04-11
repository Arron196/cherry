"use client";

import { useMemo } from "react";
import Link from "next/link";
import { format, formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import { motion, useReducedMotion } from "framer-motion";
import {
    Activity,
    ArrowRight,
    Bell,
    Loader2,
    Package,
    Radio,
    Star,
    TriangleAlert,
} from "lucide-react";
import {
    ResponsiveContainer,
    LineChart,
    Line,
    PieChart,
    Pie,
    Cell,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
} from "recharts";
import {
    useDashboardStats,
} from "@/hooks/use-queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SupplyChainMap } from "@/components/dashboard/supply-chain-map";
import { BlockchainLedger } from "@/components/dashboard/blockchain-ledger";
import { SensorCharts } from "@/components/dashboard/sensor-charts";

const QUALITY_COLORS: Record<string, string> = {
    A: "#22c55e",
    B: "#eab308",
    C: "#ef4444",
};

const CHART_INITIAL_DIMENSION = { width: 800, height: 280 };

const STAGE_LABELS: Record<string, string> = {
    harvest: "采摘",
    storage: "存储",
    transport: "运输",
    retail: "零售",
};

const createFadeIn = (reduceMotion: boolean) => ({
    hidden: reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 14 },
    visible: (i: number) =>
        reduceMotion
            ? { opacity: 1, y: 0 }
            : {
                opacity: 1,
                y: 0,
                transition: { delay: i * 0.08, duration: 0.36 },
            },
});

const chartTooltip = {
    backgroundColor: "rgba(15, 23, 42, 0.95)",
    border: "1px solid rgba(56, 189, 248, 0.2)",
    borderRadius: "8px",
    color: "#fff",
    boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
    backdropFilter: "blur(8px)",
};

const chartTooltipItem = {
    fontSize: "13px",
    fontFamily: "monospace",
    color: "#e2e8f0"
};

const chartTooltipLabel = {
    fontSize: "12px",
    color: "#94a3b8",
    marginBottom: "4px"
};

interface CustomPieTooltipPayload {
    name?: string;
    value?: number | string;
    payload: {
        color?: string;
    };
}

const CustomPieTooltip = ({ active, payload }: { active?: boolean; payload?: CustomPieTooltipPayload[] }) => {
    if (active && payload && payload.length) {
        const item = payload[0];
        const color = item.payload.color || "#94a3b8";
        return (
            <div style={chartTooltip} className="px-3 py-2 flex flex-col gap-1 shadow-2xl">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }}></div>
                    <span style={{ color }} className="font-bold text-sm">
                        {item.name}
                    </span>
                </div>
                <div className="text-white font-mono text-sm pl-4">
                    {item.value} <span className="text-slate-400 text-xs">批次</span>
                </div>
            </div>
        );
    }
    return null;
};

export default function DashboardPage() {
    const shouldReduceMotion = Boolean(useReducedMotion());
    const fadeIn = useMemo(() => createFadeIn(shouldReduceMotion), [shouldReduceMotion]);

    const { data: dashboardStats, isLoading: isDashboardLoading } = useDashboardStats();
    const overview = dashboardStats?.overview;
    const tempTrend = dashboardStats?.temperature_trend;
    const qualityDist = dashboardStats?.quality_distribution;
    const stageDist = dashboardStats?.stage_distribution;
    const recentEvents = dashboardStats?.recent_events;

    const statCards = useMemo(
        () => [
            {
                title: "总批次数",
                value: overview?.total_batches ?? "--",
                helper: "全链路追踪对象",
                icon: Package,
                iconClass: "text-cyan-300 drop-shadow-[0_0_8px_rgba(103,232,249,0.8)]",
                toneClass: "from-cyan-400/20 to-cyan-500/5",
                borderClass: "hover:border-cyan-400/50 group-hover:shadow-[0_0_20px_rgba(34,211,238,0.2)]",
            },
            {
                title: "活跃设备",
                value: overview?.active_devices ?? "--",
                helper: "当前在线采集节点",
                icon: Radio,
                iconClass: "text-emerald-300 drop-shadow-[0_0_8px_rgba(110,231,183,0.8)]",
                toneClass: "from-emerald-400/20 to-emerald-500/5",
                borderClass: "hover:border-emerald-400/50 group-hover:shadow-[0_0_20px_rgba(16,185,129,0.2)]",
            },
            {
                title: "平均品质分",
                value: overview?.avg_quality_score != null ? overview.avg_quality_score.toFixed(1) : "--",
                helper: "过去 24h 评分平均",
                icon: Star,
                iconClass: "text-amber-300 drop-shadow-[0_0_8px_rgba(252,211,77,0.8)]",
                toneClass: "from-amber-400/20 to-amber-500/5",
                borderClass: "hover:border-amber-400/50 group-hover:shadow-[0_0_20px_rgba(251,191,36,0.2)]",
            },
            {
                title: "待处理告警",
                value: overview?.open_alerts ?? "--",
                helper: "异常工单实时统计",
                icon: Bell,
                iconClass: overview?.open_alerts && overview.open_alerts > 0 ? "text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.8)] animate-pulse" : "text-slate-300",
                toneClass: overview?.open_alerts && overview.open_alerts > 0 ? "from-red-400/20 to-red-500/5" : "from-slate-400/20 to-slate-500/5",
                borderClass: "hover:border-red-400/50 group-hover:shadow-[0_0_20px_rgba(248,113,113,0.2)]",
            },
        ],
        [overview]
    );

    const tempChartData = useMemo(() => {
        if (!tempTrend) return [];
        return tempTrend.map((p) => ({
            time: format(new Date(p.timestamp), "HH:mm"),
            avg: Number(p.avg_temperature.toFixed(1)),
            min: Number(p.min_temperature.toFixed(1)),
            max: Number(p.max_temperature.toFixed(1)),
        }));
    }, [tempTrend]);

    const pieData = useMemo(() => {
        if (!qualityDist) return [];
        return qualityDist.map((d) => ({
            name: `${d.grade}级`,
            value: d.count,
            color: QUALITY_COLORS[d.grade] || "#6b7280",
        }));
    }, [qualityDist]);

    const stageChartData = useMemo(() => {
        if (!stageDist) return [];
        return stageDist.map((d) => ({
            name: STAGE_LABELS[d.stage] || d.stage,
            count: d.count,
        }));
    }, [stageDist]);

    const recentEventTime = recentEvents?.[0]?.timestamp
        ? formatDistanceToNow(new Date(recentEvents[0].timestamp), { addSuffix: true, locale: zhCN })
        : "暂无事件";

    return (
        <div className="max-w-[1600px] mx-auto w-full space-y-8 pb-8 px-4 md:px-8">
                        <motion.section
                custom={0}
                variants={fadeIn}
                initial="hidden"
                animate="visible"
                className="panel-shell edge-highlight relative overflow-hidden rounded-2xl border border-slate-700/60 bg-gradient-to-br from-slate-900/90 to-slate-800/90 p-8 md:p-10 shadow-2xl backdrop-blur-md"
            >
                <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary-500/20 blur-3xl animate-[aurora-shift_14s_ease-in-out_infinite]" />
                <div className="pointer-events-none absolute -left-16 bottom-[-76px] h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl animate-[aurora-shift_18s_ease-in-out_infinite]" />
                <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
                    <div className="space-y-3">
                        <div className="flex items-center gap-3">
                            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-500/20 border border-primary-500/30 text-primary-400 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                                <Activity className="h-6 w-6" />
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
                                供应全链路态势感知
                            </h1>
                        </div>
                        <p className="text-slate-400 max-w-2xl text-sm md:text-base leading-relaxed">
                            实时监控农产品全生命周期的温湿度指标、品质评级与区块链防伪溯源事件，随时掌握资产流转。
                        </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                        <Link href="/events" className="inline-flex">
                            <Button size="lg" className="h-11 rounded-full px-6 font-medium shadow-lg hover:shadow-primary-500/25 transition-all">
                                事件流汇总
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Button>
                        </Link>
                        <Link href="/alerts" className="inline-flex">
                            <Button size="lg" variant="outline" className="h-11 rounded-full px-6 border-slate-600 bg-slate-800/50 hover:bg-slate-700/50 font-medium text-slate-200 transition-all">
                                告警处理中心
                            </Button>
                        </Link>
                    </div>
                </div>
                
                <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-slate-700/60 pt-6 relative z-10">
                    <div className="flex items-center gap-2 rounded-full border border-slate-700/80 bg-slate-900/60 px-3 py-1.5 shadow-inner">
                        <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                        <span className="text-xs font-medium text-slate-300">本月事件流：<span className="text-white">{overview?.total_events ?? "--"}</span> 笔</span>
                    </div>
                    <div className="ml-auto text-xs text-slate-400 flex items-center gap-1.5">
                        <Radio className="h-3.5 w-3.5" />
                        <span className="text-slate-300 font-medium">数据最后更新：{recentEventTime}</span>
                    </div>
                </div>
            </motion.section>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {statCards.map((stat, idx) => {
                    const Icon = stat.icon;
                    return (
                        <motion.div key={stat.title} custom={idx + 1} variants={fadeIn} initial="hidden" animate="visible" whileHover={{ scale: 1.02, y: -4 }}>
                            <Card className={`panel-shell edge-highlight relative overflow-hidden border-slate-700/80 bg-slate-900/86 transition-all duration-500 group ${stat.borderClass || ""}`}>
                                <div className={`pointer-events-none absolute inset-0 opacity-40 transition-opacity duration-500 group-hover:opacity-100 bg-gradient-to-br ${stat.toneClass}`} />
                                <CardHeader className="relative flex flex-row items-start justify-between space-y-0 pb-3">
                                    <div>
                                        <CardTitle className="text-sm font-medium text-slate-200">{stat.title}</CardTitle>
                                        <p className="mt-1 text-xs text-slate-300">{stat.helper}</p>
                                    </div>
                                    <div className="edge-highlight flex h-9 w-9 items-center justify-center rounded-lg border border-slate-700/80 bg-slate-800/78">
                                        <Icon className={`h-4 w-4 ${stat.iconClass}`} />
                                    </div>
                                </CardHeader>
                                <CardContent className="relative">
                                    {isDashboardLoading ? (
                                        <Loader2 className="h-5 w-5 animate-spin text-slate-300" />
                                    ) : (
                                        <div className="metric-figure text-4xl font-semibold tracking-tight text-slate-100">{stat.value}</div>
                                    )}
                                </CardContent>
                            </Card>
                        </motion.div>
                    );
                })}
            </div>

            {/* High visual features section */}
            <motion.div custom={6} variants={fadeIn} initial="hidden" animate="visible" className="grid gap-6 xl:grid-cols-3">
                <div className="xl:col-span-3">
                    <SupplyChainMap dashboardStats={dashboardStats} />
                </div>
                <div className="xl:col-span-2">
                    <SensorCharts dashboardStats={dashboardStats} />
                </div>
                <div className="xl:col-span-1">
                    <BlockchainLedger dashboardStats={dashboardStats} />
                </div>
            </motion.div>

            <div className="grid gap-4 lg:grid-cols-7">
                <motion.div custom={7} variants={fadeIn} initial="hidden" animate="visible" className="lg:col-span-4">
                    <Card className="panel-shell edge-highlight p-0">
                        <CardHeader className="pb-3">
                            <CardTitle className="display-heading text-base text-slate-100">温度趋势（最近 24 小时）</CardTitle>
                            <p className="text-xs text-slate-300">平均值与上下边界的变化曲线</p>
                        </CardHeader>
                        <CardContent>
                            {isDashboardLoading ? (
                                <div className="flex h-64 items-center justify-center">
                                    <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
                                </div>
                            ) : tempChartData.length > 0 ? (
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                        <LineChart data={tempChartData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                            <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#cbd5e1" }} stroke="#64748b" />
                                            <YAxis tick={{ fontSize: 11, fill: "#cbd5e1" }} stroke="#64748b" unit={"°C"} />
                                            <Tooltip 
                                                contentStyle={chartTooltip} 
                                                itemStyle={chartTooltipItem} 
                                                labelStyle={chartTooltipLabel} 
                                            />
                                            <Legend wrapperStyle={{ fontSize: 12, color: "#cbd5e1" }} />
                                            <Line type="monotone" dataKey="avg" stroke="#22c55e" strokeWidth={2.5} dot={false} isAnimationActive={false} name="平均温度" />
                                            <Line type="monotone" dataKey="max" stroke="#f43f5e" strokeWidth={1.4} strokeDasharray="4 4" dot={false} isAnimationActive={false} name="最高温度" />
                                            <Line type="monotone" dataKey="min" stroke="#38bdf8" strokeWidth={1.4} strokeDasharray="4 4" dot={false} isAnimationActive={false} name="最低温度" />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <div className="flex h-64 items-center justify-center text-sm text-slate-300">暂无温度数据</div>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>

                <motion.div custom={7} variants={fadeIn} initial="hidden" animate="visible" className="lg:col-span-3">
                    <Card className="panel-shell edge-highlight p-0">
                        <CardHeader className="pb-3">
                            <CardTitle className="display-heading text-base text-slate-100">品质等级分布</CardTitle>
                            <p className="text-xs text-slate-300">分级占比用于观察批次质量结构</p>
                        </CardHeader>
                        <CardContent>
                            {isDashboardLoading ? (
                                <div className="flex h-64 items-center justify-center">
                                    <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
                                </div>
                            ) : pieData.length > 0 ? (
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                        <PieChart>
                                            <Pie
                                                data={pieData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={58}
                                                outerRadius={92}
                                                paddingAngle={2}
                                                dataKey="value"
                                                isAnimationActive={false}
                                                label={({ name, percent }: { name?: string; percent?: number }) =>
                                                    `${name ?? ""} ${((percent ?? 0) * 100).toFixed(0)}%`
                                                }
                                            >
                                                {pieData.map((entry, index) => (
                                                    <Cell key={index} fill={entry.color} />
                                                ))}
                                            </Pie>
                                            <Tooltip content={<CustomPieTooltip />} />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <div className="flex h-64 items-center justify-center text-sm text-slate-300">暂无品质数据</div>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>
            </div>

            <div className="grid gap-4 lg:grid-cols-7">
                <motion.div custom={8} variants={fadeIn} initial="hidden" animate="visible" className="lg:col-span-3">
                    <Card className="panel-shell edge-highlight p-0">
                        <CardHeader className="pb-3">
                            <CardTitle className="display-heading text-base text-slate-100">供应链阶段分布</CardTitle>
                            <p className="text-xs text-slate-300">观测批次集中在哪些环节</p>
                        </CardHeader>
                        <CardContent>
                            {isDashboardLoading ? (
                                <div className="flex h-56 items-center justify-center">
                                    <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
                                </div>
                            ) : stageChartData.length > 0 ? (
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                        <BarChart data={stageChartData} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                            <XAxis type="number" tick={{ fontSize: 11, fill: "#cbd5e1" }} stroke="#64748b" />
                                            <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "#cbd5e1" }} stroke="#64748b" width={64} />
                                            <Tooltip 
                                                contentStyle={chartTooltip} 
                                                itemStyle={chartTooltipItem} 
                                                labelStyle={chartTooltipLabel}
                                                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                            />
                                            <Bar dataKey="count" fill="#22c55e" radius={[0, 8, 8, 0]} isAnimationActive={false} name="批次数" />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <div className="flex h-56 items-center justify-center text-sm text-slate-300">暂无阶段数据</div>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>

                <motion.div custom={9} variants={fadeIn} initial="hidden" animate="visible" className="lg:col-span-4">
                    <Card className="panel-shell edge-highlight p-0">
                        <CardHeader className="flex flex-row items-center justify-between pb-3">
                            <div>
                                <CardTitle className="display-heading text-base text-slate-100">最近事件</CardTitle>
                            </div>
                            <Link href="/events" className="inline-flex">
                                <Button size="sm" variant="ghost">
                                    查看全部
                                    <ArrowRight className="ml-1.5 h-4 w-4" />
                                </Button>
                            </Link>
                        </CardHeader>
                        <CardContent>
                            {isDashboardLoading ? (
                                <div className="flex h-56 items-center justify-center">
                                    <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
                                </div>
                            ) : recentEvents && recentEvents.length > 0 ? (
                                <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                                    {recentEvents.map((evt) => (
                                        <Link
                                            key={evt.id}
                                            href={`/trace/${evt.batch_id}`}
                                            className="group edge-highlight flex items-center justify-between gap-3 rounded-xl border border-slate-700/75 bg-slate-800/58 px-3 py-2.5 transition-colors hover:border-cyan-400/55 hover:bg-slate-800/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300/65"
                                        >
                                            <div className="min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <Activity className="h-4 w-4 shrink-0 text-primary-300" />
                                                    <span className="truncate text-sm font-medium text-slate-100 group-hover:text-primary-200">
                                                        {evt.batch_id}
                                                    </span>
                                                </div>
                                                <p className="mt-1 truncate text-xs text-slate-300">{evt.device_id}</p>
                                            </div>
                                            <div className="flex shrink-0 items-center gap-2">
                                                {evt.quality_grade && (
                                                    <Badge
                                                        variant={
                                                            evt.quality_grade === "A"
                                                                ? "success"
                                                                : evt.quality_grade === "C"
                                                                  ? "destructive"
                                                                  : "warning"
                                                        }
                                                    >
                                                        {evt.quality_grade}
                                                    </Badge>
                                                )}
                                                {evt.ingest_status === "FAILED_RETRYING" && <TriangleAlert className="h-4 w-4 text-red-300" />}
                                                <span className="font-mono text-xs text-slate-300">
                                                    {formatDistanceToNow(new Date(evt.timestamp), {
                                                        addSuffix: true,
                                                        locale: zhCN,
                                                    })}
                                                </span>
                                            </div>
                                        </Link>
                                    ))}
                                </div>
                            ) : (
                                <div className="flex h-56 items-center justify-center text-sm text-slate-300">暂无事件数据</div>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>
            </div>
        </div>
    );
}
