"use client";

import { Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { InitialKeyDraft } from "./device-admin.types";

type DeviceRegisterCardProps = {
    highlightSectionId: string | null;
    newDeviceId: string;
    displayName: string;
    enableInitialKey: boolean;
    initialKeyDraft: InitialKeyDraft;
    latestInitialKeySecret: string | null;
    isPending: boolean;
    onNewDeviceIdChange: (value: string) => void;
    onDisplayNameChange: (value: string) => void;
    onEnableInitialKeyChange: (value: boolean) => void;
    onInitialKeyDraftChange: (value: InitialKeyDraft) => void;
    onSubmit: () => void;
    onCopyInitialSecret: () => void;
};

export function DeviceRegisterCard({
    highlightSectionId,
    newDeviceId,
    displayName,
    enableInitialKey,
    initialKeyDraft,
    latestInitialKeySecret,
    isPending,
    onNewDeviceIdChange,
    onDisplayNameChange,
    onEnableInitialKeyChange,
    onInitialKeyDraftChange,
    onSubmit,
    onCopyInitialSecret,
}: DeviceRegisterCardProps) {
    return (
        <Card
            id="section-device-register"
            className={cn(
                "panel-shell edge-highlight order-1 transition-[border-color,box-shadow] duration-300",
                highlightSectionId === "section-device-register" && "border-primary-400/60 shadow-[0_0_0_1px_rgba(74,222,128,0.4),0_0_34px_-12px_rgba(34,197,94,0.85)]"
            )}
        >
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Plus className="h-5 w-5 text-primary-500" />
                    注册新设备
                </CardTitle>
                <CardDescription>创建设备身份，并可选“一步创建首个签名密钥”。</CardDescription>
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
                        <label htmlFor="new-device-id" className="text-sm font-medium text-slate-300">
                            设备 ID *
                        </label>
                        <Input
                            id="new-device-id"
                            placeholder="例如：factory-sensor-01"
                            value={newDeviceId}
                            onChange={(event) => onNewDeviceIdChange(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label htmlFor="display-name" className="text-sm font-medium text-slate-300">
                            显示名称
                        </label>
                        <Input
                            id="display-name"
                            placeholder="例如：1 号产线温度传感器"
                            value={displayName}
                            onChange={(event) => onDisplayNameChange(event.target.value)}
                        />
                    </div>

                    <label className="edge-highlight flex items-center gap-2 rounded-md border border-slate-700/75 bg-slate-900/55 px-3 py-2 text-sm text-slate-200">
                        <input
                            type="checkbox"
                            checked={enableInitialKey}
                            onChange={(event) => onEnableInitialKeyChange(event.target.checked)}
                            className="h-4 w-4"
                        />
                        注册时同步创建首个签名密钥（推荐）
                    </label>

                    {enableInitialKey && (
                        <div className="edge-highlight space-y-2 rounded-md border border-slate-700/75 bg-slate-900/55 p-3">
                            <div className="space-y-2">
                                <label htmlFor="initial-key-id" className="text-xs text-slate-300">
                                    首钥 Key ID
                                </label>
                                <Input
                                    id="initial-key-id"
                                    placeholder="首钥 Key ID（例如：factory-sensor-01-v1）"
                                    value={initialKeyDraft.key_id}
                                    onChange={(event) => onInitialKeyDraftChange({ ...initialKeyDraft, key_id: event.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <label htmlFor="initial-key-algorithm" className="text-xs text-slate-300">
                                    首钥算法
                                </label>
                                <Input
                                    id="initial-key-algorithm"
                                    placeholder="首钥算法（默认：HMAC_SHA256）"
                                    value={initialKeyDraft.algorithm}
                                    onChange={(event) => onInitialKeyDraftChange({ ...initialKeyDraft, algorithm: event.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <label htmlFor="initial-key-secret" className="text-xs text-slate-300">
                                    首钥密钥
                                </label>
                                <Input
                                    id="initial-key-secret"
                                    type="password"
                                    placeholder="首钥密钥（仅返回一次，请保存）"
                                    value={initialKeyDraft.secret}
                                    onChange={(event) => onInitialKeyDraftChange({ ...initialKeyDraft, secret: event.target.value })}
                                />
                            </div>
                        </div>
                    )}

                    <Button className="w-full" type="submit" disabled={!newDeviceId.trim() || isPending}>
                        {isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "立即注册"}
                    </Button>

                    {latestInitialKeySecret && (
                        <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                            <p>首钥密钥仅在创建时可见，请立即复制保存：</p>
                            <code className="block break-all rounded bg-slate-950/60 px-2 py-1">{latestInitialKeySecret}</code>
                            <Button type="button" variant="outline" size="sm" onClick={onCopyInitialSecret}>
                                复制首钥密钥
                            </Button>
                        </div>
                    )}
                </form>
            </CardContent>
        </Card>
    );
}
