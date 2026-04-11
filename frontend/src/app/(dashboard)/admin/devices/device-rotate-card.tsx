"use client";

import { useMemo, useState } from "react";
import { Check, Copy, Key, Loader2 } from "lucide-react";
import { ManagedDeviceKey, RotateDeviceKeyResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { KeyQueryState } from "./device-admin.types";
import { formatDateTime, toCnKeyStatus } from "./device-admin.utils";

type DeviceRotateCardProps = {
    highlightSectionId: string | null;
    rotateDeviceId: string;
    rotateKeyId: string;
    rotateAlgorithm: string;
    rotateSecret: string;
    isPending: boolean;
    keyQueryState: KeyQueryState;
    keyQueryMessage: string;
    keyList: ManagedDeviceKey[];
    keyListDeviceId: string;
    lastRotateResult: RotateDeviceKeyResponse | null;
    onRotateDeviceIdChange: (value: string) => void;
    onRotateKeyIdChange: (value: string) => void;
    onRotateAlgorithmChange: (value: string) => void;
    onRotateSecretChange: (value: string) => void;
    onSubmit: () => void;
    onQueryManagedDeviceKeys: (deviceId: string) => void;
    onCopyRetiredKeyIds: (deviceId: string, keyIds: string[], context: "轮换" | "停用") => void;
};

export function DeviceRotateCard({
    highlightSectionId,
    rotateDeviceId,
    rotateKeyId,
    rotateAlgorithm,
    rotateSecret,
    isPending,
    keyQueryState,
    keyQueryMessage,
    keyList,
    keyListDeviceId,
    lastRotateResult,
    onRotateDeviceIdChange,
    onRotateKeyIdChange,
    onRotateAlgorithmChange,
    onRotateSecretChange,
    onSubmit,
    onQueryManagedDeviceKeys,
    onCopyRetiredKeyIds,
}: DeviceRotateCardProps) {
    const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
    const retiredKeyIdsFromList = useMemo(
        () => keyList
            .filter((item) => item.status === "retired")
            .map((item) => item.key_id),
        [keyList]
    );

    const copyKeyId = async (keyId: string) => {
        try {
            await navigator.clipboard.writeText(keyId);
            setCopiedKeyId(keyId);
            window.setTimeout(() => setCopiedKeyId((current) => current === keyId ? null : current), 1600);
        } catch {
            setCopiedKeyId(null);
        }
    };

    return (
        <Card
            id="section-device-rotate"
            className={cn(
                "panel-shell edge-highlight border-slate-700/75 order-2 transition-[border-color,box-shadow] duration-300",
                highlightSectionId === "section-device-rotate" && "border-primary-400/60 shadow-[0_0_0_1px_rgba(74,222,128,0.4),0_0_34px_-12px_rgba(34,197,94,0.85)]"
            )}
        >
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Key className="h-5 w-5 text-yellow-400" />
                    密钥轮换
                </CardTitle>
                <CardDescription>调用 /admin/devices/&lt;device_id&gt;/keys 完成密钥轮换。</CardDescription>
            </CardHeader>
            <CardContent>
                <form
                    className="space-y-4"
                    onSubmit={(event) => {
                        event.preventDefault();
                        onSubmit();
                    }}
                >
                    <div className="space-y-2">
                        <label htmlFor="rotate-device-id" className="text-sm font-medium text-slate-300">
                            目标设备 ID
                        </label>
                        <Input
                            id="rotate-device-id"
                            placeholder="目标设备 ID"
                            value={rotateDeviceId}
                            onChange={(event) => onRotateDeviceIdChange(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label htmlFor="rotate-key-id" className="text-sm font-medium text-slate-300">
                            新 Key ID
                        </label>
                        <Input
                            id="rotate-key-id"
                            placeholder="新 Key ID"
                            value={rotateKeyId}
                            onChange={(event) => onRotateKeyIdChange(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label htmlFor="rotate-algorithm" className="text-sm font-medium text-slate-300">
                            算法
                        </label>
                        <Input
                            id="rotate-algorithm"
                            placeholder="算法（默认：HMAC_SHA256）"
                            value={rotateAlgorithm}
                            onChange={(event) => onRotateAlgorithmChange(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label htmlFor="rotate-secret" className="text-sm font-medium text-slate-300">
                            新共享密钥
                        </label>
                        <Input
                            id="rotate-secret"
                            placeholder="新共享密钥（用于签名）"
                            value={rotateSecret}
                            onChange={(event) => onRotateSecretChange(event.target.value)}
                        />
                    </div>
                    <Button type="submit" variant="secondary" className="w-full" disabled={isPending}>
                        {isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "执行密钥轮换"}
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        className="w-full"
                        disabled={!rotateDeviceId.trim() || keyQueryState === "loading"}
                        onClick={() => onQueryManagedDeviceKeys(rotateDeviceId)}
                    >
                        {keyQueryState === "loading" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        查询密钥列表
                    </Button>
                </form>

                {(keyQueryState !== "idle" || lastRotateResult) && (
                    <div className="mt-4 space-y-3 rounded-md border border-slate-700/75 bg-slate-900/45 p-3 text-sm">
                        {keyQueryMessage ? <p className="text-slate-300">{keyQueryMessage}</p> : null}

                        {lastRotateResult && (
                            <div className="space-y-2 rounded border border-primary-400/30 bg-primary-500/10 p-3 text-slate-300">
                                <p className="font-medium text-slate-100">最近一次轮换结果</p>
                                <div className="grid gap-2 sm:grid-cols-2">
                                    <p>设备：{lastRotateResult.device_id}</p>
                                    <p>状态：{toCnKeyStatus(lastRotateResult.status)}</p>
                                    <p className="break-all">当前 Key：{lastRotateResult.key_id}</p>
                                    <p>算法：{lastRotateResult.algorithm}</p>
                                </div>

                                <div className="flex flex-wrap gap-2">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => void copyKeyId(lastRotateResult.key_id)}
                                    >
                                        {copiedKeyId === lastRotateResult.key_id ? (
                                            <Check className="mr-2 h-3.5 w-3.5 text-emerald-300" />
                                        ) : (
                                            <Copy className="mr-2 h-3.5 w-3.5" />
                                        )}
                                        复制当前 Key ID
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        disabled={lastRotateResult.retired_key_ids.length === 0}
                                        onClick={() => onCopyRetiredKeyIds(lastRotateResult.device_id, lastRotateResult.retired_key_ids, "轮换")}
                                    >
                                        <Copy className="mr-2 h-3.5 w-3.5" />
                                        复制本次退役 Key ID
                                    </Button>
                                </div>

                                {lastRotateResult.retired_key_ids.length > 0 ? (
                                    <div className="space-y-1 rounded border border-slate-700/75 bg-slate-950/45 p-2">
                                        <p className="text-slate-200">本次退役 Key ID：</p>
                                        {lastRotateResult.retired_key_ids.map((keyId) => (
                                            <code key={keyId} className="block break-all rounded bg-slate-900/60 px-2 py-1 text-xs text-slate-200">
                                                {keyId}
                                            </code>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-slate-300">本次轮换没有退役旧 Key。</p>
                                )}
                            </div>
                        )}

                        {keyQueryState === "loaded" && (
                            <div className="space-y-2">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="text-slate-200">设备 {keyListDeviceId} 密钥列表：</p>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        disabled={retiredKeyIdsFromList.length === 0}
                                        onClick={() => onCopyRetiredKeyIds(keyListDeviceId, retiredKeyIdsFromList, "轮换")}
                                    >
                                        <Copy className="mr-2 h-3.5 w-3.5" />
                                        复制列表退役 Key
                                    </Button>
                                </div>
                                {keyList.length === 0 ? (
                                    <p className="text-slate-300">暂无密钥数据。</p>
                                ) : (
                                    <div className="space-y-2">
                                        {keyList.map((item) => {
                                            const isActive = item.status === "active";
                                            return (
                                                <div
                                                    key={String(item.key_id)}
                                                    className={cn(
                                                        "rounded border px-3 py-2 text-slate-300",
                                                        isActive
                                                            ? "border-emerald-400/35 bg-emerald-500/10"
                                                            : "border-slate-700/75 bg-slate-950/35"
                                                    )}
                                                >
                                                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                                        <div className="min-w-0 space-y-1">
                                                            <p className="break-all font-mono text-slate-100">
                                                                {isActive ? "当前 Key: " : "Key ID: "}{item.key_id}
                                                            </p>
                                                            <p>
                                                                算法: {item.algorithm} ｜ 状态: {toCnKeyStatus(item.status)}
                                                            </p>
                                                            <p>
                                                                生效: {formatDateTime(item.activated_at)} ｜ 退役: {formatDateTime(item.retired_at)}
                                                            </p>
                                                        </div>
                                                        <Button
                                                            type="button"
                                                            variant="outline"
                                                            size="sm"
                                                            className="shrink-0"
                                                            onClick={() => void copyKeyId(item.key_id)}
                                                        >
                                                            {copiedKeyId === item.key_id ? (
                                                                <Check className="mr-2 h-3.5 w-3.5 text-emerald-300" />
                                                            ) : (
                                                                <Copy className="mr-2 h-3.5 w-3.5" />
                                                            )}
                                                            复制 Key ID
                                                        </Button>
                                                    </div>
                                            </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
