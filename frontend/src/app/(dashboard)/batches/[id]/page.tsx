"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { format } from "date-fns";
import { motion } from "framer-motion";
import {
    Box,
    Loader2,
    ArrowLeft,
    Leaf,
    Snowflake,
    Store,
    Truck,
    Activity,
    Cpu,
    Radio,
    ShieldAlert,
    Database,
    Thermometer,
    Droplets,
    Wind,
    type LucideIcon,
} from "lucide-react";
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
} from "recharts";
import {
    useTrace,
    useBatchStages,
    useBatchSensorHistory,
} from "@/hooks/use-queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const STAGE_CONFIG: Record<string, { icon: LucideIcon; label: string; color: string }> = {
    harvest: { icon: Leaf, label: "采摘", color: "text-emerald-400" },
    storage: { icon: Snowflake, label: "存储", color: "text-cyan-400" },
    transport: { icon: Truck, label: "运输", color: "text-indigo-400" },
    retail: { icon: Store, label: "零售", color: "text-purple-400" },
};

const QUALITY_COLORS: Record<string, string> = {
    A: "text-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]",
    B: "text-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.5)]",
    C: "text-red-400 shadow-[0_0_10px_rgba(248,113,113,0.5)]",
};

const CHART_INITIAL_DIMENSION = { width: 800, height: 320 };

const GlowCard = ({ children, className = "", delay = 0 }: { children: React.ReactNode, className?: string, delay?: number }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay, ease: "easeOut" }}
        className={`relative overflow-hidden rounded-xl border border-cyan-500/20 bg-slate-900/60 p-6 backdrop-blur-xl ${className}`}
    >
        <div className="pointer-events-none absolute -inset-px rounded-xl opacity-0 transition duration-300 hover:opacity-100" 
             style={{ background: "linear-gradient(45deg, transparent 40%, rgba(6,182,212,0.1) 45%, rgba(6,182,212,0.2) 50%, transparent 60%)" }} 
        />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(6,182,212,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(6,182,212,0.02)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none" />
        {children}
    </motion.div>
);

export default function BatchDetailPage() {
    const params = useParams();
    const batchId = params.id as string;

    const { data: trace, isLoading: isTraceLoading, isError: isTraceError, refetch } = useTrace(batchId);
    const { data: stageInfo, isLoading: isStagesLoading } = useBatchStages(batchId);
    const { data: sensorHistory, isLoading: isSensorLoading } = useBatchSensorHistory(batchId);

    const sensorChartData = useMemo(() => {
        if (!sensorHistory) return [];
        return sensorHistory.map((p) => ({
            time: format(new Date(p.timestamp), "HH:mm"),
            temperature: p.temperature_c,
            humidity: p.humidity_pct,
            co2: p.co2_ppm ?? null,
        }));
    }, [sensorHistory]);

    if (isTraceLoading) {
        return (
            <div className="flex h-full items-center justify-center pt-32">
                <div className="relative flex items-center justify-center">
                    <div className="absolute h-24 w-24 rounded-full border-t-2 border-cyan-500 animate-spin" />
                    <div className="absolute h-16 w-16 rounded-full border-b-2 border-indigo-500 animate-[spin_1.5s_linear_reverse_infinite]" />
                    <Cpu className="h-8 w-8 text-cyan-400 animate-pulse" />
                </div>
            </div>
        );
    }

    if (isTraceError || !trace) {
        return (
            <div className="flex h-full flex-col items-center justify-center pt-32">
                <GlowCard className="flex max-w-md flex-col items-center text-center">
                    <ShieldAlert className="mb-4 h-16 w-16 text-rose-500 drop-shadow-[0_0_15px_rgba(244,63,94,0.5)]" />
                    <h2 className="text-2xl font-bold text-white mb-2 font-mono">节点离线</h2>
                    <p className="text-slate-400 mb-6 font-mono text-sm leading-relaxed">
                        无法建立与批次序列的量子连接 [{batchId}]。 <br/>
                        遥测数据不可用或信号在虚空中丢失。
                    </p>
                    <div className="flex gap-4">
                        <Button variant="outline" className="border-cyan-500/50 bg-transparent text-cyan-400 hover:bg-cyan-500/10" asChild>
                            <Link href="/batches">中止连接</Link>
                        </Button>
                        <Button className="bg-cyan-500 text-slate-900 hover:bg-cyan-400" onClick={() => refetch()}>
                            重新尝试
                        </Button>
                    </div>
                </GlowCard>
            </div>
        );
    }

    const stages = stageInfo?.stages || [];

    return (
        <div className="mx-auto max-w-[1600px] w-full space-y-8 pb-32">
            {/* Holographic Header */}
            <div className="relative flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-cyan-500/20 pb-6">
                <div className="absolute -left-10 top-0 h-full w-[2px] bg-gradient-to-b from-transparent via-cyan-500 to-transparent opacity-50" />
                <div className="space-y-4">
                    <Button variant="link" className="group h-8 px-0 text-cyan-500 hover:text-cyan-400" asChild>
                        <Link href="/batches">
                            <ArrowLeft className="mr-2 h-4 w-4 transition-transform group-hover:-translate-x-1" />
                            <span className="font-mono text-xs tracking-widest">返回列表</span>
                        </Link>
                    </Button>
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <div className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse" />
                            <h1 className="text-4xl font-black tracking-tight text-white drop-shadow-[0_2px_10px_rgba(255,255,255,0.2)]">
                                批次全息态扫描
                            </h1>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-sm">
                            <Badge variant="outline" className="border-cyan-500/30 bg-cyan-500/10 text-cyan-300 font-mono">
                                <Database className="mr-1.5 h-3 w-3" />
                                {trace.batch_id}
                            </Badge>
                            <Badge variant="outline" className="border-indigo-500/30 bg-indigo-500/10 text-indigo-300 font-mono">
                                <Radio className="mr-1.5 h-3 w-3" />
                                溯源协议 V2.4
                            </Badge>
                        </div>
                    </div>
                </div>
            </div>

            {/* Stage Progress (Cyberpunk version) */}
            <GlowCard delay={0.1} className="relative !p-8">
                <h3 className="mb-8 font-mono text-xs font-bold tracking-widest text-cyan-500 uppercase flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    供应链流转模型
                </h3>
                
                {isStagesLoading ? (
                    <div className="flex h-20 items-center justify-center">
                        <Loader2 className="h-6 w-6 animate-spin text-cyan-500" />
                    </div>
                ) : stages.length > 0 ? (
                    <div className="relative flex items-center justify-between">
                        {/* Connecting Line String */}
                        <div className="absolute left-[10%] right-[10%] top-6 h-[2px] bg-slate-800">
                            <div className="absolute inset-0 h-full bg-gradient-to-r from-emerald-500 via-cyan-500 to-transparent bg-[length:200%_100%] animate-[bg-shift_3s_linear_infinite] opacity-50" />
                        </div>

                        {stages.map((stage, idx) => {
                            const cfg = STAGE_CONFIG[stage.stage] || { icon: Box, label: stage.label || stage.stage, color: "text-cyan-400" };
                            const StageIcon = cfg.icon;
                            const isCompleted = stage.status === "completed";
                            const isActive = stage.status === "active";

                            return (
                                <div key={stage.stage || idx} className="relative z-10 flex flex-col items-center gap-4">
                                    <div className={`relative flex h-14 w-14 items-center justify-center rounded-xl border-2 transition-all duration-500 ${
                                        isCompleted
                                            ? "border-emerald-500/50 bg-emerald-950/40 shadow-[0_0_15px_rgba(52,211,153,0.3)]"
                                            : isActive
                                                ? "border-cyan-400 bg-cyan-950/40 shadow-[0_0_20px_rgba(34,211,238,0.5)] scale-110"
                                                : "border-slate-700 bg-slate-900/80"
                                    }`}>
                                        {isActive && (
                                            <div className="absolute -inset-2 rounded-xl border border-cyan-400/30 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite]" />
                                        )}
                                        <StageIcon className={`h-6 w-6 ${isCompleted ? "text-emerald-400" : isActive ? "text-cyan-400 animate-pulse" : "text-slate-500"}`} />
                                    </div>
                                    
                                    <div className="text-center">
                                        <div className={`text-sm font-bold ${isCompleted ? "text-emerald-300" : isActive ? "text-cyan-300 drop-shadow-[0_0_5px_rgba(34,211,238,0.8)]" : "text-slate-400"}`}>
                                            {cfg.label}
                                        </div>
                                        <div className="mt-1 font-mono text-[10px] text-slate-500">
                                            {stage.entered_at ? format(new Date(stage.entered_at), "MM-dd HH:mm") : "等待中"}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-center font-mono text-sm text-slate-500">暂无阶段遥测数据</div>
                )}
            </GlowCard>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column (Chart) */}
                <div className="lg:col-span-2 space-y-8">
                    <GlowCard delay={0.2}>
                        <div className="mb-6 flex items-center justify-between">
                            <h3 className="font-mono text-xs font-bold tracking-widest text-indigo-400 uppercase flex items-center gap-2">
                                <Activity className="h-4 w-4" />
                                传感器遥测矩阵
                            </h3>
                            <div className="flex gap-4">
                                <Badge variant="outline" className="border-rose-500/30 bg-rose-500/10 text-rose-400 font-mono text-[10px]">
                                    <Thermometer className="mr-1 h-3 w-3" /> 温度过高
                                </Badge>
                                <Badge variant="outline" className="border-blue-500/30 bg-blue-500/10 text-blue-400 font-mono text-[10px]">
                                    <Droplets className="mr-1 h-3 w-3" /> 湿度正常
                                </Badge>
                            </div>
                        </div>

                        {isSensorLoading ? (
                            <div className="flex h-80 items-center justify-center">
                                <div className="h-10 w-10 border-t-2 border-indigo-500 rounded-full animate-spin" />
                            </div>
                        ) : sensorChartData.length > 0 ? (
                            <div className="h-80 w-full">
                                <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                                    <AreaChart data={sensorChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                                            </linearGradient>
                                            <linearGradient id="colorHum" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                        <XAxis dataKey="time" stroke="#475569" tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} dy={10} />
                                        <YAxis yAxisId="left" stroke="#475569" tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} dx={-10} />
                                        <YAxis yAxisId="right" orientation="right" stroke="#475569" tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} dx={10} />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: "rgba(15, 23, 42, 0.9)",
                                                border: "1px solid rgba(56, 189, 248, 0.2)",
                                                borderRadius: "8px",
                                                boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
                                                color: "#fff",
                                                backdropFilter: "blur(8px)",
                                            }}
                                            itemStyle={{ fontSize: "12px", fontFamily: "monospace" }}
                                            labelStyle={{ fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}
                                        />
                                        <Legend iconType="circle" wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "20px" }} />
                                        <Area yAxisId="left" type="monotone" dataKey="temperature" name="温度(°C)" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorTemp)" />
                                        <Area yAxisId="right" type="monotone" dataKey="humidity" name="湿度(%)" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorHum)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        ) : (
                            <div className="flex h-80 items-center justify-center font-mono text-sm text-slate-500">
                                未发现遥测数据
                            </div>
                        )}
                    </GlowCard>

                    {/* Timeline */}
                    <GlowCard delay={0.4}>
                        <h3 className="mb-6 font-mono text-xs font-bold tracking-widest text-emerald-400 uppercase flex items-center gap-2">
                            <Wind className="h-4 w-4" />
                            量子事件追溯日志
                        </h3>
                        <div className="relative pl-6 border-l border-emerald-500/20 space-y-8">
                            {trace.timeline.map((event, i) => {
                                const isAnchored = event.ingest_status === "ANCHORED";
                                return (
                                    <motion.div
                                        key={event.event_id || i}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.5 + i * 0.1 }}
                                        className="relative"
                                    >
                                        {/* Node Marker */}
                                        <div className={`absolute -left-[33px] top-1.5 h-4 w-4 rounded-full border-2 ${
                                            isAnchored ? "border-emerald-500 bg-slate-900 shadow-[0_0_10px_rgba(52,211,153,0.8)]" : "border-slate-500 bg-slate-900"
                                        }`} />

                                        <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-5 transition-all hover:bg-slate-800/60 hover:border-emerald-500/30">
                                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                                                <div className="flex items-center gap-3">
                                                    <span className="font-mono text-sm font-bold text-white">事件 {event.event_id}</span>
                                                    {isAnchored ? (
                                                        <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 font-mono text-[10px]">已锚定</Badge>
                                                    ) : (
                                                        <Badge variant="outline" className="border-slate-600 text-slate-400 font-mono text-[10px]">等待中</Badge>
                                                    )}
                                                    {event.quality_grade && (
                                                        <Badge className={`bg-transparent border font-mono text-[10px] ${
                                                            event.quality_grade === "A" ? "border-emerald-500/50 text-emerald-400" :
                                                            event.quality_grade === "C" ? "border-red-500/50 text-red-400" : "border-yellow-500/50 text-yellow-400"
                                                        }`}>
                                                            评级_{event.quality_grade}
                                                        </Badge>
                                                    )}
                                                </div>
                                                <span className="font-mono text-[11px] text-slate-400">
                                                    {format(new Date(event.timestamp), "yyyy.MM.dd HH:mm:ss")}
                                                </span>
                                            </div>

                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm font-mono">
                                                <div>
                                                    <span className="text-slate-500 text-[10px] block mb-1">处理状态</span>
                                                    <span className="text-slate-300">{event.ingest_status}</span>
                                                </div>
                                                {event.anchor && (
                                                    <div className="md:col-span-2">
                                                        <span className="text-slate-500 text-[10px] block mb-1">链上哈希</span>
                                                        <code className="block bg-slate-950/80 rounded px-3 py-2 text-xs text-indigo-300 border border-slate-800 truncate">
                                                            {event.anchor.transaction_hash}
                                                        </code>
                                                    </div>
                                                )}
                                                {event.alert_snapshot && event.alert_snapshot.total > 0 && (
                                                    <div className="md:col-span-2">
                                                        <div className="flex items-center gap-2 mt-2 bg-rose-950/30 border border-rose-500/20 rounded p-3 text-rose-400 text-xs">
                                                            <ShieldAlert className="h-4 w-4" />
                                                            严重告警： {event.alert_snapshot.high_open} / {event.alert_snapshot.open}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </div>
                    </GlowCard>
                </div>

                {/* Right Column */}
                <div className="space-y-8">
                    {/* Quality Badges */}
                    {trace.timeline.some((e) => e.quality_grade) && (
                        <GlowCard delay={0.3}>
                            <h3 className="mb-6 font-mono text-xs font-bold tracking-widest text-amber-400 uppercase flex items-center gap-2">
                                <Thermometer className="h-4 w-4" />
                                质量评估矩阵
                            </h3>
                            <div className="space-y-3">
                                {trace.timeline.filter(e => e.quality_grade).map((e, idx) => (
                                    <div key={e.event_id || idx} className="flex items-center gap-4 rounded-xl border border-slate-700/50 bg-slate-800/30 p-4 transition-all hover:bg-slate-800/50">
                                        <div className={`flex items-center justify-center h-12 w-12 rounded-lg bg-slate-900 border border-slate-700 text-2xl font-black font-mono ${QUALITY_COLORS[e.quality_grade!] || "text-slate-400"}`}>
                                            {e.quality_grade}
                                        </div>
                                        <div className="flex-1 font-mono">
                                            <div className="text-xs text-slate-400 mb-1">事件 {e.event_id}</div>
                                            <div className="text-sm text-slate-200">
                                                {format(new Date(e.timestamp), "MM.dd HH:mm")}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </GlowCard>
                    )}
                    
                    {/* Node Info (Static for visuals) */}
                    <GlowCard delay={0.5}>
                        <h3 className="mb-6 font-mono text-xs font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-2">
                            <Radio className="h-4 w-4" />
                            网络节点状态
                        </h3>
                        <div className="space-y-4 font-mono text-xs">
                            <div className="flex justify-between items-center border-b border-slate-700/50 pb-2">
                                <span className="text-slate-500">链路状态</span>
                                <span className="text-emerald-400 flex items-center gap-2"><div className="h-1.5 w-1.5 bg-emerald-400 rounded-full animate-pulse"/> 安全</span>
                            </div>
                            <div className="flex justify-between items-center border-b border-slate-700/50 pb-2">
                                <span className="text-slate-500">加密协议</span>
                                <span className="text-slate-300">AES-256-GCM</span>
                            </div>
                            <div className="flex justify-between items-center pb-2">
                                <span className="text-slate-500">丢包率</span>
                                <span className="text-slate-300">0.004%</span>
                            </div>
                        </div>
                    </GlowCard>
                </div>
            </div>
            
            {/* Global Background UI Elements */}
            <div className="fixed inset-0 pointer-events-none -z-10 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-900/10 via-slate-950 to-slate-950" />
        </div>
    );
}
