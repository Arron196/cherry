"use client";

import { motion } from "framer-motion";
import { TreePine, Factory, Truck, Store, Radio } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useSimulationStore } from "@/hooks/use-simulation";
import type { DashboardStatsResponse } from "@/types/api";

const baseNodes = [
    { id: "farm", label: "源头数字农田", icon: TreePine, color: "text-emerald-400", statsLabel: "温湿度传感器", statMax: 120 },
    { id: "factory", label: "数字化初加工", icon: Factory, color: "text-cyan-400", statsLabel: "加工批次/天", statMax: 35 },
    { id: "logistics", label: "冷链运输网络", icon: Truck, color: "text-blue-400", statsLabel: "在途车辆", statMax: 12 },
    { id: "retail", label: "零售终端门店", icon: Store, color: "text-amber-400", statsLabel: "待上架包裹", statMax: 80 },
];

export function SupplyChainMap({ dashboardStats }: { dashboardStats?: DashboardStatsResponse }) {
    const { isSimulating } = useSimulationStore();
    const stageCounts = new Map(
        (dashboardStats?.stage_distribution ?? []).map((item) => [item.stage, item.count])
    );
    const stats = [
        stageCounts.get("harvest") ?? 0,
        stageCounts.get("storage") ?? 0,
        stageCounts.get("transport") ?? 0,
        stageCounts.get("retail") ?? 0,
    ];
    const hasBackendStages = stats.some((count) => count > 0);
    const waitingForRealGateway = !isSimulating && !hasBackendStages;
    const isFlowActive = isSimulating || hasBackendStages;

    return (
        <Card className="panel-shell edge-highlight col-span-full xl:col-span-2 overflow-hidden border-slate-700/80 bg-slate-900/86">
            <CardHeader className="border-b border-primary-500/10 bg-slate-900/40 px-6 py-4 flex flex-row items-center justify-between space-y-0">
                <div>
                    <CardTitle className="display-heading flex items-center gap-2 text-base font-semibold text-slate-100">
                        <div className={`h-2 w-2 rounded-full shadow-[0_0_8px_rgba(52,211,153,0.8)] ${isFlowActive ? 'bg-primary-400 animate-pulse' : 'bg-slate-600'}`} />
                        全息供应链拓扑流转网
                    </CardTitle>
                    <p className="mt-1 text-xs text-slate-400">实时追踪实物数字 孪生体的位置与状态</p>
                </div>
            </CardHeader>
            <CardContent className="min-h-[280px] h-fit p-6 relative flex flex-col items-center justify-center">
                {waitingForRealGateway && (
                    <div className="absolute top-4 right-4 z-30">
                        <Badge variant="outline" className="border-cyan-500/30 bg-slate-900/80 text-cyan-400 shadow-xl backdrop-blur-md px-3 py-1 text-xs">     
                            <Radio className="mr-1.5 h-3.5 w-3.5" />
                            等待实物流向网关...
                        </Badge>
                    </div>
                )}
                {/* Background Grid */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(100,116,139,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(100,116,139,0.06)_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_20%,transparent_100%)]" />

                <div className="relative w-full max-w-4xl flex items-center justify-between px-8 z-10 pb-20">
                    {/* Connecting svg lines & glowing dots moving along */}    
                    <div className={`absolute top-1/2 left-8 right-8 -translate-y-1/2 h-1 rounded-full overflow-hidden ${isFlowActive ? 'bg-slate-800' : 'bg-slate-800/50'}`}>
                        {isFlowActive && (
                            <motion.div
                                className="h-full w-1/4 bg-gradient-to-r from-transparent via-cyan-400 to-transparent blur-[2px] opacity-70"
                                animate={{
                                    x: ["-100%", "400%"],
                                }}
                                transition={{
                                    duration: 3,
                                    ease: "linear",
                                    repeat: Infinity,
                                }}
                            />
                        )}
                    </div>

                    {baseNodes.map((node, index) => {
                        const Icon = node.icon;
                        return (
                            <div key={node.id} className="relative group z-20 flex flex-col items-center">
                                {/* Pulsing Ring */}
                                <div className="absolute -inset-4 rounded-full bg-slate-800/0 border border-slate-700/0 group-hover:bg-slate-800/40 group-hover:border-slate-700/50 transition-all duration-500 scale-95 group-hover:scale-100" />

                                <motion.div
                                    className={`relative z-10 flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-900/90 shadow-[0_4px_14px_0_rgba(0,0,0,0.1)] backdrop-blur-sm transition-all duration-300 group-hover:scale-110 ${
                                        isFlowActive ? `group-hover:border-${node.color.split("-")[1]}-500/50 group-hover:shadow-[0_0_24px_-4px_rgba(var(--opacity-color),0.4)]` : ''
                                    }`}
                                    whileHover={{ y: -4 }}
                                >
                                    <Icon className={`h-6 w-6 ${isFlowActive ? node.color : 'text-slate-500'}`} />
                                </motion.div>
                                <div className="mt-4 text-center">
                                    <p className={`text-sm font-medium ${isFlowActive ? 'text-slate-200' : 'text-slate-400'}`}>{node.label}</p>
                                    <Badge variant="outline" className={`mt-2 scale-90 border-slate-700/60 bg-slate-900/50 text-[10px] text-slate-400 inline-flex items-center ${!isFlowActive && 'opacity-50'}`}>
                                        <div className={`mr-1.5 h-1.5 w-1.5 rounded-full ${node.color.replace('text-', 'bg-')} ${isFlowActive ? 'animate-pulse' : 'opacity-40'}`} />
                                        Node_{index + 1}0
                                    </Badge>
                                </div>
                                <div className="absolute top-full mt-12 text-center w-32">
                                    {isFlowActive && (
                                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-1 items-center">
                                          <span className="text-xs text-slate-500">{node.statsLabel}</span>
                                          <span className={`text-sm font-mono font-bold ${node.color}`}>{stats[index]}</span>
                                        </motion.div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
}
