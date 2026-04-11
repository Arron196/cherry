"use client";

import { Loader2, Power } from "lucide-react";
import { DisableDeviceResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getDeviceStatusMeta } from "./device-admin.utils";

type DeviceDisableCardProps = {
    highlightSectionId: string | null;
    disableDeviceId: string;
    disableReason: string;
    isPending: boolean;
    lastDisableResult: DisableDeviceResponse | null;
    onDisableDeviceIdChange: (value: string) => void;
    onDisableReasonChange: (value: string) => void;
    onSubmit: () => void;
    onCopyRetiredKeyIds: (deviceId: string, keyIds: string[], context: "轮换" | "停用") => void;
};

export function DeviceDisableCard({
    highlightSectionId,
    disableDeviceId,
    disableReason,
    isPending,
    lastDisableResult,
    onDisableDeviceIdChange,
    onDisableReasonChange,
    onSubmit,
    onCopyRetiredKeyIds,
}: DeviceDisableCardProps) {
    return (
        <Card
            id="section-device-disable"
            className={cn(
                "panel-shell edge-highlight border-slate-700/75 md:col-span-2 order-3 transition-[border-color,box-shadow] duration-300",
                highlightSectionId === "section-device-disable" && "border-primary-400/60 shadow-[0_0_0_1px_rgba(74,222,128,0.4),0_0_34px_-12px_rgba(34,197,94,0.85)]"
            )}
        >
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Power className="h-5 w-5 text-red-400" />
                    停用设备
                </CardTitle>
                <CardDescription>调用 /admin/devices/&lt;device_id&gt;/disable 将设备停用。</CardDescription>
            </CardHeader>
            <CardContent>
                <form
                    className="grid gap-4 md:grid-cols-3"
                    onSubmit={(event) => {
                        event.preventDefault();
                        onSubmit();
                    }}
                >
                    <div className="space-y-2">
                        <label htmlFor="disable-device-id" className="text-sm font-medium text-slate-300">
                            目标设备 ID
                        </label>
                        <Input
                            id="disable-device-id"
                            placeholder="目标设备 ID"
                            value={disableDeviceId}
                            onChange={(event) => onDisableDeviceIdChange(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label htmlFor="disable-reason" className="text-sm font-medium text-slate-300">
                            停用原因（可选）
                        </label>
                        <Input
                            id="disable-reason"
                            placeholder="停用原因（可选）"
                            value={disableReason}
                            onChange={(event) => onDisableReasonChange(event.target.value)}
                        />
                    </div>
                    <Button variant="destructive" className="w-full" type="submit" disabled={isPending}>
                        {isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "确认停用"}
                    </Button>
                </form>

                {lastDisableResult && (
                    <div className="mt-4 space-y-2 rounded-md border border-slate-700/75 bg-slate-900/45 p-3 text-sm text-slate-300">
                        <p>最近一次停用结果：</p>
                        <p>设备：{lastDisableResult.device_id}</p>
                        <p>状态：{getDeviceStatusMeta(lastDisableResult.status).label}</p>
                        <p>退役旧 Key：{lastDisableResult.retired_key_ids.length} 个</p>

                        {lastDisableResult.retired_key_ids.length > 0 ? (
                            <div className="space-y-2 rounded border border-slate-700/75 bg-slate-950/45 p-2">
                                <p className="text-slate-200">退役 Key ID 明细：</p>
                                <div className="space-y-1">
                                    {lastDisableResult.retired_key_ids.map((keyId) => (
                                        <code key={keyId} className="block break-all rounded bg-slate-900/60 px-2 py-1 text-xs text-slate-200">
                                            {keyId}
                                        </code>
                                    ))}
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => onCopyRetiredKeyIds(lastDisableResult.device_id, lastDisableResult.retired_key_ids, "停用")}
                                >
                                    复制退役 Key ID
                                </Button>
                            </div>
                        ) : (
                            <p className="text-slate-300">本次停用没有退役旧 Key。</p>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
