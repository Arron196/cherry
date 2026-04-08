"use client";

import { useMemo } from "react";
import { Activity, Thermometer, Droplets, Waves } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useSimulationStore } from "@/hooks/use-simulation";
import type { DashboardStatsResponse } from "@/types/api";
import {
    LineChart,
    Line,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

const MAX_DATA_POINTS = 20;
const VEHICLES = ['粤B·782A9', '粤A·331C2', '浙B·991D4', '京A·230F1', '沪C·880E5'];
const CHART_INITIAL_DIMENSION = { width: 800, height: 280 };

type ChartPoint = { time: string; temp: number; hum: number; vib: number };

function formatPointTime(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "--:--:--";
    }
    return date.toLocaleTimeString("en-GB", { hour12: false });
}

export function SensorCharts({ dashboardStats }: { dashboardStats?: DashboardStatsResponse }) {
    const { isSimulating, sensorData } = useSimulationStore();

    const backendPoints: ChartPoint[] = (dashboardStats?.recent_events ?? [])
        .filter((event) => event.temperature_c != null && event.humidity_pct != null)
        .slice()
        .reverse()
        .map((event) => ({
            time: formatPointTime(event.timestamp),
            temp: Number(event.temperature_c),
            hum: Number(event.humidity_pct),
            vib: Number(event.vibration_g ?? 0),
        }));

    const visualPoints: ChartPoint[] = sensorData.map((point) => ({
        time: point.time,
        temp: point.temp,
        hum: point.hum,
        vib: point.vib,
    }));

    const hasBackendTelemetry = backendPoints.length > 0;
    const data = (
        isSimulating
            ? backendPoints.length >= 3 ? backendPoints : visualPoints
            : backendPoints
    ).slice(-MAX_DATA_POINTS);
    const latestPoint = data[data.length - 1];
    const waitingForRealGateway = !isSimulating && !hasBackendTelemetry;
    const currentVehicle = useMemo(() => {
        const latestDeviceId = dashboardStats?.recent_events?.[0]?.device_id;
        if (!latestDeviceId) {
            return VEHICLES[0];
        }
        const index = Math.abs(
            Array.from(latestDeviceId).reduce((acc, char) => acc + char.charCodeAt(0), 0)
        ) % VEHICLES.length;
        return VEHICLES[index];
    }, [dashboardStats?.recent_events]);

    return (
        <Card className="panel-shell edge-highlight col-span-full xl:col-span-1 overflow-hidden border-slate-700/80 bg-slate-900/86">
            <CardHeader className="border-b border-primary-500/10 bg-slate-900/40 px-6 py-4 flex flex-row items-center justify-between space-y-0">
                <div>
                    <CardTitle className="display-heading flex items-center gap-2 text-base font-semibold text-slate-100">
                        <Activity className="h-4 w-4 text-accent-teal" />
                        环境遥测与动环感知
                    </CardTitle>
                    <p className="mt-1 text-xs text-cyan-400/80">车厢 {currentVehicle} （进行中）</p>
                </div>
            </CardHeader>
            <CardContent className="h-[280px] p-6 relative flex flex-col gap-4">
                {waitingForRealGateway && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/60 backdrop-blur-[2px]">
                        <div className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/80 px-4 py-2 text-sm text-slate-300 shadow-xl">
                            <Activity className="h-4 w-4 text-cyan-400" />      
                            等待真实网关推送数据...
                        </div>
                    </div>
                )}
                <div className={`grid grid-cols-3 gap-2 ${waitingForRealGateway ? 'opacity-50' : ''}`}>
                    <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-3 flex flex-col gap-1 items-center justify-center relative overflow-hidden group">
                        <div className="absolute inset-0 bg-primary-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                        <Thermometer className="h-4 w-4 text-emerald-400 mb-1" />
                        <span className="font-mono text-lg font-bold text-slate-100">{latestPoint ? latestPoint.temp.toFixed(1) : '--.-'}°C</span>
                        <span className="text-[10px] text-slate-400">平均冷柜温</span>
                    </div>
                    <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-3 flex flex-col gap-1 items-center justify-center relative overflow-hidden group">
                        <div className="absolute inset-0 bg-cyan-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                        <Droplets className="h-4 w-4 text-cyan-400 mb-1" />     
                        <span className="font-mono text-lg font-bold text-slate-100">{latestPoint ? latestPoint.hum.toFixed(1) : '--.-'}%</span>
                        <span className="text-[10px] text-slate-400">箱体湿度</span>
                    </div>
                    <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-3 flex flex-col gap-1 items-center justify-center relative overflow-hidden group">
                        <div className="absolute inset-0 bg-amber-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                        <Waves className="h-4 w-4 text-amber-400 mb-1" />       
                        <span className="font-mono text-lg font-bold text-slate-100">{latestPoint ? latestPoint.vib.toFixed(2) : '-.--'}G</span>
                        <span className="text-[10px] text-slate-400">综合震动极值</span>
                    </div>
                </div>

                <div className={`flex-1 mt-2 min-h-0 relative ${waitingForRealGateway ? 'opacity-30' : ''}`}>
                    <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={CHART_INITIAL_DIMENSION}>
                        <LineChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} vertical={false} />
                            <Tooltip
                                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(51, 65, 85, 0.8)", borderRadius: "8px", fontSize: "12px" }} 
                                itemStyle={{ color: "#e2e8f0" }}
                            />
                            <Line
                                type="monotone"
                                dataKey="temp"
                                stroke="#10b981"
                                strokeWidth={2}
                                dot={false}
                                isAnimationActive={false}
                                yAxisId="left"
                            />
                            <Line
                                type="monotone"
                                dataKey="vib"
                                stroke="#fbbf24"
                                strokeWidth={2}
                                dot={false}
                                isAnimationActive={false}
                                yAxisId="right"
                            />
                            <YAxis yAxisId="left" domain={[0, 6]} hide />       
                            <YAxis yAxisId="right" orientation="right" domain={[0, 3]} hide />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
}
