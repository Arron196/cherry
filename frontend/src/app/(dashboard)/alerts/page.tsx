"use client";

import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import { ArrowUpCircle, CheckCircle, Loader2, ShieldAlert } from "lucide-react";
import { useAlerts, useAlertActions } from "@/hooks/use-queries";
import { useAuthStore } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { t } from "@/lib/translations";

export default function AlertsPage() {
    const { data, isLoading, isError, error, refetch, isFetching } = useAlerts({ limit: 50 });
    const { ack, resolve, escalate } = useAlertActions();
    const { role } = useAuthStore();
    const canAct = role === "admin" || role === "regulator";
    const [feedback, setFeedback] = useState<{ type: "ok" | "error"; text: string } | null>(null);

    const handleAction = async (action: "ack" | "resolve" | "escalate", id: number) => {
        try {
            if (action === "ack") await ack.mutateAsync(id);
            if (action === "resolve") await resolve.mutateAsync(id);
            if (action === "escalate") await escalate.mutateAsync(id);
            setFeedback({ type: "ok", text: "操作成功，列表已更新。" });
        } catch (error) {
            const detail = typeof error === "object" && error !== null && "detail" in error ? String((error as { detail: unknown }).detail) : "未知错误";
            setFeedback({ type: "error", text: `操作失败：${detail}` });
        }
    };

    const alertQueryErrorDetail = typeof error === "object" && error !== null && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "请稍后重试。";

    return (
        <div className="space-y-7">
            <section className="panel-shell edge-highlight p-5 md:p-6">
                <div className="flex items-center gap-3">
                    <span className="edge-highlight inline-flex h-10 w-10 items-center justify-center rounded-xl border border-red-400/30 bg-red-500/15 text-red-300">
                        <ShieldAlert className="h-5 w-5" />
                    </span>
                    <div>
                        <h1 className="display-heading text-2xl font-semibold tracking-tight text-white md:text-3xl">告警中心</h1>
                        <p className="mt-1 text-sm text-slate-300">处理 待处理 / 处理中 / 已解决 全流程告警。</p>
                    </div>
                </div>
            </section>

            <Card className="panel-shell edge-highlight">
                <CardHeader>
                    <CardTitle className="display-heading">当前系统告警</CardTitle>
                </CardHeader>
                <CardContent>
                    {feedback && (
                        <div
                            className={`mb-4 rounded-md border px-3 py-2 text-sm ${feedback.type === "ok"
                                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                                : "border-red-500/30 bg-red-500/10 text-red-300"
                                }`}
                        >
                            {feedback.text}
                        </div>
                    )}

                    {isLoading && (
                        <div className="flex h-32 items-center justify-center">
                            <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
                        </div>
                    )}

                    {isError && !isLoading && (
                        <div className="edge-highlight mb-4 flex flex-col items-start gap-3 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                            <p>告警数据加载失败：{alertQueryErrorDetail}</p>
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => refetch()}
                                disabled={isFetching}
                            >
                                {isFetching && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                                重试
                            </Button>
                        </div>
                    )}

                    <div className="space-y-4">
                        {!isLoading && !isError && data?.alerts.map((alertItem) => (
                            <div
                                key={alertItem.id}
                            className="edge-highlight flex flex-col items-start justify-between gap-4 rounded-xl border border-slate-700/75 bg-slate-800/55 p-4 transition-colors hover:border-cyan-400/35 hover:bg-slate-800/72 md:flex-row md:items-center"
                            >
                                <div className="space-y-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span
                                            className={`edge-highlight inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium uppercase tracking-wider ${alertItem.severity === "critical"
                                                ? "bg-red-500/20 text-red-300"
                                                : alertItem.severity === "high"
                                                    ? "bg-orange-500/20 text-orange-300"
                                                    : alertItem.severity === "medium"
                                                        ? "bg-yellow-500/20 text-yellow-300"
                                                        : "bg-blue-500/20 text-blue-300"
                                                }`}
                                        >
                                            {t(alertItem.severity)}
                                        </span>
                                        <span
                                            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium uppercase tracking-wider ${alertItem.status === "open"
                                                ? "border-red-500/50 text-red-300"
                                                : alertItem.status === "acknowledged"
                                                    ? "border-yellow-500/50 text-yellow-300"
                                                    : "border-emerald-500/50 text-emerald-300"
                                                }`}
                                        >
                                            {t(alertItem.status)}
                                        </span>
                                        <span className="text-xs text-slate-300">
                                            {formatDistanceToNow(new Date(alertItem.raised_at), {
                                                addSuffix: true,
                                                locale: zhCN,
                                            })}
                                        </span>
                                    </div>
                                    <p className="font-medium text-slate-100">{alertItem.message}</p>
                                    <p className="font-mono text-xs text-slate-300">类型：{t(alertItem.alert_type)} ｜ 事件 ID：{alertItem.event_id}</p>
                                </div>

                                {canAct && alertItem.status !== "resolved" && (
                                    <div className="flex shrink-0 flex-wrap gap-2">
                                        {alertItem.status === "open" && (
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => handleAction("ack", alertItem.id)}
                                                disabled={ack.isPending}
                                            >
                                                确认
                                            </Button>
                                        )}
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            className="border-emerald-500/20 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 hover:text-emerald-200"
                                            onClick={() => handleAction("resolve", alertItem.id)}
                                            disabled={resolve.isPending}
                                        >
                                            <CheckCircle className="mr-1 h-3 w-3" />
                                            解决
                                        </Button>
                                        {alertItem.severity !== "critical" && (
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="text-red-300 hover:bg-red-500/10 hover:text-red-200"
                                                onClick={() => handleAction("escalate", alertItem.id)}
                                                disabled={escalate.isPending}
                                            >
                                                <ArrowUpCircle className="mr-1 h-3 w-3" />
                                                升级
                                            </Button>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                        {data?.alerts.length === 0 && !isLoading && !isError && (
                            <div className="py-8 text-center text-slate-300">
                                <CheckCircle className="mx-auto mb-2 h-12 w-12 opacity-20" />
                                暂无活跃告警，系统状态良好。
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
