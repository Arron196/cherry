"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DeviceTestEventResult } from "./device-admin.types";
import { toPrettyJson } from "./device-admin.utils";

type DeviceTestEventCardProps = {
    guideDeviceId: string;
    resolvedGuideKeyId: string;
    resolvedGuideAlgorithm: string;
    testEventBatchId: string;
    testEventTimestamp: string;
    testEventTemperature: string;
    testEventHumidity: string;
    testEventStatus: string;
    isPending: boolean;
    testEventError: string;
    testEventResult: DeviceTestEventResult | null;
    onBatchIdChange: (value: string) => void;
    onTimestampChange: (value: string) => void;
    onTemperatureChange: (value: string) => void;
    onHumidityChange: (value: string) => void;
    onStatusChange: (value: string) => void;
    onUseCurrentTime: () => void;
    onSubmit: () => void;
};

export function DeviceTestEventCard({
    guideDeviceId,
    resolvedGuideKeyId,
    resolvedGuideAlgorithm,
    testEventBatchId,
    testEventTimestamp,
    testEventTemperature,
    testEventHumidity,
    testEventStatus,
    isPending,
    testEventError,
    testEventResult,
    onBatchIdChange,
    onTimestampChange,
    onTemperatureChange,
    onHumidityChange,
    onStatusChange,
    onUseCurrentTime,
    onSubmit,
}: DeviceTestEventCardProps) {
    return (
        <Card className="panel-shell edge-highlight md:col-span-2 border-slate-700/75">
            <CardHeader>
                <CardTitle>自动签名并发送测试事件</CardTitle>
                <CardDescription>
                    使用当前页面可用的设备、key_id 与 secret，自动签名后调用 `/v1/events`。成功后会刷新设备列表与详情。
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-slate-300">
                <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded border border-slate-700/75 bg-slate-900/45 px-3 py-2">
                        <p className="text-slate-300">device_id</p>
                        <p className="font-mono text-slate-100">{guideDeviceId}</p>
                    </div>
                    <div className="rounded border border-slate-700/75 bg-slate-900/45 px-3 py-2">
                        <p className="text-slate-300">key_id</p>
                        <p className="font-mono text-slate-100">{resolvedGuideKeyId}</p>
                    </div>
                    <div className="rounded border border-slate-700/75 bg-slate-900/45 px-3 py-2">
                        <p className="text-slate-300">algorithm</p>
                        <p className="font-mono text-slate-100">{resolvedGuideAlgorithm}</p>
                    </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-xs text-slate-300" htmlFor="test-event-batch-id">批次 ID</label>
                        <Input
                            id="test-event-batch-id"
                            value={testEventBatchId}
                            onChange={(event) => onBatchIdChange(event.target.value)}
                            placeholder="例如：batch-demo-20260211-100000"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs text-slate-300" htmlFor="test-event-timestamp">时间戳（ISO8601）</label>
                        <Input
                            id="test-event-timestamp"
                            value={testEventTimestamp}
                            onChange={(event) => onTimestampChange(event.target.value)}
                            placeholder="例如：2026-02-11T10:00:00Z"
                        />
                    </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                    <div className="space-y-2">
                        <label className="text-xs text-slate-300" htmlFor="test-event-temperature">温度（℃）</label>
                        <Input
                            id="test-event-temperature"
                            value={testEventTemperature}
                            onChange={(event) => onTemperatureChange(event.target.value)}
                            placeholder="4.2"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs text-slate-300" htmlFor="test-event-humidity">湿度（%）</label>
                        <Input
                            id="test-event-humidity"
                            value={testEventHumidity}
                            onChange={(event) => onHumidityChange(event.target.value)}
                            placeholder="72"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs text-slate-300" htmlFor="test-event-status">状态</label>
                        <Input
                            id="test-event-status"
                            value={testEventStatus}
                            onChange={(event) => onStatusChange(event.target.value)}
                            placeholder="stable"
                        />
                    </div>
                </div>

                <div className="flex flex-wrap gap-2">
                    <Button type="button" onClick={onSubmit} loading={isPending}>
                        自动签名并发送
                    </Button>
                    <Button type="button" variant="outline" onClick={onUseCurrentTime} disabled={isPending}>
                        使用当前时间
                    </Button>
                </div>

                {testEventError ? <p className="text-sm whitespace-pre-line text-red-300">{testEventError}</p> : null}

                {testEventResult && (
                    <div className="space-y-3 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-3">
                        <div className="grid gap-2 text-xs md:grid-cols-3">
                            <p>Idempotency-Key：<span className="font-mono text-slate-100">{testEventResult.idempotency_key}</span></p>
                            <p>event_id：<span className="font-mono text-slate-100">{testEventResult.response.event_id}</span></p>
                            <p>ingest_status：<span className="font-mono text-slate-100">{testEventResult.response.ingest_status}</span></p>
                        </div>
                        <div>
                            <p className="mb-1 text-xs text-emerald-100">请求与返回详情</p>
                            <pre className="overflow-x-auto rounded bg-slate-950/70 p-2 text-xs text-slate-200">
                                {toPrettyJson(testEventResult)}
                            </pre>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
