"use client";

import { useState } from "react";
import { format } from "date-fns";
import { Loader2, Play, RotateCcw, ShieldCheck } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Services } from "@/lib/services";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { t } from "@/lib/translations";

const statusOptions = ["RECEIVED", "ANCHORING", "ANCHORED", "FAILED_RETRYING", "DEAD_LETTER"] as const;

export default function AnchoringPage() {
    const queryClient = useQueryClient();
    const [status, setStatus] = useState<(typeof statusOptions)[number]>("RECEIVED");
    const [message, setMessage] = useState<string | null>(null);
    const limit = 20;

    const { data, isLoading } = useQuery({
        queryKey: ["anchoring", status],
        queryFn: () => Services.getAnchoringTasks({ status, limit }),
    });

    const requeueMutation = useMutation({
        mutationFn: (id: number) => Services.requeueAnchoringTask(id),
        onSuccess: () => {
            setMessage("任务已重新入队。请稍后刷新查看状态。");
            queryClient.invalidateQueries({ queryKey: ["anchoring"] });
        },
        onError: (error) => {
            const detail = typeof error === "object" && error !== null && "detail" in error ? String((error as { detail: unknown }).detail) : "未知错误";
            setMessage(`重入队失败：${detail}`);
        },
    });

    const runOnceMutation = useMutation({
        mutationFn: () => Services.runAnchoringOnce(),
        onSuccess: () => {
            setMessage("已触发一次锚定执行。");
            queryClient.invalidateQueries({ queryKey: ["anchoring"] });
        },
        onError: (error) => {
            const detail = typeof error === "object" && error !== null && "detail" in error ? String((error as { detail: unknown }).detail) : "未知错误";
            setMessage(`执行失败：${detail}`);
        },
    });

    return (
        <div className="space-y-7">
            <section className="panel-shell edge-highlight p-5 md:p-6">
                <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
                    <div className="flex items-center gap-3">
                        <span className="edge-highlight inline-flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-400/30 bg-emerald-500/15 text-emerald-300">
                            <ShieldCheck className="h-5 w-5" />
                        </span>
                        <div>
                            <h1 className="display-heading text-2xl font-semibold tracking-tight text-white md:text-3xl">锚定任务</h1>
                            <p className="mt-1 text-sm text-slate-300">按状态管理链上锚定队列并支持失败任务重入队。</p>
                        </div>
                    </div>
                    <Button onClick={() => runOnceMutation.mutate()} disabled={runOnceMutation.isPending}>
                        {runOnceMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                        立即执行锚定
                    </Button>
                </div>
            </section>

            <Card className="panel-shell edge-highlight">
                <CardHeader>
                    <div className="flex flex-wrap items-center gap-2">
                        {statusOptions.map((itemStatus) => (
                            <Button
                                key={itemStatus}
                                variant={status === itemStatus ? "default" : "secondary"}
                                size="sm"
                                onClick={() => setStatus(itemStatus)}
                            >
                                {t(itemStatus)}
                            </Button>
                        ))}
                    </div>
                </CardHeader>
                <CardContent>
                    {message && (
                        <div className="edge-highlight mb-4 rounded-md border border-slate-700/75 bg-slate-800/60 px-3 py-2 text-sm text-slate-200">
                            {message}
                        </div>
                    )}

                    {isLoading && (
                        <div className="flex items-center justify-center p-8">
                            <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
                        </div>
                    )}

                    <div className="space-y-4">
                        {data?.items.map((task) => (
                            <div
                                key={task.ingest_request_id}
                                className="edge-highlight flex flex-col justify-between gap-3 rounded-xl border border-slate-700/75 bg-slate-800/55 p-4 transition-colors hover:border-cyan-400/35 hover:bg-slate-800/72 md:flex-row md:items-center"
                            >
                                <div>
                                    <p className="font-mono text-sm text-slate-200">任务 #{task.ingest_request_id} ｜ 批次：{task.batch_id || "N/A"}</p>
                                    <div className="mt-1 flex flex-wrap items-center gap-2">
                                        <span className="text-xs text-slate-300">{format(new Date(task.created_at), "yyyy-MM-dd HH:mm:ss")}</span>
                                        {task.last_error && <span className="text-xs text-red-300">错误：{task.last_error}</span>}
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="mr-2 text-right">
                                        <span className="mr-2 text-xs uppercase text-slate-300">重试次数</span>
                                        <span className="font-mono text-white">{task.retry_count}</span>
                                    </div>
                                    {(task.status === "FAILED_RETRYING" || task.status === "DEAD_LETTER") && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => requeueMutation.mutate(task.ingest_request_id)}
                                            disabled={requeueMutation.isPending}
                                        >
                                            <RotateCcw className="mr-1 h-3 w-3" /> 重新入队
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                        {data?.items.length === 0 && !isLoading && (
                            <div className="py-8 text-center border border-dashed border-slate-700/50 rounded-xl text-slate-400 bg-slate-800/20">
                                当前状态 <span className="font-semibold text-slate-300 px-1">{t(status)}</span> 下暂无任务记录
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
