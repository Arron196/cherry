"use client";

import { useMemo, useState } from "react";
import { Services } from "@/lib/services";
import { signTraceEventPayload } from "@/lib/signing";
import { ProblemDetails, TraceEventContractPayload } from "@/types/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Wrench } from "lucide-react";

type AnyRecord = Record<string, unknown>;

const DEFAULT_TRACE_EVENT_PAYLOAD = {
    version: "1.0.0",
    device_id: "device-001",
    batch_id: "batch-2026-02-10",
    timestamp: "2026-02-10T02:00:00Z",
    sensor_payload: {
        temperature_c: 4.2,
        humidity_pct: 73.0,
        status: "stable",
    },
    signature_envelope: {
        algorithm: "HMAC_SHA256",
        signature: "placeholder-signature",
        key_id: "factory-key-1",
    },
};

function toPrettyJson(value: unknown): string {
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
}

function formatError(error: unknown): string {
    if (typeof error === "object" && error !== null && "detail" in error) {
        const problem = error as ProblemDetails;
        return problem.detail || "请求失败，请稍后重试。";
    }
    if (error instanceof Error) {
        return error.message;
    }
    return "请求失败，请检查输入后重试。";
}

function parseTraceEventPayload(raw: string): { ok: true; data: TraceEventContractPayload } | { ok: false; message: string } {
    let parsed: unknown;
    try {
        parsed = JSON.parse(raw);
    } catch {
        return { ok: false, message: "事件 JSON 格式错误，请检查逗号和引号。" };
    }

    if (typeof parsed !== "object" || parsed === null) {
        return { ok: false, message: "事件 JSON 必须是对象。" };
    }

    const payload = parsed as AnyRecord;
    const requiredStringFields = ["version", "device_id", "batch_id", "timestamp"] as const;
    for (const field of requiredStringFields) {
        if (typeof payload[field] !== "string" || payload[field].trim() === "") {
            return { ok: false, message: `字段 ${field} 不能为空字符串。` };
        }
    }

    if (typeof payload.sensor_payload !== "object" || payload.sensor_payload === null || Array.isArray(payload.sensor_payload)) {
        return { ok: false, message: "字段 sensor_payload 必须是对象。" };
    }

    if (typeof payload.signature_envelope !== "object" || payload.signature_envelope === null || Array.isArray(payload.signature_envelope)) {
        return { ok: false, message: "字段 signature_envelope 必须是对象。" };
    }

    const signatureEnvelope = payload.signature_envelope as AnyRecord;
    const signatureFields = ["algorithm", "signature", "key_id"] as const;
    for (const field of signatureFields) {
        if (typeof signatureEnvelope[field] !== "string" || signatureEnvelope[field].trim() === "") {
            return { ok: false, message: `字段 signature_envelope.${field} 不能为空字符串。` };
        }
    }

    return {
        ok: true,
        data: {
            version: payload.version as string,
            device_id: payload.device_id as string,
            batch_id: payload.batch_id as string,
            timestamp: payload.timestamp as string,
            sensor_payload: payload.sensor_payload as Record<string, unknown>,
            signature_envelope: {
                algorithm: signatureEnvelope.algorithm as string,
                signature: signatureEnvelope.signature as string,
                key_id: signatureEnvelope.key_id as string,
            },
        },
    };
}

function parseNumber(input: string): number | null {
    const value = Number(input);
    return Number.isFinite(value) ? value : null;
}

export default function ApiToolsPage() {
    const [policyId, setPolicyId] = useState("policy-123");
    const [temperature, setTemperature] = useState("5");
    const [humidity, setHumidity] = useState("72");
    const [idempotencyKey, setIdempotencyKey] = useState("idem-001");
    const [signingSecret, setSigningSecret] = useState("super-secret");
    const [traceEventJson, setTraceEventJson] = useState(toPrettyJson(DEFAULT_TRACE_EVENT_PAYLOAD));

    const [healthResult, setHealthResult] = useState<string>("");
    const [contractResult, setContractResult] = useState<string>("");
    const [ingestResult, setIngestResult] = useState<string>("");
    const [qualityResult, setQualityResult] = useState<string>("");
    const [activateResult, setActivateResult] = useState<string>("");

    const [healthError, setHealthError] = useState<string>("");
    const [contractError, setContractError] = useState<string>("");
    const [ingestError, setIngestError] = useState<string>("");
    const [qualityError, setQualityError] = useState<string>("");
    const [activateError, setActivateError] = useState<string>("");

    const [loading, setLoading] = useState({
        health: false,
        contract: false,
        ingest: false,
        quality: false,
        activate: false,
    });

    const parsedTraceEvent = useMemo(() => parseTraceEventPayload(traceEventJson), [traceEventJson]);

    const ensureSignedTraceEvent = async (
        payload: TraceEventContractPayload,
    ): Promise<TraceEventContractPayload> => {
        if (payload.signature_envelope.algorithm !== "HMAC_SHA256") {
            return payload;
        }

        const secret = signingSecret.trim();
        if (!secret) {
            return payload;
        }

        const signedPayload = await signTraceEventPayload(payload, secret);
        setTraceEventJson(toPrettyJson(signedPayload));
        return signedPayload;
    };

    const handleSignPayload = async () => {
        setIngestError("");
        setContractError("");
        if (!parsedTraceEvent.ok) {
            setIngestError(parsedTraceEvent.message);
            return;
        }

        if (parsedTraceEvent.data.signature_envelope.algorithm !== "HMAC_SHA256") {
            setIngestError("当前仅支持 HMAC_SHA256 自动签名。请修改 algorithm 后重试。");
            return;
        }

        if (!signingSecret.trim()) {
            setIngestError("请输入签名密钥后再自动签名。");
            return;
        }

        try {
            const signedPayload = await ensureSignedTraceEvent(parsedTraceEvent.data);
            setIngestResult(`已自动签名，signature: ${signedPayload.signature_envelope.signature}`);
        } catch (error) {
            setIngestError(`自动签名失败：${formatError(error)}`);
        }
    };

    const handleHealth = async () => {
        setLoading((prev) => ({ ...prev, health: true }));
        setHealthError("");
        setHealthResult("");
        try {
            const data = await Services.getHealth();
            setHealthResult(toPrettyJson(data));
        } catch (error) {
            setHealthError(formatError(error));
        } finally {
            setLoading((prev) => ({ ...prev, health: false }));
        }
    };

    const handleContractValidate = async () => {
        setContractError("");
        setContractResult("");
        if (!parsedTraceEvent.ok) {
            setContractError(parsedTraceEvent.message);
            return;
        }

        setLoading((prev) => ({ ...prev, contract: true }));
        try {
            const signedPayload = await ensureSignedTraceEvent(parsedTraceEvent.data);
            const data = await Services.validateTraceEventContract(signedPayload);
            setContractResult(toPrettyJson(data));
        } catch (error) {
            setContractError(formatError(error));
        } finally {
            setLoading((prev) => ({ ...prev, contract: false }));
        }
    };

    const handleIngest = async () => {
        setIngestError("");
        setIngestResult("");

        if (!idempotencyKey.trim()) {
            setIngestError("请输入 Idempotency-Key。该字段为必填。");
            return;
        }

        if (!parsedTraceEvent.ok) {
            setIngestError(parsedTraceEvent.message);
            return;
        }

        setLoading((prev) => ({ ...prev, ingest: true }));
        try {
            const signedPayload = await ensureSignedTraceEvent(parsedTraceEvent.data);
            const data = await Services.ingestEvent({
                payload: signedPayload,
                idempotencyKey: idempotencyKey.trim(),
            });
            setIngestResult(toPrettyJson(data));
        } catch (error) {
            setIngestError(formatError(error));
        } finally {
            setLoading((prev) => ({ ...prev, ingest: false }));
        }
    };

    const handleQualityGrade = async () => {
        setQualityError("");
        setQualityResult("");

        const temperatureValue = parseNumber(temperature);
        const humidityValue = parseNumber(humidity);

        if (temperatureValue === null) {
            setQualityError("温度必须是数字。示例：5 或 5.5");
            return;
        }

        if (humidityValue === null) {
            setQualityError("湿度必须是数字。示例：72 或 72.5");
            return;
        }

        if (temperatureValue < -50 || temperatureValue > 120) {
            setQualityError("温度超出范围，应在 -50 到 120 之间。");
            return;
        }

        if (humidityValue < 0 || humidityValue > 100) {
            setQualityError("湿度超出范围，应在 0 到 100 之间。");
            return;
        }

        setLoading((prev) => ({ ...prev, quality: true }));
        try {
            const data = await Services.gradeQuality({
                temperature_c: temperatureValue,
                humidity_pct: humidityValue,
            });
            setQualityResult(toPrettyJson(data));
        } catch (error) {
            setQualityError(formatError(error));
        } finally {
            setLoading((prev) => ({ ...prev, quality: false }));
        }
    };

    const handleActivatePolicy = async () => {
        setActivateError("");
        setActivateResult("");

        if (!policyId.trim()) {
            setActivateError("请输入策略 ID。");
            return;
        }

        setLoading((prev) => ({ ...prev, activate: true }));
        try {
            const data = await Services.activatePolicy(policyId.trim());
            setActivateResult(toPrettyJson(data));
        } catch (error) {
            setActivateError(formatError(error));
        } finally {
            setLoading((prev) => ({ ...prev, activate: false }));
        }
    };

    return (
        <div className="space-y-7">
            <section className="panel-shell edge-highlight p-5 md:p-6">
                <div className="flex items-center gap-3">
                    <span className="edge-highlight inline-flex h-10 w-10 items-center justify-center rounded-xl border border-primary-400/30 bg-primary-500/15 text-primary-300">
                        <Wrench className="h-5 w-5" />
                    </span>
                    <div>
                        <h1 className="display-heading text-2xl font-semibold tracking-tight text-white md:text-3xl">接口工具台</h1>
                        <p className="mt-1 text-sm text-slate-300">
                            演示后端接口联调：健康检查、合同校验、事件写入、质量评分、策略激活。
                        </p>
                    </div>
                </div>
            </section>

            <Card className="panel-shell edge-highlight">
                <CardHeader>
                    <CardTitle className="display-heading">公共参数</CardTitle>
                    <CardDescription>
                        以下 TraceEvent JSON 同时用于“合同校验”和“事件写入”。
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                        <div className="space-y-2">
                            <label className="text-sm text-slate-300" htmlFor="signing-secret">
                                签名密钥（演示用）
                            </label>
                            <Input
                                id="signing-secret"
                                type="password"
                                value={signingSecret}
                                onChange={(event) => setSigningSecret(event.target.value)}
                                placeholder="例如 super-secret"
                            />
                        </div>
                        <Button type="button" variant="secondary" onClick={handleSignPayload}>
                            自动签名 payload
                        </Button>
                    </div>
                    <label className="text-sm text-slate-300" htmlFor="trace-event-json">
                        TraceEvent JSON
                    </label>
                    <textarea
                        id="trace-event-json"
                        className="edge-highlight min-h-[280px] w-full rounded-lg border border-slate-600/80 bg-slate-900/65 p-3 font-mono text-xs text-slate-100 outline-none transition-[border-color,box-shadow] focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/35"
                        value={traceEventJson}
                        onChange={(event) => setTraceEventJson(event.target.value)}
                    />
                    {!parsedTraceEvent.ok && (
                        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
                            {parsedTraceEvent.message}
                        </div>
                    )}
                </CardContent>
            </Card>

            <div className="grid gap-4 xl:grid-cols-2">
                <Card className="panel-shell edge-highlight border-slate-700/75">
                    <CardHeader>
                        <CardTitle>GET /health</CardTitle>
                        <CardDescription>公开接口，无需鉴权。</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <Button onClick={handleHealth} loading={loading.health}>发送请求</Button>
                        {healthError && <p className="text-sm text-red-300">{healthError}</p>}
                        {healthResult && <pre className="edge-highlight overflow-x-auto rounded-lg border border-slate-700/75 bg-slate-950/70 p-3 text-xs text-slate-200">{healthResult}</pre>}
                    </CardContent>
                </Card>

                <Card className="panel-shell edge-highlight border-slate-700/75">
                    <CardHeader>
                        <CardTitle>POST /contracts/trace-events/validate</CardTitle>
                        <CardDescription>公开接口，校验 TraceEvent 合同并返回 canonical_hash。</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <Button onClick={handleContractValidate} loading={loading.contract}>发送请求</Button>
                        {contractError && <p className="text-sm text-red-300">{contractError}</p>}
                        {contractResult && <pre className="edge-highlight overflow-x-auto rounded-lg border border-slate-700/75 bg-slate-950/70 p-3 text-xs text-slate-200">{contractResult}</pre>}
                    </CardContent>
                </Card>

                <Card className="panel-shell edge-highlight border-slate-700/75">
                    <CardHeader>
                        <CardTitle>POST /v1/events（ingest）</CardTitle>
                        <CardDescription>公开接口，要求 Idempotency-Key。</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="space-y-2">
                            <label className="text-sm text-slate-300" htmlFor="idempotency-key">Idempotency-Key</label>
                            <Input
                                id="idempotency-key"
                                value={idempotencyKey}
                                onChange={(event) => setIdempotencyKey(event.target.value)}
                                placeholder="例如 idem-001"
                            />
                        </div>
                        <Button onClick={handleIngest} loading={loading.ingest}>发送请求</Button>
                        {ingestError && <p className="text-sm text-red-300">{ingestError}</p>}
                        {ingestResult && <pre className="edge-highlight overflow-x-auto rounded-lg border border-slate-700/75 bg-slate-950/70 p-3 text-xs text-slate-200">{ingestResult}</pre>}
                    </CardContent>
                </Card>

                <Card className="panel-shell edge-highlight border-slate-700/75">
                    <CardHeader>
                        <CardTitle>POST /v1/quality/grade</CardTitle>
                        <CardDescription>公开接口，根据温湿度给出质量等级。</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                            <div className="space-y-2">
                                <label className="text-sm text-slate-300" htmlFor="temperature">温度（℃）</label>
                                <Input
                                    id="temperature"
                                    type="number"
                                    value={temperature}
                                    onChange={(event) => setTemperature(event.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm text-slate-300" htmlFor="humidity">湿度（%）</label>
                                <Input
                                    id="humidity"
                                    type="number"
                                    value={humidity}
                                    onChange={(event) => setHumidity(event.target.value)}
                                />
                            </div>
                        </div>
                        <Button onClick={handleQualityGrade} loading={loading.quality}>发送请求</Button>
                        {qualityError && <p className="text-sm text-red-300">{qualityError}</p>}
                        {qualityResult && <pre className="edge-highlight overflow-x-auto rounded-lg border border-slate-700/75 bg-slate-950/70 p-3 text-xs text-slate-200">{qualityResult}</pre>}
                    </CardContent>
                </Card>

                <Card className="panel-shell edge-highlight border-slate-700/75 xl:col-span-2">
                    <CardHeader>
                        <CardTitle>{"POST /admin/policies/{policy_id}/activate"}</CardTitle>
                        <CardDescription>
                            管理接口，需要 Bearer Token（会自动从登录态附带）。
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
                            <div className="space-y-2">
                                <label className="text-sm text-slate-300" htmlFor="policy-id">策略 ID</label>
                                <Input
                                    id="policy-id"
                                    value={policyId}
                                    onChange={(event) => setPolicyId(event.target.value)}
                                    placeholder="例如 policy-123"
                                />
                            </div>
                            <Button onClick={handleActivatePolicy} loading={loading.activate}>激活策略</Button>
                        </div>
                        {activateError && <p className="text-sm text-red-300">{activateError}</p>}
                        {activateResult && <pre className="edge-highlight overflow-x-auto rounded-lg border border-slate-700/75 bg-slate-950/70 p-3 text-xs text-slate-200">{activateResult}</pre>}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
