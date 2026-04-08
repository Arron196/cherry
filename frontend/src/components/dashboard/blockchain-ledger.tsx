"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Database, Link2, Hexagon } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useSimulationStore } from "@/hooks/use-simulation";
import type { DashboardStatsResponse } from "@/types/api";

interface BlockEntry {
    id: string;
    hash: string;
    time: string;
    node: string;
}

const generateDeterministicHash = (seed: number) => {
    let value = seed;
    return (
        "0x" +
        Array.from({ length: 40 }, (_, index) => {
            value = (value * 1664525 + 1013904223 + index) >>> 0;
            return (value & 0xf).toString(16);
        }).join("")
    );
};

const INITIAL_BLOCKS: BlockEntry[] = Array.from({ length: 6 }, (_, index) => {
    const blockNumber = 18298 - index;
    return {
        id: `BLK-${blockNumber}`,
        hash: generateDeterministicHash(blockNumber),
        time: `14:${String(42 - index).padStart(2, "0")}:00`,
        node: ["Node-C", "Node-B", "Node-A"][index % 3],
    };
});

export function BlockchainLedger({ dashboardStats }: { dashboardStats?: DashboardStatsResponse }) {
    const { isSimulating, blocks: generatedBlocks } = useSimulationStore();

    const eventBlocks: BlockEntry[] = (dashboardStats?.recent_events ?? [])
        .filter((event) => event.ingest_status === "ANCHORED")
        .map((event) => {
            const timestamp = new Date(event.timestamp);
            return {
                id: `EVT-${event.id}`,
                hash: event.anchor_transaction_hash ?? generateDeterministicHash(event.id),
                time: Number.isNaN(timestamp.getTime())
                    ? "--:--:--"
                    : timestamp.toLocaleTimeString("en-GB", { hour12: false }),
                node: event.device_id,
            };
        });
    const hasBackendBlocks = eventBlocks.length > 0;
    const blocks = (
        hasBackendBlocks
            ? eventBlocks
            : isSimulating && generatedBlocks.length > 0
              ? generatedBlocks
              : isSimulating
                ? INITIAL_BLOCKS
                : []
    ).slice(0, 10);
    const waitingForRealGateway = !isSimulating && !hasBackendBlocks;

    return (
        <Card className="panel-shell edge-highlight col-span-full xl:col-span-1 overflow-hidden border-slate-700/80 bg-slate-900/86">
            <CardHeader className="border-b border-primary-500/10 bg-slate-900/40 px-6 py-4 flex flex-row items-center justify-between space-y-0">
                <div>
                    <CardTitle className="display-heading flex items-center gap-2 text-base font-semibold text-slate-100">
                        <Database className="h-4 w-4 text-primary-400" />
                        区块链锚定流水
                    </CardTitle>
                    <p className="mt-1 text-xs text-slate-400">实时分布式账本共识监控</p>
                </div>
                <div className="flex -space-x-1.5">
                    <div className={`h-3 w-3 rounded-full border border-slate-800 bg-primary-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] ${isSimulating ? 'animate-pulse' : 'opacity-40'}`} />
                    <div className="h-3 w-3 rounded-full border border-slate-800 bg-cyan-400" />
                    <div className="h-3 w-3 rounded-full border border-slate-800 bg-amber-400" />
                </div>
            </CardHeader>
            <CardContent className="h-[280px] p-0 relative overflow-hidden bg-[rgb(var(--background))] font-mono text-xs">
                {waitingForRealGateway && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/60 backdrop-blur-[2px]">
                        <div className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/80 px-4 py-2 text-sm text-slate-300 shadow-xl">
                            <Database className="h-4 w-4 text-cyan-400" />
                            等待真实网关推送区块...
                        </div>
                    </div>
                )}
                {/* Scanline overlay */}
                <div className="absolute inset-0 pointer-events-none z-10 bg-[linear-gradient(rgba(16,185,129,0.1)_1px,transparent_1px)] bg-[size:100%_4px] mix-blend-overlay opacity-30" />
                <div className="h-full w-full overflow-hidden p-4">
                    <AnimatePresence initial={false}>
                        {blocks.map((block) => (
                            <motion.div
                                key={block.id}
                                initial={{ opacity: 0, y: -20, x: -10 }}
                                animate={{ opacity: 1, y: 0, x: 0 }}
                                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                                className="group mb-2.5 flex items-center gap-3 rounded-lg border border-slate-800/80 bg-slate-900/60 p-2.5 shadow-sm transition-colors hover:border-primary-500/30 hover:bg-slate-800"
                            >
                                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-slate-700 bg-slate-950 text-slate-400 group-hover:text-primary-400 group-hover:border-primary-500/50 transition-colors">
                                    <Hexagon className="h-3.5 w-3.5" />
                                </div>
                                <div className="flex min-w-0 flex-1 flex-col gap-1">
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="font-semibold text-primary-300">
                                            {block.id}
                                        </span>
                                        <span className="text-[10px] text-slate-500 flex items-center">
                                            <Link2 className="mr-1 h-3 w-3" />
                                            {block.node}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between gap-3">
                                        <span className="truncate text-slate-400 font-mono text-[11px] opacity-75">
                                            {block.hash}
                                        </span>
                                        <span className="shrink-0 text-slate-500">
                                            {block.time}
                                        </span>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            </CardContent>
        </Card>
    );
}
