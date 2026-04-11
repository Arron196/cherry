"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type DeviceIngestGuideCardProps = {
    guideDeviceId: string;
    resolvedGuideKeyId: string;
    resolvedGuideAlgorithm: string;
    resolvedGuideSecret: string;
    hasRealGuideSecret: boolean;
    guidePayloadExample: string;
    guideRequestExample: string;
};

export function DeviceIngestGuideCard({
    guideDeviceId,
    resolvedGuideKeyId,
    resolvedGuideAlgorithm,
    resolvedGuideSecret,
    hasRealGuideSecret,
    guidePayloadExample,
    guideRequestExample,
}: DeviceIngestGuideCardProps) {
    return (
        <Card className="panel-shell edge-highlight md:col-span-2 border-slate-700/75">
            <CardHeader>
                <CardTitle>设备接入向导（演示版）</CardTitle>
                <CardDescription>
                    用当前页面已创建的设备与密钥，构造 `/v1/events` 上报请求。当前后端仅支持 `HMAC_SHA256`。
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="grid gap-3 md:grid-cols-4">
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
                    <div className="rounded border border-slate-700/75 bg-slate-900/45 px-3 py-2">
                        <p className="text-slate-300">secret</p>
                        <p className="font-mono text-slate-100">{resolvedGuideSecret}</p>
                    </div>
                </div>

                <div className="rounded border border-slate-700/75 bg-slate-900/45 px-3 py-2">
                    <p className="mb-1 text-slate-200">上报 payload 示例（签名前结构）：</p>
                    <pre className="overflow-x-auto rounded bg-slate-950/60 p-2 text-xs text-slate-200">
                        {guidePayloadExample}
                    </pre>
                </div>

                <div className="rounded border border-slate-700/75 bg-slate-900/45 px-3 py-2">
                    <p className="mb-1 text-slate-200">请求示例（cURL）：</p>
                    <pre className="overflow-x-auto rounded bg-slate-950/60 p-2 text-xs text-slate-200">
                        {guideRequestExample}
                    </pre>
                </div>

                <div className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-amber-200">
                    <p>签名规则：仅对 `version/device_id/batch_id/timestamp/sensor_payload/signature_envelope.algorithm/signature_envelope.key_id` 做 canonicalize 后计算 HMAC-SHA256（hex）。</p>
                    <p className="mt-1">密钥来源：设备当前 active key 对应的 secret。</p>
                    <p className="mt-2">{hasRealGuideSecret ? "当前可用 secret：" : "暂无真实 secret，展示演示值："}</p>
                    <code className="block break-all rounded bg-slate-950/60 px-2 py-1 text-xs">{resolvedGuideSecret}</code>
                </div>
            </CardContent>
        </Card>
    );
}
