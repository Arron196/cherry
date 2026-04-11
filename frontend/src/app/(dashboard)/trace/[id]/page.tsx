"use client";

import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import { AlertCircle, Anchor, Clock, Loader2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useTrace } from "@/hooks/use-queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function TraceDetailPage() {
    const params = useParams();
    const batchId = params.id as string;
    const { data: trace, isLoading, isError, error, refetch, isFetching } = useTrace(batchId);

    const errorStatus = typeof error === "object" && error !== null && "status" in error
        ? Number((error as { status: unknown }).status)
        : null;
    const traceErrorDetail = typeof error === "object" && error !== null && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002";

    const isNotFound = (isError && errorStatus === 404) || (!isError && !trace);

    if (isLoading) {
        return (
            <div className="flex h-full items-center justify-center pt-20">
                <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
            </div>
        );
    }

    if (isNotFound) {
        return (
            <div className="flex h-full flex-col items-center justify-center pt-20 text-slate-300">
                <AlertCircle className="mb-4 h-12 w-12" />
                <h2 className="text-xl font-semibold">{"\u672a\u627e\u5230\u6eaf\u6e90\u6570\u636e"}</h2>
                <p>{"\u672a\u627e\u5230\u6279\u6b21 ID\uff1a"}{batchId}{" \u7684\u65f6\u95f4\u7ebf\u4fe1\u606f"}</p>
            </div>
        );
    }

    if (isError) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-3 pt-20 text-slate-300">
                <AlertCircle className="h-12 w-12 text-red-300" />
                <h2 className="text-xl font-semibold text-red-300">{"\u8bf7\u6c42\u5931\u8d25"}</h2>
                <p className="max-w-xl text-center text-sm text-slate-300">
                    {"\u6eaf\u6e90\u6570\u636e\u52a0\u8f7d\u5931\u8d25\uff1a"}{traceErrorDetail}
                </p>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={() => refetch()}
                    disabled={isFetching}
                >
                    {isFetching && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                    {"\u91cd\u8bd5"}
                </Button>
            </div>
        );
    }

    if (!trace) {
        return null;
    }

    return (
        <div className="mx-auto max-w-[1600px] w-full space-y-7">
            <section className="panel-shell edge-highlight flex flex-col gap-2 p-5 md:p-6">
                <h1 className="display-heading mb-1 text-2xl font-semibold tracking-tight text-white md:text-3xl">{"\u6eaf\u6e90\u8be6\u60c5"}</h1>
                <div className="flex items-center gap-2 text-sm text-slate-300">
                    <span className="font-semibold text-slate-200">{"\u6279\u6b21 ID\uff1a"}</span> {trace.batch_id}
                </div>
            </section>

            <Card className="panel-shell edge-highlight">
                <CardHeader>
                    <CardTitle className="display-heading">{"\u4e8b\u4ef6\u65f6\u95f4\u7ebf"}</CardTitle>
                    <CardDescription>{"\u6309\u65f6\u95f4\u987a\u5e8f\u5c55\u793a\u672c\u6279\u6b21\u7684\u4e8b\u4ef6\u8bb0\u5f55\u3002"}</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="relative ml-3 space-y-8 border-l border-cyan-500/25 pb-4">
                        {trace.timeline.map((event, index) => {
                            const date = new Date(event.timestamp);
                            const isAnchored = event.ingest_status === "ANCHORED";
                            const eventKey = event.event_id ?? `${event.timestamp}-${index}`;

                            return (
                                <div key={eventKey} className="relative mb-8 ml-5">
                                    <span
                                        className={`absolute -left-[31px] flex h-7 w-7 items-center justify-center rounded-full ring-4 ring-slate-900 ${isAnchored ? "bg-emerald-500/20 text-emerald-300" : "bg-primary-500/20 text-primary-300"
                                            }`}
                                    >
                                        {isAnchored ? <Anchor className="h-4 w-4" /> : <Clock className="h-4 w-4" />}
                                    </span>

                                    <div className="edge-highlight rounded-lg border border-slate-700/75 bg-slate-800/55 p-4 transition-colors hover:border-cyan-400/35 hover:bg-slate-800/72">
                                        <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                                            <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
                                                {"\u4e8b\u4ef6 #"}{event.event_id}
                                                {isAnchored && (
                                                    <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                                                        {"\u5df2\u951a\u5b9a"}
                                                    </span>
                                                )}
                                            </h3>
                                            <time className="text-sm text-slate-300">{format(date, "PPP p", { locale: zhCN })}</time>
                                        </div>

                                        <div className="mt-2 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
                                            <div>
                                                <span className="block text-xs uppercase tracking-wider text-slate-300">{"\u5904\u7406\u72b6\u6001"}</span>
                                                <span className="font-mono text-slate-200">{event.ingest_status}</span>
                                            </div>
                                            {event.quality_grade && (
                                                <div>
                                                    <span className="block text-xs uppercase tracking-wider text-slate-300">{"\u8d28\u91cf\u7b49\u7ea7"}</span>
                                                    <span
                                                        className={`font-bold ${event.quality_grade === "A"
                                                            ? "text-emerald-300"
                                                            : event.quality_grade === "B"
                                                                ? "text-blue-300"
                                                                : "text-yellow-300"
                                                            }`}
                                                    >
                                                        {event.quality_grade}
                                                    </span>
                                                </div>
                                            )}
                                            {event.anchor && (
                                                <div className="mt-1 border-t border-slate-700/75 pt-2 md:col-span-2">
                                                    <span className="mb-1 block text-xs uppercase tracking-wider text-slate-300">{"\u94fe\u4e0a\u4ea4\u6613\u54c8\u5e0c"}</span>
                                                    <code className="edge-highlight block truncate rounded-md border border-slate-700/70 bg-slate-950/88 px-2 py-1 text-xs text-slate-200">
                                                        {event.anchor.transaction_hash}
                                                    </code>
                                                </div>
                                            )}
                                            {event.alert_snapshot && event.alert_snapshot.total > 0 && (
                                                <div className="mt-1 md:col-span-2">
                                                    <div className="edge-highlight flex items-center gap-2 rounded border border-yellow-400/30 bg-yellow-500/10 p-2 text-xs text-yellow-300">
                                                        <AlertCircle className="h-4 w-4" />
                                                        <span>
                                                            {"\u6253\u5f00\u544a\u8b66 "}{event.alert_snapshot.open}{" \u6761\uff08\u9ad8\u4f18\u5148\u7ea7\u53ca\u4ee5\u4e0a "}{event.alert_snapshot.high_open}{" \u6761\uff09"}
                                                        </span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
